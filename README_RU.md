# oni-devops-traces — русская версия

> **Открытый датасет multi-turn DevOps agent трейсов** в формате
> `Thought → Code → Observation`, distilled из существующих instruction-датасетов
> через локальную 31B teacher LLM. Готов к подмесу в SFT на 24GB GPU.

[![License](https://img.shields.io/badge/code-Apache_2.0-blue.svg)](LICENSE)
[![Data](https://img.shields.io/badge/data-MIT_(inherited)-green.svg)](LICENSE)
[![Format](https://img.shields.io/badge/format-JSONL_agent_traces-orange.svg)](DATASET_FORMAT.md)

🇬🇧 [English version (primary)](README.md)

```
data/
├── own_anchors/            ← 1867 ручных золотых трейсов (эталон формата)
├── distilled_bash_pipes/   ← Linux CLI, пайплайны, awk/grep/sed
├── distilled_django/       ← Django scaffolding
├── distilled_express/      ← Express.js routing/middleware
├── distilled_microservices/← очереди сообщений, service discovery
└── ...                     (растёт по мере distillation)
```

---

## TL;DR

```python
from datasets import load_dataset

ds = load_dataset("path/to/this/repo", data_dir="data/distilled_bash_pipes")
# Каждый item: {"messages": [...], "meta": {...}}
# messages — multi-turn agent dialog, готов для SFT
```

Хотите пересобрать сами или адаптировать на свой домен — см. [REPRODUCE.md](REPRODUCE.md).

---

## Зачем мы это сделали

### Что мы делали

Файн-тюним Qwen3-14B в локального DevOps AI-агента. Цель: чтобы он жил на одной
RTX 3090, понимал нашу инфраструктуру (SSH, Docker, nginx, Django, Vue/React),
вёл многошаговый диалог с инструментами (`bash`, `read_file`, `write_file`,
`list_dir`), и **не врал про успех** когда команда упала.

### Что было нужно — multi-turn agent traces

Чтобы агент учился в формате `Thought → Code → Observation → Thought → ...`,
ему нужны примеры **точно в этом формате**. Не "вопрос → ответ", а полный
диалог с инструментами и проверками.

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

### Что было доступно — и что не так

Существующие открытые code-датасеты (миллионы примеров, отличного качества):

| Dataset | Items | Format |
|---|---:|---|
| [`ise-uiuc/Magicoder-Evol-Instruct-110K`](https://huggingface.co/datasets/ise-uiuc/Magicoder-Evol-Instruct-110K) | 110,000 | `instruction → response` (single-turn) |
| [`ise-uiuc/Magicoder-OSS-Instruct-75K`](https://huggingface.co/datasets/ise-uiuc/Magicoder-OSS-Instruct-75K) | 75,000 | `instruction → response` (single-turn) |
| [`bigcode/commitpackft`](https://huggingface.co/datasets/bigcode/commitpackft) | 4M+ | `before/after/message` git commits |
| [`nuprl/CanItEdit`](https://huggingface.co/datasets/nuprl/CanItEdit) | small | `before → instruction → after` |

**Проблема:** все эти датасеты — **single-turn**. Модель видит «вопрос-ответ»,
учится написать код в один присест, **не учится итеративному циклу с
инструментами**.

Когда мы попытались напрямую подмешать Magicoder в наш training set — модель
**регрессировала** на agent-задачах. Подтверждено три эпохи подряд (base-3, base-4,
base-5 версии нашего fine-tune). Корень: **format mismatch** — модель путалась
между «отвечай в один блок» и «веди диалог с tools».

### Что мы сделали — distillation pipeline

Берём raw `instruction → response` пару из источника. Скармливаем местному
teacher LLM (gemma4:31b, Apache 2.0, помещается в 24GB GPU) с **5 эталонными
few-shot примерами** в нашем agent-формате. Teacher переоборачивает каждый
item в полноценный multi-turn agent trace с реалистичными observations и
verification-перед-final_answer.

На выходе фильтруем по composite format-compliance score (>=84.8/100) — берём
только те, что прошли строгий шаблон. Acceptance ~80-90% на разных источниках.

**Результат — этот репо.** Каждый `data/distilled_*` — кусок raw HF/GitHub
датасета, переоборудованный в наш agent-format, лицензионно-совместимый
(MIT в основном, Apache 2.0 для нашего кода и teacher contributions).

### Кому это полезно

- **Файн-тюнерам локальных агентов** — берёте готовый JSONL, кладёте в SFT
  pipeline (Unsloth, TRL, axolotl), нажимаете кнопку
- **Researchers** — можно изучать как teacher LLM "разворачивает" single-turn
  в multi-turn, какая часть деградирует при distillation
- **DevOps-командам** которые хотят свой локальный copilot — берёте именно
  domain-specific subset (django/express/microservices) и финтюните под себя

---

## Какие данные взяли и зачем

| Subset | Источник | Items raw → accepted | Зачем взяли |
|---|---|---:|---|
| `bash_pipes` | Magicoder-Evol filter on grep/awk/sed/find/xargs/jq | 300 → ~265 | Linux CLI пайплайны — наш агент устойчиво рулит одной командой, но плохо строит `grep \| awk \| sort \| uniq -c \| sort -rn \| head` цепочки |
| `django` | Magicoder-Evol filter on Django ecosystem | 300 → ~265 | Django scaffolding — был провал на L1.1 (0/11) в нашей base-6.v2 |
| `express` | Magicoder-Evol filter on Express.js | 250 → ~220 | Node.js backend coverage был тонким (10 seeds на весь JS ecosystem) |
| `microservices` | Magicoder-Evol filter on distributed | 250 → ~220 | Kubernetes/cloud отсутствовал (0 seeds) |
| `design_patterns` | Magicoder-Evol filter on GoF | 250 → ~220 | Архитектурные решения в задачах "спроектируй pub/sub" |
| `solid` | Magicoder-Evol filter on SOLID/refactor | 250 → ~220 | Не просто писать код, но улучшать его |
| `frontend_fullstack` | Magicoder-Evol filter on JS/TS/Node/HTML/CSS | 400 → ~350 | Tooling (eslint/prettier/jest/vite/webpack) |
| `js_only` | Magicoder-Evol filter on plain JS | 400 → ~350 | Различать vanilla JS vs TypeScript |
| `ts_only` | Magicoder-Evol filter on TypeScript | 400 → ~350 | Interfaces/types/generics/tsconfig |

Полный каталог с описанием каждого subset, провенансом, лицензиями, и связями
с бенчмарк-числами — в [CATALOG.md](CATALOG.md).

---

## Format (формат данных)

Каждый трейс — JSON line. Минимум 4 turn'а (system + user + assistant + user),
типично 6-15. Каждый assistant turn = `Thought + <code>tool_call(...)</code>`.
Каждый user turn после assistant = `Observation: ...`. Последний assistant turn =
`<code>final_answer("...")</code>`.

Полная спецификация: [DATASET_FORMAT.md](DATASET_FORMAT.md).

---

## Как мы это собрали

### Выбор teacher-модели

Прогнали 4 кандидата через 20-trial бенчмарк (одинаковые items, одинаковые
few-shot, метрики format compliance):

| Модель | VRAM | 20-trial AVG | Catastrophic 0.0 | Решение |
|---|---:|---:|---:|---|
| **gemma4:31b** | 19 GB | **92.0** | **0%** | 🏆 WINNER |
| qwen3.6:27b | 17 GB | 72.7 | 15% | runner-up но 15% полного fail |
| qwen2.5-coder:32b | 23 GB | 84.8 (5-trial) | n/a | стабильный но медленнее |
| deepseek-coder-v2:16b-lite | 14 GB | 44.8 | n/a | контекст слишком короткий |

Полный отчёт с per-trial разбивкой: [meta/benchmark_results.md](meta/benchmark_results.md).

### Параметры distillation

```yaml
teacher: gemma4:31b
quant: default (Q4)
num_ctx: 16384            # 8K приводит к loop'ам / truncation
num_predict: 4000
temperature: 0.7
repeat_penalty: 1.15      # защита от бесконечных повторов
think: false              # критично для Qwen3-family (gemma4 не нужен но безвреден)
keep_alive: 24h
min_score: 84.8           # composite format-compliance threshold
```

### Composite scoring

Каждый сгенерированный trace оценивается по 8 метрикам:

| Метрика | Вес | Что меряет |
|---|---:|---|
| `json_parses` | 1.0 | Валидный JSON `{messages, meta}` |
| `has_messages` | 1.0 | ≥4 messages в array |
| `system_present` | 0.5 | system role есть |
| `assistant_has_thought_and_code` | 1.0 | каждый assistant turn = Thought + `<code>` |
| `tool_call_present` | 0.8 | хотя бы один из 5 tools вызван |
| `final_answer_present` | 1.0 | последний assistant = final_answer |
| `verification_before_final` | 0.7 | была проверка перед final_answer |
| `step_count_in_range` | 0.3 | 3-15 assistant turns |

Score 0-100. Threshold 84.8 = "format-clean enough для production training".

---

## Воспроизведение

```bash
# 1. Скачать teacher
ollama pull gemma4:31b

# 2. Distill любой HF датасет
python scripts/distill.py \
    --source path/to/raw.jsonl \
    --output runs/my_topic \
    --teacher gemma4:31b \
    --min-score 84.8

# 3. Использовать для SFT
cat data/own_anchors/train.jsonl \
    data/distilled_bash_pipes/data.jsonl \
    > combined.jsonl
# скормить в свой SFT trainer
```

Полный пошаговый гайд: [REPRODUCE.md](REPRODUCE.md).

---

## Лицензии

| Что | Лицензия | Примечания |
|---|---|---|
| Этот код (scripts/) | Apache 2.0 | можно forkить freely |
| `data/own_anchors/` | Apache 2.0 | наши hand-crafted трейсы |
| `data/distilled_*/` | MIT (inherited) | от Magicoder семейства |
| Teacher contributions | Apache 2.0 | gemma4 outputs free |

См. [LICENSE](LICENSE) и per-subset LICENSE файлы для деталей.

---

## Цитирование

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

- [x] Benchmark 4 teacher кандидатов → gemma4:31b winner (92.0/100)
- [x] Первый distilled subset: `bash_pipes` (Magicoder filter)
- [ ] Прогнать остальные Magicoder фильтры (~2710 items left)
- [ ] Distill из `commitpackft` (реальные git commits)
- [ ] Distill из курированных GitHub репо (tldr-pages, node-best-practices)
- [ ] Зеркало на HuggingFace Hub для `load_dataset` discovery
- [ ] Recipe configs для комбинирования subsets

---

## Issues / Contributions

Если найдёте трейс который явно сломан (неправильный tool name, hallucinated
observation, missing `final_answer`) — откройте issue с `meta.trace_hash` из
JSONL, мы регенерируем этот item.

Хотите добавить subset из своего домена (Kubernetes, Terraform, AWS)? PR с
filter-script и raw source description приветствуется.
