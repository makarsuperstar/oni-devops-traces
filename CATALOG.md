# SeedBuilder — Каталог датасетов

> **ГЛАВНАЯ ЦЕЛЬ — мы сами.** Single source of truth для собственной работы:
> что у нас на диске, откуда взялось, для чего. Когда сядем в новой сессии
> через месяц — взглянул в каталог и сразу понятно что брать в новый build.
>
> **Вторично — GitHub-публикация.** Тот же контент с минимальными правками
> можно вынести в публичный репо, людям пригодится.
>
> **Команды пользователя:**
> - «загляни в каталог» / «прочитай CATALOG.md» — для общего обзора
> - «какой lib_id под X?» — Claude найдёт по skills tags
> - «обнови каталог» — перегенерировать таблицы из реального состояния library/
>
> **Команды Claude (в next session):**
> - При создании нового build — сначала смотрит CATALOG → выбирает lib_items
> - При завершении distill — добавляет запись в DISTILLED секцию
> - При появлении нового чемпиона — обновляет Чемпионы секцию

---

## Легенда

```
KIND      Тип источника:
            seeds_filter  — собственные seeds.yaml через фильтр id_prefixes
            manual_jsonl  — руками написанные трейсы
            huggingface   — скачано с HuggingFace через download_item.py
            github        — клон GitHub-репо, парсинг файлов
            distilled     — выход SeedBuilder pipeline (через teacher LLM)

STATUS    used        — используется в текущем чемпионе (base-7.v2)
          deprecated  — попадало в base-3..5 которые проиграли, выпилено
          ballast     — на диске лежит, но в build'ах не подмешивается
          source      — сырьё для distillation pipeline (НЕ в обучение)

SKILLS    Тэги навыков, которые трейсы тренируют у студента
```

---

## 🟢 OWN — наши собственные (используются в чемпионе base-7.v2)

19 lib_items, **1867 трейсов в финальном train.jsonl**.

| ID | KIND | SKILLS | Used in | Лицензия |
|---|---|---|---|---|
| `seeds_scaffold_fix` | manual_jsonl (45 hand-written) | agent_protocol, anti_pattern, heredoc_fallback, verify_before_final | base-6/7/8 | Project's own |
| `seeds_multi_file_scaffold` | seeds_filter (11 seeds) | one_file_one_step, project_scaffold (Vue/React/Next/Django/nginx/celery/grafana/CI) | base-7/8 | Project's own |
| `seeds_agent_protocol` | seeds_filter (8 seeds) | thought_code_observation, tool_usage, final_answer | all base | Project's own |
| `seeds_honest_failure_verification` | seeds_filter (7 seeds) | dont_lie_about_success, retry_on_fail, honest_recovery | all base | Project's own |
| `seeds_misc_basics` | seeds_filter (30 seeds) | read_answer, list_count, write_validate, multi_file_read | all base | Project's own |
| `seeds_ssh` | seeds_filter (6 seeds) | ed25519_keygen, ssh_copy_id, port_forward, scp, diagnose_perm_denied | all base | Project's own |
| `seeds_git` | seeds_filter (10 seeds) | clone_branch, switch, conventional_commits, conflict_resolve, rebase_squash | all base | Project's own |
| `seeds_docker` | seeds_filter (27 seeds) | build_run_exec, networks, volumes, healthcheck, recreate_cycle | all base | Project's own |
| `seeds_nginx_systemd_supervisord` | seeds_filter (7 seeds) | reverse_proxy_ssl, systemd_hardening, supervisord_log_rotate, gzip+SPA | all base | Project's own |
| `seeds_ci_cd` | seeds_filter (10 seeds) | gitlab_ci, github_actions, GHCR_push, deploy_via_ssh | all base | Project's own |
| `seeds_django_flask_fastapi` | seeds_filter (22 seeds) | settings_urls_models_views_serializers, REST endpoints | all base | Project's own |
| `seeds_celery_redis` | seeds_filter (6 seeds) | task_decorator_retry, beat_schedule, worker_run, redis_pubsub, canvas | all base | Project's own |
| `seeds_databases` | seeds_filter (5 seeds) | postgres_create, pg_dump_restore, slow_query_index, mongo_pymongo, sqlite_ctx | all base | Project's own |
| `seeds_js_vue_react_next_rn` | seeds_filter (10 seeds) | Vue3_SFC_pinia, React18_hooks, Next14_app_router, RN_screen | all base | Project's own |
| `seeds_websocket` | seeds_filter (2 seeds) | py_websockets_server_rooms, JS_reconnecting_client, broadcast | all base | Project's own |
| `seeds_webrtc_jitsi` | seeds_filter (8 seeds) | RTCPeerConnection, ICE_signaling, JVB_health, jitsi_iframe, CDP_debug | all base | Project's own |
| `seeds_logs_monitoring` | seeds_filter (4 seeds) | tail_grep_buffered, journalctl_p_err, glitchtip_query, prometheus_promql | all base | Project's own |
| `seeds_playwright_cdp` | seeds_filter (3 seeds) | playwright_test, screenshot_on_fail, route_mock, console_capture | all base | Project's own |
| `seeds_code_review` | seeds_filter (4 seeds) | jsdoc_typescript, python_type_hints, split_long_function, http_timeout_error | all base | Project's own |

