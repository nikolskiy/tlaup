# 10: tlaplus/Examples manifest format

## Question
What is the manifest format of github.com/tlaplus/Examples (outcome vocabulary, state counts, other per-model fields), how do its CI scripts map TLC output and exit codes to outcomes, and what does that mean for tlaup's JSON result schema (milestone 4)?

## Source
Full clone of https://github.com/tlaplus/Examples at commit 334c3983a2f44ac78fce89d1d20aa79ceb3e6987 (2026-11-09). Files, pinned to that SHA:
- https://github.com/tlaplus/Examples/blob/334c3983a2f44ac78fce89d1d20aa79ceb3e6987/manifest-schema.json
- https://github.com/tlaplus/Examples/blob/334c3983a2f44ac78fce89d1d20aa79ceb3e6987/.github/scripts/tla_utils.py (`resolve_tlc_exit_code`, `extract_state_count_info`, `check_model`)
- https://github.com/tlaplus/Examples/blob/334c3983a2f44ac78fce89d1d20aa79ceb3e6987/.github/scripts/check_small_models.py, `smoke_test_large_models.py`, `record_model_state_space.py`
- https://github.com/tlaplus/Examples/blob/334c3983a2f44ac78fce89d1d20aa79ceb3e6987/DEVELOPING.md

Captured in `tests/fixtures/research/10-examples-manifest/`: `manifest-schema.json` (full schema) and `tcp-manifest.json` (a real per-example manifest with TLC, Apalache and zero-model modules).

## Short answer
- **Current layout: one `manifest.json` per example folder** (`specifications/<name>/manifest.json`, 83 files), validated by one root `manifest-schema.json`. A single root `manifest.json` existed from 4d227cd (2023-02-14, "Added JSON manifest with CI validation (#61)") until f4f8613 (2025-07-31, "JSON schema and validation script now check split manifest"), where `git log --diff-filter=D` shows it deleted. No root manifest.json exists at HEAD.
- **Outcome vocabulary (the `result` enum, verbatim):** `"success"`, `"assumption failure"`, `"deadlock failure"`, `"safety failure"`, `"liveness failure"`, `"unknown"`.
- **Mapping is by TLC process exit code only** (`resolve_tlc_exit_code`): 0 success, 10 assumption failure, 11 deadlock failure, 12 safety failure, 13 liveness failure. Any other code becomes the stringified number ("1", "255"), which never equals a manifest value, so CI fails. `unknown` is never produced from an exit code.
- **State counts:** `distinctStates`, `totalStates`, `stateDepth` (optional integers), parsed from TLC stdout by regex; stored and checked only for `mode == "exhaustive search"` with `result == "success"`.

## Confidence
Verified for the schema and scripts at the pinned commit (read from source, counts by grep). Not done: I did not run TLC or the scripts, so the exit-code table is what their code assumes, not something I observed from TLC.

## Evidence

### Schema (per-example file)
Top level (all required, no extra properties): `sources` string[], `authors` string[], `tags` (enum `beginner|intermediate|ewd`), `modules[]`.
Module: required `path`, `features`, `models`; optional `proof: {maxRuntimeMinutes: integer}`. `features` items: enum `pluscal | action composition`. `models` may be empty.
Model: required `path` (the .cfg), `runtime`, `mode`, `result`; optional `distinctStates`, `totalStates`, `stateDepth` (integer), `workers` (integer >= 1 or `"auto"`).
- `runtime`: string, pattern `^(([0-9][0-9]:[0-9][0-9]:[0-9][0-9])|unknown)$` (HH:MM:SS; `format_timespan` rounds sub-second up to 00:00:01). `unknown` parses as the maximum timedelta, so it counts as a large model.
- `mode`: `"exhaustive search"`, `"generate"`, `"symbolic"`, or `{"simulate": {"traceCount": <number>}}`. `get_run_mode`: exhaustive -> no flag, generate -> `-generate`, simulate -> `-simulate num=<traceCount>`; `symbolic` runs Apalache (`apalache-mc check --length=5`) instead of TLC.
- `result`: `{"enum": ["success", "assumption failure", "deadlock failure", "safety failure", "liveness failure", "unknown"]}`.

