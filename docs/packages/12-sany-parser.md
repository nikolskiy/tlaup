# 12. The SANY parser

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup_parse.SanyParser` reads SANY's output one line at a time, gives every line a class, and returns each diagnostic once, when it is complete, with its severity, module, file, location and message. It passes the golden tests over the SANY captures of both builds, written first and failing, and `SanyResult` has a dictionary form for the expected files of [15](15-golden-expected-results.md).

## Covers

- Roadmap items:
  - "Fix SANY error grouping: errors are flushed after every line, the error block never ends so later TLC messages become SANY errors, and lines keep their newline ... Cover `Semantic errors:`, `***Parse Error***` and the 1.8.0 `Linting of module` line." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the parser and its state machine. That SANY's text is given to it only between messages 2220 and 2219 of a TLC run is [13](13-tlc-parser.md); that the runner no longer asks for errors after every line is package 37.
  - "Golden-file tests for SANY and PlusCal output per TLC version; passthrough after `--` for each." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)), in part: the SANY golden tests. PlusCal is package 14; the full expected results are 15; passthrough is tested in the feature files of 41 and 42.
  - "Move the parser stack ... into its own import package" ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: `sany.py`. See [09](09-parse-package-and-model.md).
- Design sections:
  - [10 P8](../design/10-parser.md#p8-sany-output): the line classes, the state machine, the parse-error diagnostic, the duplicate rule, severity (D55), the warning forms, the file of a diagnostic, the tests headed "Golden, SANY alone", and the paragraph that makes them the parser's own tests with `SanyResult.to_dict()` and `from_dict()` (question Q18). The bullet "Scope inside TLC" and the tests headed "Golden, inside TLC" are package 13.
  - [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package): `SanyParser`, `SanyStep`, `SanyLineClass`, `SanyResult` of the public surface.
  - [21 S5](../design/21-other-tools.md#s5-golden-files-for-sany-and-pluscal): the SANY row of its table, as the parser's own assertions (not facts, Q18). Moving the captures is package 07; the PlusCal row is 14.
  - Preserved-behaviour row R31 (SANY's output is split into errors and warnings with module and range): its owner ([inventory](../design/preserved-behaviour-2026-11-22.md)).

## Depends on

- [09](09-parse-package-and-model.md): `Diagnostic` and `Location`; the package skeleton and `__init__.py`.
- [07](07-golden-files.md): `tests/parse/golden/sany/<build>/` with one `.out` file per case and `cases.toml`.

Changed from the draft: the draft says this package depends on 10. It does not: SANY's text is unframed, and the parser needs neither the `Framer` nor the code table. It needs 09 and 07, so it can run beside [10](10-framing-and-codes.md) and [11](11-values.md). P8's "Depends on" now says the same: P2 for the parser, P4 only for the window inside a TLC run, which is 13's part.

## Files

Creates:

- `src/tlaup_parse/sany.py`: `SanyParser`, `SanyStep`, `SanyLineClass`, `SanyResult`. P2 lists the three types in the public surface without naming a module; stage 4 puts them with the parser.
- `tests/parse/test_sany.py` (named in the layout of [01 T3](../design/01-testing.md#t3-golden-files)).

Changes:

- `src/tlaup_parse/__init__.py`: export the four names.

Deletes: nothing. `src/tlaup/tlc/sany.py` stays until package 39; its old test went in 03b.

Shared with 10 and 11, which run beside this package: `src/tlaup_parse/__init__.py` (one import line and `__all__` entries).

## Interfaces

Provides ([10 P2](../design/10-parser.md#p2-the-tlaup_parse-package)):

```python
class SanyParser:
    def feed(self, line: str) -> SanyStep: ...  # what the line was, and the diagnostics it completed
    def close(self) -> SanyStep: ...  # line_class is None; the diagnostic still open, if any
    @property
    def result(self) -> SanyResult: ...


