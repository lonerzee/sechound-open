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
