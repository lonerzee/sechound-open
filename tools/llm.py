"""
llm.py — model-agnostic LLM invocation.

Every SecHound tool calls `complete()` instead of talking to a specific model.
Pick the backend with $SECHOUND_LLM:

    claude      (default) the `claude` CLI — agentic: supports tool use
                (`tools=`), live streaming (`stream_to=`), and MCP configs.
    command     any CLI via the $SECHOUND_LLM_CMD template (e.g. Ollama,
                `llm`, a local server wrapper). Prompt is fed on stdin.
                Template placeholders: {model}.
    anthropic   Anthropic Messages API (needs `anthropic` + $ANTHROPIC_API_KEY).
    openai      OpenAI-compatible Chat Completions API (needs `openai` +
                $OPENAI_API_KEY; set $OPENAI_BASE_URL for Ollama/LM Studio/etc).

Capability note: `tools=` (agentic code-reading) and `stream_to=` are honored
only by agentic backends (`claude`, and `command` if your command is itself
agentic). The API backends are completion-only — they receive the prompt and
return text, ignoring `tools`/`stream_to` with a one-line warning. The critic
and verifier lanes need to grep the codebase, so they require an agentic
backend; pure-API backends are fine for compounder and the review lanes.

Default models per backend are env-overridable; see `default_model()`.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LLMResult:
    text: str = ""
    exit_code: int = 0
    error: str = ""
    elapsed_s: float = 0.0
    stderr_tail: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.error and self.exit_code == 0


def provider() -> str:
    return (os.environ.get("SECHOUND_LLM") or "claude").strip().lower()


def default_model(tier: str = "default") -> str:
    """Resolve the model id for a workload tier, per active provider.

    Override per tier with $SECHOUND_MODEL_<TIER>, globally with $SECHOUND_MODEL.
    """
    env = os.environ.get(f"SECHOUND_MODEL_{tier.upper()}") or os.environ.get("SECHOUND_MODEL")
    if env:
        return env
    p = provider()
    table = {
        "claude": {
            "default": "claude-sonnet-4-6",
            "expensive_tasks": "claude-opus-4-8",
            "cheap_tasks": "claude-haiku-4-5-20251001",
        },
        "anthropic": {
            "default": "claude-sonnet-4-6",
            "expensive_tasks": "claude-opus-4-8",
            "cheap_tasks": "claude-haiku-4-5-20251001",
        },
        "openai": {
            "default": "gpt-4o",
            "expensive_tasks": "gpt-4o",
            "cheap_tasks": "gpt-4o-mini",
        },
        "gemini": {
            "default": "gemini-2.0-flash",
            "expensive_tasks": "gemini-2.0-pro",
            "cheap_tasks": "gemini-2.0-flash-lite",
        },
    }.get(p, {})
    return table.get(tier, table.get("default", "default"))


def available() -> tuple[bool, str]:
    """Return (is_usable, reason). Cheap pre-flight before a batch of calls."""
    p = provider()
    if p == "claude":
        return (bool(shutil.which("claude")), "claude CLI not on PATH")
    if p == "command":
        cmd = os.environ.get("SECHOUND_LLM_CMD")
        if not cmd:
            return (False, "SECHOUND_LLM=command but $SECHOUND_LLM_CMD is unset")
        bin0 = shlex.split(cmd)[0] if cmd else ""
        return (bool(shutil.which(bin0)), f"command '{bin0}' not on PATH")
    if p == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return (False, "ANTHROPIC_API_KEY unset")
        try:
            import anthropic  # noqa: F401
        except Exception:
            return (False, "`pip install anthropic` required for SECHOUND_LLM=anthropic")
        return (True, "")
    if p == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            return (False, "OPENAI_API_KEY unset")
        try:
            import openai  # noqa: F401
        except Exception:
            return (False, "`pip install openai` required for SECHOUND_LLM=openai")
        return (True, "")
    if p == "gemini":
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            return (False, "GEMINI_API_KEY (or GOOGLE_API_KEY) unset")
        try:
            import google.generativeai  # noqa: F401
        except Exception:
            return (False, "`pip install google-generativeai` required for SECHOUND_LLM=gemini")
        return (True, "")
    return (False, f"unknown SECHOUND_LLM provider: {p}")


def is_agentic() -> bool:
    """True if the active provider can use tools / read the codebase."""
    p = provider()
    if p == "claude":
        return True
    if p == "command":
        # The user's command may or may not be agentic; assume it can be.
        return True
    return False  # api backends are completion-only


def complete(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    timeout: int = 300,
    tools: str | None = None,
    cwd: str | Path | None = None,
    stream_to: Path | None = None,
    stderr_to: Path | None = None,
    mcp_config: str | Path | None = None,
    tier: str = "default",
) -> LLMResult:
    """Run one completion. Returns LLMResult (always — errors are reported in
    `.error`, never raised, so callers can degrade gracefully)."""
    model = model or default_model(tier)
    p = provider()
    started = time.time()

    if tools and not is_agentic():
        sys.stderr.write(
            f"[llm] provider '{p}' is completion-only; ignoring tools={tools!r} "
            f"(this lane wanted to read the codebase — use SECHOUND_LLM=claude or a "
            f"command backend for full fidelity)\n"
        )

    try:
        if p == "claude":
            r = _claude_cli(system_prompt, user_prompt, model, timeout, tools, cwd,
                            stream_to, stderr_to, mcp_config)
        elif p == "command":
            r = _command(system_prompt, user_prompt, model, timeout, cwd, stream_to, stderr_to)
        elif p == "anthropic":
            r = _anthropic_api(system_prompt, user_prompt, model, timeout)
        elif p == "openai":
            r = _openai_api(system_prompt, user_prompt, model, timeout)
        elif p == "gemini":
            r = _gemini_api(system_prompt, user_prompt, model, timeout)
        else:
            r = LLMResult(error=f"unknown SECHOUND_LLM provider: {p}")
    except Exception as e:  # never let a provider bug crash the pipeline
        r = LLMResult(error=f"{type(e).__name__}: {e}")

    r.elapsed_s = round(time.time() - started, 2)

    # Backends that don't stream (the API ones) still owe the caller a log file
    # if one was requested, so orchestrate's live.log is never a dangling path.
    if stream_to is not None and not stream_to.exists():
        try:
            stream_to.write_text(r.text or "", encoding="utf-8")
        except Exception:
            pass
    return r


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #

def _stream_pipe(pipe, log_path: Path | None, buf: list[str]) -> None:
    if log_path is not None:
        with log_path.open("w", encoding="utf-8", errors="replace") as fh:
            for line in pipe:
                fh.write(line)
                fh.flush()
                buf.append(line)
    else:
        for line in pipe:
            buf.append(line)


def _claude_cli(system_prompt, user_prompt, model, timeout, tools, cwd,
                stream_to, stderr_to, mcp_config) -> LLMResult:
    if not shutil.which("claude"):
        return LLMResult(error="claude CLI not on PATH")
    cmd = ["claude", "--model", model, "--system-prompt", system_prompt,
           "--print", "--output-format", "text"]
    if tools:
        cmd += ["--allowedTools", tools]
    if mcp_config and Path(mcp_config).exists():
        cmd += ["--mcp-config", str(mcp_config)]
    # The prompt goes on STDIN, never as a trailing positional: `--allowedTools`
    # is variadic and would otherwise swallow the prompt as another tool name,
    # making claude exit 1 with "Input must be provided ...".

    # Stream when a log path is given (orchestrator lanes); else simple capture.
    if stream_to is not None:
        stdout_buf: list[str] = []
        stderr_buf: list[str] = []
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, cwd=str(cwd) if cwd else None)
        try:
            proc.stdin.write(user_prompt)
            proc.stdin.close()
        except Exception:
            pass
        t_out = threading.Thread(target=_stream_pipe, args=(proc.stdout, stream_to, stdout_buf), daemon=True)
        t_err = threading.Thread(target=_stream_pipe, args=(proc.stderr, stderr_to, stderr_buf), daemon=True)
        t_out.start()
        t_err.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return LLMResult(text="".join(stdout_buf), error=f"timeout after {timeout}s")
        t_out.join()
        t_err.join()
        return LLMResult(text="".join(stdout_buf), exit_code=proc.returncode,
                         stderr_tail="".join(stderr_buf)[-2000:])

    try:
        proc = subprocess.run(cmd, input=user_prompt, capture_output=True, text=True,
                              timeout=timeout, cwd=str(cwd) if cwd else None)
    except subprocess.TimeoutExpired:
        return LLMResult(error=f"timeout after {timeout}s")
    return LLMResult(text=proc.stdout or "", exit_code=proc.returncode,
                     stderr_tail=(proc.stderr or "")[-2000:])


def _command(system_prompt, user_prompt, model, timeout, cwd, stream_to, stderr_to) -> LLMResult:
    template = os.environ.get("SECHOUND_LLM_CMD")
    if not template:
        return LLMResult(error="SECHOUND_LLM=command but $SECHOUND_LLM_CMD is unset")
    argv = [tok.replace("{model}", model) for tok in shlex.split(template)]
    prompt = f"{system_prompt}\n\n{user_prompt}"
    try:
        proc = subprocess.run(argv, input=prompt, capture_output=True, text=True,
                              timeout=timeout, cwd=str(cwd) if cwd else None)
    except subprocess.TimeoutExpired:
        return LLMResult(error=f"timeout after {timeout}s")
    out = proc.stdout or ""
    if stream_to is not None:
        try:
            stream_to.write_text(out, encoding="utf-8")
        except Exception:
            pass
    return LLMResult(text=out, exit_code=proc.returncode, stderr_tail=(proc.stderr or "")[-2000:])


def _anthropic_api(system_prompt, user_prompt, model, timeout) -> LLMResult:
    import anthropic
    client = anthropic.Anthropic(timeout=timeout)
    msg = client.messages.create(
        model=model,
        max_tokens=int(os.environ.get("SECHOUND_MAX_TOKENS", "4096")),
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    return LLMResult(text=text)


def _openai_api(system_prompt, user_prompt, model, timeout) -> LLMResult:
    import openai
    kwargs = {"timeout": timeout}
    if os.environ.get("OPENAI_BASE_URL"):
        kwargs["base_url"] = os.environ["OPENAI_BASE_URL"]
    client = openai.OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=int(os.environ.get("SECHOUND_MAX_TOKENS", "4096")),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return LLMResult(text=resp.choices[0].message.content or "")


def _gemini_api(system_prompt, user_prompt, model, timeout) -> LLMResult:
    import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"])
    gm = genai.GenerativeModel(model, system_instruction=system_prompt)
    resp = gm.generate_content(user_prompt, request_options={"timeout": timeout})
    return LLMResult(text=getattr(resp, "text", "") or "")
