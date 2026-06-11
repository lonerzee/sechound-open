import sechound_lib as sl


def test_resolver_ignores_sechound_marker_above_checkout(tmp_path, monkeypatch):
    """A `.sechound/` belonging to a *separate* install (e.g. ~/.sechound) sits
    above our checkout. The resolver must never climb into it."""
    outside = tmp_path / ".sechound" / "other-install-eng"
    outside.mkdir(parents=True)

    clone = tmp_path / "sechound-open"
    mine = clone / "engagements" / "mine"
    mine.mkdir(parents=True)

    monkeypatch.setattr(sl, "repo_root", lambda: clone)
    monkeypatch.chdir(clone)
    monkeypatch.delenv("SECHOUND_ENGAGEMENT", raising=False)

    resolved = sl.resolve_engagement_arg(None)
    assert resolved == mine
    assert ".sechound" not in str(resolved)  # never resolved the other install


def test_resolver_uses_marker_within_checkout(tmp_path, monkeypatch):
    """A `.sechound/<id>/` marker inside the checkout is still honored."""
    clone = tmp_path / "sechound-open"
    active = clone / ".sechound" / "active"
    active.mkdir(parents=True)

    monkeypatch.setattr(sl, "repo_root", lambda: clone)
    monkeypatch.chdir(clone)
    monkeypatch.delenv("SECHOUND_ENGAGEMENT", raising=False)

    assert sl.resolve_engagement_arg(None) == active
