"""SeedBuilder — distillation runner.

Usage:
    python distill.py --source library/hf_magicoder_bash_pipes_filter/data/data.jsonl \\
                      --output runs/<lib_id>_<ts>/ \\
                      --teacher gemma4:31b \\
                      --min-score 84.8 \\
                      --resume

Берёт raw items из source, прогоняет через teacher с few-shot из
seedbuilder/reference/few_shot_v1.jsonl, валидирует format compliance,
сохраняет принятые трейсы (score >= min-score) в output/data.jsonl.

Resume support: если output/state.json существует — пропускаем уже обработанные
индексы. Прервать и запустить заново — продолжит с того же места.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# import shared utilities from run_benchmark
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_benchmark import (
    build_prompt,
    call_ollama,
    composite_score,
    try_parse_trace,
    validate_format,
    REFERENCE,
)

DEFAULT_TEACHER = "gemma4:31b"
DEFAULT_MIN_SCORE = 84.8


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Path to raw JSONL (instruction/response items)")
    ap.add_argument("--output", required=True, help="Output directory for runs/<lib_id>_<ts>/")
    ap.add_argument("--teacher", default=DEFAULT_TEACHER)
    ap.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    ap.add_argument("--max-items", type=int, default=None, help="Limit for testing")
    ap.add_argument("--resume", action="store_true", help="Skip already processed indexes")
    ap.add_argument("--reference", default=str(REFERENCE), help="Few-shot reference jsonl")
    args = ap.parse_args()

    src = Path(args.source)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir = out_dir / "rejected"
    rejected_dir.mkdir(exist_ok=True)
    state_path = out_dir / "state.json"
    accepted_path = out_dir / "data.jsonl"

    # Load source
    raw_items = [json.loads(l) for l in open(src)]
    if args.max_items:
        raw_items = raw_items[: args.max_items]
    print(f"Source: {src} ({len(raw_items)} items)")

    # Load reference
    few_shot = [json.loads(l) for l in open(args.reference)]
    print(f"Reference: {args.reference} ({len(few_shot)} few-shot examples)")

    # Resume state
    state = {"processed_idx": [], "accepted": 0, "rejected": 0}
    if args.resume and state_path.exists():
        state = json.loads(state_path.read_text())
        print(f"Resuming: {len(state['processed_idx'])} processed, "
              f"{state['accepted']} accepted, {state['rejected']} rejected")
    processed = set(state["processed_idx"])

    # Open accept file in append mode
    accept_f = open(accepted_path, "a", encoding="utf-8")

    print(f"\nTeacher: {args.teacher}")
    print(f"Min score: {args.min_score}")
    print(f"Output: {out_dir}")
    print(f"\n=== Distilling ===")

    t0 = time.time()
    for idx, item in enumerate(raw_items):
        if idx in processed:
            continue
        prompt = build_prompt(few_shot, item)
        try:
            raw_resp, stats = call_ollama(args.teacher, prompt, timeout=600)
        except Exception as e:
            print(f"  [{idx:04d}] CALL_FAIL: {e}")
            state["processed_idx"].append(idx)
            state_path.write_text(json.dumps(state, ensure_ascii=False))
            continue

        ok, trace, parse_err = try_parse_trace(raw_resp)
        if ok:
            metrics = validate_format(trace)
            metrics["json_parses"] = True
            score = composite_score(metrics)
        else:
            metrics = {"json_parses": False, "parse_error": parse_err}
            score = 0.0

        accepted = ok and score >= args.min_score
        verdict = "ACCEPT" if accepted else "REJECT"

        if accepted:
            # Add provenance meta and write to accepted
            if "meta" not in trace or not isinstance(trace.get("meta"), dict):
                trace["meta"] = {}
            trace["meta"].update({
                "source": f"distilled_via_{args.teacher.replace(':', '_')}",
                "source_idx": idx,
                "teacher_score": score,
                "distill_ts": datetime.now().isoformat(timespec="seconds"),
            })
            accept_f.write(json.dumps(trace, ensure_ascii=False) + "\n")
            accept_f.flush()
            state["accepted"] += 1
        else:
            (rejected_dir / f"reject_{idx:04d}.json").write_text(
                json.dumps({
                    "source_idx": idx,
                    "raw_item": item,
                    "raw_response": raw_resp,
                    "metrics": metrics,
                    "score": score,
                    "reason": parse_err if not ok else f"score {score} < {args.min_score}",
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            state["rejected"] += 1

        state["processed_idx"].append(idx)
        state_path.write_text(json.dumps(state, ensure_ascii=False))

        elapsed = time.time() - t0
        rate = (idx + 1 - len(processed)) / max(1, elapsed) * 60  # items/min since resume
        eta_min = (len(raw_items) - idx - 1) / max(0.01, rate)
        print(f"  [{idx:04d}/{len(raw_items)}] {verdict} score={score:5.1f} "
              f"({stats['wall_sec']:.0f}s)  rate={rate:.1f}/min  ETA={eta_min:.0f}min")

    accept_f.close()

    # Final summary + lib_item metadata.yaml
    src_name = src.parent.parent.name  # library/<lib_id>/data/data.jsonl → <lib_id>
    lib_id = f"distilled_{src_name}"
    metadata = {
        "id": lib_id,
        "name": f"Distilled from {src_name} via {args.teacher}",
        "type": "agent_traces",
        "source": {
            "kind": "distilled",
            "source_lib": src_name,
            "teacher": args.teacher,
            "min_score": args.min_score,
            "few_shot_reference": args.reference,
            "distilled_ts": datetime.now().isoformat(timespec="seconds"),
        },
        "stats": {
            "raw_items": len(raw_items),
            "accepted": state["accepted"],
            "rejected": state["rejected"],
            "acceptance_rate": round(state["accepted"] / max(1, len(raw_items)), 3),
        },
    }
    (out_dir / "metadata.yaml").write_text(
        "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in metadata.items()),
        encoding="utf-8",
    )

    # Self-describing README inside the run dir — чтобы через месяц
    # зайдя в эту папку было сразу понятно что это, откуда, кто сделал,
    # как использовать дальше.
    readme_lines = [
        f"# Distilled dataset run — {lib_id}",
        f"",
        f"Сгенерировано: {datetime.now().isoformat(timespec='seconds')}",
        f"",
        f"## Что это",
        f"",
        f"`{state['accepted']}` agent-format трейсов в нашем JSONL-формате,",
        f"конвертированы из raw `instruction → response` пар через teacher-LLM.",
        f"Готово к подмешиванию в `experiments/base_3_dataset/library/{lib_id}/`",
        f"и далее в recipe для тренировки следующего base.",
        f"",
        f"## Конфигурация",
        f"",
        f"- **Source:** `{src}` ({len(raw_items)} raw items)",
        f"- **Teacher:** `{args.teacher}`",
        f"- **Few-shot reference:** `{args.reference}` ({len(few_shot)} examples)",
        f"- **Min score threshold:** {args.min_score}",
        f"",
        f"## Результат",
        f"",
        f"- **Accepted:** {state['accepted']} / {len(raw_items)} ({100*metadata['stats']['acceptance_rate']:.1f}%)",
        f"- **Rejected:** {state['rejected']} (см. `rejected/` для разбора)",
        f"",
        f"## Файлы",
        f"",
        f"```",
        f"{out_dir.name}/",
        f"├── data.jsonl          # принятые трейсы (готовые к обучению)",
        f"├── metadata.yaml       # lib_item meta для подмешивания в library/",
        f"├── state.json          # состояние для resume",
        f"├── README.md           # этот файл",
        f"└── rejected/           # отброшенные с причинами (для отладки)",
        f"```",
        f"",
        f"## Как использовать дальше",
        f"",
        f"```bash",
        f"# 1. Создать новый lib_item",
        f"LIB_DIR=experiments/base_3_dataset/library/{lib_id}",
        f"mkdir -p $LIB_DIR/data",
        f"cp data.jsonl $LIB_DIR/data/data.jsonl",
        f"cp metadata.yaml $LIB_DIR/metadata.yaml",
        f"",
        f"# 2. Sync на бокс",
        f"rsync -av $LIB_DIR/ oni@192.168.31.135:/home/oni/oni/$LIB_DIR/",
        f"",
        f"# 3. В recipe нового build добавить stage:",
        f"#",
        f"#   - id: NN_distilled_<topic>",
        f"#     items:",
        f"#     - lib_id: {lib_id}",
        f"#       paraphrase: 1   # уже разнообразный, paraphrase не нужен",
        f"```",
        f"",
        f"## Воспроизведение",
        f"",
        f"```bash",
        f"python seedbuilder/distill.py \\",
        f"    --source {src} \\",
        f"    --output {out_dir} \\",
        f"    --teacher {args.teacher} \\",
        f"    --min-score {args.min_score} \\",
        f"    --reference {args.reference}",
        f"```",
        f"",
        f"## Лицензия",
        f"",
        f"Наследует ограничения source-датасета и teacher-модели.",
        f"Источник: {src.parent.parent.name} → see CATALOG.md SOURCE секция.",
        f"Teacher gemma4 — Apache 2.0.",
    ]
    (out_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")

    print(f"\n=== DONE ===")
    print(f"Accepted: {state['accepted']}/{len(raw_items)} ({100*metadata['stats']['acceptance_rate']:.1f}%)")
    print(f"Rejected: {state['rejected']}")
    print(f"Output:   {out_dir}/data.jsonl")
    print(f"Meta:     {out_dir}/metadata.yaml")
    print(f"Readme:   {out_dir}/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
