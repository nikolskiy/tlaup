# 09. The tlaup_parse package and its result model

Size: M. Suggested model: most capable. Status: ready.

## Goal

A second import package, `src/tlaup_parse/`, exists beside `tlaup`, ships in the same wheel, imports nothing from `tlaup` and holds the whole result model: `RunResult` and its parts with `to_dict()` and `from_dict()`, the twenty events, and `describe_exit_status`. No parser is in it yet and nothing in `tlaup` imports it.

## Covers

- Roadmap items:
  - "Move the parser stack (message framing, codes, values, models, SANY parser) into its own import package that imports nothing from `tlaup`" ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: this package makes the import package and its model. [10](10-framing-and-codes.md) adds framing and codes, [11](11-values.md) values, [12](12-sany-parser.md) the SANY parser, [13](13-tlc-parser.md) the TLC parser, 14 the PlusCal parser; package 39 deletes the old modules under `src/tlaup/tlc/`.
  - `describe_exit_status` has no open item of its own in milestones 1 to 2. It is the part of milestone 4's "Exit codes" item ("the meaning of TLC's code printed and included in JSON") that [02 X1](../design/02-cross-cutting.md#x1-exit-codes) says is built in milestone 1b, and the result line of [22 O3](../design/22-reporters.md#o3-terminal-reporter) needs it.
- Design sections:
  - [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package): the package itself, its rules, `pyproject.toml`, the import-isolation test, `ExitStatus`. The modules `framing.py`, `codes.py`, `tlc.py`, `sany.py` and `pcal.py` of P2's table are packages 10, 12, 13 and 14; `values.py` is started here (the `Value` type) and finished in 11.
  - [10 P3](../design/10-parser.md#p3-result-model): every type and every event. How `status` and `verdict` are *set* is the parser's work, package 13; this package defines the types and their defaults.
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes): only the paragraph "The meaning of a code" and its table of codes, words and meanings (question Q4, decision D63). The exit-code scheme of tlaup itself is packages 02 and 17.

## Depends on

