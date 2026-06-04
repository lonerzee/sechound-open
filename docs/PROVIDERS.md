# LLM providers

SecHound is model-agnostic. Every tool calls one function — `llm.complete()` in
`tools/llm.py` — and never talks to a specific model directly. Swap the backend
with the `SECHOUND_LLM` environment variable; nothing else changes.

## Backends

| `SECHOUND_LLM` | Backend | Agentic? | Needs |
|---|---|---|---|
| `claude` (default) | `claude` CLI | **yes** — tool use, streaming, MCP | `claude` on PATH |
| `command` | any CLI via `$SECHOUND_LLM_CMD` | depends on your CLI | the CLI on PATH |
| `anthropic` | Anthropic Messages API | no (completion-only) | `pip install anthropic`, `$ANTHROPIC_API_KEY` |
| `openai` | OpenAI-compatible Chat API | no (completion-only) | `pip install openai`, `$OPENAI_API_KEY` |
| `gemini` | Google Gemini API | no (completion-only) | `pip install google-generativeai`, `$GEMINI_API_KEY` |

> Azure OpenAI and other OpenAI-compatible gateways work through the `openai`
> backend by setting `$OPENAI_BASE_URL`.

### Agentic vs. completion-only

Some stages need the model to **read the codebase** (grep cited files, verify
controls): the **critic** and the **static UltraReview lane**. Those require an
*agentic* backend (`claude`, or a `command` backend that is itself agentic).
With a completion-only API backend they still run, but they reason only from the
finding text — weaker verdicts. The tool prints a one-line warning when this
happens. The **compounder** and **counter** lane work fine on any backend.

## Examples

```bash
# Default — Claude Code CLI (full agentic fidelity)
export SECHOUND_LLM=claude

# Local model via Ollama (prompt is fed on stdin; {model} is substituted)
export SECHOUND_LLM=command
export SECHOUND_LLM_CMD="ollama run {model}"
export SECHOUND_MODEL=llama3.1

# Anthropic API directly (no CLI)
export SECHOUND_LLM=anthropic
export ANTHROPIC_API_KEY=sk-...
export SECHOUND_MODEL=claude-sonnet-4-6

# Any OpenAI-compatible endpoint (OpenAI, LM Studio, vLLM, ...)
export SECHOUND_LLM=openai
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=http://localhost:1234/v1   # optional, for local servers
export SECHOUND_MODEL=gpt-4o
```

## Model tiers

Tools ask for a *tier*, not a hard-coded model, so you can map cost/capability
per backend:

| Tier | Used by | Override |
|---|---|---|
| `default` | planner, executor, compounder, orchestrator | `$SECHOUND_MODEL_DEFAULT` |
| `expensive_tasks` | critic, UltraReview | `$SECHOUND_MODEL_EXPENSIVE_TASKS` |
| `cheap_tasks` | bulk/mechanical lanes | `$SECHOUND_MODEL_CHEAP_TASKS` |

`$SECHOUND_MODEL` overrides every tier at once. Per-tier defaults live in
`tools/llm.py::default_model()`.

## Adding a backend

`tools/llm.py` is the only file to touch. Add a branch to `complete()` and a
small `_yourprovider(...)` function returning an `LLMResult`. Update
`available()`, `is_agentic()`, and `default_model()` for the new name. No other
module needs to change — that's the point of the seam.