Usage at HEAD, counted by grep over `specifications/*/manifest.json` (243 models): result success 210, safety failure 19, unknown 11, liveness failure 3; no `assumption failure` or `deadlock failure` entries. Mode: exhaustive search 191, symbolic 46, generate 3, simulate 3.

**Size class:** no field now. A `size` field existed and was removed in 3c0c83b (2025-08-20, "Manifest: removed model size field in favor of runtime"; `tlaLanguageVersion` removed too). Size is derived from `runtime`: <= 30 s is small (`check_small_models.py`: run to completion, hard timeout 60 s, 120 s for symbolic); > 30 s is large (`smoke_test_large_models.py`: run 5 s then stop). Proof modules are filtered by `proof.maxRuntimeMinutes` (47b0e2c, 2026-05-25).

**Features** are per module, not per model, verified against module source by `check_manifest_features.py` (tree-sitter), and they change TLC flags (`get_tlc_feature_flags`).

### Sample (fixture tcp-manifest.json)
```json
{"path": "specifications/tcp/MCtcp.cfg", "runtime": "00:00:01", "mode": "exhaustive search",
 "result": "success", "distinctStates": 1182, "totalStates": 6322, "stateDepth": 14}
```
and `{"path": "specifications/tcp/APtcp.cfg", "runtime": "00:00:01", "mode": "symbolic", "result": "success"}` (no counts).

### How CI maps TLC to outcomes
Command (`tla_utils.check_model`): `java -Dtlc2.TLC.ide=Github ... tlc2.TLC <module> -config <cfg> -workers <n|auto> -lncheck final -cleanup [-generate | -simulate num=N]`, stdout and stderr merged.
1. `actual = resolve_tlc_exit_code(returncode)`, compared as a string to `model['result']`.
2. `TimeoutExpired` fails a small-model check and passes a smoke test. A smoke test that finishes within 5 s still compares the result and logs "consider updating recorded runtime".
3. State counts (small check, when `is_state_count_valid` and the manifest holds any count): regexes on stdout
   - `(?P<total_states>[\d,]+) states generated, (?P<distinct_states>[\d,]+) distinct states found, 0 states left on queue.`
   - `The depth of the complete state graph search is (?P<state_depth>[\d,]+).`
   Numbers parsed with the en_US locale (thousands separators). A missing line fails the check. Distinct and total are compared; the depth comparison is commented out because depth is nondeterministic (tlaplus/tlaplus#883), though depth is still recorded. Absent manifest fields are skipped.
4. `record_model_state_space.py` writes the three counts for small, exhaustive, successful models, skipping two known nondeterministic ones (SpanTreeRandom.cfg, EWD998ChanTrace.cfg).
5. Symbolic (Apalache) models use the same table, so only exit 0 yields a named outcome (success). Read from code, not run.

TLC exit codes relied on: 0, 10, 11, 12, 13. All others are unmapped.

## Implications for the roadmap
- tlaup's JSON outcome can reuse the five exit-code-derived values verbatim (success, assumption failure, deadlock failure, safety failure, liveness failure) for codes 0/10/11/12/13, and should also carry the raw exit code plus a separate category for everything else (parse errors, config errors, timeouts, crashes). Upstream drops that information by stringifying. `unknown` in upstream means "not recorded", so a result report needs no `unknown`, or should define it differently.
- For statistics use the same names and types to stay comparable: `distinctStates`, `totalStates`, `stateDepth` (integers, thousands separators stripped), `runtime` as HH:MM:SS. A snake_case schema is possible but then needs a documented mapping; this is a design choice.
- Counts upstream come only from completed exhaustive runs ("0 states left on queue"); state depth is documented as unstable between runs.
- `mode` values map to TLC flags (exhaustive, generate, simulate with traceCount); `symbolic` is Apalache and outside `tlaup tlc`.
- The manifest records expected results per model; it has no errors, traces, SANY diagnostics or coverage. Those parts of tlaup's schema have no upstream precedent.
- No size class to mirror; it is derived from runtime with a 30 s cut.

## Open follow-ups
- Confirm against real TLC runs (and the TLC-exit-codes question's research) that 10 to 13 are emitted as assumed, and which codes appear for SANY parse errors, config errors and Java crashes.
- Learn why 11 models are `unknown` (likely never run to completion); not checked.
- The schema has no `$schema` key (draft unspecified); pick a draft for tlaup's published schema.

## Date checked
2026-11-14
