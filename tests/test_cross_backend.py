"""End-to-end proof that a real pipeline stage runs on a non-Claude backend.

The README claims SecHound is model-agnostic. `test_llm.py` proves the seam and
each backend's call shape; this proves an actual *stage* (triage) produces
correct output when driven by a backend that is not the Claude CLI — using the
`command` backend pointed at a tiny fake "model" script. No network, no SDK,
no Claude CLI.
"""
import importlib
import os
import stat
import sys
from pathlib import Path

import pytest


@pytest.fixture
def fake_model(tmp_path):
    """A stand-in 'model': ignores the prompt on stdin, emits a fixed triage
    verdict array for the two ids the test feeds in. Stands for any local model
    (Ollama, llm, a server wrapper) wired via $SECHOUND_LLM_CMD."""
    script = tmp_path / "fake_model.py"
    script.write_text(
        "import sys\n"
        "sys.stdin.read()\n"  # consume the prompt like a real model would
        "print('''[\n"
        '  {"id": "F1", "verdict": "likely_true_positive",  "reason": "reachable sink", "severity": "HIGH"},\n'
        '  {"id": "F2", "verdict": "likely_false_positive", "reason": "test fixture",   "severity": "LOW"}\n'
        "]''')\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_triage_stage_runs_on_command_backend(monkeypatch, fake_model):
    monkeypatch.setenv("SECHOUND_LLM", "command")
    monkeypatch.setenv("SECHOUND_LLM_CMD", f"{sys.executable} {fake_model}")

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import llm
    importlib.reload(llm)
    import triage
    importlib.reload(triage)

    # The backend is genuinely usable without Claude on PATH.
    ok, reason = llm.available()
    assert ok, reason

    findings = [
        {"id": "F1", "title": "IDOR on /api/objects/{id}", "severity": "HIGH",
         "domain": "web", "summary": "no object-level authz"},
        {"id": "F2", "title": "hardcoded key in test", "severity": "MEDIUM",
         "domain": "secrets", "summary": "fixture credential"},
    ]
    verdicts = triage._triage_batch(findings, checklist="(none)", model="fake",
                                    timeout=15, deep=False)

    assert "__error__" not in verdicts
    assert verdicts["F1"]["verdict"] == "likely_true_positive"
    assert verdicts["F2"]["verdict"] == "likely_false_positive"
    assert verdicts["F1"]["severity"] == "HIGH"
