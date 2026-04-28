"""SeedBuilder benchmark runner — Phase 1 Step 3.

Запускается на боксе (где Ollama). Для каждой модели × каждого test item делает
конверсию и сохраняет результат в seedbuilder/benchmarks/<model_safe>/trial_NN.json.

Usage:
    python run_benchmark.py --model qwen2.5-coder:32b-instruct-q5_K_M
    python run_benchmark.py --model deepseek-coder-v2:16b-lite-instruct-q6_K --max 5

Без --model — прогоняет все из MODEL_CANDIDATES.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
REFERENCE = PROJECT_ROOT / "reference" / "few_shot_v1.jsonl"
TEST_SET = PROJECT_ROOT / "benchmarks" / "test_set" / "test_set_v1.jsonl"
OUT_DIR = PROJECT_ROOT / "benchmarks"

OLLAMA_URL = "http://localhost:11434"

MODEL_CANDIDATES = [
    "qwen2.5-coder:32b-instruct-q5_K_M",
    "qwen3:32b",
    "glm4:32b",
    "mistral-small:24b-instruct-2506-q6_K",
    "deepseek-coder-v2:16b-lite-instruct-q6_K",
]


def safe_name(model: str) -> str:
    return re.sub(r"[:/]", "_", model)


def build_prompt(few_shot: list[dict], raw_item: dict) -> str:
    examples_block = "\n\n".join(
        f"=== EXAMPLE {i+1} ===\n{json.dumps(t, ensure_ascii=False, indent=2)}"
        for i, t in enumerate(few_shot)
    )
    return f"""You are a converter. Given a raw <instruction, response> pair, output a JSON \
agent-trace in the EXACT format shown in the examples.

Format requirements (HARD):
- Output ONE JSON object: {{"messages": [...], "meta": {{...}}}}.
- "messages" is array of {{"role": "system"|"user"|"assistant", "content": "..."}}.
- system identical to the one in examples.
- assistant turns: "Thought: ...\\n<code>\\n  <python_with_one_tool_call>\\n</code>".
- user turns after assistant are "Observation: ..." with realistic command output.
- Last assistant turn calls final_answer(...).
- One file per write_file call (if scaffolding).
- Verify before final_answer (read_file/list_dir/curl/cat).

Tools: bash, read_file, write_file, list_dir, final_answer.

EXAMPLES (study format carefully):

{examples_block}

=== CONVERT THIS ===
instruction: {json.dumps(raw_item.get('instruction', ''), ensure_ascii=False)}
response_hint: {json.dumps(raw_item.get('response', '')[:1500], ensure_ascii=False)}