**Источники этих seeds:** все 180 seeds руками написаны в `seeds.yaml`,
плюс 45 hand-curated полных трейсов в `seeds_scaffold_fix/data/data.jsonl`.

---

## 🟡 SOURCE — сырьё для distillation (НЕ в обучении)

Эти датасеты **сырыми не годятся** (формат `instruction → response`,
не agent loop). Лежат на диске как **источник материала** для SeedBuilder
pipeline.

### HuggingFace (3010 items суммарно)

| ID | HF ID | Items | Skills (после distill) | Лицензия исходника |
|---|---|---:|---|---|
| `hf_magicoder_bash_pipes_filter` | `ise-uiuc/Magicoder-Evol-Instruct-110K` | 300 | grep/awk/sed/find/xargs/jq/sort/uniq | MIT |
| `hf_magicoder_django_filter` | same | 300 | Django ecosystem | MIT |
| `hf_magicoder_express_filter` | same | 250 | Express.js routing/middleware/validation | MIT |
| `hf_magicoder_microservices_filter` | same | 250 | message queues, service discovery | MIT |
| `hf_magicoder_design_patterns_filter` | same | 250 | GoF patterns | MIT |
| `hf_magicoder_solid_filter` | same | 250 | SOLID principles, refactoring | MIT |
| `hf_magicoder_frontend_fullstack_filter` | same | 400 | Node ecosystem, HTML/CSS, JS/TS depth, tooling | MIT |
| `hf_magicoder_js_only_filter` | same | 400 | vanilla JS — function/var/closures/promises/async-await | MIT |
| `hf_magicoder_ts_only_filter` | same | 400 | TypeScript interfaces/types/generics/tsconfig | MIT |
| `hf_magicoder_eslint_filter` | same | 10 | ESLint configs + rules | MIT |
| `hf_magicoder_oss_full` | `ise-uiuc/Magicoder-OSS-Instruct-75K` | 200 | broad code-instruct OSS code | MIT |
| `hf_magicoder_evol_full` | `ise-uiuc/Magicoder-Evol-Instruct-110K` | (full) | broad Python/JS/etc | MIT |
| `hf_canitedit` | `nuprl/CanItEdit` | (small) | surgical code edit before→after | (check) |
| `hf_commitpack_dockerfile` | `bigcode/commitpackft` | (filter) | real Dockerfile commits | (check) |
| `hf_commitpack_yaml` | `bigcode/commitpackft` | (filter) | real YAML config commits | (check) |

### GitHub (раскрытие планируется)

| ID | Repo | Stars | Skills (после distill) | Лицензия |
|---|---|---:|---|---|
| `gh_tldr_pages` | tldr-pages/tldr | 50k | bash command examples (grep/find/etc) | CC-BY |
| `gh_node_best_practices` | goldbergyoni/nodebestpractices | 100k | Node.js production patterns | CC-BY-SA |
| `gh_python_design_patterns` | faif/python-patterns | 40k | Python GoF patterns | MIT |
| `gh_java_design_patterns` | iluwatar/java-design-patterns | 90k | All 23 GoF + others | MIT |
| `gh_expressjs_examples` | expressjs/express | 66k | Express auth/error/routing/middleware | MIT |
| `gh_airbnb_javascript` | airbnb/javascript | 143k | JS style guide good/bad examples | MIT |
| `gh_javascript_questions` | lydiahallie/javascript-questions | 60k | JS quirks deep Q&A | (check) |
| `gh_eslint_rules_docs` | eslint/eslint | 25k | ESLint rule docs with examples | MIT |
| `gh_jsdoc_examples` | jsdoc/jsdoc | (n/a) | JSDoc/TSDoc syntax reference | Apache-2.0 |

⚠️ **Все эти 9 GitHub items пока имеют 0 items locally** — данные не извлечены.
Нужно прогнать `_tools/download_item.py` или вручную скачать.

---

## 🔵 DISTILLED — выход SeedBuilder pipeline (создаются)

**Пока пусто.** Будут создаваться после `RUNBOOK_DISTILL` runs.

Шаблон будущей записи:

```
| ID | Source | Teacher | Items | Acceptance | Used in | Score range |
|---|---|---|---:|---|---|---|
| `distilled_hf_magicoder_bash_pipes_filter` | hf_magicoder_bash_pipes_filter | gemma4:31b | TBD/300 | TBD% | base-10 | 84.8-100 |
| `distilled_hf_magicoder_django_filter` | hf_magicoder_django_filter | gemma4:31b | TBD/300 | TBD% | base-10 | 84.8-100 |
| ... | ... | ... | ... | ... | ... | ... |
```

После каждого distill prod-run обновлять эту секцию.

---

## 🏆 Чемпионы (используют какие lib_items)

