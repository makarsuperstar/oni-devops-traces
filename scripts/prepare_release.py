"""SeedBuilder — упаковка distilled run в release-формат для GitHub.

Берёт `seedbuilder/runs/<run_id>/`, генерит самодостаточный release-пакет
в `<repo>/data/distilled_<topic>/` с README + LICENSE + data.jsonl, готовый
к `git add` и `git commit`.

Usage:
    python prepare_release.py \\
        --run /path/to/seedbuilder/runs/<run_id> \\
        --repo /path/to/oni-devops-traces \\
        --topic bash_pipes
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# License heredity — какая лицензия для distilled output на основе source
SOURCE_LICENSES = {
    # Magicoder family (MIT)
    "Magicoder-Evol-Instruct-110K": "MIT",
    "Magicoder-OSS-Instruct-75K": "MIT",
    # CommitPack
    "commitpackft": "MIT",  # bigcode releases as MIT
    # CanItEdit
    "CanItEdit": "MIT",
    # Default
    "_default": "MIT",
}

# Per-topic rationale templates — почему этот распилл вообще нужен
RATIONALE = {
    "bash_pipes": """
Этот subset закрывает gap который мы наблюдали в Stage 1 SSH бенчмарках:
fine-tuned модель устойчиво справляется с одной командой, но плохо строит
**пайплайны** типа `grep | awk | sort | uniq -c | sort -rn | head -10`.
В исходной seeds.yaml только 6 SSH seeds × paraphrase → ~75 трейсов на
этот класс — мало для надёжного выучивания паттерна.

Source — Magicoder-Evol-Instruct-110K, отфильтровано по ключевым словам
(grep, awk, sed, find, xargs, sort, uniq, head, tail, cut, tr, jq, wc, ps,
lsof, netstat, ss). 300 примеров с реальными bash-pipeline задачами.
""",
    "django": """
Этот subset усиливает Django/Flask/FastAPI scaffold-навыки модели —
именно тот класс задач где наш чемпион проседал на Phase 3 L1.1
(0/11 в base-6.v2, восстановилось до 8+/11 в base-7).

Source — Magicoder-Evol с фильтром по Django ecosystem keywords
(models.py, views, serializers, urls.py, settings.py, INSTALLED_APPS,
django.db, REST framework и т.д.).
""",
    "express": """
Express.js patterns: routing, middleware, validation, error handling.
Расширяет наши seeds_django_flask_fastapi на Node.js backend, где у
oni-агента покрытие было слабее (10 seeds на весь JS/Vue/React/Next/RN).

Source — Magicoder-Evol filter на Express keywords (router, middleware,
req.body, res.status, app.use, etc).
""",
    "microservices": """
Microservices, message queues, service discovery, distributed-systems
patterns. Покрывает domain который у нас вообще отсутствует в seeds.yaml
(Kubernetes/cloud — 0 seeds), даёт базу для будущих DevOps задач.

Source — Magicoder-Evol filter на microservices keywords.
""",
    "design_patterns": """
GoF design patterns в коде. Усиливает обоснованность архитектурных
решений модели в задачах вроде «спроектируй subscriber/publisher на
WebSocket» или «реализуй retry с backoff».

Source — Magicoder-Evol filter на pattern names (Singleton, Factory,
Observer, Strategy, etc).
""",
    "solid": """
SOLID principles + clean code refactoring patterns. Учит модель не
просто писать рабочий код, но и **улучшать** существующий — рефакторить,
разделять ответственности, уменьшать coupling.

Source — Magicoder-Evol filter на SOLID/refactoring keywords.
""",
    "frontend": """
JS/TS/Node fullstack: HTML/CSS, tooling (eslint/prettier/jest/vite/webpack),
JSDoc, npm/nvm. Расширяет frontend coverage где у нас было всего 10 seeds
на весь Vue/React/Next/RN ecosystem.

Source — Magicoder-Evol broad filter на frontend keywords.
""",
    "js_only": """
Vanilla JavaScript — function/var/const, classes, async/await, promises,
closures, prototypes — БЕЗ TypeScript/JSX. Помогает модели различать
plain JS и TypeScript-флейворы.

