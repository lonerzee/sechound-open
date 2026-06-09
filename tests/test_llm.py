import importlib
import sys
import types


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


# --------------------------------------------------------------------------- #
# API backends: prove each call path matches its SDK's shape and routes the
# system/user prompt correctly. No network — the SDK module is faked in
# sys.modules so the real `import openai`/`anthropic`/`google.generativeai`
# inside the backend resolves to our stub. Guards against SDK-signature drift
# that would otherwise only surface on a user's first live call.
# --------------------------------------------------------------------------- #

def test_openai_backend_call_shape(monkeypatch):
    captured = {}

    class _Completions:
        def create(self, **kw):
            captured.update(kw)
            msg = types.SimpleNamespace(content="OPENAI_REPLY")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    class _Chat:
        completions = _Completions()

    class _OpenAI:
        def __init__(self, **kw):
            captured["client_kwargs"] = kw
            self.chat = _Chat()

    fake = types.ModuleType("openai")
    fake.OpenAI = _OpenAI
    monkeypatch.setitem(sys.modules, "openai", fake)

    llm = _reload(monkeypatch, "openai", OPENAI_API_KEY="sk-test",
                  OPENAI_BASE_URL="http://localhost:11434/v1")
    ok, reason = llm.available()
    assert ok, reason
    res = llm.complete("SYS", "USR", model="gpt-test", timeout=7)
    assert res.error == "" and res.text == "OPENAI_REPLY"
    assert captured["model"] == "gpt-test"
    # base_url honored (Ollama/LM Studio compatibility) + prompt routed by role
    assert captured["client_kwargs"]["base_url"] == "http://localhost:11434/v1"
    roles = {m["role"]: m["content"] for m in captured["messages"]}
    assert roles["system"] == "SYS" and roles["user"] == "USR"


def test_anthropic_backend_call_shape(monkeypatch):
    captured = {}

    class _Messages:
        def create(self, **kw):
            captured.update(kw)
            block = types.SimpleNamespace(type="text", text="ANTHROPIC_REPLY")
            return types.SimpleNamespace(content=[block])

    class _Anthropic:
        def __init__(self, **kw):
            self.messages = _Messages()

    fake = types.ModuleType("anthropic")
    fake.Anthropic = _Anthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake)

    llm = _reload(monkeypatch, "anthropic", ANTHROPIC_API_KEY="sk-ant-test")
    ok, reason = llm.available()
    assert ok, reason
    res = llm.complete("SYS", "USR", model="claude-test", timeout=7)
    assert res.error == "" and res.text == "ANTHROPIC_REPLY"
    assert captured["model"] == "claude-test"
    # system prompt is a top-level arg in the Messages API, not a message
    assert captured["system"] == "SYS"
    assert captured["messages"] == [{"role": "user", "content": "USR"}]


def test_gemini_backend_call_shape(monkeypatch):
    captured = {}

    class _Model:
        def __init__(self, model, system_instruction=None):
            captured["model"] = model
            captured["system_instruction"] = system_instruction

        def generate_content(self, prompt, **kw):
            captured["prompt"] = prompt
            return types.SimpleNamespace(text="GEMINI_REPLY")

    genai = types.ModuleType("google.generativeai")
    genai.configure = lambda **kw: captured.setdefault("configured", kw)
    genai.GenerativeModel = _Model
    google_pkg = types.ModuleType("google")
    google_pkg.generativeai = genai
    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.generativeai", genai)

    llm = _reload(monkeypatch, "gemini", GEMINI_API_KEY="g-test")
    ok, reason = llm.available()
    assert ok, reason
    res = llm.complete("SYS", "USR", model="gemini-test", timeout=7)
    assert res.error == "" and res.text == "GEMINI_REPLY"
    assert captured["model"] == "gemini-test"
    # Gemini takes the system prompt as system_instruction, user as content
    assert captured["system_instruction"] == "SYS"
    assert captured["prompt"] == "USR"


def test_api_backend_never_raises_on_sdk_error(monkeypatch):
    # A provider bug must surface as LLMResult.error, never crash the pipeline.
    class _BoomOpenAI:
        def __init__(self, **kw):
            raise RuntimeError("sdk exploded")

    fake = types.ModuleType("openai")
    fake.OpenAI = _BoomOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake)
    llm = _reload(monkeypatch, "openai", OPENAI_API_KEY="sk-test")
    res = llm.complete("s", "u", timeout=5)
    assert not res.ok and "sdk exploded" in res.error


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
