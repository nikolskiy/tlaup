# 14. The PlusCal parser

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup_parse.PcalParser` reads the PlusCal translator's output one line at a time and gives a `PcalResult`: the translator's version, the files it says it wrote, the labels it added, its errors as diagnostics, and every line it did not recognise, in order. It passes the golden tests over the PlusCal captures of both builds, and `PcalResult` has a dictionary form for the expected files of [15](15-golden-expected-results.md).

## Covers

- Roadmap items:
  - "Golden-file tests for SANY and PlusCal output per TLC version; passthrough after `--` for each." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 306), in part: the PlusCal golden tests. The SANY tests are [12](12-sany-parser.md); the move of the captures is [07](07-golden-files.md); the full expected results are 15; passthrough is tested in the feature files of [41](41-sany-command.md) and [42](42-pcal-command.md).
  - "`pcal` command: run the PlusCal translator; passthrough for its flags." (milestone 1b, line 299), in part: the parser the command feeds. The command is 42.
  - "Move the parser stack ... into its own import package that imports nothing from `tlaup`" ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: `pcal.py`, the one module of [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package)'s table that is new. See [09](09-parse-package-and-model.md).
- Design sections:
  - [21 S2](../design/21-other-tools.md#s2-pcal), step 3 only: `PcalResult` and what the parser recognises. Steps 1, 2, 4 and 5 (the command, its printing, its exit code) are 42.
  - [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package): `PcalParser` of the public surface, and the package's rules.
  - [21 S5](../design/21-other-tools.md#s5-golden-files-for-sany-and-pluscal): the PlusCal row of its table, as tests. The SANY row is 12; the full expected results are 15.

## Depends on

- [09](09-parse-package-and-model.md): `Diagnostic`, `Location`, their `to_dict()`; the package skeleton, `__init__.py`, the import-isolation test.
- [07](07-golden-files.md): `tests/parse/golden/pcal/v1.7.4/` and `pcal/2026.11.15.002146/`, one `.out` per case (the command line, `[exit=N]` and the `-- files before/after:` lines removed) and a `cases.toml` with `files_before` and `files_after`.

Unchanged from the draft. Not a dependency: [08](08-golden-facts.md), which decided that `tests/parse/facts.py` holds TLC facts only; the per-case PlusCal assertions are written here, red first. If 08's `tests/parse/drive.py` is on `main` (it should be, since 08 runs early in the track), use its `read_lines`; nothing else of 08 is needed. This package imports nothing from `tlaup` and runs beside [10](10-framing-and-codes.md) to [13](13-tlc-parser.md).

## Files

Creates:

- `src/tlaup_parse/pcal.py`: `PcalParser`, `PcalResult`.
- `tests/parse/test_pcal.py` (named in [01 T3](../design/01-testing.md#t3-golden-files)'s layout).

Changes:

- `src/tlaup_parse/__init__.py`: export `PcalParser` and `PcalResult`.

Deletes: nothing. Nothing in `src/tlaup` parses PlusCal output today.

Shared with 10, 11, 12 and 13, which run beside this package: `src/tlaup_parse/__init__.py` (one import line and two `__all__` entries).

## Interfaces

Provides, from [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package) and [21 S2](../design/21-other-tools.md#s2-pcal):

```python
# tlaup_parse/pcal.py
class PcalParser:
    def feed(self, line: str) -> list[Diagnostic]: ...    # one line, with or without its ending; the diagnostics it completed
    def close(self) -> list[Diagnostic]: ...              # end of input: the diagnostic still open, if any
    @property
    def result(self) -> PcalResult: ...

@dataclass
class PcalResult:
    version: str | None
    files_written: list[str]              # from "New file X written."
    labels_added: list[tuple[str, int, int]]
    diagnostics: list[Diagnostic]         # tool="pcal"
    other: list[str]                      # lines not recognised, kept

    def to_dict(self) -> dict[str, object]     # written by stage 4
