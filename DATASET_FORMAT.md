# Dataset format specification

All datasets in this repo follow the same JSONL schema: one line = one
agent trace.

## Top-level structure

```json
{
  "messages": [...],
  "meta": {...}
}
```

### `messages` — array of dialog turns

Required. Each message has `role` and `content`. Roles in order:

```
system     ← anchor (identical across all traces in a subset)
user       ← original task description
assistant  ← Thought: ... + <code>...</code>
user       ← Observation: ... (response from previous tool call)
assistant  ← Thought: ... + <code>...</code>
user       ← Observation: ...
...
assistant  ← <code>final_answer("...")</code>
```

Minimum 4 messages: `[system, user, assistant, user]`. Typical 6-15 messages.

### `meta` — provenance metadata

Required. Common fields:

```json
{
  "source": "agent_traces:seeds_ssh"        // string: where this trace came from
                                             //   "agent_traces:<lib_id>"  for own seeds
                                             //   "distilled_via_<teacher>" for distilled
  "stage": "06_ssh",                         // string: stage in our recipe (own only)
  "template": "bash_chain",                  // string: generation template (own only)
  "seed_id": "ssh_keygen_setup_passwordless",// string: source seed (own only)
  "variation": 3,                            // int: paraphrase variation (own only)
  "trace_hash": "a38efc58a216",              // string: 12-char md5 of messages content

  // distilled-specific:
  "source_idx": 42,                          // int: index in source dataset
  "teacher_score": 95.5,                     // float: composite format score 0-100
  "distill_ts": "2026-04-28T03:14:22"        // string: ISO timestamp
}
```

## System prompt (anchor)

Every trace's first message is identical:

```
You are a DevOps agent. Solve tasks by calling Python tools in a Thought -> Code -> Observation loop.

Each step: write a 'Thought: ...' line, then a <code>...</code> block with Python that calls tools or uses print(). You will see 'Observation:' with the printed output. Continue until you can call final_answer(...) in a <code> block.

Tools:
- bash(command: str, timeout: int = 60, cwd: str | None = None) -> str
- read_file(path: str, lines: str | None = None) -> str
- write_file(path: str, content: str, mode: str = "overwrite") -> str
- list_dir(path: str, recursive: bool = False, max_depth: int = 3) -> str
- final_answer(answer: str) -> None

Rules: always emit a Thought and a <code> block. Use print() to carry data forward. Call final_answer only when done.
```

## Tools — schema

| Tool | Signature | Purpose |
|---|---|---|
| `bash` | `(command: str, timeout: int = 60, cwd: str \| None = None)` | Run shell command, returns combined stdout+stderr |
| `read_file` | `(path: str, lines: str \| None = None)` | Read file, optional `0:50` line range |
| `write_file` | `(path: str, content: str, mode: str = "overwrite")` | Write file, mode `overwrite` or `append` |
| `list_dir` | `(path: str, recursive: bool = False, max_depth: int = 3)` | List directory |
| `final_answer` | `(answer: str)` | Terminate trace with final answer |

Each `<code>` block must call **exactly one** tool. No wrapping in functions,
no try/except scaffolding around tool calls. Plain top-level call only.

## Assistant turn structure

```
Thought: <one or two sentences explaining what to do next>
<code>
out = bash(command="...")
print(out)
</code>
```

`print(...)` carries data into the next Observation. Without `print` the
agent loses the result.

## User Observation turn structure

```
Observation:
$ <command>
[exit <N>]
--- stdout ---
<stdout content>
--- stderr ---
<stderr content if any>
```

Or for `write_file`:

```
Observation:
wrote 252 chars to /path/to/file (overwrite)
```

Or for `read_file`:

```
Observation:
<file content>
```

## Critical rules for format compliance

1. **One file = one step.** When scaffolding multiple files, each file is
   a separate `write_file` call in a separate assistant turn. Never batch
   3 files in one `<code>` block — Python parser breaks on triple-quoted
   strings, Vue `<script setup>` tags, YAML colons.

2. **For YAML/heredoc-tricky content, use bash heredoc.** Example:
   ```
   <code>
   out = bash(command="cat > /tmp/config.yaml <<'EOF'\nkey: $value\nEOF")
   print(out)
   </code>
   ```
   Single-quoted EOF prevents shell expansion.

3. **Verify before final_answer.** Always read back the file you wrote,
   curl the endpoint you started, list the directory you scaffolded.
   Don't claim success without proof.

4. **Honest failure is OK.** If a step actually fails, the trace shows
   the failure, the diagnosis, and either a recovery or an honest
   `final_answer("Tried X. It failed because Y. Could not recover within scope.")`.

## Length distribution (typical)

| Aspect | Range | Avg |
|---|---|---|
| Messages per trace | 4-30 | ~8 |
| Assistant turns | 1-15 | ~3-4 |
| Total characters | 1000-15000 | ~2700 |

## Tooling

- Generate own traces: see `scripts/build_recipe.py` (recipe + seeds.yaml → train.jsonl)
- Distill foreign datasets: see `scripts/distill.py` (raw instruction/response → agent format)
- Validate format: see `scripts/validate_trace.py` (JSON schema check + composite score)
