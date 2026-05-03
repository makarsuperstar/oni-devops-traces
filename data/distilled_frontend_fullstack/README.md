# distilled_frontend_fullstack

`310 agent-format traces` distilled from **hf_magicoder_frontend_fullstack_filter** via
`gemma4:31b` (Apache 2.0) using few-shot prompting with traces from our
fine-tuned DevOps agent oni:base-7.v2.

## Format

JSON Lines (`.jsonl`), one trace per line. Each trace is a multi-turn
agent dialog in the Thought→Code→Observation pattern.

See [DATASET_FORMAT.md](../../DATASET_FORMAT.md) in repo root for full
schema specification.

## Stats

| Metric | Value |
|---|---|
| Raw source items | 400 |
| Accepted (score >= 84.8) | 310 (77.5%) |
| Format compliance | 100% (filter threshold) |
| Distilled at | 2026-05-02T13:41:31 |

## Why this subset exists

Этот subset был distilled для расширения покрытия в категории frontend_fullstack.
См. CATALOG.md в корне репо для полного контекста зачем мы делаем
эти датасеты — основная цель это finetune локального DevOps агента
из Qwen3-14B.

## Provenance

- **Source dataset**: hf_magicoder_frontend_fullstack_filter
- **Filter / extraction**: see CATALOG.md in repo root
- **Teacher LLM**: gemma4:31b
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
ds = load_dataset("path/to/repo", data_dir="data/distilled_frontend_fullstack")
```

### As raw JSONL

```bash
wget https://raw.githubusercontent.com/<USER>/oni-devops-traces/main/data/distilled_frontend_fullstack/data.jsonl
```

### Combining with other subsets for finetune

Каждый файл `data.jsonl` уже совместим с нашим training pipeline.
Для finetune Qwen3-14B можно просто concat несколько subsets:

```bash
cat data/own_anchors/train.jsonl \
    data/distilled_frontend_fullstack/data.jsonl \
    data/distilled_<other>/data.jsonl \
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
- Acceptance rate 77.5% означает что 22.5% raw
  items были отброшены — обычно из-за format breaks (truncated JSON,
  missing final_answer, wrong tool names). См. `rejected/` в run
  директории на стороне разработчика для разбора.

## License

MIT License (inherited from source dataset hf_magicoder_frontend_fullstack_filter)

This subset is a derivative work distilled from hf_magicoder_frontend_fullstack_filter (MIT-licensed)
via gemma4:31b (Apache 2.0) using few-shot prompting with traces from
oni:base-7.v2 (Apache 2.0). All upstream licenses are MIT-compatible.

You are free to use, modify, and redistribute under MIT terms.


## Citation

```bibtex
@misc{oni-devops-traces-2026,
  title={Distilled DevOps Agent Traces from Magicoder via gemma4:31b},
  author={MakarSuperstar},
  year={2026},
  url={https://github.com/<USER>/oni-devops-traces}
}
```

---

*Этот README был сгенерирован автоматически из `seedbuilder/prepare_release.py`
на основе metadata конкретного distillation run.*
