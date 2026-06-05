"""
findings_db.py — the canonical findings registry library.

One JSON file (`findings/findings_db.json`, gitignored) holds the array of
finding records. All tools load/mutate/save through here so the file stays
deterministically sorted and de-duplicated by root cause.

Override the DB path with $SECHOUND_DB.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.RLock()


def _db_path() -> Path:
    env = os.environ.get("SECHOUND_DB")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "findings" / "findings_db.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_db() -> list[dict]:
    path = _db_path()
    with _LOCK:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []


def sorted_findings(db: list[dict]) -> list[dict]:
    """Deterministic order so the file is byte-stable across writers."""
    return sorted(db, key=lambda f: str(f.get("id") or f.get("title") or ""))


def save_db(db: list[dict]) -> None:
    path = _db_path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted_findings(db), indent=2), encoding="utf-8")


def _norm(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def component_of(f: dict) -> str:
    """The logical grouping — 'component' (new) or 'service' (legacy alias)."""
    return (f.get("component") or f.get("service") or "").lower()


def location_of(f: dict) -> str:
    """The locator — 'location' (new), else 'endpoint', else first file cite."""
    return (f.get("location") or f.get("endpoint")
            or (f.get("files") or [""])[0] or "").lower()


def check_duplicate(db: list[dict], finding: dict) -> str | None:
    """Return the id of an existing finding with the same root cause, else None.

    Root cause ≈ same component+location (covers cross-scanner hits on the same
    file:line/route/resource), or a high title-word overlap within a component.
    Symptom-level (exact title) matching is intentionally NOT used.
    """
    comp = component_of(finding)
    loc = location_of(finding)
    title_words = _norm(finding.get("title", ""))
    fid = finding.get("id")
    for existing in db:
        if fid and existing.get("id") == fid:
            continue  # a finding never de-duplicates against its own record
        ecomp = component_of(existing)
        # Same location + same (or both-empty) component → same root cause.
        # Empty-component match lets two scanners on the same file:line collapse.
        if loc and location_of(existing) == loc and ecomp == comp:
            return existing.get("id")
        ew = _norm(existing.get("title", ""))
        if title_words and ew:
            overlap = len(title_words & ew) / len(title_words)
            if overlap >= 0.75 and ecomp == comp:
                return existing.get("id")
    return None


def _next_id(db: list[dict], finding: dict) -> str:
    # Prefix from component, else domain, else GEN (so imported web findings get SH-WEB-*).
    raw = finding.get("component") or finding.get("service") or finding.get("domain") or "GEN"
    svc = re.sub(r"[^A-Z0-9]", "", raw.upper()) or "GEN"
    prefix = f"SH-{svc}-"
    nums = [
        int(m.group(1))
        for f in db
        if (m := re.match(rf"^{re.escape(prefix)}(\d+)$", str(f.get("id") or "")))
    ]
    return f"{prefix}{(max(nums) + 1 if nums else 1):04d}"


def upsert(finding: dict) -> tuple[str, str]:
    """Insert or update a finding. Returns (id, action) where action is
    'inserted' | 'updated' | 'duplicate'."""
    with _LOCK:
        db = load_db()

        # Update in place if the id already exists.
        fid = finding.get("id")
        if fid:
            for existing in db:
                if existing.get("id") == fid:
                    existing.update(finding)
                    existing["last_updated"] = utcnow()
                    save_db(db)
                    return fid, "updated"

        # Root-cause dedup before assigning a new id.
        dup = check_duplicate(db, finding)
        if dup:
            return dup, "duplicate"

        if not fid:
            fid = _next_id(db, finding)
            finding["id"] = fid
        finding.setdefault("status", "candidate")
        finding.setdefault("found_at", utcnow()[:10])
        finding["last_updated"] = utcnow()
        db.append(finding)
        save_db(db)
        return fid, "inserted"