Source — Magicoder-Evol filter на JS-specific keywords.
""",
    "ts_only": """
TypeScript-specific code: interfaces, types, generics, enums,
declarations, tsconfig, .ts/.tsx files. Балансирует js_only subset.

Source — Magicoder-Evol filter на TS-specific keywords.
""",
    "_default": """
Этот subset был distilled для расширения покрытия в категории {topic}.
См. CATALOG.md в корне репо для полного контекста зачем мы делаем
эти датасеты — основная цель это finetune локального DevOps агента
из Qwen3-14B.
""",
}


def safe_topic(topic: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", topic.lower()).strip("_")


def license_for_source(source_lib: str) -> str:
    for key in SOURCE_LICENSES:
        if key in source_lib:
            return SOURCE_LICENSES[key]
    return SOURCE_LICENSES["_default"]


def license_text(license_name: str, source_name: str) -> str:
    if license_name == "MIT":
        return f"""MIT License (inherited from source dataset {source_name})

This subset is a derivative work distilled from {source_name} (MIT-licensed)
via gemma4:31b (Apache 2.0) using few-shot prompting with traces from
oni:base-7.v2 (Apache 2.0). All upstream licenses are MIT-compatible.

You are free to use, modify, and redistribute under MIT terms.
"""
    return f"License: {license_name} (verify upstream license compatibility before use)"


def build_release_readme(
    topic: str,
    n_traces: int,
    metadata: dict,
    rationale: str,
    license_name: str,
    source_name: str,
) -> str:
    accept_pct = round(100 * metadata.get("stats", {}).get("acceptance_rate", 0), 1)
    raw_count = metadata.get("stats", {}).get("raw_items", "?")
    accepted = metadata.get("stats", {}).get("accepted", n_traces)
    teacher = metadata.get("source", {}).get("teacher", "gemma4:31b")
    distilled_ts = metadata.get("source", {}).get("distilled_ts", "")
    return f"""# distilled_{topic}

`{n_traces} agent-format traces` distilled from **{source_name}** via
`{teacher}` (Apache 2.0) using few-shot prompting with traces from our
fine-tuned DevOps agent oni:base-7.v2.

## Format

JSON Lines (`.jsonl`), one trace per line. Each trace is a multi-turn
agent dialog in the Thought→Code→Observation pattern.

See [DATASET_FORMAT.md](../../DATASET_FORMAT.md) in repo root for full
schema specification.

## Stats

| Metric | Value |
|---|---|
| Raw source items | {raw_count} |
| Accepted (score >= 84.8) | {accepted} ({accept_pct}%) |
| Format compliance | 100% (filter threshold) |
| Distilled at | {distilled_ts} |

## Why this subset exists

{rationale.strip()}

## Provenance

- **Source dataset**: {source_name}
- **Filter / extraction**: see CATALOG.md in repo root
- **Teacher LLM**: {teacher}
- **Few-shot reference**: 5 anchor traces from oni:base-7.v2 (see `meta/few_shot_reference.jsonl`)
- **Quality threshold**: composite format-compliance score >= 84.8/100
  (json_parses, has_messages, system_present, tool_call_present,
  final_answer_present, verification_before_final, step_count_in_range)

The teacher was selected from a 4-candidate benchmark — see
[meta/benchmark_results.md](../../meta/benchmark_results.md) for the
full ranking that put gemma4:31b at 92.0/100 vs runners-up
(qwen3.6:27b 72.7, qwen2.5-coder:32b 84.8 pilot, deepseek-coder-v2:16b FAIL).

## Usage

### As HuggingFace dataset (когда замиррорим на HF)

```python
from datasets import load_dataset
ds = load_dataset("path/to/repo", data_dir="data/distilled_{topic}")
```

### As raw JSONL

```bash
wget https://raw.githubusercontent.com/<USER>/oni-devops-traces/main/data/distilled_{topic}/data.jsonl
```

### Combining with other subsets for finetune

Каждый файл `data.jsonl` уже совместим с нашим training pipeline.
Для finetune Qwen3-14B можно просто concat несколько subsets:

