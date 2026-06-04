import importlib


def _reload(monkeypatch, provider, **env):
    monkeypatch.setenv("SECHOUND_LLM", provider)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import llm
    importlib.reload(llm)
    return llm


def test_provider_default(monkeypatch):
    monkeypatch.delenv("SECHOUND_LLM", raising=False)
    import llm
    importlib.reload(llm)
    assert llm.provider() == "claude"


def test_default_model_per_provider(monkeypatch):
    assert _reload(monkeypatch, "openai").default_model("cheap_tasks") == "gpt-4o-mini"
    assert _reload(monkeypatch, "claude").default_model("expensive_tasks") == "claude-opus-4-8"


def test_model_env_override(monkeypatch):
    llm = _reload(monkeypatch, "claude", SECHOUND_MODEL="my-model")
    assert llm.default_model("default") == "my-model"


def test_is_agentic(monkeypatch):
    assert _reload(monkeypatch, "claude").is_agentic() is True
    assert _reload(monkeypatch, "openai").is_agentic() is False
    assert _reload(monkeypatch, "anthropic").is_agentic() is False


def test_command_unset_is_unavailable(monkeypatch):
    monkeypatch.delenv("SECHOUND_LLM_CMD", raising=False)
    llm = _reload(monkeypatch, "command")
    ok, reason = llm.available()
    assert ok is False and "SECHOUND_LLM_CMD" in reason


def test_command_backend_roundtrip(monkeypatch):
    # `cat` echoes the prompt back — proves the model-agnostic path end to end
    # with no network and no Claude CLI.
    llm = _reload(monkeypatch, "command", SECHOUND_LLM_CMD="cat")
    res = llm.complete("SYSTEM_MARKER", "USER_MARKER", timeout=10)
    assert res.error == ""
    assert "SYSTEM_MARKER" in res.text and "USER_MARKER" in res.text


def test_unknown_provider_reports_error(monkeypatch):
    llm = _reload(monkeypatch, "nope")
    res = llm.complete("s", "u", timeout=5)
    assert "unknown" in res.error.lower()


def test_claude_prompt_via_stdin_not_argv(monkeypatch):
    # Regression guard: `claude --allowedTools` is variadic and would swallow a
    # trailing positional prompt (exit 1). The prompt must go on stdin.
    llm = _reload(monkeypatch, "claude")

    captured = {}

    class FakeProc:
        stdout = '{"ok": true}'
        stderr = ""
        returncode = 0

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["input"] = kw.get("input")
        return FakeProc()

    monkeypatch.setattr(llm.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(llm.subprocess, "run", fake_run)

    llm.complete("SYSTEM", "THE_PROMPT", tools="Bash,Read", timeout=5)
    assert captured["input"] == "THE_PROMPT"        # prompt on stdin
    assert "THE_PROMPT" not in captured["cmd"]       # never a positional arg
    assert "--allowedTools" in captured["cmd"]
