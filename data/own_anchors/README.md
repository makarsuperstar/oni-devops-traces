# own_anchors — golden hand-crafted traces

**1,867 multi-turn agent traces** in our exact JSONL format. This is the
training set of our current champion model (`oni:base-7.v2`, Stage 1 SSH 15/22,
realworld 4/5 honest).

## What's inside

Multi-turn agent traces covering 19 DevOps domains:

- **Agent protocol** — Thought→Code→Observation cycle, tool usage anchors
- **Honest failure / verification** — don't lie about success, verify before final_answer
- **Multi-file scaffold** — Vue/React/Next/Django/nginx/celery/grafana/CI scaffolds (1 file = 1 step)
- **SSH workflow** — ed25519 keygen, port-forward, scp, diagnose
- **Git** — clone/branch/rebase/conflict-resolve/squash
- **Docker** — build/run/exec/networks/volumes/healthcheck
- **nginx + systemd + supervisord** — reverse proxy, hardening, log rotate
- **CI/CD** — GitLab CI, GitHub Actions, GHCR push, deploy via SSH
- **Python web** — Django/Flask/FastAPI scaffold + routes/serializers/views
- **Celery + Redis** — task decorator, retry, beat, pubsub, canvas
- **Databases** — Postgres/MongoDB/SQLite operations
- **JS/TS frontend** — Vue3/React18/Next14/RN
- **WebSocket / WebRTC / Jitsi** — realtime communication
- **Logs/monitoring** — tail/grep/journalctl/promql
- **Playwright/CDP** — browser automation
- **Code review** — JSDoc/types/refactoring

Full breakdown by domain in [../../CATALOG.md](../../CATALOG.md).

## Why "anchors"

These traces were the basis for selecting the teacher LLM (gemma4:31b) and
serve as the **format specification** the teacher mimics when distilling
foreign datasets. 5 of these traces are extracted to `meta/few_shot_reference.jsonl`
for use during distillation.

## Format

```json
{
  "messages": [
    {"role": "system",   "content": "You are a DevOps agent..."},
    {"role": "user",     "content": "<task>"},
    {"role": "assistant","content": "Thought: ...\n<code>tool(...)</code>"},
    {"role": "user",     "content": "Observation: ..."},
    ...
    {"role": "assistant","content": "<code>final_answer(\"...\")</code>"}
  ],
  "meta": {
    "source": "agent_traces:<lib_id>",
    "stage": "08_docker",
    "template": "docker_recreate_fix",
    "seed_id": "docker_recreate_env",
    "variation": 3,
    "trace_hash": "4a551c919001"
  }
}
```

Full schema: [../../DATASET_FORMAT.md](../../DATASET_FORMAT.md).

## Stats

| Metric | Value |
|---|---|
| Total traces | 1,867 |
| Unique seeds (templates) | 170 |
| Unique generation templates | 14 (`bash_chain`, `multi_file_scaffold`, etc.) |
| Avg messages per trace | 7.8 |
| Avg chars per trace | 2,715 |
| File size | ~6 MB (JSONL) |

## Provenance

These were **hand-crafted** by the project authors over several months:
- 180 hand-written seed templates in `seeds.yaml`
- 45 hand-curated full traces (most complex anti-pattern fixes)
- Combined via 14 trace-generation templates with paraphrase variations

No upstream third-party dataset was used. License: **Apache 2.0**.

## License

Apache 2.0 — see [../../LICENSE](../../LICENSE).
