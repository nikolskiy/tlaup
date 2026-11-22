# 42. The `pcal` command

Size: S. Suggested model: mid-tier. Status: ready, except how the labels the translator added are printed, which waits on question (pcal added labels) of the index; everything else, and the scenario without that one assertion, can be built.

## Goal

`tlaup pcal SPEC [-- translator arguments]` runs the PlusCal translator of the pinned build in the spec's folder, prints its errors on stdout in the editor form with the spec's path, prints every line it does not recognise as written, says on stderr which files it wrote, and exits with the translator's own code.

## Covers

- Roadmap items ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)):
  - "`pcal` command: run the PlusCal translator; passthrough for its flags." (line 299), in full apart from its integration test ([52](52-integration-tests.md)). The parser is [14](14-pcal-parser.md).
  - "Golden-file tests for SANY and PlusCal output per TLC version; passthrough after `--` for each." (line 306), in part: passthrough for `pcal` in `pcal.feature`.
  - "Keep all three thin ..." (line 304), in part: `pcal` keeps to S4's rules, on [41](41-sany-command.md)'s shared shape.
- Design sections:
  - [21 S2](../design/21-other-tools.md#s2-pcal): steps 1, 2, 4 and 5, the paragraph on the files `pcal` changes and its help text, the feature tests. Step 3 (the parser) is 14; the integration test is 52.
  - [21](../design/21-other-tools.md), the head, for `pcal`: `signals_held` entered plainly and held until the command has printed; `--java-opt`, `--auto-install`, the arguments after `--`.
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes) rule 4 (`pcal` passes the translator's code through, 255 after `-writeAST` included); [02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr) for `pcal`.

## Depends on

- [41](41-sany-command.md): `resolve_tool_invocation("pcal", ...)` (the jar alone on the classpath, `cwd` the spec's folder), `build_tool_command`, `ENTRY_POINTS["pcal"]`, the shared `get_build` wrapper in `cmd/common.py`, and the shape of `cmd/sany.py` and `tools/sany.py`, which this package follows.
- [14](14-pcal-parser.md): `PcalParser`, `PcalResult`, and that `result.other` grows as lines are fed.
- [21](21-java-launcher.md): `signals_held`, `run_streaming(..., merge_stderr=True)`, `ProcessOutcome`.
- [38](38-terminal-reporter.md): `format_diagnostic` and its path rule (relative to the starting folder when beneath it), through 41.
- [18](18-feature-harness.md): the steps, `tests/test_features.py`, the fake `java` that logs its working folder.
- [07](07-golden-files.md): the PlusCal captures under `tests/parse/golden/pcal/<build>/` and the specs they were made from.

Unchanged from the draft (41, 14) in substance; 21, 38, 18 and 07 are named for what is used directly. Runs beside [43](43-repl-command.md) and the other packages after 41.

## Files

Creates:

- `src/tlaup/tools/pcal.py`: `run_pcal`, `PcalSink`, `PcalOutcome`, `written_notes`, `trim_full_stop`.
- `src/tlaup/cmd/pcal.py`: the command.
- `tests/features/pcal.feature`.
- `tests/unit/tools/test_pcal.py`.

Changes:

- `src/tlaup/cli.py`: one line registering `pcal`.
- `CHANGELOG.md`: the entry under Changelog.

Deletes: nothing.

Files another package of the same period touches: `src/tlaup/cli.py` (one registration line each for 43 and the other packages after 41); `CHANGELOG.md`; `src/tlaup/tools/` gets `repl.py` from 43 beside this package's `pcal.py`, with no shared line.

## Interfaces

Provides, written by stage 4 on the shape of [41](41-sany-command.md)'s `tools/sany.py`, from what S2 says in words:

```python
# tlaup/tools/pcal.py
class PcalSink(Protocol):
    def other(self, line: str) -> None                     # a line the parser did not recognise: stdout, as written
    def diagnostic(self, diagnostic: Diagnostic) -> None   # file set to the spec, the doubled full stop trimmed

@dataclass(frozen=True)
class PcalOutcome:
    result: PcalResult
    process: ProcessOutcome
    exit_code: int                                         # process.exit_code: the translator's, or a signal's

def run_pcal(inv: ToolInvocation, java_inv: JavaInvocation, sink: PcalSink,
             finish: Callable[[PcalOutcome], None]) -> PcalOutcome
def written_notes(files_written: Sequence[str], spec: Path, cwd: Path) -> list[str]       # pure
def trim_full_stop(message: str) -> str                                                  # pure

# tlaup/cmd/pcal.py
def pcal(ctx: typer.Context,
         spec: str,                                   # required (C1)
         pcal_args: list[str] | None = None,          # everything after `--`
         java_opt: list[str] | None = None,           # --java-opt OPT, repeatable
         auto_install: str | None = None) -> None     # --auto-install stable|rolling, else TLAUP_AUTO_INSTALL
```

**`run_pcal`.** `with signals_held() as signals:` `run_streaming(java_inv, on_stdout=..., on_stderr=..., signals=signals, merge_stderr=True)` ("the two streams read through one pipe as for `sany`", S2 step 2; stderr was empty in every run, so this loses nothing and keeps the order). Each line goes to one `PcalParser.feed`. After each call, first each diagnostic it returned goes to `sink.diagnostic`, then each line it appended to `result.other` goes to `sink.other`; that keeps stdout in the translator's order, since a line that completes a diagnostic comes after it. A diagnostic is handed on with `file` set to the spec's path (the translator names no file) and its message passed through `trim_full_stop`. `on_stderr` is never called with `merge_stderr=True`; pass a function that raises `InternalError`. When the child has ended and no signal stopped it: `parser.close()` and its diagnostics, then `finish(outcome)`, still inside the block. After a signal the parser is not closed and `finish` is not called, as for `sany`: the diagnostics completed by then are printed, no notes are.

**`trim_full_stop`** (S2 step 4, "the doubled full stop trimmed"): a message that ends in `..` loses one full stop; any other message is unchanged. The parser keeps the text as printed (14); only what is printed is trimmed.

**`written_notes`** (S2 step 4): one note per name in `files_written`, in order. The spec's own file name gives `<path> translated (previous version saved as <stem>.old)`; any other name gives `<path> written`. `<path>` is the spec's folder joined with the name, written by the same rule as a diagnostic's path (relative to the folder tlaup was started from when beneath it, else absolute), so that with the spec in the starting folder the notes read as S2's examples: `Pcal.tla translated (previous version saved as Pcal.old)`, `Pcal.cfg written`. The `.old` name is the bare file name, as the translator gives it. Written by stage 4: S2 gives the two examples and not the rule for a spec elsewhere. The translator writes the `New file X written.` lines only after a translation succeeded, so the notes appear exactly in the cases S2 calls "on success" (none after `-writeAST`, which writes `Wrote file AST.tla.` and exits 255).

**The command** is 41's `sany` with three differences: `resolve_tool_invocation("pcal", ...)`, `run_pcal`, and a `finish` that prints `written_notes` with `ui.note` on stderr. Then `raise typer.Exit(outcome.exit_code)`: the translator's code unchanged (D29), including 255 after a successful `-writeAST`; 130, 143 or 129 after a signal; 141 after a closed pipe. The sink prints diagnostics with `format_diagnostic` on `ui.out` and other lines on `ui.out` as text, never as markup, not wrapped.

**What is not printed**, read from S2 step 4, which lists what is printed: the banner, `Parsing completed.`, `Translation completed.` and the `New file X written.` lines (the notes stand for the last). Stage 4's reading; the report names it, since `sany` writes its banner and progress to stderr instead.

**Waiting on question (pcal added labels).** S2 step 3 recognises `The following label was added:` and its lines into `labels_added`, and step 4 does not say where they are printed, so with `-- -label -reportLabels` the report the user asked for would be printed nowhere. Recommended answer: print each added label on stdout, one line per label, `<spec path>:<line>:<col>: label <name> added` (stdout because it is part of the result, X2's test; the position form so that an editor can jump to it). Until the index answers, the label lines are not printed and the scenario below asserts only the rest.

Help of `pcal` (S2), which [50](50-help-and-messages.md) may reword and not drop: the first lines say what is written: the spec is rewritten in place and the previous version kept as `SPEC.old`; `SPEC.cfg` is written or rewritten with no backup, and `-- -nocfg` leaves it alone. Then, in the same words as `sany`'s line, that it reads the spec from the spec's own folder. tlaup adds no `-nocfg` itself (D23: no prompts; S2, Rejected).

Consumes: `resolve_tool_invocation`, `build_tool_command`, `ToolInvocation`, `cmd/common.py` (41); `PcalParser`, `PcalResult` (14); `signals_held`, `run_streaming`, `ProcessOutcome`, `JavaInvocation` (21); `format_diagnostic` and the path rule (38); `Diagnostic` (09); `read_auto_install` (28); `Ui` (16); `AppContext` (02).

## Tests that must pass

`tests/features/pcal.feature`, in-process (pipes; no situation of T5 applies), the fake `java` replaying the PlusCal captures of 07 and the spec of the case from the golden specs. On both builds unless said:

- Success (`pcal-good`, exit 0): exit 0; `stderr contains "Pcal.tla translated (previous version saved as Pcal.old)"` and `stderr contains "Pcal.cfg written"`; `stdout is empty`.
- A syntax error (`pcal-syntaxerr`, exit 255): `stdout contains "PcalSyn.tla:6:20: error: Expected \"do\" but found \":=\"" 1 times`; exit 255; stderr holds no note.
- `-- -nocfg` (`pcal-nocfg`): `java was started with "-nocfg"`; `stderr contains "Pcal.tla translated"`; `stderr does not contain "Pcal.cfg written"`.

Added by stage 4, each from a line of S2:

- The doubled full stop (`pcal-noalg`, exit 255): `stdout contains "PcalNoAlg.tla: error: Beginning of algorithm string --algorithm not found."` and `stdout does not contain "found.."`; no `:line:col`.
- `-writeAST` (`pcal-writeast`, exit 255): exit 255 (X1 rule 4); `stdout contains "Wrote file AST.tla."`; `stderr does not contain "translated"`.
- `-- -label -reportLabels` (`pcal-label`): both arguments in the logged command; exit 0; the two notes. *Waiting on question (pcal added labels):* the label line on stdout.
- The working folder (S2 step 2): tlaup started in another folder with the spec named by a relative path; `java was started in the folder` the spec's folder and `java was started with "Pcal.tla"`.
- Nothing recognised is printed: neither `stdout` nor `stderr` contains `Parsing completed.`.
- The preflight: a missing spec exits 4 and `java was not started`; `--java-opt=-Xss8m` is in the logged command.

`tests/unit/tools/test_pcal.py`, plain pytest:

- `trim_full_stop`: `... found..` loses one full stop; a message ending in one full stop, and one ending in none, are unchanged.
- `written_notes`: the two notes of S2's examples for a spec in the starting folder, in the translator's order; a spec in a subfolder gives paths relative to the starting folder; a spec outside it gives absolute paths; no names, no notes.
- `run_pcal` with the fake `java` as a real child (the edge's fake, T12 rule 1), replaying `pcal-spec` on rolling and a sink that records its calls: the calls come in the translator's order (`other("Wrote file AST.tla.")`, the diagnostic, then its two continuation lines as `other`, with the empty lines 14's rule keeps in their places), the diagnostic's `file` is the spec, and `finish` is called once, after the last call. Replaying `pcal-good`: no sink call and `finish` with both files written. This test runs under `signals_held` in the test process's main thread, as 21's launcher tests do; sending no signal, it needs no child Python process.

Old tests: none. No stateful test applies.

## Changelog

Added (S2, word for word): "`tlaup pcal SPEC` runs the PlusCal translator. It rewrites the spec in place and keeps the previous version as `SPEC.old`, as the translator does. It also writes `SPEC.cfg`, replacing an existing one without a backup; pass `-- -nocfg` to keep yours."

## Context for the worker

**State of `main`.** 41 is in: `tlaup/tools/` with `ENTRY_POINTS` and the shared invocation, `cmd/sany.py`, `cmd/common.py`, `format_diagnostic`. `PcalParser` is in `tlaup_parse` (14). [43](43-repl-command.md) may be in flight beside this package; it adds `tools/repl.py` and `cmd/repl.py` and one line in `cli.py`.

**Decisions this rests on.** D5 and S4: thin; no flag of tlaup's own beyond `--java-opt` and `--auto-install`, no reinterpretation of the result (the exit code passes through), no look at the arguments, no files written by tlaup. D23: no prompt, although the command changes the user's files; that is what it is for, and the help says what is written. D29: the translator's code, unchanged. D30, D22: errors on stdout in the editor form; notes on stderr. D9: every unrecognised line is printed. D56: the launcher's encoding options keep v1.7.4's translator on Java 11 under a C locale from writing non-ASCII comments into the spec as `?` (research 21); nothing to do here but not to bypass `argv()`.

**Facts a worker could miss** (S2, restated from research 12 and 32):

- The translator rewrites the `.tla` file in place, moves the previous file to `X.old`, and writes `X.cfg` unless `-nocfg`. An existing `X.cfg` is rewritten with no backup: the lines after its marker line are kept; in a cfg with no marker line the user's lines survive under a new marker, but the generated `SPECIFICATION` line is dropped. Only those two cases of an existing cfg were run.
- Started elsewhere with an absolute spec it writes `X.old`, `X.cfg` and the new `X.tla` beside the spec all the same; only `-writeAST` writes `AST.tla` into the working folder, and the file names in its messages follow the argument as given. Running it in the spec's folder gives `sany` and `pcal` one rule, keeps `AST.tla` beside the spec and the messages short.
- It does not check TLA+ expressions inside the algorithm; SANY does.
- What an interrupted translator leaves in the `.tla` file is the translator's business and was not tried (21, head).

**Traps.**

- The fake `java` writes no files, so no feature scenario can show the three files. That, and what happens to an existing cfg with and without the marker line, is the integration test of 52.
- The replays name the files as the translator wrote them, bare; the notes join them to the spec's folder. A scenario with the spec in the starting folder reads exactly as S2's examples.
- `files_written` comes from the replay, not from the disk; the command never looks for the files.
- Imports inside the command function, as for `sany` ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)).

**Known gaps; do not close them here.** How the added labels are printed (the question above). A message on several lines is printed as its first line in the editor form and the rest as unrecognised lines (14's reading of S2). The per-run `java.io.tmpdir` of question 27 concerns SANY and TLC, not the translator.

**Windows (D15).** Paths with `pathlib`; the path rule decides "beneath" before computing a relative path, since two drives make `relpath` raise. No Windows CI.

## Done when

- `pcal.feature` and `tests/unit/tools/test_pcal.py` pass on Linux and macOS in CI; `uv run poe lint` and `uv run poe test` pass.
- The changelog entry is under `## [Unreleased]`.
- The pull request shows `pcal.feature` failing before the command existed (T12 rule 6), and says whether the labels question was answered and how the labels are printed, or that they are not printed yet.

## Out of scope

- `PcalParser`, `PcalResult` and the PlusCal golden tests: [14](14-pcal-parser.md). Their expected results: [15](15-golden-expected-results.md).
- `ENTRY_POINTS`, `resolve_tool_invocation`, the editor form itself: [41](41-sany-command.md), [38](38-terminal-reporter.md).
- Integration tests ([01 T9](../design/01-testing.md#t9-integration-tests)), all in [52](52-integration-tests.md): the `pcal` half of the T9 row "`sany` on a good and a bad spec; `pcal` on a copy of a PlusCal spec" (the exit codes of D29 and the three files `pcal` leaves), and S2's integration test: on a copy of a PlusCal spec, on both builds, the three files appear, and an existing cfg with the marker line and one without it end as research 12 found.
- The command-tree test: [48](48-command-tree.md). Help wording beyond the lines above: [50](50-help-and-messages.md).

## Risks

- From S2: the `chksum` and the order of `VARIABLES` in the translation differ between builds; tlaup does not read the translated file. Only two cases of an existing cfg were run by the research.
- From the cut: until the labels question is answered, `-reportLabels` reports nothing through tlaup; the labels are in the result and the user's spec has them.
- From the cut: what is printed for the banner and the two completion lines (nothing) is stage 4's reading of S2 step 4; if the maintainer wants them on stderr as `sany` does, it is a few lines here and a class of recognised lines in 14.