```bash
cat data/own_anchors/train.jsonl \\
    data/distilled_{topic}/data.jsonl \\
    data/distilled_<other>/data.jsonl \\
    > combined_train.jsonl
```

См. [REPRODUCE.md](../../REPRODUCE.md) для полного training workflow.

## Limitations / known gaps

- Teacher gemma4:31b был выбран по format compliance, не по domain expertise.
  В сложных domain-specific задачах могут быть subtle ошибки в командах
  (например, неправильный флаг nginx или неточное имя env var).
- Observations в трейсах **сгенерированы** teacher'ом, не реальные
  command outputs. Для большинства команд они правдоподобны, но иногда
  модель может выдумать формат вывода.
- Acceptance rate {accept_pct}% означает что {100 - accept_pct:.1f}% raw
  items были отброшены — обычно из-за format breaks (truncated JSON,
  missing final_answer, wrong tool names). См. `rejected/` в run
  директории на стороне разработчика для разбора.

## License

{license_text(license_name, source_name)}

## Citation

```bibtex
@misc{{oni-devops-traces-{datetime.now().year},
  title={{Distilled DevOps Agent Traces from Magicoder via gemma4:31b}},
  author={{MakarSuperstar}},
  year={{{datetime.now().year}}},
  url={{https://github.com/<USER>/oni-devops-traces}}
}}
```

---

*Этот README был сгенерирован автоматически из `seedbuilder/prepare_release.py`
на основе metadata конкретного distillation run.*
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="Path to seedbuilder/runs/<run_id>/")
    ap.add_argument("--repo", required=True, help="Path to oni-devops-traces repo on disk")
    ap.add_argument("--topic", required=True, help="Topic shortname (e.g. bash_pipes, django)")
    args = ap.parse_args()

    run = Path(args.run)
    repo = Path(args.repo)
    if not (run / "data.jsonl").exists():
        print(f"ERROR: {run}/data.jsonl not found")
        return 1
    if not (run / "metadata.yaml").exists():
        print(f"ERROR: {run}/metadata.yaml not found")
        return 1

    # Load metadata (it's actually JSON inside .yaml because we wrote with json.dumps)
    meta_text = (run / "metadata.yaml").read_text()
    meta = {}
    for line in meta_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            try:
                meta[k.strip()] = json.loads(v.strip())
            except json.JSONDecodeError:
                meta[k.strip()] = v.strip()

    source_lib = meta.get("source", {}).get("source_lib", "")
    source_name = source_lib  # display name; could be improved
    license_name = license_for_source(source_lib)

    topic_safe = safe_topic(args.topic)
    out_dir = repo / "data" / f"distilled_{topic_safe}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy data.jsonl
    n_traces = sum(1 for _ in open(run / "data.jsonl"))
    shutil.copy2(run / "data.jsonl", out_dir / "data.jsonl")
    print(f"Copied {n_traces} traces → {out_dir}/data.jsonl")

    # 2. README.md (auto-generated)
    rationale = RATIONALE.get(topic_safe, RATIONALE["_default"]).format(topic=topic_safe)
    readme = build_release_readme(
        topic=topic_safe,
        n_traces=n_traces,
        metadata=meta,
        rationale=rationale,
        license_name=license_name,
        source_name=source_name,
    )
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    print(f"Wrote README.md (license={license_name})")

    # 3. LICENSE
    (out_dir / "LICENSE").write_text(license_text(license_name, source_name), encoding="utf-8")
    print(f"Wrote LICENSE ({license_name})")

    # 4. Print git commands for the user
    print(f"\n=== READY ===")
    print(f"Subset path: {out_dir}")
    print(f"Files: data.jsonl ({n_traces} traces), README.md, LICENSE")
    print(f"\nNext steps:")
    print(f"  cd {repo}")
    print(f"  git add data/distilled_{topic_safe}/")
    print(f"  git commit -m 'Add distilled_{topic_safe} ({n_traces} traces from {source_name} via {meta.get(\"source\", {}).get(\"teacher\", \"gemma4\")})'")
    print(f"  git push origin main")
    print(f"\nThen update CATALOG.md in repo root with the new entry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
