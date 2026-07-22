# 0003 — The LLM is swappable, and only one file knows which one we use

**Status:** accepted · **Date:** 2026-07-22

## The question

The chat client needs a language model. Do we write against one vendor's SDK, or
keep the model layer pluggable — and if pluggable, through what?

## The decision

**Pluggable, via LangChain's `init_chat_model()`.** The model is named by a single
environment variable in `provider:model` form:

```bash
LLM_MODEL=anthropic:claude-opus-4-8
LLM_MODEL=openai:gpt-4.1
LLM_MODEL=google_genai:gemini-2.0-flash
LLM_MODEL=ollama:qwen2.5:14b
```

**Exactly one file — `chat-client/app/llm.py` — knows a vendor exists.** No other
file in the repository imports a provider SDK. A CI check greps for it, because a
convention nobody enforces stops being true within a month.

## Why

**Readers shouldn't need our API key to learn MCP.** Someone working through this
series should be able to point it at Ollama and follow along for free. Hard-coding
a vendor puts a paywall in front of the lesson.

**MCP is vendor-neutral, so the demo should be too.** The whole premise of the
protocol is that any model can call any tool. A companion repo that only works
with one provider quietly contradicts the thing it's teaching.

**One coupling point is the actual lesson.** "Make it swappable" usually means
scattering abstractions everywhere. Here it means the opposite: everything else
takes a model object as an argument and doesn't care where it came from. That's a
design habit worth showing.

## Why not LiteLLM as the default

LiteLLM proxy is genuinely good, and we document it as the "going further" path.
But as the *default* it costs a fifth container, a config file, and a layer of
indirection sitting between the reader and the thing they're trying to see.
`init_chat_model()` is one function call with zero infrastructure.

Because `llm.py` is the only coupling point, adopting a gateway later is two
environment variables — LiteLLM, vLLM, OpenRouter, Groq, and LM Studio all speak
the OpenAI-compatible protocol:

```bash
LLM_MODEL=openai:whatever-you-named-it
OPENAI_API_BASE=http://litellm:4000
```

Keeping that door open is the point of the abstraction. Walking through it on day
one is not.

## What it costs

**Independence is not equivalence, and we have to say so.** MCP is tool calling.
Our agent loop asks a model to pick the right tool from twelve, fill in its
arguments, read the result, and decide whether to call another. Frontier models do
that reliably. A 7B model on a laptop frequently doesn't — it invents tool names,
fabricates arguments, or loops.

So the repo ships three things rather than a vague promise:

- **A verified baseline** named in `.env.example`, so anyone who just wants it to
  work has a known-good setting.
- **Honest field notes in the README** — what we actually tested, and how it
  actually behaved. Not a benchmark; observations, including the failures.
- **`LLM_ALLOWED_TOOLS`**, so a weaker model can be handed four tools instead of
  twelve and succeed. This turns out to be a genuinely useful technique, and a
  good demonstration of why small, sharp tools beat one clever tool.

**Provider quirks leak a little.** Token limits, tool-call formats, and streaming
behaviour differ. `init_chat_model` smooths most of it; where it doesn't, the
workaround goes in `llm.py` with a comment naming the provider — not spread
through the graph.

## See also

- `PLAN.md` §9.1 — the model layer
- `PLAN.md` §9.2 — not every model can do this
- `PLAN.md` §8 — tool design, and why the menu should be short
