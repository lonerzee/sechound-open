"""
sechound_lib.py — shared helpers: engagement resolution + model selection.

Kept dependency-free so every tool can import it without a package install.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sechound_model(tier: str = "default") -> str:
    """Resolve the model id for a workload tier (delegates to the provider layer
    so model defaults track whichever backend $SECHOUND_LLM selects).

    Override per-tier with $SECHOUND_MODEL_<TIER> or globally with $SECHOUND_MODEL.
    """
    try:
        from llm import default_model
        return default_model(tier)
    except Exception:
        env = os.environ.get(f"SECHOUND_MODEL_{tier.upper()}") or os.environ.get("SECHOUND_MODEL")
        return env or "claude-sonnet-4-6"


def repo_root() -> Path:
    """The sechound-open checkout root (parent of tools/)."""
    return Path(__file__).resolve().parent.parent


def load_profile(name: str | None = None) -> dict | None:
    """Load a domain profile's FP addendum + invariants for prompt injection.

    `name` explicit wins; else read `profile:` from config/targets.yaml. Returns
    {name, fp, invariants} or None. Works without PyYAML (reads the markdown/yaml
    files as raw text; only the config lookup needs yaml).
    """
    if name is None:
        cfg = repo_root() / "config" / "targets.yaml"
        if cfg.exists():
            try:
                import yaml
                name = (yaml.safe_load(cfg.read_text()) or {}).get("profile")
            except Exception:
                name = None
    if not name:
        return None
    pdir = repo_root() / "profiles" / name
    if not pdir.is_dir():
        return None
    fp = pdir / "FP_CHECKLIST.md"
    inv = pdir / "invariants.yaml"
    return {
        "name": name,
        "fp": fp.read_text(encoding="utf-8") if fp.exists() else "",
        "invariants": inv.read_text(encoding="utf-8") if inv.exists() else "",
    }


def profile_context(name: str | None = None) -> str:
    """A prompt-injectable block for the active profile (empty string if none)."""
    p = load_profile(name)
    if not p:
        return ""
    out = [f"\n## Active profile: {p['name']} (domain-specific controls — apply on top of the core)"]
    if p["fp"]:
        out.append(f"### Profile FP patterns\n{p['fp']}")
    if p["invariants"]:
        out.append(f"### Profile invariants to falsify\n```yaml\n{p['invariants']}\n```")
    return "\n\n".join(out)


def resolve_engagement_arg(arg: str | None) -> Path:
    """Resolve an engagement directory.

    Order: explicit arg → $SECHOUND_ENGAGEMENT → walk up from cwd looking for a
    `.sechound/<id>/` marker → the most recent dir under engagements/.
    """
    if arg:
        return Path(arg).resolve()

    env = os.environ.get("SECHOUND_ENGAGEMENT")
    if env:
        return Path(env).resolve()

    cur = Path.cwd()
    for parent in [cur, *cur.parents]:
        marker = parent / ".sechound"
        if marker.is_dir():
            subs = [p for p in marker.iterdir() if p.is_dir()]
            if subs:
                return sorted(subs, key=lambda p: p.stat().st_mtime)[-1]

    eng_root = repo_root() / "engagements"
    if eng_root.is_dir():
        subs = [p for p in eng_root.iterdir() if p.is_dir() and p.name != ".gitkeep"]
        if subs:
            return sorted(subs, key=lambda p: p.stat().st_mtime)[-1]

    raise SystemExit(
        "Could not resolve an engagement. Pass one as an argument, set "
        "$SECHOUND_ENGAGEMENT, or create engagements/<id>/."
    )
