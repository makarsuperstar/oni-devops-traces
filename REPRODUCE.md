# Reproduce — как собрать датасет с нуля

## Минимальный setup

- **GPU:** один с 24 GB VRAM (RTX 3090 / 4090 / A6000 etc) — для teacher
- **Disk:** 100 GB free для моделей + raw data + распиленных трейсов
- **OS:** Linux (Ubuntu 22.04 tested)
- **Python:** 3.10+

```bash
# 1. Ollama
curl -fsSL https://ollama.com/install.sh | sh
systemctl --user start ollama

# 2. Teacher model
ollama pull gemma4:31b   # ~19 GB on disk, fits in 24 GB VRAM at Q4_0 default

# 3. Python deps
pip install requests pyyaml pydantic tqdm
```

## Получение source data

Любая HuggingFace dataset с полями `instruction` + `response` подойдёт.
Минимально стартовый источник — Magicoder семейство:

```python
from datasets import load_dataset

ds = load_dataset("ise-uiuc/Magicoder-Evol-Instruct-110K")
# Filter under 110K to ~300 items by topic keywords
keywords = ["grep", "awk", "sed", "find", "xargs", "sort", "uniq",
            "head", "tail", "cut", "tr", "jq", "wc", "ps", "lsof", "netstat"]
filtered = [
    item for item in ds["train"]
    if any(kw in item["instruction"].lower() for kw in keywords)
]
# Save first 300 to JSONL
import json
with open("raw_bash_pipes.jsonl", "w") as f:
    for item in filtered[:300]:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
```

## Distill через teacher

```bash
python scripts/distill.py \
    --source raw_bash_pipes.jsonl \
    --output runs/bash_pipes_$(date +%Y-%m-%d_%H-%M) \
    --teacher gemma4:31b \
    --min-score 84.8
```

ETA: ~90 sec/item × 300 = 7-8 hours overnight on RTX 3090.

Resume support: если crashed — запустить ту же команду с `--resume`,
продолжит с последнего обработанного индекса.

Output:
- `runs/<id>/data.jsonl` — accepted traces (one per line)
- `runs/<id>/metadata.yaml` — lib_item meta
- `runs/<id>/state.json` — для resume
- `runs/<id>/rejected/` — отброшенные с причинами
- `runs/<id>/README.md` — self-describing report

## Использовать для finetune

Пакет совместим с любым SFT trainer'ом ожидающим OpenAI chat format:

### Unsloth (Qwen3-14B на одной 3090)

```python
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    "Qwen/Qwen3-14B",
    max_seq_length=4096,
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(model, r=64, lora_alpha=64)

# Load combined trace data
import json
def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]

train_data = load_jsonl("data/own_anchors/train.jsonl") + \
             load_jsonl("data/distilled_bash_pipes/data.jsonl") + \
             load_jsonl("data/distilled_django/data.jsonl")

# Apply chat template
def format_trace(t):
    return tokenizer.apply_chat_template(
        t["messages"], tokenize=False, add_generation_prompt=False
    )

# Train... (see Unsloth docs for full SFT loop)
```

### TRL (HF transformers)

```python
from datasets import Dataset
from trl import SFTTrainer

ds = Dataset.from_list([
    {"messages": t["messages"]}
    for path in ["data/own_anchors/train.jsonl", "data/distilled_bash_pipes/data.jsonl"]
    for t in (json.loads(l) for l in open(path))
])

trainer = SFTTrainer(
    model="Qwen/Qwen3-14B",
    train_dataset=ds,
    # ...
)
trainer.train()
```

## Deploy в Ollama (для inference)

После SFT + merge:

```dockerfile
# Modelfile
FROM ./model.gguf

TEMPLATE """{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
<think>

</think>

"""
# CRITICAL для Qwen3 семейства — пред-закрытый <think></think>
# иначе модель циклится в thinking-mode

SYSTEM """You are a DevOps agent. ..."""
PARAMETER stop "<|im_end|>"
```

```bash
ollama create my-devops-agent -f Modelfile
ollama run my-devops-agent
```

## Бенчмарк своей модели

См. `scripts/run_benchmark.py` — берёт 20 stratified test items + 5
few-shot, прогоняет любую модель, выдаёт composite score.

```bash
python scripts/run_benchmark.py --model my-devops-agent --max 20
```

Pass criteria: composite >= 60/100 (acceptable),
>= 80 (good teacher quality).

## Полный pipeline в одну команду

```bash
# Distill all 12 Magicoder filters in sequence (3-4 nights)
for src in bash_pipes django express microservices design_patterns \
           solid frontend js_only ts_only eslint oss_full; do
    python scripts/distill.py \
        --source raw_${src}.jsonl \
        --output runs/${src}_$(date +%Y-%m-%d) \
        --teacher gemma4:31b \
        --min-score 84.8 \
        --resume
done
```

## Лицензия derived dataset

Distillation создаёт derivative work. Лицензия выходного датасета =
наиболее ограничительная из:
1. Source dataset license (например, Magicoder = MIT)
2. Teacher model license (gemma4 = Apache 2.0 — output free)
3. Few-shot reference license (наш проект — Apache 2.0)

MIT + Apache 2.0 совместимы для derivative — output можно публиковать
под MIT (более ограничительная) или Apache 2.0 (с attribution к MIT
sources). На практике: сохраняем MIT для conservativeness.

## Воспроизведение нашего бенчмарка teacher'а

```bash
# 1. Pull all 4 candidates (110+ GB total)
for m in qwen2.5-coder:32b-instruct-q5_K_M qwen3.6:27b gemma4:31b \
         deepseek-coder-v2:16b-lite-instruct-q6_K; do
    ollama pull $m
done

# 2. Run benchmark on each
for m in ...; do
    python scripts/run_benchmark.py --model $m
done

# 3. Aggregate scores
cat seedbuilder/benchmarks/scores_v1.json
# Победитель должен быть gemma4:31b (~92.0/100)
```

## Common issues

| Проблема | Решение |
|---|---|
| Qwen3-family выдаёт пустой response | Установлен `think: False` в API call |
| Ollama выгружает model между inference | Set `OLLAMA_KEEP_ALIVE=24h` env |
| GPU OOM на втором прогоне | Перезапустить `ollama serve` (старая модель не выгрузилась) |
| Distill упал ночью | Запустить ту же команду с `--resume` |
| Acceptance rate < 30% на конкретном source | Source плохо подходит — переделать промпт или взять другой source |
