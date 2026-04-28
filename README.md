# oni-devops-traces

> **Open multi-turn DevOps agent traces** in `Thought → Code → Observation` format,
> distilled from existing instruction datasets via a local 31B teacher LLM.
> Drop-in for SFT on 24GB GPUs.

[![License](https://img.shields.io/badge/code-Apache_2.0-blue.svg)](LICENSE)
[![Data](https://img.shields.io/badge/data-MIT_(inherited)-green.svg)](LICENSE)
[![Format](https://img.shields.io/badge/format-JSONL_agent_traces-orange.svg)](DATASET_FORMAT.md)
[![Teacher](https://img.shields.io/badge/teacher-gemma4%3A31b-purple.svg)](#how-we-built-this)
[![Local](https://img.shields.io/badge/run-local_24GB_GPU-red.svg)](REPRODUCE.md)

🇷🇺 [Русская версия / Russian translation](README_RU.md)

```
data/
├── own_anchors/            ← 1867 hand-crafted golden traces (the format spec)
├── distilled_bash_pipes/   ← Linux command-line, pipes, awk/grep/sed
├── distilled_django/       ← Django scaffolding & patterns
├── distilled_express/      ← Express.js routing & middleware
├── distilled_microservices/← message queues, service discovery
└── ...                     (grows as we distill more sources)
```

---

## TL;DR

```python
from datasets import load_dataset

ds = load_dataset("path/to/this/repo", data_dir="data/distilled_bash_pipes")
# Each item: {"messages": [...], "meta": {...}}
# messages — multi-turn agent dialog, ready for SFT
```

To rebuild from scratch or adapt to your own domain — see [REPRODUCE.md](REPRODUCE.md).

---

## Why we built this

### What we were doing

Fine-tuning Qwen3-14B into a local DevOps AI agent. Goal: have it run on a single
RTX 3090, understand our infrastructure (SSH, Docker, nginx, Django, Vue/React),
carry on a multi-turn dialog with tools (`bash`, `read_file`, `write_file`,
`list_dir`), and **honestly report failures** instead of pretending success
when a command actually broke.

### What we needed — multi-turn agent traces

To teach the agent the `Thought → Code → Observation → Thought → ...` format,
we need examples **in exactly that format**. Not "question → answer", but a full
dialog with tool calls and verification.

```json
{"messages": [
  {"role": "system", "content": "You are a DevOps agent..."},
  {"role": "user", "content": "Set up nginx reverse proxy..."},
  {"role": "assistant", "content": "Thought: First write the config.\n<code>write_file(...)</code>"},
  {"role": "user", "content": "Observation: wrote 245 chars to /etc/nginx/sites-available/app"},
  {"role": "assistant", "content": "Thought: Now test it.\n<code>bash(command='nginx -t')</code>"},
  {"role": "user", "content": "Observation: $ nginx -t\n[exit 0]\nsyntax is ok"},
  {"role": "assistant", "content": "<code>final_answer('nginx config OK, reloaded')</code>"}
]}
```

### What was available — and what was wrong with it

Existing open-source code datasets (millions of examples, great quality):

| Dataset | Items | Format |
|---|---:|---|
| [`ise-uiuc/Magicoder-Evol-Instruct-110K`](https://huggingface.co/datasets/ise-uiuc/Magicoder-Evol-Instruct-110K) | 110,000 | `instruction → response` (single-turn) |
| [`ise-uiuc/Magicoder-OSS-Instruct-75K`](https://huggingface.co/datasets/ise-uiuc/Magicoder-OSS-Instruct-75K) | 75,000 | `instruction → response` (single-turn) |
| [`bigcode/commitpackft`](https://huggingface.co/datasets/bigcode/commitpackft) | 4M+ | `before/after/message` git commits |
| [`nuprl/CanItEdit`](https://huggingface.co/datasets/nuprl/CanItEdit) | small | `before → instruction → after` |

**The problem:** these are all **single-turn**. The model sees a question and
an answer, learns to produce code in one shot, but **does not learn the
iterative tool-use loop**.

When we tried to mix Magicoder directly into our training set, the model
**regressed** on agent tasks. We confirmed this across three iterations
(base-3, base-4, base-5 of our fine-tune). Root cause: **format mismatch** —
the model got confused between "answer in one block" and "carry on a dialog
with tools".

### What we did — distillation pipeline

Take a raw `instruction → response` pair from a source. Feed it to a local
teacher LLM (gemma4:31b, Apache 2.0, fits in 24GB VRAM) along with **5 anchor
few-shot examples** in our agent format. The teacher rewraps each item into a
proper multi-turn agent trace with realistic observations and verification
before `final_answer`.

We then filter by composite format-compliance score (>=84.8/100) — keeping only
items that pass our strict template check. Acceptance is 80-90% across sources.

**Result — this repo.** Each `data/distilled_*` is a chunk of a raw HF/GitHub
dataset, rewrapped into our agent format, license-compatible (mostly MIT,
Apache 2.0 for our code and teacher contributions).

### Who this is useful for

- **Local agent fine-tuners** — grab the JSONL, drop it into your SFT pipeline
  (Unsloth, TRL, axolotl), press the button
- **Researchers** — see how a teacher LLM "unfolds" single-turn into multi-turn,
  what degrades during distillation
- **DevOps teams** that want their own local copilot — pick a domain-specific
  subset (django/express/microservices) and fine-tune for your stack

---

## What we took and why

| Subset | Source | Items raw → accepted | Why this domain |
|---|---|---:|---|
| `bash_pipes` | Magicoder-Evol filter on grep/awk/sed/find/xargs/jq | 300 → ~265 | Linux CLI pipelines — our agent handles single commands well, but struggles with `grep \| awk \| sort \| uniq -c \| sort -rn \| head` chains |
| `django` | Magicoder-Evol filter on Django ecosystem | 300 → ~265 | Django scaffolding — was 0/11 on our L1.1 benchmark in base-6.v2 |
| `express` | Magicoder-Evol filter on Express.js | 250 → ~220 | Node.js backend coverage was thin (10 seeds for the entire JS ecosystem) |
| `microservices` | Magicoder-Evol filter on distributed | 250 → ~220 | Kubernetes/cloud absent (0 seeds) |
| `design_patterns` | Magicoder-Evol filter on GoF | 250 → ~220 | Architectural reasoning in tasks like "design a pub/sub" |
| `solid` | Magicoder-Evol filter on SOLID/refactor | 250 → ~220 | Not just write code — improve it |
| `frontend_fullstack` | Magicoder-Evol filter on JS/TS/Node/HTML/CSS | 400 → ~350 | Tooling (eslint/prettier/jest/vite/webpack) |
| `js_only` | Magicoder-Evol filter on plain JS | 400 → ~350 | Distinguish vanilla JS from TypeScript |
| `ts_only` | Magicoder-Evol filter on TypeScript | 400 → ~350 | Interfaces/types/generics/tsconfig |

Full catalog with per-subset description, provenance, licenses, and links to
benchmark scores: [CATALOG.md](CATALOG.md).

---

## Format

Each trace is one JSON line. Minimum 4 turns (system + user + assistant + user),
typically 6-15. Each assistant turn = `Thought + <code>tool_call(...)</code>`.
Each user turn after assistant = `Observation: ...`. Last assistant turn =
`<code>final_answer("...")</code>`.

Full spec: [DATASET_FORMAT.md](DATASET_FORMAT.md).

---

## How we built this

### Teacher selection

We benchmarked 4 candidates on a 20-trial test set (identical items, identical
few-shot, format-compliance metrics):

| Model | VRAM | 20-trial AVG | Catastrophic 0.0 | Verdict |
|---|---:|---:|---:|---|
| **gemma4:31b** | 19 GB | **92.0** | **0%** | 🏆 WINNER |
| qwen3.6:27b | 17 GB | 72.7 | 15% | runner-up but 15% complete fails |
| qwen2.5-coder:32b | 23 GB | 84.8 (5-trial) | n/a | stable but slower |
| deepseek-coder-v2:16b-lite | 14 GB | 44.8 | n/a | context too short |

Full report with per-trial breakdown: [meta/benchmark_results.md](meta/benchmark_results.md).

### Distillation parameters

```yaml
teacher: gemma4:31b
quant: default (Q4)
num_ctx: 16384            # 8K causes loops / truncation
num_predict: 4000
temperature: 0.7
repeat_penalty: 1.15      # protects against infinite repetition
think: false              # critical for Qwen3-family (gemma4 doesn't need it but safe)
keep_alive: 24h
min_score: 84.8           # composite format-compliance threshold
```

### Composite scoring

Each generated trace is scored on 8 metrics:

| Metric | Weight | What it checks |
|---|---:|---|
| `json_parses` | 1.0 | Valid JSON `{messages, meta}` |
| `has_messages` | 1.0 | ≥4 messages in array |
| `system_present` | 0.5 | system role is there |
| `assistant_has_thought_and_code` | 1.0 | every assistant turn = Thought + `<code>` |
| `tool_call_present` | 0.8 | at least one of 5 tools called |
| `final_answer_present` | 1.0 | last assistant calls final_answer |
| `verification_before_final` | 0.7 | something was verified before final_answer |
| `step_count_in_range` | 0.3 | 3-15 assistant turns |

Score 0-100. Threshold 84.8 = "format-clean enough for production training".

---

## Reproduce

```bash
# 1. Get teacher
ollama pull gemma4:31b

# 2. Distill any HF dataset
python scripts/distill.py \
    --source path/to/raw.jsonl \
    --output runs/my_topic \
    --teacher gemma4:31b \
    --min-score 84.8

# 3. Use for SFT
cat data/own_anchors/train.jsonl \
    data/distilled_bash_pipes/data.jsonl \
    > combined.jsonl
# feed into your SFT trainer
```

Full step-by-step guide: [REPRODUCE.md](REPRODUCE.md).

---

## License

| What | License | Notes |
|---|---|---|
| This code (scripts/) | Apache 2.0 | fork freely |
| `data/own_anchors/` | Apache 2.0 | our hand-crafted traces |
| `data/distilled_*/` | MIT (inherited) | from Magicoder family |
| Teacher contributions | Apache 2.0 | gemma4 outputs are free |

See [LICENSE](LICENSE) and per-subset LICENSE files for details.

---

## Citation

```bibtex
@misc{oni-devops-traces-2026,
  title={Open multi-turn DevOps agent traces, distilled},
  author={MakarSuperstar},
  year={2026},
  url={https://github.com/makarsuperstar/oni-devops-traces}
}
```

---

## Roadmap

- [x] Benchmark 4 teacher candidates → gemma4:31b winner (92.0/100)
- [x] First distilled subset: `bash_pipes` (Magicoder filter)
- [ ] Cover remaining Magicoder filters (~2710 items left)
- [ ] Distill from `commitpackft` (real git commits)
- [ ] Distill from curated GitHub repos (tldr-pages, node-best-practices)
- [ ] Mirror on HuggingFace Hub for `load_dataset` discovery
- [ ] Publish recipe configs for combining subsets

---

## Issues / Contributions

If you find a trace that's clearly broken (wrong tool name, hallucinated
observation, missing `final_answer`), open an issue with the trace's
`meta.trace_hash` from the JSONL — we will regenerate that item.

Want to add a subset from your domain (Kubernetes, Terraform, AWS)? PRs with
a filter script and raw-source description are welcome.
