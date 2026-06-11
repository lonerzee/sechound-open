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


import re as _re

_FRONTMATTER = _re.compile(r"^---\s*\n(.*?)\n---\s*\n", _re.DOTALL)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Frontmatter parsed shallowly (no yaml dep
    needed for the simple key: value / list lines our skills use)."""
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("-"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, text[m.end():]


def skill_index() -> list[dict]:
    """Catalog of available hunt skills: [{name, description, domain}]."""
    sdir = repo_root() / "skills"
    out = []
    if not sdir.is_dir():
        return out
    for p in sorted(sdir.glob("*/SKILL.md")):
        fm, _ = _split_frontmatter(p.read_text(encoding="utf-8"))
        out.append({"name": fm.get("name", p.parent.name),
                    "description": fm.get("description", ""),
                    "domain": fm.get("domain", "")})
    return out


def skill_index_text() -> str:
    """Compact, prompt-injectable catalog so the model knows what's available."""
    rows = [f"- {s['name']} [{s['domain']}]: {s['description']}" for s in skill_index()]
    return "## Available hunt skills (load by name)\n" + "\n".join(rows) if rows else ""


def load_skill(name: str) -> str:
    """Full body of one skill (frontmatter stripped), or '' if not found."""
    p = repo_root() / "skills" / name / "SKILL.md"
    if not p.exists():
        return ""
    _, body = _split_frontmatter(p.read_text(encoding="utf-8"))
    return body.strip()


def skill_context(names: list[str], cap: int = 6) -> str:
    """Concatenate the bodies of the named skills for injection (deduped, capped)."""
    seen, blocks = set(), []
    for n in names:
        n = (n or "").strip()
        if not n or n in seen:
            continue
        seen.add(n)
        body = load_skill(n)
        if body:
            blocks.append(f"### Skill: {n}\n{body}")
        if len(blocks) >= cap:
            break
    return ("\n\n## Loaded hunt skills\n\n" + "\n\n".join(blocks)) if blocks else ""


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
    manifest = pdir / "profile.yaml"
    skills: list[str] = []
    if manifest.exists():
        try:
            import yaml
            skills = (yaml.safe_load(manifest.read_text()) or {}).get("skills") or []
        except Exception:
            # yaml-less fallback: scrape "  - skill-name" lines under a skills: key
            in_skills = False
            for ln in manifest.read_text().splitlines():
                if ln.startswith("skills:"):
                    in_skills = True
                    continue
                if in_skills:
                    m = _re.match(r"\s*-\s*(\S+)", ln)
                    if m:
                        skills.append(m.group(1))
                    elif ln and not ln[0].isspace():
                        break
    return {
        "name": name,
        "fp": fp.read_text(encoding="utf-8") if fp.exists() else "",
        "invariants": inv.read_text(encoding="utf-8") if inv.exists() else "",
        "skills": skills,
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

    The marker walk is bounded to this checkout: it never climbs above
    repo_root(). A `.sechound/` directory outside the clone (e.g. the
    `~/.sechound/` owned by a separate SecHound install) is deliberately
    ignored, so two installs on one machine can't resolve each other's
    engagements.
    """
    if arg:
        return Path(arg).resolve()

    env = os.environ.get("SECHOUND_ENGAGEMENT")
    if env:
        return Path(env).resolve()

    root = repo_root()
    cur = Path.cwd()
    for parent in [cur, *cur.parents]:
        if parent == root or root in parent.parents:  # only within this checkout
            marker = parent / ".sechound"
            if marker.is_dir():
                subs = [p for p in marker.iterdir() if p.is_dir()]
                if subs:
                    return sorted(subs, key=lambda p: p.stat().st_mtime)[-1]
        if parent == root:
            break  # never climb above the checkout (avoids ~/.sechound collision)

    eng_root = repo_root() / "engagements"
    if eng_root.is_dir():
        subs = [p for p in eng_root.iterdir() if p.is_dir() and p.name != ".gitkeep"]
        if subs:
            return sorted(subs, key=lambda p: p.stat().st_mtime)[-1]

    raise SystemExit(
        "Could not resolve an engagement. Pass one as an argument, set "
        "$SECHOUND_ENGAGEMENT, or create engagements/<id>/."
    )
