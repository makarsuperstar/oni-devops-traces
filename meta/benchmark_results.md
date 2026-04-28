# SeedBuilder Benchmark — WINNER

> Дата прогона: 2026-04-27 ночь / 2026-04-28 утро
> Версия test set: `test_set_v1.jsonl` (20 items)
> Версия few-shot reference: `few_shot_v1.jsonl` (5 traces from base-7/train.jsonl)

## 🏆 ПОБЕДИТЕЛЬ: `gemma4:31b`

**AVG composite score: 92.0/100** на 20-trial benchmark.

```
ollama pull gemma4:31b      # 19 GB on disk
ollama run gemma4:31b       # ~20 GB VRAM, fits 24GB GPU
```

### Почему именно она

| Critical metric | Значение |
|---|---|
| **Format compliance стабильность** | **0% катастрофических провалов** (vs 15% у qwen3.6) |
| **Perfect trials** | **55% trials на 100/100** (11 из 20) |
| **Min score** | 69.7 (никогда не уходит ниже) |
| **Speed** | 55-228 s/trial, avg ~90s |
| **VRAM** | 19 GB (свободно ~5 GB под KV cache) |
| **License** | Apache 2.0 |
| **Release** | Апрель 2026 (свежак) |

## Полная таблица результатов

```
МОДЕЛЬ                                 PILOT(5)    FULL(20)    100s     0.0s     SPEED      VRAM    ИТОГ
gemma4:31b                             95.1        92.0        11 (55%) 0 (0%)   55-228s    19 GB   🏆 WINNER
qwen3.6:27b                            91.8        72.7         6 (30%) 3 (15%)  22-122s    17 GB   2nd, но 15% катастроф
qwen2.5-coder:32b-instruct-q5_K_M      84.8        TBD         TBD      TBD      95-151s    23 GB   3rd (full pending)
deepseek-coder-v2:16b-lite-q6_K        44.8        FAIL        N/A      N/A      6-20s      14 GB   ❌ обрезает выводы
```

## Ключевые выводы

1. **5-trial pilot обманчив.** Qwen3.6 на пилоте дал 91.8 (3× perfect 100), но на 20 трейлах упал до 72.7 — выявились 3 trials где модель полностью ломала формат и выдавала 0.0. Pilot оптимально стратифицировать или сразу делать full-run.

2. **`think: false` критичен для Qwen3-family.** Без этого qwen3.6 по умолчанию весь num_predict тратит на thinking, response остаётся пустым. Параметр зашит в `run_benchmark.py`.

3. **DeepSeek 16B Lite слабоват** для нашей задачи — short context не вмещает 5 few-shot + длинный raw item, обрезает на середине (`has_messages: False`, генерит system+1turn вместо полной цепочки).

4. **Параметры размера vs качество в нашей категории:**
   - 16B (DeepSeek) → не справляется
   - 27B (qwen3.6) → справляется, но нестабильно
   - 31B (gemma4) → стабильный winner
   - 32B (qwen2.5-coder) → стабильный, но pilot 84.8 < gemma4 92.0

5. **Качество > новизны.** qwen3.6 свежее (22 апр 2026), но gemma4 (Apache 2.0, апр 2026) даёт лучший stable output на нашем формате.

## Per-trial breakdown — Gemma 4 31B

```
t0009  95.5    t0086 100.0   t0157  69.7
t0013 100.0    t0091  69.7   t0176 100.0
t0016 100.0    t0096 100.0   t0182 100.0
t0052  84.8    t0099  69.7   t0232  95.5
t0056  84.8    t0118 100.0   t0249 100.0
t0083 100.0    t0119  69.7   t0265 100.0
                 t0141 100.0
                 t0150 100.0

100.0: 11 trials (55%)
95.5:   2 trials (10%)
84.8:   2 trials (10%)
69.7:   5 trials (25%)
0.0:    0 trials  (0%)
```

## Что используем для distillation

```
TEACHER MODEL:    gemma4:31b
PROMPT_OPTIONS:   think: false (на всякий, безопасно для всех)
                  num_ctx: 16384
                  num_predict: 4000
                  temperature: 0.7
EXPECTED OUTPUT QUALITY:
  ~55% трейсов сразу 100% format-compliant (~ pristine)
  ~25% частично OK (один metric не дотягивает) — нужна коррекция
  ~10% средне (84.8) — пропускаем
  ~10% низковато (69.7) — отсеиваем при фильтре
  ~0% катастроф — экономим на retry logic
```

## Failed candidates — что НЕ берём

| Модель | Почему отброшена |
|---|---|
| `deepseek-coder-v2:16b-lite-q6_K` | Обрезает выводы, не вмещает 5 few-shot + raw item |
| `qwen3.6:27b` | 15% катастроф (полный provals формата, 0.0) — нужен retry или filter |
| `mistral-small-3.2:24b` | Не тестировали (отложено, gemma4 победила сильно) |
| `qwen3:32b-q5_K_M` | Не тестировали (вероятно похожая на qwen3.6 проблема) |
| `glm-4-32b-q5_K_M` | Не тестировали (по плану, но gemma4 закрывает вопрос) |

## Артефакты

- Per-trial JSON: `seedbuilder/benchmarks/gemma4_31b/trial_*.json`
- Summary: `seedbuilder/benchmarks/gemma4_31b/summary.json`
- Aggregate: `seedbuilder/benchmarks/scores_v1.json`
- Логи: `/tmp/full_*.log` на боксе

## Next step

→ `RUNBOOK_DISTILL.md` (создать) — overnight prod-run на 3010 hf_magicoder_* трейсов через `gemma4:31b`. ETA 2-3 ночи на 3090, $0.