Output the JSON object only. No markdown fences, no commentary, no preamble.
"""


def call_ollama(model: str, prompt: str, timeout: int = 300) -> tuple[str, dict]:
    t0 = time.time()
    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,  # critical for Qwen3-family — иначе response пустой
            "keep_alive": "24h",  # держать модель в VRAM, не выгружать
            "options": {
                "temperature": 0.7,
                "num_predict": 4000,
                "num_ctx": 16384,    # 8K приводил к loop'ам и труncation; 16K с CPU offload работает
                "repeat_penalty": 1.15,  # защита от infinite loops которые видели на 8K
            },
        },
        timeout=timeout,
    )
    r.raise_for_status()
    j = r.json()
    return j.get("response", ""), {
        "wall_sec": round(time.time() - t0, 2),
        "eval_count": j.get("eval_count"),
        "prompt_eval_count": j.get("prompt_eval_count"),
        "eval_duration_ns": j.get("eval_duration"),
    }


def try_parse_trace(raw_response: str) -> tuple[bool, dict | None, str]:
    """Returns (json_parses, parsed_obj_or_none, error_msg)."""
    s = raw_response.strip()
    # strip common wrappers (markdown code fences)
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    # find first { ... last } heuristic
    if not s.startswith("{"):
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            s = m.group(0)
    try:
        obj = json.loads(s)
        return True, obj, ""
    except json.JSONDecodeError as e:
        return False, None, f"JSONDecodeError: {e}"
    except Exception as e:
        return False, None, f"{type(e).__name__}: {e}"


def validate_format(trace: dict) -> dict:
    """Score format compliance metrics. Returns dict of bool/int values."""
    metrics = {
        "json_parses": True,
        "has_messages": False,
        "has_meta": False,
        "system_present": False,
        "assistant_has_thought_and_code": False,
        "tool_call_present": False,
        "final_answer_present": False,
        "verification_before_final": False,
        "step_count": 0,
        "step_count_in_range": False,
    }
    msgs = trace.get("messages") or []
    metrics["has_messages"] = isinstance(msgs, list) and len(msgs) >= 4
    metrics["has_meta"] = "meta" in trace
    if not msgs:
        return metrics
    metrics["system_present"] = any(m.get("role") == "system" for m in msgs)
    a_turns = [m for m in msgs if m.get("role") == "assistant"]
    metrics["step_count"] = len(a_turns)
    metrics["step_count_in_range"] = 3 <= len(a_turns) <= 15
    if a_turns:
        all_have_pattern = all(
            "Thought" in m["content"] and "<code>" in m["content"]
            for m in a_turns[:-1]  # last is often pure final_answer
        )
        metrics["assistant_has_thought_and_code"] = all_have_pattern
    tools = ("bash(", "read_file(", "write_file(", "list_dir(", "final_answer(")
    metrics["tool_call_present"] = any(
        any(t in m["content"] for t in tools) for m in a_turns
    )
    last_assistant = a_turns[-1] if a_turns else None
    metrics["final_answer_present"] = bool(
        last_assistant and "final_answer(" in last_assistant["content"]
    )
    if last_assistant and len(a_turns) >= 2:
        prev_turns = a_turns[:-1]
        verify_tools = ("read_file(", "list_dir(", "bash(", "curl", "cat ")
        metrics["verification_before_final"] = any(
            any(t in m["content"] for t in verify_tools) for m in prev_turns
        )
    return metrics


def composite_score(metrics: dict) -> float:
    """0-100 score weighted per BENCHMARK.md."""
    weights = {
        "json_parses": 1.0,
        "has_messages": 1.0,
        "has_meta": 0.3,
        "system_present": 0.5,
        "assistant_has_thought_and_code": 1.0,
        "tool_call_present": 0.8,
        "final_answer_present": 1.0,
        "verification_before_final": 0.7,
        "step_count_in_range": 0.3,
    }
    total_weight = sum(weights.values())
    earned = sum(weights[k] * (1.0 if metrics.get(k) else 0.0) for k in weights)
    return round(100 * earned / total_weight, 1)


def run_one_model(model: str, max_items: int | None = None) -> dict:
    few_shot = [json.loads(l) for l in open(REFERENCE)]
    test_items = [json.loads(l) for l in open(TEST_SET)]
    if max_items:
        test_items = test_items[:max_items]

    out_dir = OUT_DIR / safe_name(model)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Benchmarking {model} on {len(test_items)} items ===")
    results = []
    for i, item in enumerate(test_items):
        tid = item.get("_test_id", f"t{i:04d}")
        prompt = build_prompt(few_shot, item)
        print(f"  [{i+1:02d}/{len(test_items)}] {tid}", end=" ", flush=True)
        try:
            raw_resp, stats = call_ollama(model, prompt)
        except Exception as e:
            print(f"FAIL: {e}")
            results.append({"test_id": tid, "error": str(e), "score": 0.0})
            continue
        ok, trace, parse_err = try_parse_trace(raw_resp)
        if ok:
            metrics = validate_format(trace)
            score = composite_score(metrics)
            metrics["json_parses"] = True
        else:
            metrics = {"json_parses": False, "parse_error": parse_err}
            score = 0.0
        result = {
            "test_id": tid,
            "score": score,
            "wall_sec": stats["wall_sec"],
            "metrics": metrics,
            "stats": stats,
            "raw_response_len": len(raw_resp),
        }
        results.append(result)
        # Save individual trial artifact
        trial_path = out_dir / f"trial_{tid}.json"
        trial_path.write_text(
            json.dumps(
                {
                    "model": model,
                    "test_id": tid,
                    "prompt_len": len(prompt),
                    "raw_response": raw_resp,
                    "parsed_trace": trace if ok else None,
                    "metrics": metrics,
                    "score": score,
                    "stats": stats,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"score={score:5.1f}  ({stats['wall_sec']}s)")

    avg = sum(r["score"] for r in results) / max(1, len(results))
    summary = {
        "model": model,
        "n_trials": len(results),
        "avg_score": round(avg, 1),
        "results": results,
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  >>> {model}: AVG SCORE {avg:.1f}/100 over {len(results)} trials")
    print(f"  >>> Summary: {summary_path}")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="single model to test; if omitted, run all candidates")
    ap.add_argument("--max", type=int, default=None, help="limit test items (for pilot)")
    args = ap.parse_args()

    models = [args.model] if args.model else MODEL_CANDIDATES
    summaries = []
    for m in models:
        try:
            s = run_one_model(m, args.max)
            summaries.append(s)
        except Exception as e:
            print(f"\n!!! Skipping {m}: {e}")
            summaries.append({"model": m, "error": str(e)})

    # Aggregate scoring
    print("\n\n=== AGGREGATE ===")
    print(f"{'MODEL':50s}  AVG_SCORE  TRIALS")
    for s in summaries:
        if "error" in s:
            print(f"  {s['model']:48s}  ERROR: {s['error'][:60]}")
            continue
        print(f"  {s['model']:48s}  {s['avg_score']:5.1f}     {s['n_trials']}")

    agg_path = OUT_DIR / "scores_v1.json"
    agg_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nAggregate saved: {agg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
