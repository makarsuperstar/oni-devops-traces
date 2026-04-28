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

# Источники — ПОЛНЫЙ список. Хуже не будет иметь все.
# Порядок приоритета: DevOps-критические сначала, потом frontend / broad.
# Если сорс ещё не скачан с HF (нет data.jsonl) — chain SKIP'нет, мы потом
# докачаем и повторно запустим chain.
SOURCES=(
    # === DEVOPS CORE === ✓ done или running
    "hf_magicoder_bash_pipes_filter"           # 300  ✓ Linux CLI pipelines
    "hf_magicoder_django_filter"                # 300  ✓ Python backend
    "hf_magicoder_express_filter"               # 250  Node backend
    "hf_magicoder_microservices_filter"         # 250  distributed/queues
    "hf_magicoder_design_patterns_filter"       # 250  GoF patterns
    "hf_magicoder_solid_filter"                 # 250  refactoring
    # === DEVOPS GAPS ADDED 29 APR === метадата готова, нужно download_item.py
    "hf_magicoder_ssh_filter"                   # 300  🔥 SSH workflow (Stage 1 critical)
    "hf_magicoder_docker_advanced_filter"       # 300  🔥 Docker advanced patterns
    "hf_magicoder_kubernetes_filter"            # 200  🔥 K8s manifests + kubectl
    "hf_magicoder_ci_cd_specific_filter"        # 250  GitLab CI / GitHub Actions / Jenkins
    "hf_magicoder_postgres_advanced_filter"     # 250  PostgreSQL advanced
    # === FRONTEND (re-included) === хуже не будет
    "hf_magicoder_frontend_fullstack_filter"    # 400  JS/TS/HTML/CSS tooling
    "hf_magicoder_js_only_filter"               # 400  vanilla JS
    "hf_magicoder_ts_only_filter"               # 400  TypeScript
    # === MISC ===
    "hf_magicoder_oss_full"                     # 200  broad OSS code (Magicoder-OSS-75K)
    "hf_magicoder_eslint_filter"                # 10   trivial but включаем
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
