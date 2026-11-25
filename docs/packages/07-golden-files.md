# 07. Golden files

Size: M. Suggested model: most capable. Status: built.

## Goal

The research captures that the design adopts are golden files under `tests/parse/golden/`, moved with `git mv`, filed by tool and by build, each build folder with a `cases.toml` and a `build.toml`; the hand-made framing cases are in `synthetic/` with a `.why` file each; `scripts/capture_golden.py` can capture a build again; the research README says what moved where. No parser and no parser test is part of it.

## Covers

- Roadmap items:
  - "Capture real `-tool` output from TLC 1.7.4 and the current rolling build ... as golden files kept with the parser's tests, filed by TLC version (decision D7) ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust), line 156), in part: the captures become the golden files, filed by build. The failing facts are [08](08-golden-facts.md); the parser that makes them pass is [09](09-parse-package-and-model.md) to [13](13-tlc-parser.md); the expected parsed results are [15](15-golden-expected-results.md).
  - "Golden-file tests for SANY and PlusCal output per TLC version; passthrough after `--` for each." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 315), in part: the SANY and PlusCal captures moved. The tests are [12](12-sany-parser.md) and [14](14-pcal-parser.md), the expected results 15, passthrough the feature files of 41 and 42.
- Design sections:
  - [01 T3](../design/01-testing.md#t3-golden-files): "Where they live" (with `specs/<build>/`), "What moves" (every row but the last, research 28's row included), "Captures this design named before they existed" with its five placements, the research README lines, `cases.toml`, `build.toml`, "Re-capturing", "Synthetic cases" (all twelve), and the `detect-secrets` check under Risks. The facts are 08; "How the parser is driven" and the three properties are 10 and 13; the full expected results are 15. The last row of the move table (the manifests to `tests/unit/data/manifests/`) is [05](05-github-recordings.md).
  - [10 P1](../design/10-parser.md#p1-golden-files): the files. P1 is done only when facts and expected results pass too (08, 13, 15).
  - [21 S5](../design/21-other-tools.md#s5-golden-files-for-sany-and-pluscal): the move of the SANY and PlusCal captures, from research 12 and research 22. The tests are 12 and 14.
  - From [11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load) (Tests, "Golden"): research 28's two class-version captures, which T3's table now lists.

## Depends on

- [03](03-test-foundation.md): the pytest settings of [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings) (`testpaths = ["tests"]`, so that `tests/parse/` is collected; `norecursedirs` with `tests/fixtures`), which the consistency test of this package needs. Nothing else.

Unchanged from the draft.

## Files

Size of the move, counted on the tree of 2026-11-21 (tracked files): about 500 renames and 24 new files. Per source:

| From `tests/fixtures/research/` | Files moved | To `tests/parse/golden/` |
| --- | --- | --- |
| `01-tlc-output/1.7.4/*.out`, `1.8.0/*.out` | 40 (20 cases per build) | `tlc/v1.7.4/<case>.out`, `tlc/2026.11.15.002146/<case>.out`. The folder `1.8.0` becomes the rolling folder: the v1.8.0 and `rolling` jars were byte-identical when captured (SHA-256 `7e53aa63...`), version line `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`. |
| `01-tlc-output/1.*/plain/*.out` | 40 | `tlc/<build>/plain/<case>.out`. Not parsed; replayed for `--raw` scenarios. |
| `01-tlc-output/specs/` | 34 (with `java/tlc2/module/Boom.java` and `BoomTrace.java`) | `specs/`, `specs/java/...` |
| `02-json-traces/Live.tool.1.8.0.out` | 1 | `tlc/2026.11.15.002146/dump-trace-live.out` |
| `02-json-traces/Live.tool.1.7.4.out`, `Stut.tool.1.7.4.out` | 2 | `tlc/v1.7.4/json-live.out`, `json-stut.out` |
| `02-json-traces/Live.tla`, `.cfg`, `Stut.tla`, `.cfg` | 4 | `specs/` |
| `12-sany-pcal-repl/<v>/outputs/sany-*.txt`, `pcal-*.txt` that are one command | 88: v1.7.4 17 SANY and 18 PlusCal, v1.8.0 35 SANY and 18 PlusCal | `sany/<build>/<name>.out`, `pcal/<build>/<name>.out` (the file name without `.txt`), then edited (below) |
| `12-sany-pcal-repl/v1.7.4/inputs/` | 20 | `specs/`. The v1.8.0 inputs are byte-identical and stay as evidence. |
| `13-override-loading/<v>/out/<case>.txt` for the ten cases T3 names | 20 | `tlc/<build>/override-<case>.out` |
| `13-override-loading/v1.7.4/cases/<case>/` for the same ten | 41 | `specs/overrides/<case>/` (spec, cfg, `modules/`, `java/`, and `noprop` where it exists). The v1.8.0 copies are identical and stay. |
| `22-more-tool-captures/<v>/<case>.out`, the 84 cases per build that are not `q01-*` or `q12-*` | about 162 (placements 1 to 4 below) | `tlc/<build>/`, `tlc/<build>/plain/` (the three cases run without `-tool`), `sany/<build>/` |
| `22-more-tool-captures/v1.7.4/tool-missing-module.err` | 1 (placement 2) | `tlc/v1.7.4/tool-missing-module.err` |
| `22-more-tool-captures/specs/` | 21 | `specs/` |
| `22-more-tool-captures/<v>/inputs/` | 12 (placement 4) | `specs/<build>/` |
| `15-exit-codes/specs/` used by research 22's `tool-*` cases | 19 (`Act`, `Asrt`, `Assum`, `BadCfg`, `CfgSyn`, `Eval`, `NextEval`, `Ok`, `Oom` with their cfg; `NoCfg.tla`), not `Live` (placement 3) | `specs/` |
| `28-java-11-and-macos-java/out/` (placement 5) | 4 | `tlc/<build>/override-class-too-new-index.out`, `override-class-too-new-listed.out` |

The specs of every adopted case move with it, because `scripts/capture_golden.py` runs each case from `golden/specs/` and the feature steps take "a spec from the golden specs" ([01 T5](../design/01-testing.md#t5-feature-files-and-steps)). Within `specs/` no two sources share a file name except `Live` (placement 3), checked by script.

Creates:

- `tests/parse/golden/` as above, with `cases.toml` and `build.toml` in each of the six build folders (`tlc`, `sany`, `pcal` times two builds). The `plain/` captures get their entries in the `tlc` folder's `cases.toml`, under a table that says so (see Interfaces).
- `tests/parse/golden/synthetic/`: twelve cases, `<case>.out` and `<case>.why` each (see Interfaces).
- `scripts/capture_golden.py`.
- `tests/parse/test_golden_files.py` (stage 4's name; T3's layout lists none): the consistency test (see Tests). It reads files only and imports nothing from `tlaup` or `tlaup_parse`.
- `tests/parse/__init__.py`, empty, if no other package of the parser track has created it, so that `tests.parse.facts` can be imported by the integration tests later.

Changes:

- Each moved research 12 file, in a commit of its own after the pure rename: the first line (the command), the `[exit=N]` line and, in the PlusCal files, the `-- files before:` and `-- files after:` lines that follow it are removed; their content goes into `cases.toml` (T3). Nothing else in the file changes.
- `tests/fixtures/research/README.md`: one line per moved folder saying what went where and when, and the sentence "No test reads these files yet ..." made true (some of its files are now golden files elsewhere; what stays is evidence). Package 05 adds its own lines for research 29 and the manifests: a small conflict in one table.
- `.secrets.baseline`, only if `detect-secrets` flags a line of a new `build.toml` (the 40-digit commit, the 64-digit SHA-256): one `exclude_lines` pattern for that exact line shape, such as `^commit = "[0-9a-f]{40}"$` (conventions, "Secrets and personal data"). Package 05 also adds patterns here.
- `docs/contributing/development.md`: if the code map, after package 03's update, does not name `tests/parse/golden/` and `scripts/capture_golden.py`, add a clause for each.

Deletes: nothing. Everything not moved stays under `tests/fixtures/research/` as evidence (T3), including research 1's `commands.txt` and READMEs, research 12's REPL, XML, `tlc-version`, `sany-message-codes` and `pcal-retranslate-and-lint` files and its `pcal-results/`, research 13's `.cmd`, `.exit` and `.javac.txt` files (their content is in `cases.toml`), research 22's `q01-*` and `q12-*` re-runs and its empty `.err` files, and all helper scripts.

Shared within the parser track (07 to 15): `tests/parse/__init__.py` (whichever package creates `tests/parse/` first); `.secrets.baseline` and the research README with 05 (each adds lines).

## Interfaces

Provides, to 08, 10, 11, 12, 13, 14, 15, 18 (the fake `java` replays golden files), 34, 41, 42 and 52:

**Case names.** A case is the file name without extension and is the same on both builds when the same command was run on both. Names are kept as the research gave them (`violation`, `sany-semerr`, `pcal-err`, `difftrace-violation`, `tool-assum`), with three prefixes added: `override-` for research 13 and 28, and the names of research 2's three files given in the table above. Some cases exist on one build only (`dump-trace-live` on rolling; `json-live`, `json-stut` on v1.7.4; research 12's rolling-only SANY runs). Where a flag does not exist on v1.7.4 (`-generate`, `ALIAS`, `-noGenerateSpecTE`) the v1.7.4 file is the refusal and is a case of its own under the same name (T3).

**`build.toml`** (T3), one per build folder, the same in `tlc`, `sany` and `pcal`:

```toml
line = "stable"            # or "rolling"
tag = "v1.7.4"             # rolling: "rolling" (the v1.8.0 jar was the same bytes)
commit = "5a47802..."      # the full 40 digits; rolling: bc1b506...
calver = "2026.11.15.002146"   # rolling only
sha256 = "936a2620..."     # stage 4's addition: the jar the folder was captured with, all 64 digits;
                           # rolling 7e53aa636dac...
```

The values are shortened here, and only here: `build.toml` holds them in full. The commits come from the `X-Git-Revision` lines of the recorded manifests, which 05 moves to `tests/unit/data/manifests/`; the two SHA-256 values are in the READMEs of the two capture folders this package moves, `tests/fixtures/research/01-tlc-output/1.7.4/README.md` and `1.8.0/README.md` (checked by stage 4), and in `12-sany-pcal-repl/jar-sha256.txt` and `22-more-tool-captures/jar-sha256.txt`. The `detect-secrets` hook flags a full commit or digest as a high-entropy string. Per the [conventions](../contributing/conventions.md#secrets-and-personal-data), exclude exactly that line shape in `.secrets.baseline` (an `exclude_lines` pattern such as `^(commit|sha256) = "[0-9a-f]{40,64}"`), never the file or the folder, and say so in the pull request. (Reconciled by stage 4: the full values in this file tripped the same hook.)

How a live jar finds its folder ([01 T9](../design/01-testing.md#t9-integration-tests)): a jar with a build time takes the one folder whose `line` is `rolling`; a jar without one the folder whose `tag` equals its own.

**`cases.toml`** (T3 gives the first five keys and the two PlusCal ones; the rest are written by stage 4, so that the capture script can run every case again and the integration tests know which cases a live run can reproduce). One table per case:

| Key | Meaning |
| --- | --- |
| `spec` | The module name, or a path under `golden/specs/` (`"overrides/legacy_ok/spec"`, `"v1.7.4/PcalStaleAlg"`). Absent for a case with no spec (`version-bad-option`, `tool-noargs`, `sany-noargs`). |
| `args` | The arguments after the main class, without the spec, and for `tlc` without `-tool` and `-metadir`, which the script always adds: `[]` for `violation`, `["-coverage", "1"]` for `coverage`, `["-config", "ParamsX.cfg"]` for `params-step-violation`. For `sany` and `pcal`, the whole argument list after the main class, file names included, since the recorded file argument is not always last or one file (`sany-dcst`, `sany-twofiles`, `pcal-noext`; settled while building 07, a low-impact choice by the stage 5 lead). |
| `exit` | The exit code as recorded. Absent where the research did not record one (research 2's three files), with a `note` saying so. |
| `java` | The Java version, `"25.0.5"` for research 1, 2, 12, 13 and 22; research 28 ran on `"11.0.33"` (its 2187 line). |
| `captured` | The date. For a TLC case the date in its own `Starting... (...)` line (message 2185); otherwise the date the research folder's README gives. |
| `files_before`, `files_after` | PlusCal only: the lines that followed `[exit=N]`. |
| `source` | Where the file came from, for the reviewer and for history: `"research 22, v1.7.4/tool-assum.out"`. |
| `stderr` | The name of the `.err` file beside it, when the tool wrote to stderr and the streams were captured apart. Absent means nothing was written to stderr, or (research 1, 12, 13) the two streams were captured joined. |
| `plain` | `true` for a case under `plain/` (run without `-tool`; not parsed). |
| `stdin` | The text given on standard input (`sany-d-scripted`, and research 22's `-d` cases). |
| `jvm_options`, `classpath`, `java_sources`, `cwd` | What the Java-override and research 13 cases need: options before the main class (`-DTLA-Library=modules`, `-Dtlc2.overrides.TLCOverrides=...`, `-Xmx64m` for `tool-oom`), extra class path entries, sources to compile with `javac --release 11` first, and the working folder under `golden/specs/`. Copied from the recorded command (`commands.txt`, research 13's `.cmd`), with machine paths turned into paths relative to the spec's folder. |
| `stopped` | How the run ended when it did not end by itself: `"SIGTERM after 80 s"` (`checkpoint-run`), `"killed by the driver after 120 s"` (`generate-success` on rolling, exit 137). A live run cannot reproduce such a case; the integration tests (52) skip it. |
| `recover_from` | `checkpoint-recover`: the case whose checkpoint it recovers. |
| `note` | Free text, for anything else a reader needs (for example "spec not kept as a file by research 28"). |

Every value is copied from a research record (`commands.txt`, the README tables, the `[exit=N]` lines, `.cmd` and `.exit` files), never guessed. Generating the six files with a one-off script from those records is the sensible way; the script is not committed, and the pull request says how the files were made.

**Synthetic cases** (T3's list of twelve), the last four each made from a real capture with the smallest edit that produces the shape, the first eight written by hand, and each with `<case>.why` saying why it exists, which capture it came from and exactly what was changed. The note is never inside the `.out` file. Suggested names (packages 10 and 13 use the last four):

| Case | Shape (P4's rule it exercises) |
| --- | --- |
| `startmsg-minus-one` | A start marker with code `-1`: plain text, nothing raises. |
| `leading-zero` | A marker whose number has a leading zero (`02185`): plain text. |
| `unterminated` | A start marker with no end at end of input: closed `truncated` by `close()`. |
| `end-without-start` | An end marker whose code matches no open message (T3: "an end whose code does not match"): plain text. |
| `crossed-ends` | An end marker for the outer message while an inner one is open: the inner is closed `truncated`. |
| `end-marker-text-after` | An end marker with text after it at the top level: the text is the message's `after`. |
| `error-in-info` | A severity-1 message nested in a severity-0 one: one error. |
| `print-end-marker` | Marker text printed by the spec with text after it, outside any open message of that code (P4, the sixth framing rule): plain text. |
| `invalid-utf8` | A copy of `tlc/v1.7.4/violation.out` with the bytes `FF FE` put into one unframed line and a Latin-1 `é` (byte `E9`) into one value of a trace state ([11 R3](../design/11-runner.md#r3-non-utf-8-output)). |
| `crlf` | A copy of a real capture with every line ending `\r\n` (P4, Tests). |
| `cut-off` | A real capture cut inside a message and before the finish message 2186 (P3, Tests: status `RUNNING` and verdict `incomplete` after `close()`). |
| `unknown-code` | A real capture in which the codes of three messages are changed to codes that are in no TLC table, one each at severity 1, 3 and 0 (P4, rule 4). Choose codes absent from TLC's tables as P4 and P5 list them and from today's `src/tlaup/tlc/codes.py`; the `.why` names them. |

**`scripts/capture_golden.py`** (T3): `scripts/capture_golden.py --jar PATH --build NAME`. It runs every case of the `tlc`, `sany` and `pcal` `cases.toml` of an existing folder of the jar's release line (or of a folder named with an option, the worker's choice) with the given jar, each in a fresh temporary copy of its spec folder and with a fresh `-metadir` for TLC, and writes `tests/parse/golden/<tool>/NAME/<case>.out` (and `.err` when stderr is not empty), with the repository and temporary paths replaced by `<repo>` and `<tmp>` as the pre-commit hooks require; volatile values (times, pids, seeds, rates) are left as captured. TLC's stdout and stderr are read apart; SANY's and PlusCal's through one pipe, as `tlaup sany` and `tlaup pcal` read them ([21 S1](../design/21-other-tools.md#s1-sany)). It writes the new folder's `cases.toml` with the exit codes it saw and a `build.toml` from the jar's manifest, prints every case whose exit code differs from the folder it ran from, and refuses to write into a folder that already holds `.out` files. It honours `stdin`, `jvm_options`, `classpath`, `java_sources` (compiled with `javac --release 11`), `cwd`, `stopped` (stops the run the same way) and `recover_from`, and skips with a printed reason a case it cannot run (no spec file). It is a developer tool: not run in CI, needs Java, uses only the standard library (`tomllib` to read; the TOML it writes is simple enough to write by hand), and passes `ruff` and `mypy --strict`, which `uv run poe lint` applies to `scripts/`.

Consumes: nothing.

## Tests that must pass

`tests/parse/test_golden_files.py`, plain pytest, reading files only (paths from `Path(__file__)`, since the isolation fixture changes the working folder):

- Each of the six build folders has a `build.toml` with `line` `stable` or `rolling`, and the two `line` values of one tool are different (at most one rolling folder, D19 and T3).
- Every `.out` file in a build folder and its `plain/` has exactly one table in that folder's `cases.toml`, and every table has its file; every `stderr` key names a file that exists.
- Every `spec` names a file under `golden/specs/`, except the cases whose `note` says the spec was not kept.
- Every `.out` in `synthetic/` has a `.why`, and every `.why` a `.out`.
- `synthetic/crlf.out` contains `\r\n` on every line, and `synthetic/invalid-utf8.out` contains the bytes `FF FE` and `E9`: so a hook or a git setting that rewrote them would be caught.
- No `.out` file under `tlc/`, `sany/` or `pcal/` contains the research 12 framing lines (a first line starting `$ java`, a line `[exit=`), so the edit is complete.

Nothing else changes: no test reads `tests/fixtures/research/` (checked by search on 2026-11-21), and the old suite is gone (03b). Preserved-behaviour rows: none is this package's; the golden files are what the parser packages' rows are tested on.

## Changelog

None. Nothing a user sees changes.

## Context for the worker

**State of `main` when this starts.** Package 03 is in: the isolation fixture, the fakes, the T10 pytest settings, the development guide update, and no old test. `tests/parse/` may not exist; packages 08 to 14 of the parser track start from this one. The old parser (`src/tlaup/tlc/parser.py`, `sany.py`) is untouched and stays until package 39.

**What reads the old paths, and what happens to it.** No test and no tool of the project reads `tests/fixtures/research/` today. `pyproject.toml` excludes the folder from ruff for its helper scripts; that stays, and nothing with a `.py` extension moves. The research helper scripts (`22-more-tool-captures/run.py`, `13-override-loading/run-cases.sh`, `28-java-11-and-macos-java/java_matrix.py` and others) name the old paths and stop matching the tree; they did not run as they are anyway (the research README says why), and they stay as evidence. The design and research documents quote the old paths; they are historical, and the research README records the move (T3, Risks). Do not edit them.

**The order of commits** that keeps the pull request reviewable: (1) the pure `git mv`s, nothing else, so that `git diff -M --stat main` shows only 100 % renames; (2) the research 12 edit; (3) the `cases.toml` and `build.toml` files; (4) the synthetic cases; (5) the capture script; (6) the test; (7) the research README, the secrets baseline and the guide. Never edit a capture except in commit 2: a capture is evidence, and its paths (`<tmp>/q01/run/...`, `<repo>/tests/fixtures/research/13-override-loading/...`) stay as captured.

**Traps in the research 12 files.** SANY prints an empty line before its banner; that line is tool output and stays. v1.7.4's `sany-noargs` printed nothing, so its `.out` is an empty file. `sany-d-scripted` (rolling) ends `>>[rc=0]`, with the explorer's last prompt `>>` written without a newline and the record glued to it: the `.out` ends with `>>` and no newline, and `exit = 0` goes into `cases.toml`. `sany-message-codes.txt` is a list written by hand from SANY's message table, not output, and stays. `pcal-retranslate-and-lint.txt` is several commands with notes and stays (T3); research 22's `sany-stale-*` captures replace it as golden input.

**Traps in the research 22 files.** `checkpoint-recover`'s recorded command names the folder `checkpoint-run` left (`<tmp>/q22/meta/<v>/checkpoint-run/26-11-18-...`); `recover_from` replaces it. `generate-success` on rolling was killed by the driver at 120 s (exit 137), on v1.7.4 it is the refusal (exit 1). `checkpoint-run` was stopped by SIGTERM at 80 s (exit 143). The `q01-*` and `q12-*` cases are re-runs of research 1 and 12 with the streams apart (placement 1). Several captures carry ANSI escape codes (`sany-help` and `tool-help` on rolling, `tool-help` on v1.7.4); they are part of the output and stay.

**Traps in the research 13 files.** The `.txt` files hold TLC's output; the `.cmd` beside each holds a `cd` into the case folder and the full command with machine paths replaced. The ten cases are identical in `v1.7.4/cases/` and `v1.8.0/cases/` (checked), so one copy moves. Their `classes/` folders were never committed; the capture script compiles `java/` itself.

**`detect-secrets`.** T3 asks to check, when moving, the two `exclude_lines` patterns for the manifest and tag-list hashes. The manifests are now package 05's and the tag list does not move, so for this package the check is: run the hook over everything moved and created (pre-commit does it on commit, and a rename counts as a change). The moved captures hold no 40-digit hash; `build.toml` holds two long hexadecimal values and may be flagged; then add a pattern for that exact line shape, never a path ([conventions](../contributing/conventions.md#secrets-and-personal-data)).

**Other hooks.** The captures were committed through the same hooks, so a pure rename passes them. For the synthetic files: `mixed-line-ending` rewrites only a file with mixed endings, so `crlf.out` must be `\r\n` throughout; run every hook on `invalid-utf8.out` and `crlf.out`, and if one rewrites or rejects them, exclude that one hook for that one exact path in `.pre-commit-config.yaml` and say so in the pull request. The pre-commit check of T12 rule 3 (no marker text in `.py` or `.feature` files) does not apply to `.out` files.

**Decisions this rests on.** D7: golden files live with the parser's tests. D19: two builds are supported, the latest stable and the current rolling, so at most one rolling folder exists; a newer rolling capture replaces it in the pull request that adds it (T3). The design agent's decision to move rather than copy (README, "Decisions the design agent made"): one copy, not two.

**Platform (D15).** Folder names hold no `:`; the rolling folder is named by its CalVer with dots. The capture script builds paths with `pathlib`, finds `java` and `javac` with `shutil.which`, and starts them from argument lists, never through a shell.

**How research 22's captures join the golden folders** (T3's five placements, question Q3, settled by the maintainer on 2026-11-24). Research 22 re-ran research 1's and 12's cases under the same names, captured stdout and stderr apart where the earlier research joined them, generated build-specific inputs, and used a spec whose name another moved spec already has. What T3 now says, with what it means for the move:

1. *Re-runs of older cases.* `q01-*` (20 per build) and `q12-*` (60 per build) repeat research 1's and 12's cases. The research 1 and 12 files are the golden files, and the re-runs stay with research 22 as evidence. The design's counts (P4: 117 files, 1,618 messages; P8: the SANY script run) and its examples were made on those files; research 22 found stderr empty in all 40 `q01` runs, so research 1's joined files are TLC's stdout; and [21 S1](../design/21-other-tools.md#s1-sany) wants SANY's two streams joined, which only research 12's files hold (its v1.7.4 `File does not exist` line is in the joined file, where P8's tests look for it).
2. *Stderr.* For a TLC case, the `.err` file moves beside the `.out` when it is not empty (only v1.7.4's `tool-missing-module`), and `cases.toml` names it; empty `.err` files stay. Research 22's two SANY cases with a non-empty `.err` (`sany-missing-module-ext` on v1.7.4, `sany-nofile-no-sep` on both builds) stay as evidence: their streams were captured apart, so no file holds them in the order SANY wrote them, and research 12's `sany-missingmod` and `sany-nofile` are the same cases joined.
3. *`Live`.* Research 2's `Live.tla` moves to `specs/`, and research 22's `tool-live` ran research 15's different `Live.tla`; a module's name must equal its file's, so `tool-live` is not adopted. Liveness violations are covered by research 1's two liveness cases, research 2's `json-live` and research 22's `difftrace-liveness`.
4. *Build-specific inputs.* The PlusCal-stale specs (`PcalStaleAlg`, `PcalStaleTla`, `PcalStaleBoth`) were generated by research 22 with each build's own translator and differ between the builds; they go to `golden/specs/<build>/`, named like the build folders, and the cases name them by that path. `golden/specs/` itself stays shared by all builds.
5. *Research 28.* Its two `-tool` captures on Java 11 (message 2173 for a too-new index class; a 1000 holding `UnsupportedClassVersionError` for a too-new listed class), which R7's tests use and P5 takes the kind of 2173 from: `ovr-javac25-default-<build>-java11-tool.txt` and `ovr-mixed-index-release11-listed-javac25-default-<build>-java11-tool.txt` (with the `.exit` content in `cases.toml`) move to `tlc/<build>/override-class-too-new-index.out` and `override-class-too-new-listed.out`; `<build>` `rolling` is the same jar as the rolling folder (its version line is `2026.11.15.002146`). Research 28 kept their specs inside its script, not as files, so the cases have no `spec` and the capture script skips them with a note. Package 34 depends on finding them.

## Done when

- The move is complete as tabled, decided points included; `git diff -M --stat main` on the first commit shows only renames.
- `tests/parse/test_golden_files.py` passes; `uv run poe lint` and `uv run poe test` pass; pre-commit passes on every moved and new file; CI is green.
- The research README has its lines; `detect-secrets` passes with at most an exact line-shape pattern added.
- The capture script was run, if a JVM and the two jars were at hand, for at least one case of each tool on each build into a scratch folder outside the repository, and its output had the shape of the moved captures (paths replaced, timestamps differing); the pull request says whether this was done. Its output is not committed.
- The pull request lists the counts per destination folder and says how `cases.toml` was generated.
- One pull request; a separate review agent can review it in one sitting by checking the renames by `--stat`, the research 12 edit as a diff, `cases.toml` against the research records on a sample per source, and every synthetic file with its `.why` in full.

## Out of scope

- The manifests (`03-jar-identity/manifest-*.txt`, `14-jar-manifest/*.MF` to `tests/unit/data/manifests/`, T3's last row) and the `detect-secrets` manifest pattern check: [05](05-github-recordings.md). The GitHub recordings of research 29: 05.
- `tests/fixtures/releases.json`, `tags.json` and `naming_dynamic` (deleted with the old suite in 03b, D62) and `naming_fixed` (moved beside its T9 row by [52](52-integration-tests.md)).
- `facts.py` and `test_facts.py`: [08](08-golden-facts.md). The framing rebuild over every file: [10](10-framing-and-codes.md). The SANY and PlusCal golden tests: [12](12-sany-parser.md), [14](14-pcal-parser.md). `test_golden.py` and the TLC parser: [13](13-tlc-parser.md). The expected `<case>.json` files: [15](15-golden-expected-results.md).
- The fake `java` that replays these files: [03](03-test-foundation.md); the feature files that replay them: 18 and later.
- A rolling capture newer than 2026.11.15.002146: a later pull request with the capture script.

## Risks

- From T3: moving breaks the paths quoted in the research result files; they are historical and the README records the move. A live rolling build newer than the rolling folder is checked against that folder's facts (T9); a failing fact then means upstream changed its output, and the answer is a new capture.
- From the cut: about 500 renames in one pull request. Reviewable only because the renames are a commit of their own with no content change; a worker who mixes edits into that commit makes the pull request unreviewable.
- The five placements above are settled; a later change to one is a small follow-up move, but facts (08) and expected files (15) keyed by those case names move with it.
- `cases.toml` grows beyond T3's five keys. Each key is there for the capture script or the integration tests; a key nobody reads should not be added.
- Under `core.autocrlf` (Windows, D15) Git could rewrite the golden files' line endings until package [57](57-repo-hygiene.md) adds the `.gitattributes` rule of [30 H2](../design/30-ci-and-release.md#h2-clean-task-and-gitignore) (`tests/parse/golden/** -text`); 57 may land before or after this package. The consistency test catches a rewritten `crlf.out` or `invalid-utf8.out`; other files would only change their line endings, which the parser ignores by design. Not tried on Windows.
