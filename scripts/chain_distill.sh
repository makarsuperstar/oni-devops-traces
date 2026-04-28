#!/bin/bash
# SeedBuilder chain — последовательно прогоняет все hf_magicoder_* источники
# через distill.py. Запускается ПОСЛЕ того как один prod-run закончился.
# Каждый следующий source стартует автоматически когда предыдущий завершился.
#
# Usage (на боксе):
#   nohup bash chain_distill.sh > /tmp/distill_chain.log 2>&1 < /dev/null & disown
#
# Resume support: если упал/перезапустили — текущий source распознаётся по
# последнему run dir, продолжает через --resume.

set -e

cd /home/oni/oni

# Источники — DevOps focus only.
# Порядок: от точно DevOps к DevOps-смежному. Идём ПОСТЕПЕННО,
# по одному за ночь, не торопимся.
#
# Frontend-only (js_only, ts_only, frontend_fullstack), oss_full,
# eslint_filter — НЕ ДЛЯ нашего DevOps-агента. Закомментированы.
# При необходимости в будущем — раскомментировать.
SOURCES=(
    "hf_magicoder_bash_pipes_filter"           # 300  ★ Linux CLI пайплайны (running now)
    "hf_magicoder_django_filter"                # 300  ★ Python backend deployment context
    "hf_magicoder_express_filter"               # 250  ★ Node backend deployment context
    "hf_magicoder_microservices_filter"         # 250  ★ distributed systems, queues, service discovery
    "hf_magicoder_design_patterns_filter"       # 250  · architectural reasoning (DevOps-adjacent)
    "hf_magicoder_solid_filter"                 # 250  · refactoring/code review (DevOps-adjacent)
    # Skipped — pure frontend, не относится к DevOps-агенту:
    # "hf_magicoder_frontend_fullstack_filter"    # 400  не наш домен
    # "hf_magicoder_js_only_filter"               # 400  не наш домен
    # "hf_magicoder_ts_only_filter"               # 400  не наш домен
    # "hf_magicoder_oss_full"                     # 200  слишком broad, низкое signal-to-noise
    # "hf_magicoder_eslint_filter"                # 10   trivial объём
)

VENV=/home/oni/oni/.venv/bin/python
TEACHER="gemma4:31b"
MIN_SCORE=84.8
LIB_BASE="experiments/base_3_dataset/library"
RUNS="seedbuilder/runs"

echo "[$(date)] === CHAIN DISTILL START ==="

for src in "${SOURCES[@]}"; do
    SRC_FILE="${LIB_BASE}/${src}/data/data.jsonl"

    if [ ! -f "$SRC_FILE" ]; then
        echo "[$(date)] SKIP $src (no source file: $SRC_FILE)"
        continue
    fi

    # SHORT name = source без префикса hf_magicoder_ и без суффикса _filter
    SHORT="${src##hf_magicoder_}"
    SHORT="${SHORT%_filter}"

    # Определить existing run dir для этого source — ищем по SHORT
    EXISTING=$(ls -dt ${RUNS}/${SHORT}_prod_* 2>/dev/null | head -1 || true)

    if [ -n "$EXISTING" ] && [ -f "$EXISTING/state.json" ]; then
        # Проверим — не закончен ли уже (есть README.md = pипelнap done)
        if [ -f "$EXISTING/README.md" ]; then
            echo "[$(date)] DONE already $src → $EXISTING (skip)"
            continue
        fi
        OUT="$EXISTING"
        echo "[$(date)] RESUME $src → $OUT"
    else
        TS=$(date +%Y-%m-%d_%H-%M)
        OUT="${RUNS}/${SHORT}_prod_${TS}"
        echo "[$(date)] START  $src → $OUT"
    fi

    # Дождаться freе GPU (другой distill.py не должен крутиться)
    while pgrep -f 'distill.py' > /dev/null; do
        sleep 30
    done

    # Запустить distill для текущего source
    $VENV seedbuilder/distill.py \
        --source "$SRC_FILE" \
        --output "$OUT" \
        --teacher "$TEACHER" \
        --min-score "$MIN_SCORE" \
        --resume \
        2>&1 | tee -a /tmp/distill_chain_${SHORT}.log

    if [ $? -ne 0 ]; then
        echo "[$(date)] FAIL $src — abort chain (manual intervention)"
        exit 2
    fi

    # Краткая статистика
    if [ -f "$OUT/state.json" ]; then
        $VENV -c "
import json
d = json.load(open('$OUT/state.json'))
n = len(d['processed_idx']); a = d['accepted']; r = d['rejected']
print(f'[$(date)] $src DONE: processed={n}, accepted={a} ({100*a/max(n,1):.1f}%), rejected={r}')
"
    fi
done

echo "[$(date)] === CHAIN DISTILL COMPLETE ==="