- [03](03-test-foundation.md): the pytest settings of [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings) (`--strict-markers`, `filterwarnings = error`, `testpaths = ["tests"]`, the coverage section), the autouse isolation fixture, and the mechanical checks of [01 T12](../design/01-testing.md#t12-rules-for-writing-tests). Nothing from `src/tlaup` is used.

Changed from the draft: nothing. This package needs neither the golden files (07) nor the facts (08).

## Files

Creates:

- `src/tlaup_parse/__init__.py`: exports the public names this package defines (listed under Interfaces). Everything else in the package is private.
- `src/tlaup_parse/py.typed`: empty.
- `src/tlaup_parse/model.py`: the P3 types and the events.
- `src/tlaup_parse/values.py`: the `Value` dataclass only, with its `to_dict()` and `from_dict()`. Written by stage 4: P3's `Variable` has a field of type `Value`, so the type must exist before package 11; 11 adds `parse_value` to this file. The design puts `Value` in `values.py` ([10 P7](../design/10-parser.md#p7-values)), so it is not moved into `model.py`.
- `src/tlaup_parse/exit_status.py`: `ExitStatus`, `describe_exit_status`.
- `tests/parse/test_import_isolation.py`, `tests/parse/test_model.py`, `tests/parse/test_exit_status.py`. The layout of [01 T3](../design/01-testing.md#t3-golden-files) lists no file for these three tests; the names are stage 4's. Create `tests/parse/` (with an `__init__.py` if the other test folders have one at that time) when package 07 has not made it yet.

Changes:

- `pyproject.toml`:
  - `[tool.setuptools.package-data]` gets `tlaup_parse = ["py.typed"]`. `[tool.setuptools.packages.find]` already has `include = ["tlaup*"]`, which matches `tlaup_parse`; check it, change nothing.
  - Coverage: `[tool.coverage.run] source` must name `tlaup` and `tlaup_parse` (T10). Package 03 writes that section; if it left `tlaup_parse` out because the package did not exist, add it here.
  - mypy: today the task is `mypy .` with `exclude = ["build", "tests/"]`, which already checks `src/tlaup_parse` in strict mode. If an earlier package changed it to name packages, name both.
  - The `lint-bandit` task runs `bandit ... -r src/tlaup`; add `src/tlaup_parse`. The design does not mention bandit; this follows from "a second top-level package" and is said in the pull request.
- `.pre-commit-config.yaml`: the bandit hook has the same `-r src/tlaup`; add `src/tlaup_parse`.
- `MANIFEST.in`: add `include src/tlaup_parse/py.typed` beside the line for `src/tlaup/py.typed`.
- `docs/contributing/development.md`: one line in the code map for `src/tlaup_parse/` (what it is, that it imports nothing from `tlaup`).

Deletes: nothing. `src/tlaup/tlc/models.py`, `codes.py`, `values.py`, `parser.py` and `sany.py` stay as they are until package 39.

Shared with other packages of the parser track: `src/tlaup_parse/__init__.py` (10, 11, 12, 13 and 14 each add their own export lines; a conflict is one import line and one entry of `__all__`), and `pyproject.toml` (03, 07 and the build package 56 touch other sections; this package adds one package-data line and at most one word to two lists).

## Interfaces

Provides. All signatures are copied from [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package) and [10 P3](../design/10-parser.md#p3-result-model) unless marked "written by stage 4". Read P3's code block for the comment on every field; it is the specification and is not repeated here.

**`model.py`, the result types** (plain dataclasses, standard library only):

| Type | Frozen | Fields, in P3's order |
| --- | --- | --- |
| `RunResult` | no | `tool`, `mode`, `workers`, `phase`, `status`, `verdict`, `resumed`, `counts_approximate`, `errors`, `warnings`, `sany`, `module_files`, `overrides_loaded`, `progress`, `stats`, `coverage`, `output`, `output_dropped`, `unframed_lines`, `sany_lines_used`, `unknown_messages`, `info`, `started`, `finished`, `duration_ms` |
| `Phase` (Enum) | | `NOT_STARTED`, `PARSING`, `STARTING`, `INITIAL_STATES`, `CHECKING`, `LIVENESS`, `FINISHED` |
| `Status` (Enum) | | `RUNNING`, `SUCCESS`, `FAILURE`, `INTERRUPTED` |
| `Verdict` (Enum) | | `ERRORS`, `NO_ERROR`, `NO_ERROR_BOUNDED`, `INCOMPLETE`, `NOT_CHECKED` |
| `ErrorKind` (Enum) | | `invariant`, `deadlock`, `property`, `assertion`, `assumption`, `postcondition`, `evaluation`, `config`, `parse`, `exception`, `usage`, `other` (these are the dictionary values; twelve members) |
| `ToolInfo` | yes | `version`, `revision`, `date`, `line`, `raw` |
| `TlcMessage` | yes | `code`, `severity`, `name`, `body`, `before = ""`, `after = ""`, `truncated = False`; properties `lines` and `nested`; method `text_lines()` |
| `TlcError` | no | `kind`, `name`, `message`, `related`, `trace` |
| `Trace` | no | `states`, `loop_to`, `stuttering` |
| `TraceState` | yes | `index`, `action`, `location`, `header`, `variables`, `lines` |
| `Variable` | yes | `name`, `value`, `raw`, `printed = True` |
| `Location` | yes | `module`, `line`, `column`, `end_line`, `end_column` |
| `Progress` | yes | `diameter`, `generated`, `distinct`, `queue`, `at` |
| `FinalStats` | yes | `total_states`, `distinct_states`, `queue`, `state_depth`, `collision_probability`, `outdegree` |
| `CoverageItem` | yes | `kind`, `name`, `location`, `sub_location`, `count`, `distinct`, `depth` |
| `Diagnostic` | yes | `tool`, `severity`, `message`, `module`, `file`, `location`, `details = ()` |

`TlcError` and `Trace` are not frozen because the parser appends to `related` and `states` and sets `trace`, `loop_to` and `stuttering` while the run goes; `RunResult` is not frozen because the parser fills it and the runner sets `status = INTERRUPTED`, `counts_approximate` and, in the cases P3 names, `verdict = INCOMPLETE`.

Defaults of a fresh `RunResult()` (written by stage 4 where the design gives none): every optional field `None`, every list and dict empty, the counters 0, `resumed` and `counts_approximate` false, `phase = NOT_STARTED`, `status = RUNNING` ("`RUNNING` from the start", P3), `verdict = INCOMPLETE`. P3 says the parser decides the verdict at `close()` and does not say what the field holds before; `INCOMPLETE` is what P3's verdict table gives for a result with no error and no finish message, so a fresh result already agrees with the table.

**`TlcMessage`'s three readers** are pure functions over `body` and belong to this package although P4 specifies one of them:

- `lines`: the `str` items of `body`, in order.
- `nested`: the `TlcMessage` items of `body`, in order.
- `text_lines()`: the text as it reads with the markers taken out ([10 P4](../design/10-parser.md#p4-framing-and-never-losing-output), "Reading a message's text"): the items of `body` in order, a nested message contributing its own `text_lines()` with its `before` put in front of its first line and its `after` behind its last. The top-level message's own `before` and `after` are not part of it. Written by stage 4, since P4 does not say: a nested message with no lines and a non-empty `before` or `after` contributes one line, `before + after`; with all three empty it contributes nothing. No capture has either.

**`values.py`**, the type only ([10 P7](../design/10-parser.md#p7-values)):

```python
@dataclass(frozen=True)
class Value:
    kind: str  # "int", "bool", "string", "model", "set", "seq", "record", "function", "interval", "raw"
    text: str  # field(compare=False)
    items: tuple["Value", ...] = ()
    fields: tuple[tuple[str, "Value"], ...] = ()
    pairs: tuple[tuple["Value", "Value"], ...] = ()
    scalar: int | bool | str | None = None
    bounds: tuple[int, int] | None = None
```

**The dictionary form.** Every type above has `to_dict()` giving only JSON types (dict with string keys, list, str, int, bool, None; no float is needed). Rules, the first three from P3, the rest written by stage 4 from them:

- Keys are the field names, except in `FinalStats`, where `total_states`, `distinct_states` and `state_depth` are written `totalStates`, `distinctStates` and `stateDepth` (the tlaplus/Examples manifest's names).
- `Verdict` is written `"errors"`, `"no-error"`, `"no-error-bounded"`, `"incomplete"`, `"not-checked"`; `Status` as `"running"`, `"success"`, `"failure"`, `"interrupted"`; `ErrorKind` as its word; `mode` is already a string.
- `Phase` has no dictionary values in the design. Use the member names in lower case with hyphens, as `Verdict` does: `"not-started"`, `"parsing"`, `"starting"`, `"initial-states"`, `"checking"`, `"liveness"`, `"finished"`.
- A tuple or list becomes a list; an item of `TlcMessage.body` is a string or the nested message's dictionary; `Value.fields` and `Value.pairs` become lists of two-item lists; `bounds` a two-item list or `None`.
- Nothing is left out when it is empty or `None`: the expected files of package 15 then show every field.
- `from_dict(data)` is a class method on `RunResult` (and on whatever parts it needs) with `RunResult.from_dict(r.to_dict()) == r`. P3 names it only in its Tests paragraph; the signature is stage 4's. `Value.text` is not compared but must survive the round trip all the same, since reporters print it.

**The events** ([10 P3](../design/10-parser.md#p3-result-model), the table under "Events"). Each is a small frozen dataclass. The members of `Event`, one by one, written by stage 4 from P3's table (design 03 leaves them to the packages):

```python
@dataclass(frozen=True)
class VersionSeen:
    message: TlcMessage
    tool: ToolInfo


class ModeSeen:
    message: TlcMessage
    mode: str | None
    workers: int | None


class PhaseChanged:
    message: TlcMessage
    phase: Phase


class ProgressMade:
    message: TlcMessage
    progress: Progress


class OutputLine:
    line: str  # no message


class DiagnosticFound:
    diagnostic: Diagnostic  # no message


class ErrorOpened:
    message: TlcMessage
    error: TlcError


class ErrorExtended:
    message: TlcMessage
    error: TlcError


class TraceStateAdded:
    message: TlcMessage
    error: TlcError
    state: TraceState


class TraceClosed:
    message: TlcMessage | None
    error: TlcError
    trace: Trace


class WarningFound:
    message: TlcMessage


class OverrideLoaded:
    message: TlcMessage
    operator: str
    java_class: str


class CoverageAdded:
    message: TlcMessage
    item: CoverageItem


class StatsUpdated:
    message: TlcMessage
    stats: FinalStats


class CheckpointStarted:
    message: TlcMessage
    folder: str


class CheckpointWritten:
    message: TlcMessage


class Recovered:
    message: TlcMessage
    examined: int | None
    queued: int | None


class Information:
    message: TlcMessage


class UnknownMessage:
    message: TlcMessage


class Finished:
    message: TlcMessage
    duration_ms: int | None
    finished: str | None


Event = (
    VersionSeen
    | ModeSeen
    | PhaseChanged
    | ProgressMade
    | OutputLine
    | DiagnosticFound
    | ErrorOpened
    | ErrorExtended
    | TraceStateAdded
    | TraceClosed
    | WarningFound
    | OverrideLoaded
    | CoverageAdded
    | StatsUpdated
    | CheckpointStarted
    | CheckpointWritten
    | Recovered
    | Information
    | UnknownMessage
    | Finished
)
```

`message` is always the top-level message, with its nested messages inside it. `TraceClosed.message` is the one point the table leaves open: it is the 2122 or 2218 message when that is what closed the trace, and `None` when the trace was closed by the arrival of another message or by `close()` (that other message has its own event). Events that hold a `TlcError` or a `Trace` hold the live object of the result, not a copy. Events have no `to_dict()`: the JSON result of milestone 4 is the `RunResult`.

**`exit_status.py`** ([10 P2](../design/10-parser.md#p2-the-tlaup_parse-package), [02 X1](../design/02-cross-cutting.md#x1-exit-codes)):

```python
@dataclass(frozen=True)
class ExitStatus:
    code: int
    word: str        # X1's word for the code; "failure" = TLC checked and found something wrong,
                     # "error" = TLC could not check (D63); milestone 4's JSON carries it
    meaning: str     # X1's sentence for the code; the result line of 22 O3 prints it beside the verdict
    known: bool      # False for a code X1's table does not hold

def describe_exit_status(code: int) -> ExitStatus
```

The table is X1's, "The meaning of a code", settled with the maintainer (question Q4, decision D63): one row per code 0, 1, 10 to 14, 75 to 77, 150 to 153 and 255, each with its word, its meaning and `known` true, the words and meanings copied exactly as X1 writes them (75, 76 and 77 share the word `evaluation failure` and differ in the meaning; 1 is `usage error` and its meaning says the JVM also returns 1; 152 and 153 carry upstream's names). Any other integer gives `known = False`, the word `error` and the meaning `TLC returned a code it does not document.`: nobody can say of an undocumented code that something was checked and found wrong (X1, settled 2026-11-24). Write the table as data in `exit_status.py`, one entry per row; the function looks the code up and never raises. The postcondition wording of 10 is the terminal reporter's (22 O3), not a second row here.

Consumes: nothing from another package.

## Tests that must pass

Plain pytest in `tests/parse/`. No golden file is read by this package.

- `test_import_isolation.py` (P2's test): start `sys.executable -c ...` (not `python`: the isolation fixture leaves only the fakes on `PATH`) with a `sys.meta_path` finder, put first, that raises `ImportError` for the top-level names `tlaup`, `rich`, `typer`, `pydantic`, `requests` and `yaml`; the child imports `tlaup_parse` and then every module of the package (walk the package, so a module added by packages 10 to 14 is covered without touching the test), and exits 0. A second case proves the test can fail (T12 rule 6): the same child with the hook told to refuse `dataclasses` exits non-zero.
- `test_model.py`:
  - `to_dict()` of a `RunResult` built by hand so that every type and every optional branch occurs (an error with a trace, a nested message with `before` and `after`, a truncated message, a `Value` of each kind, a diagnostic with details) contains only JSON types, checked by a recursive walk, and passes `json.dumps`.
  - `RunResult.from_dict(r.to_dict()) == r` for the same result and for `RunResult()`.
  - The key and value rules: `totalStates`, `distinctStates`, `stateDepth` in `FinalStats`; the five verdict words; the four status words; the phase words.
  - `Value` equality ignores `text` and compares `scalar`: two `raw` values with different `scalar` are unequal.
  - `TlcMessage.lines`, `nested` and `text_lines()` on messages built in the test from abstract lines (`"a"`, `"b"`): order kept; a nested message's `before` in front of its first line and `after` behind its last; nesting two deep. These use made-up lines on purpose and no marker text: real output is tested in package 10 against the captures (T12 rule 3).
  - Defaults of `RunResult()` as listed under Interfaces.
  - The union `Event` has exactly the twenty members above (a test over `typing.get_args(Event)`), so a member added later without a reporter case is noticed here as well as by mypy.
- `test_exit_status.py` ([10 P2](../design/10-parser.md#p2-the-tlaup_parse-package)'s test, which X1 points to): parametrised over every row of X1's table, copied once into the test, each code returns that row's word and meaning with `known` true; codes the table does not hold (3, 99, 130, -1) give `known` false, the word `error` and the meaning above; `code` is returned unchanged; the function never raises for any integer. A change to the table or to the test without the other makes it fail.

Old tests: none are left (03b). Preserved-behaviour rows: none is this package's.

`pending` markers: this package removes none. Every fact of `tests/parse/facts.py` is an assertion on a parsed result, and no parser exists yet.

## Changelog

None in this package. P2's entry ("Changed: The TLC output parser is now the import package `tlaup_parse`, shipped with tlaup. `tlaup.tlc.parser`, `tlaup.tlc.models`, `tlaup.tlc.values`, `tlaup.tlc.codes` and `tlaup.tlc.sany` are gone.") is true only when the old modules are deleted, so package 39 writes it. P3's entry is "With P2".

## Context for the worker

- **State of `main`.** The old parser stack (`src/tlaup/tlc/parser.py`, `codes.py`, `models.py`, `values.py`, `sany.py`) is in use by `tlc/runner.py`, `tlc/formatter.py`, `tlc/components.py` and `cmd/tlc.py` and stays untouched. Nothing in `tlaup` may import `tlaup_parse` before packages 36 to 39.
- **Carried over from `tlc/models.py`: nothing by name.** The new model is written from P3. What goes: `ModelCheckResult`, `CheckState`, `CheckStatus`, `InitialStateStatItem` (it held progress; now `Progress`), `MessageLine`, `TlaValue` (now `Value`), `ErrorTraceItem` (now `TraceState`), `ErrorInfo` and `WarningInfo` (now `TlcError` and `TlcMessage`), every `file_path`, `trace_file_path`, `process_info`, `workers_count`, and timestamps as `datetime` (P3 keeps TLC's text: it prints local time with no zone).
- **Decisions.** D7 and D39: its own import package in the same wheel, named `tlaup_parse`, so the later split into its own project renames nothing. D8: reporters never parse, so the result must carry everything a reporter needs. D9: nothing is lost, which is why every message event carries its message. D54: the result has a verdict from TLC's messages beside the exit code. D14: no alias for the old module names. D63: the words of the exit-code table ("failure" when TLC checked and found something wrong, "error" when it could not check); they become milestone 4's JSON, so they are copied, never reworded.
- **The rules of the package** (P2): standard library only; no import of `tlaup`, `rich`, `typer`, `pydantic`; no file, network, clock or environment access; plain dataclasses. They hold for every later package of the track; the isolation test is the mechanical half, review the other.
- **`Unframed`** is the framer's type (package 10). Do not name anything `Text`: the reporters use Rich's `Text` (P2).
- **Names are the future JSON schema** (P3, Risks). A worker may adjust a signature under the usual rule, but a renamed field here renames a key of milestone 4's JSON; say every such change in the pull request.
- **mypy strict applies** to the new package. The `Event` union is what the reporters' exhaustiveness check of [22 O3](../design/22-reporters.md#o3-terminal-reporter) rests on, so keep it a plain union of classes, not a base class.
- **Windows (D15):** nothing here touches paths or processes; the isolation test uses `sys.executable` and an argument list.
- **Not designed, do not add:** a JSON schema file, events in JSON, `PcalResult` (package 14), `SanyResult`, `SanyStep` and `SanyLineClass` (package 12), `Unframed` and `CodeInfo` (package 10).

## Done when

- The three test files pass; `uv run poe lint` (ruff, bandit over both packages, mypy strict) and `uv run poe test` pass; CI is green.
- The tests were committed before the code and the pull request shows their red run (T12 rule 6).
- `uv build` was run once by hand and the wheel lists `tlaup_parse/py.typed` and `tlaup_parse/model.py`; the pull request says so. The standing check is [30 I4](../design/30-ci-and-release.md#i4-build-check), package 53.
- The exit-status table holds every row of X1's table, word for word.
- `docs/contributing/development.md` names the new package. No changelog entry.

## Out of scope

- Framing, `Unframed`, `render_framed`, the code table: [10](10-framing-and-codes.md).
- `parse_value`: [11](11-values.md). `SanyParser` and its types: [12](12-sany-parser.md). `TlcParser`, and with it how `status`, `verdict`, `resumed` and every other field is filled: [13](13-tlc-parser.md). `PcalParser` and `PcalResult`: 14.
- The round trip `from_dict(to_dict(r)) == r` over every golden result: [13](13-tlc-parser.md), in `test_golden.py`. The expected JSON files: 15.
- The result line that prints `describe_exit_status` ([22 O3](../design/22-reporters.md#o3-terminal-reporter)): 38. The warning when TLC's code and the verdict disagree, and its unit test (P3, Tests): `print_run_notes` in `cmd/tlc.py`, package 39.
- The build check that the wheel holds `tlaup_parse/py.typed`: 53.
- Deleting the old modules and writing the changelog entry: 39.

## Risks

- From P2: a PyPI project named `tlaup-parse` was not checked for; it is needed only at the split.
- From P3: the names become the JSON schema in milestone 4; renaming is cheap until 0.9.0 ships and costly after.
- From the cut: the model is written before any parser uses it, so a field that turns out awkward shows only in package 13. A change there is a change to this package's types and to `to_dict()`, and belongs in 13's pull request with a line saying so.
- From the cut: `[tool.coverage.run] source` may or may not name `tlaup_parse` when this package starts, depending on how package 03 handled a source package that did not exist yet. Check before assuming.