```

**What is recognised** (S2, step 3). Each line is first stripped of its line ending and of trailing white space; the stripped line is what `other` and a message hold. In the order of the translator's output:

| Line | Effect |
| --- | --- |
| The banner, `pcal.trans Version <text>` | `version` is `<text>` as printed: `1.11 of 31 December 2020` (v1.7.4), `1.12 of 01 July 2024` (rolling). |
| `Parsing completed.`, `Translation completed.` | Nothing is kept. |
| `New file <X> written.` | `<X>` is appended to `files_written`, as printed (`Pcal.tla`, then `Pcal.cfg`). |
| `The following label was added:` | Opens the label block. Each following line of the form `<name> at line <L>, column <C>` (indented in the captures) appends `(name, L, C)` to `labels_added`; the first line of another form ends the block and is read as a line of its own. |
| `Unrecoverable error:` | Opens the error block. |
| ` -- <message>`, directly after `Unrecoverable error:` | Opens a diagnostic with that message (the leading ` -- ` taken off, the rest as printed). |
| `line <L>, column <C>.` or `at line <L>, column <C>.`, with any indent, directly after the ` -- ` line | Gives the open diagnostic its location and completes it. |
| Any other line | Completes an open diagnostic, if any, and is then appended to `other`, except an empty line (next row). |
| An empty line | Completes an open diagnostic, if any. Appended to `other` only when the line before it was appended to `other`; otherwise dropped. |

"Completes": the open diagnostic is returned by the `feed` or `close` call that completed it and appended to `result.diagnostics`.

A diagnostic is `Diagnostic(tool="pcal", severity="error", message=..., module=None, file=None, location=..., details=())`: the translator's output names no file and no module (research 12: "Errors give a line and column but no file"). Its `location`, when the message had one, is `Location(module="", line=L, column=C, end_line=None, end_column=None)`; without one, `None`. Written by stage 4: `Location.module` is a `str` in [10 P3](../design/10-parser.md#p3-result-model) and the translator gives none, so it is the empty string (see the report; the alternative is an optional `module` in 09's model). The command fills in the file from its own command line (42), as `tlaup sany` does for a diagnostic whose module was never announced.

The message is kept as printed, the doubled full stop included (`... --algorithm not found..`): trimming it is a rule of how the command prints (S2, step 4), and the result is what the translator wrote. So is a message's case and spelling.

**Written by stage 4, each from what the design says in words or from the captures:**

- **The empty-line rule** is P8's rule for SANY ([10 P8](../design/10-parser.md#p8-sany-output): "an empty line is `OTHER` only directly after an `OTHER` line"), taken over because S2 says nothing about empty lines. Without it every empty line around an error block would be "not recognised" and printed by the command; with it the help text (`pcal-help`) keeps its paragraphs and the empty lines around the banner and the error block vanish. No look-ahead.
- **A message on more than one line** (`pcal-spec`: ` -- Could not find resource file Foo.tla.` and two indented lines after it). S2 recognises one ` -- ` line and an optional location line, so the two continuation lines complete the diagnostic and are `other`; the command prints them as written, after the diagnostic, in the order the translator wrote them. Joining them to the message would be a rule the design does not have (see the report).
- **`Wrote file AST.tla.`** (`-writeAST`, `-spec`) is not `New file X written.` and is not recognised: it is `other`, and `files_written` stays empty. That is what S2's list says; the command prints it as written.
- **`result.other` grows as lines are fed.** It is a plain list on the result, not a copy, so a caller can tell after each `feed` which lines were not recognised: the ones that call appended. Package 42 relies on this to print unrecognised lines in their place among the diagnostics, since `feed` returns diagnostics only. Keep it so, or say in the pull request what replaces it.
- **`to_dict()`**, for package 15's expected files, as package 12 wrote `SanyResult.to_dict()`: `{"version": ..., "files_written": [...], "labels_added": [[name, line, column], ...], "diagnostics": [<Diagnostic.to_dict()>, ...], "other": [...]}`, JSON types only, nothing left out when empty or `None`. No `from_dict`: no test needs one.

Consumes: `Diagnostic`, `Location` ([09](09-parse-package-and-model.md)).

Used by: package 42 (`tlaup pcal` feeds the merged output and prints the diagnostics, the unrecognised lines and the notes for `files_written`), package 15 (the expected files).

## Tests that must pass

`tests/parse/test_pcal.py`, plain pytest over `tests/parse/golden/pcal/<build>/`, each file read in binary, split into lines that keep their ending, decoded as UTF-8 with `errors="replace"`, fed one line per call, then `close()` (T3, "How the parser is driven"). Case ids are the ones package 07 gave in `cases.toml` (the research 12 file names without `.txt`).

The per-case assertions, written from reading the captures and committed before the parser, so that the pull request shows them failing first ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 6). S5's PlusCal row, on both builds unless said:

- Success (`pcal-good`): `version` is the build's banner text; `files_written == ["Pcal.tla", "Pcal.cfg"]`; no diagnostic; `other` empty.
- `-nocfg` (`pcal-nocfg`): `files_written == ["Pcal.tla"]`.
- Syntax error (`pcal-syntaxerr`): one diagnostic, message `Expected "do" but found ":="`, line 6, column 20; `files_written` empty.
- Assignment to an undeclared variable (`pcal-semerr`): one diagnostic, message `Assignment to undeclared variable y`, line 6, column 6 (the `at line` form).
- No algorithm (`pcal-noalg`): one diagnostic with no location, its message ending in `not found..` as printed.
- Missing label (`pcal-nolabel`): one diagnostic, `Missing label at the following location:`, line 7, column 3.
- `-label -reportLabels` (`pcal-label`): `labels_added == [("Lbl_1", 7, 3)]`, then the two files written, no diagnostic.
- Missing file (`pcal-nofile`): one diagnostic with no location; its text differs by build (`Command-line error: Input file Nope.pcal and Nope.tla.tla not found..` on v1.7.4, `Input file Nope.tla not found.` on rolling).
- Unknown option (`pcal-badopt`): one diagnostic with no location, `Command-line error: Unknown command-line option: -bogus..`.
- `-writeAST` (`pcal-writeast`): no diagnostic, `files_written` empty, `other == ["Wrote file AST.tla."]`.

The other cases 07 moves, so that no capture goes unread: `pcal-err`, `pcal-noext`, `pcal-wf`, `pcal-proc-wf`, `pcal-termination` (two files written, no diagnostic); `pcal-noargs` (one diagnostic, `Command-line error: No arguments specified..`); `pcal-spec` (one diagnostic `Could not find resource file Foo.tla.` with no location, and `Wrote file AST.tla.` and the two continuation lines in `other`, in that order, with the empty line that follows `Wrote file AST.tla.` and the one that follows the last continuation line, which the rule keeps); `pcal-help` (no diagnostic, `version` set, every non-empty line after the banner in `other`, and the empty lines between its paragraphs too).

Properties, over every file of both folders (parametrised by globbing, so a new capture is covered without editing the test):

- Feeding each line with `\n`, without it, and with `\r\n` gives equal results.
- Every diagnostic returned by a `feed` or `close` call is in `result.diagnostics`, in the same order, and nothing else is there.
- Driving the parser while reading `result` after every line changes nothing.
- The files a case says it wrote were there afterwards: for every case whose `cases.toml` entry has `files_after`, each name in `files_written` is in `files_after`. This checks the parser against a record made apart from the output, by the research script.
- `json.dumps(result.to_dict())` succeeds and the dictionary holds only JSON types.

No unit test of hand-typed translator output: tool output is captured, never typed (T12 rule 3).

Old tests: none. `pending` markers: none apply (08 wrote no PlusCal facts).

## Changelog

None. What `tlaup pcal` prints is the changelog of package 42.

## Context for the worker

- **State of `main`.** `tlaup_parse` has the model and may have framing, values and the SANY parser; this package uses none of them except `Diagnostic` and `Location`. `src/tlaup/` has nothing for PlusCal.
- **Facts about the translator's output** (research 12, restated so that no research file is needed): all its text is on stdout; stderr was empty in every run (research 22 recorded the streams apart and found the same). Success exits 0, failure 255; `-writeAST` exits 255 after succeeding. Errors carry a line and column, or nothing, never a file. Every one-line error ends in two full stops, because the translator appends one to a message that already has one. The banner differs by build; everything else in the captures is the same text on both builds except the missing-file message. `-label -reportLabels` was captured with one label only: the header for several labels was never seen, and the parser recognises only the captured header. A different header is then `other`, which the command prints as written (D9: a new shape degrades to plain text).
- **The rules of the package** ([10 P2](../design/10-parser.md#p2-the-tlaup_parse-package)): standard library only; no import of `tlaup`, `rich`, `typer`, `pydantic`; no file, network, clock or environment access. The parser does not know the spec's name and does not look for the files it reads about.
- **Decisions.** D9: a line the parser does not recognise is kept and shown, so `other` must hold every such line in order. D19: two builds, both folders must pass. D29: the command passes the translator's exit code through; the parser does not see it.
- **If a capture contradicts the table above**, the capture wins: do not bend a test; say so in the pull request, and the table needs a line.
- **Windows (D15):** nothing here touches paths; `\r\n` endings are covered by the property above.

## Done when

- `tests/parse/test_pcal.py` passes on both golden folders; `uv run poe lint` and `uv run poe test` pass; CI is green.
- The pull request shows the per-case assertions failing before the parser was added.
- The import-isolation test of 09 still passes (it walks the package, so it covers `pcal.py` without an edit).
- `PcalResult.to_dict()` exists, so that package 15's PlusCal half does not wait.
- No changelog entry; no document to update.

## Out of scope

- The `tlaup pcal` command: running the translator in the spec's folder, the editor form with the spec's path, trimming the doubled full stop, the notes on stderr, the exit code, `pcal.feature`: [42](42-pcal-command.md).
- The expected `<case>.json` files for the PlusCal cases: [15](15-golden-expected-results.md).
- Moving the captures and writing `cases.toml`: [07](07-golden-files.md).
- The integration test that runs the real translator on a copy of a PlusCal spec, on both builds: [52](52-integration-tests.md).

## Risks

- From S2: the `chksum` and the order of `VARIABLES` in the translation differ between builds; tlaup does not read the translated file, so only the golden outputs differ per build.
- From the captures: 18 cases per build, several with the same few lines. A shape the research did not run (several labels, a message on three lines of another kind, a warning) reaches the user as unrecognised lines printed as written, not as a diagnostic.
- From the cut: the empty-line rule and the reading of continuation lines are stage 4's; if the maintainer answers the report's question otherwise, the change is a few lines here and the regenerated expected files of 15.