| Build | Status | Trace count | Lib_items | Stage 1 SSH | Realworld |
|---|---|---:|---|---|---|
| `oni:v8` (legacy) | retired champion | 731 | own only | 11/22 | n/a |
| `oni:base-6.v2` | retired | 1747 | 18 own | 14/22 | n/a |
| **`oni:base-7.v2`** | **🏆 current champion** | **1867** | **19 own (no HF)** | **15/22** | **4/5 honest** |
| `oni:base-8.v2` | failed experiment | 1862 | 19 own | 14/22 ↓ | hallucinated |
| `oni:base-9` | planned (normalize) | ~1850 | repackaging base-7 seeds | TBD | TBD |
| `oni:base-10` | planned (distill) | ~3350 | base-9 + distilled | TBD | TBD |

**Champions registry на боксе:**
`experiments/base_3_dataset/builds/_champions/<id>/` —
adapter + Modelfile + chain.log + JSON results каждого чемпиона.

---

## 🛑 Deprecated / failed

| ID | Reason |
|---|---|
| `hf_magicoder_*` (raw) | Format mismatch (instruction→response без agent loop). В base-3..5 ломали модель. ⚠️ **СОХРАНЯЕМ КАК SOURCE для distillation**, но не подмешиваем raw |
| `gh_*` (raw) | То же — нет agent loop. Сохраняем как source |
| `oni:base-3` | -ший base после v8, регрессировал из-за HF mix |
| `oni:base-4` | Попытка чистить HF mix — не помогло |
| `oni:base-5` | + ещё HF — стало хуже |
| `oni:base-8.v2` | Регресс на Stage 1 (-1) + hallucinated success на realworld |

---

## Структура данных (формат трейса)

Все обучающие трейсы в нашем датасете — JSON Lines (`.jsonl`),
одна строка = один трейс:

```json
{
  "messages": [
    {"role": "system", "content": "You are a DevOps agent. Solve tasks by..."},
    {"role": "user", "content": "<task description>"},
    {"role": "assistant", "content": "Thought: ...\n<code>\n  bash(...)\n</code>"},
    {"role": "user", "content": "Observation:\n$ cmd\n[exit 0]\n--- stdout ---\n..."},
    {"role": "assistant", "content": "Thought: ...\n<code>\n  ...\n</code>"},
    ...
    {"role": "assistant", "content": "<code>\nfinal_answer(\"...\")\n</code>"}
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

**Критично для format compliance:**
- `system` message identical для всех трейсов одного датасета (anchor)
- assistant turns: `Thought: ...\n<code>\n  <python_with_one_tool_call>\n</code>`
- user turns после assistant: `Observation: ...` с реалистичным выводом
- последний assistant turn: `<code>final_answer("...")</code>`
- доступные tools: `bash`, `read_file`, `write_file`, `list_dir`, `final_answer`
- **1 файл = 1 step** для scaffold-задач (нельзя батчить write_file)

---

## Лицензии

**Наш проектный код + seeds + manual traces:** TBD (Apache 2.0 предлагается
для будущего публичного релиза).

**Distilled output:** наследует наиболее ограничительную лицензию из:
- лицензия исходника (например MIT для Magicoder)
- лицензия teacher-модели (gemma4 — Apache 2.0)
- лицензия few-shot reference (= наш проектный код)

Поэтому **distilled через gemma4 на Magicoder-source = MIT-совместимо**
(MIT и Apache 2.0 совместимы для derived works).

⚠️ **При публикации проверять каждый source** — особенно GitHub-content
с CC-BY-SA или GPL может потребовать другой лицензии для derived dataset.

---

## Будущая публикация на GitHub — что войдёт

```
oni-devops-traces/                       (предполагаемое имя)
├── README.md                            ← главная, как использовать
├── DATASET_CARD.md                      ← HF-style карточка
├── CATALOG.md                           ← этот файл
├── LICENSE                              ← Apache 2.0
├── REPRODUCE.md                         ← как пересобрать с нуля
├── data/
│   ├── own_anchors.jsonl                ← 1867 наших трейсов из base-7
│   ├── distilled_bash_pipes.jsonl       ← каждый distilled subset отдельно
│   ├── distilled_django.jsonl
│   └── ...
├── recipes/
│   └── base-N.recipe.yaml               ← как мы их объединяем для тренировки
└── meta/
    ├── teacher_config.yaml              ← gemma4:31b + prompts + params
    ├── few_shot_reference.jsonl         ← 5 anchor traces
    └── benchmark_results.json           ← результаты выбора teacher

Размер: ~50-100 MB (jsonl сжимается отлично, до ~10 MB через gzip).
```

**Не войдёт:**
- Сырые `hf_magicoder_*` JSONL — это HuggingFace, пользователь сам качает
- Тренировочные адаптеры (LoRA weights) — большие, хранятся на боксе
- Чемпион-Modelfile — публикуется отдельно через ollama.com/library

---

## Cm обновлять этот каталог

После каждого:
- Distill run → добавить запись в **DISTILLED** секцию
- Новый чемпион → обновить **Чемпионы**
- Новый seed_filter / manual_jsonl → добавить в **OWN**
- Новый source download → добавить в **SOURCE**

Этот файл — single source of truth. PR на GitHub в первую очередь будет смотреть сюда.
