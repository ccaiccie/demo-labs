# CrewAI local network-operations lab

A small, offline CrewAI lab that runs against [Ollama](https://ollama.com) on the same machine. There are no cloud API keys.

This is a product lab, not a recording guide. It shows agents, tasks, a sequential crew, custom tools, a severity-routing Flow, and a memory follow-up over syslog fixtures.

## What you need

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) listening on `http://127.0.0.1:11434`
- A small local model. The default is `qwen2.5:3b` (CPU-friendly). You can also try `llama3.2:3b` or `qwen3:4b`.

```bash
ollama pull qwen2.5:3b
# optional alternatives
# ollama pull llama3.2:3b
# ollama pull qwen3:4b
```

If you use a qwen3 model, keep `think=False` in `crews/llm_config.py` so the model does not stream a hidden thinking channel that CrewAI treats as an empty reply.

## Configure

Copy `.env.example` to `.env` if needed. The default points at a local Ollama daemon:

```
MODEL=ollama/qwen2.5:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

`OLLAMA_BASE_URL` can point at any reachable Ollama host. Leave it on loopback unless you have a reason to change it.

## Install and run

```bash
cd crewai-lab
uv sync
uv run python scripts/smoke_tools.py
uv run python crews/research_writer.py
uv run python crews/log_triage.py
uv run python flows/severity_flow.py
uv run python flows/memory_followup.py
```

Or run `./scripts/run-all.sh`.

## What each run does

| Step | Script | Output |
|---|---|---|
| Tool smoke test | `scripts/smoke_tools.py` | Confirms path-safe list/read tools, no LLM |
| Research crew | `crews/research_writer.py` | `outputs/ospf-brief.md` |
| Log triage crew | `crews/log_triage.py` | `outputs/log-triage-report.md` |
| Severity Flow | `flows/severity_flow.py` | `outputs/flow-incident.md` or `outputs/flow-digest.md`, plus `outputs/ticket-memory.md` |
| Memory follow-up | `flows/memory_followup.py` | `outputs/memory-followup.md` |

The fixtures live in `fixtures/logs/` and `fixtures/knowledge/`. Addresses are RFC 5737 documentation prefixes only.

## What we observed

These results are from a CPU-only run on Ubuntu 24.04 with Ollama and `qwen2.5:3b` (about 1.9 GB). LiteLLM is configured so `MODEL=ollama/qwen2.5:3b` uses the Ollama chat API for tool calls. `qwen3:4b` and `llama3.2:3b` are optional; they were less consistent at tool use in this lab.

- **Research crew** (`crews/research_writer.py`) wrote `outputs/ospf-brief.md`. It described the `core-sw1` / `core-sw2` topology, neighbor `192.0.2.19` on `GigabitEthernet0/1`, and treated a recovered FULL adjacency as a transient bounce rather than a standing outage.
- **Log triage crew** (`crews/log_triage.py`) wrote `outputs/log-triage-report.md`. After reading each fixture in a fresh collector crew (so device context does not leak), the report kept the three findings on the correct devices:
  - `core-sw1`: OSPF neighbor `192.0.2.19` recovered to FULL (medium).
  - `edge-fw1`: SSH deny burst from `198.51.100.66` (high).
  - `access-sw2`: MAC `00:11:22:33:44:61` flapping between `Gi1/0/12` and `Gi1/0/24` on VLAN 20 (high).
- **Severity Flow** (`flows/severity_flow.py`) classified `edge-fw1.log` as **high**, wrote `outputs/flow-incident.md`, and recorded `outputs/ticket-memory.md`.
- **Memory follow-up** (`flows/memory_followup.py`) wrote `outputs/memory-followup.md` from ticket memory only: review `198.51.100.66`, confirm whether the burst stopped, and look for a later successful admin login from a trusted address.

Small models can mis-count deny lines or overstate a recovered bounce. The fixtures are short on purpose, and the per-file collector split keeps events on the device that logged them.