@dataclass(frozen=True)
class SanyStep:
    line_class: SanyLineClass | None  # None only from close()
    diagnostics: tuple[Diagnostic, ...]  # usually empty: a diagnostic is returned when it is complete


class SanyLineClass(Enum):
    BANNER, PROGRESS, HEADER, STRUCTURE, POSITION, MESSAGE, BLANK, OTHER


@dataclass(frozen=True)
class SanyResult:
    diagnostics: tuple[Diagnostic, ...]
    module_files: dict[str, str]
    other: tuple[str, ...]  # the lines of class OTHER, in order
    lines_used: int  # how many input lines had another class

    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SanyResult": ...
```

[10 P8](../design/10-parser.md#p8-sany-output) gives `SanyResult` its dictionary form, "plain JSON types like the types of P3", with `from_dict` beside it for the same round-trip test (question Q18). Its shape, written by stage 4 from 09's rules: `diagnostics` (each as `Diagnostic.to_dict()`), `module_files`, `other` and `lines_used`, nothing left out when empty. The dictionary value of a `SanyLineClass` is its name in lower case. Package 15 decides the shape of the expected file around these (it also holds the class of every line).

Behaviour, all from P8; the two tables there (the classes, and the state machine with its seven states `preamble`, `semantic_errors`, `parse_error`, `parse_stack`, `parse_tail`, `abort`, `warnings`) are complete and were run as a script over research 12's 52 SANY captures and 110 TLC captures. Build them row by row. The points a reader could miss:

- `feed` strips trailing white space first (a line may arrive with its newline; SANY ends some lines with a space). The stripped line is what `other`, a message and `details` hold.
- At most one diagnostic is open. "Completes" means: the open diagnostic is returned if it has a message, and dropped if it has none (the line that opened it stays counted as used).
- An empty line never ends a diagnostic. It is `BLANK`, except directly after an `OTHER` line, where it is `OTHER`. No look-ahead.
- A location line counts only when it is the whole line; inside the three parse states it is an ordinary line.
- The parse-error diagnostic: message from `***Parse Error***` to `Residual stack trace follows:`; location from the first `at line L, column C` in the message, else the first `line L, col C to line L2, col C2 of module M` inside it, else none; the stack lines are `details`; the module comes from `Could not parse module M from file F` in the tail; if the input ends before the tail, `close()` returns it without a module.
- A diagnostic equal to one already returned (same severity, module, location and message) is not returned again and is not added to `result.diagnostics`. This is the whole rule for rolling's repeated abort block.
- Severity (D55): everything under `Semantic errors:` and in an abort block is `error`, 4802 and the two stuttering lints included; only a warning block (rolling) and the `!! WARNING: ` line (v1.7.4) give `warning`. There is no table of texts known to be warnings.
- `Diagnostic.tool` is `"sany"`. `Diagnostic.file` is the path recorded for the diagnostic's module by a `Parsing file <path>` line (module name from the file name, a trailing ` (jar:...)` dropped), looked up when the diagnostic completes, and `None` if the module was not announced. The parser opens no file.
- The warning block's header (`Warnings (N) during syntax parsing of F:`) gives no file: `F` has an extension in SANY alone and none inside TLC.
- `File does not exist: ... while looking in these directories: ...`, SANY's complaints about its own command line and its help text are `OTHER` on purpose.
- `result.other` is the `OTHER` lines in order; `result.lines_used` counts every other line fed, `BLANK` included, so `len(result.other) + result.lines_used` is the number of lines fed.
- A second banner (two files on one command line) completes and returns to `preamble`; `module_files` and the diagnostics keep accumulating.

Consumes: `Diagnostic`, `Location` from [09](09-parse-package-and-model.md).

Used by: package 13 (`TlcParser` owns one and feeds it the unframed lines of the SANY window; it reads `SanyStep.line_class`, `SanyStep.diagnostics`, and `result.lines_used` and `result.module_files`); package 41 (`tlaup sany` routes lines by class and returns 150 when a diagnostic of severity `error` exists, [21 S1](../design/21-other-tools.md#s1-sany)).

## Tests that must pass

`tests/parse/test_sany.py`, plain pytest over `tests/parse/golden/sany/<build>/` (research 12's joined captures and research 22's that T3 adopts), each file read in binary, split into lines that keep their line ending, decoded as UTF-8 with `errors="replace"`, and fed one line per call; `close()` at the end. Case names below are the design's; the ids are the ones package 07 gave in `cases.toml`.

Golden, SANY alone (P8 Tests, S5), on both builds unless said:

- A good spec: no diagnostics.
- Two semantic errors: two diagnostics, each with its own position.
- Two level errors with two-line messages: two diagnostics, same text and order on both builds.
- The precedence conflict (`sany-level`): one diagnostic at line 6, column 27, through the second location form.
- A parse error: one diagnostic with its module, a location and the residual stack in `details`; several parse errors in one spec: one diagnostic (SANY reports only the first).
- Missing module: one diagnostic with no location on both builds, although rolling prints it twice; on v1.7.4 the `File does not exist` line is in `other`.
- Name mismatch: one diagnostic.
- Missing file: one diagnostic (`Cannot find the specified file`), the `File does not exist` line in `other`.
- 4802 ("Non-unique fields in constructor."): one `error` (D55). The two stuttering lints: one `error` each.
- Two files on one command line: two banners, and the second file's errors are found.
- The PlusCal "changed since its last translation" warning (`sany-stale-alg`, `sany-stale-tla`, `sany-stale-both`, `sany-stale-two-files`): one `warning` each with its module and the text as printed, in v1.7.4's `!! WARNING` form and in rolling's block form.
- The help text (`sany-help`, `sany-h`; on v1.7.4 `Illegal switch: -help`), grouped flags refused (`-dl`), no arguments on rolling: no diagnostics, every non-empty line in `other`.

Properties, over every file of the two folders (parametrised by globbing):

- The lines whose `SanyStep.line_class` is `OTHER`, in order, equal `result.other`, and `result.lines_used` plus their number is the number of lines fed.
- Every diagnostic returned by a step is in `result.diagnostics`, in the same order, and none is there twice.
- Feeding each line with `\n`, without it, and with `\r\n` gives equal results.
- Driving the parser the way the old runner did, reading `result` after every line, changes nothing: the diagnostics at the end are the same. This is the roadmap's "flushed after every line" defect as a test.
- `to_dict()` passes `json.dumps` and holds only JSON types, and `SanyResult.from_dict(r.to_dict()) == r`.

Unit: the lines of one error block of a golden file fed twice in a row give the diagnostic once (P8: "feeds one diagnostic twice and gets it once"); the lines are taken from the file, not typed (T12 rule 3).

Not in this package: the class of every line as part of a stored expected result (P8: "for every SANY golden file the classes are part of the expected result"). That is a file per case, written by package 15 (15e) from this parser and reviewed against the capture.

Row R31: the tests headed "Golden, SANY alone" are its test (errors and warnings, each with its module and range, on both builds); the pull request names the row.

Written first ([01 T3](../design/01-testing.md#t3-golden-files), [21 S5](../design/21-other-tools.md#s5-golden-files-for-sany-and-pluscal), question Q18): `facts.py` holds TLC facts only, so the list "Golden, SANY alone" is written as tests in `test_sany.py`, from reading the captures, committed before the parser, and the pull request shows that run red (T12 rule 6). No `pending` marker is involved. The facts of the TLC cases that contain SANY text (`sany-semantic-error`, `parse-error`, the `stale-*-tool` captures, 4802 inside TLC) stay pending until 13.

Old tests: none are left (03b).

## Changelog

None in this package. P8's entry ("Fixed: A SANY error was reported twice, and TLC messages printed after it were shown as part of it.") describes `tlaup tlc` after the switch; package 39 writes it. What `tlaup sany` prints is the changelog of package 41.

## Context for the worker

- **State of `main`.** `tlaup_parse` has the model; `framing.py`, `codes.py` and `parse_value` may or may not be merged, and this package uses none of them. The old `src/tlaup/tlc/sany.py` is in use and stays untouched.
- **What is carried over from the old `sany.py`: the location pattern, and nothing else.** The old parser looks for the location anywhere in a line, never leaves a block once it is in one, keeps the newline, has no notion of a parse-error tail or an abort block, and returns errors and warnings from two getters that flush. The new one is P8's two tables.
- **Facts about SANY's output a worker could miss** (P8, from the captures):
  - SANY gives a module name, never a file name; the file comes from the `Parsing file` lines. The rolling build adds ` (jar:file:...)` after the path of a standard module.
  - `Linting of module M` is rolling only, and is what ends a warning block there.
  - The abort block differs by build: v1.7.4 prints `tla2sany.semantic.AbortException`, `*** Abort messages: 1`, `Unknown location` (or `In module X`) and the message; rolling prints `In module X` and the message, then `*** Errors: 1` and both again.
  - In a parse error's tail rolling prints `Could not parse module ...` twice.
  - Every capture has an empty line between a position line and its message.
  - v1.7.4's text for the "both changed" PlusCal warning is misspelt; every text is kept as printed.
  - The rolling `-help` page carries ANSI bold codes (ESC `[1m`); they are part of its `OTHER` lines.
- **The one stderr line.** SANY alone writes everything to stdout except `File does not exist: ...` (v1.7.4: for a missing module and a missing file; rolling: for a missing file only). `tlaup sany` reads both streams through one pipe, so the parser sees one stream. The golden files of these cases are research 12's, captured that way (T3's placements 1 and 2: research 22's re-runs and its two SANY cases with a separate `.err` stay as evidence), so the tests that expect the line in `other` read it there.
- **What was and was not checked before.** The script run of 2026-11-15 covered research 12's captures. The warning block, the `!! WARNING` line, v1.7.4's level errors, 4802 as its own capture and the help pages were captured later by research 22 and were not run through the script; the golden tests here are their first check. If a capture contradicts a row of the tables, do not bend the test: say so in the pull request (the capture wins, and the design needs a line).
- **Decisions.** D55: 4802 and the stuttering lints are errors, so that `tlaup sany` and `tlaup tlc` return 150 for the same spec (D29). D9: a line the state machine does not know is `OTHER` and is shown as printed, so a new shape degrades to plain text. D19: two builds are supported; both golden folders must pass.
- **The parser does no I/O and knows no command line.** When a diagnostic's module was never announced, `file` stays `None`; the `sany` command fills it (package 41).
- **Windows (D15):** paths in `Parsing file` lines are kept as text; nothing splits them except taking the file name's stem as the module name, which must work for `\` as well as `/`.

## Done when

- `test_sany.py` passes on both golden folders; `uv run poe lint` and `uv run poe test` pass; CI is green; the pull request names row R31.
- The first commit adds the golden assertions, and the pull request shows the red run.
- The import-isolation test of 09 still passes.
- No changelog entry; no document to update.

## Out of scope

- The SANY window inside a TLC run, `DiagnosticFound` events, `RunResult.sany` and `sany_lines_used`: [13](13-tlc-parser.md).
- The `tlaup sany` command, its exit code 150, the editor form `path:line:col: severity: message`, and paths relative to the working folder: 41 ([21 S1](../design/21-other-tools.md#s1-sany)).
- `PcalParser` and the PlusCal golden tests: 14.
- The expected result files for the SANY cases, with the class of every line: 15.
- Deleting `src/tlaup/tlc/sany.py`: 39.

## Risks

- From P8: SANY's text is free-form and differs between builds; unknown lines are kept, not dropped, so a new shape degrades to "shown as printed".
- From P8: the tables were checked by script on research 12's captures only; research 22's captures meet them here for the first time.
