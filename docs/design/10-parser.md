# 10. Milestone 1: the parser

Covers the ten parser items of milestone 1. Relies on decisions D7, D8, D9, D19, D39 and research [1](../research/01-tlc-output.md), [2](../research/02-json-traces.md), [12](../research/12-sany-pcal-repl.md), [13](../research/13-override-loading.md). The captured outputs quoted here are in `tests/fixtures/research/01-tlc-output/` today and move to `tests/parse/golden/` ([01 T3](01-testing.md#t3-golden-files)).

State of the code, measured on the real captures on 2026-11-15: the parser extracts 0 trace states from every real trace (`violation` has 4, `deadlock` 3, `liveness-stuttering` 2, `assertion-failure` 3) and splits the one real SANY error into several. How many depends on how the parser is driven: read once at the end it reports 2; driven as the runner drives it, with the errors read after every line, the review of 2026-11-15 counted 11 on v1.7.4 and 10 on rolling (the reviewer's count, not re-run). Coverage, progress, start and finish lines parse correctly.

Revised twice, on 2026-11-15 after the review of the first design wave and on 2026-11-15 and 2026-11-16 after the second check of the revision. The second revision changed the message model so that a message's lines and nested messages keep their order (P3, P4), added the table of events (P3), completed the SANY rules and gave every SANY line a class (P8). What was run for it: the framing rules and the SANY rules as scripts over the research captures, with the results stated in P4 and P8. Nothing else in this document was run.

## P1 Golden files

Roadmap: "Capture real `-tool` output ... as golden files kept with the parser's tests, filed by TLC version ... Add expected parsed results. Drive the parser exactly as the runner does ... These tests should fail first."

The captures of research 1 exist (20 cases per build), and research 22 captured the rest on 2026-11-19 (`-difftrace`, `-dfid`, `-generate`, checkpoints and `-recover`, `ALIAS`, the error kinds that had none, SANY's warning forms; [01 T3](01-testing.md#t3-golden-files) lists them). Revised 2026-11-20 for those captures and decisions D54 and D55; the changes are marked "top-up". Where the files live, how they are driven, the hand-written facts that fail first and the full expected results are designed in T3. This item is done when, for both builds, every TLC case that has a capture has facts and an expected result, and all pass. The facts file holds TLC facts only, since a fact takes a `RunResult`; the SANY and PlusCal cases are checked by those parsers' own tests, written failing first in the same way (P8, [21 S5](21-other-tools.md#s5-golden-files-for-sany-and-pluscal)). (Stage 4 review, 2026-11-24: the facts are TLC's only, question Q18.)

**Depends on.** T2, T3. **Risks.** The roadmap's own: the golden files may reveal more breakage than the known cases. Ten override cases of research 13 and the liveness captures of research 2 are added to the corpus for that reason; one of them, `override-method_not_public`, already showed a framing shape the first version of this design got wrong (P4).

## P2 The tlaup_parse package

Roadmap: "Move the parser stack (message framing, codes, values, models, SANY parser) into its own import package that imports nothing from `tlaup`." Decisions D7, D39.

**Design.** A second top-level import package, `src/tlaup_parse/`, shipped in the same wheel. `pyproject.toml` changes `include = ["tlaup*"]` (which already matches) and adds `tlaup_parse = ["py.typed"]` to the package data; mypy and coverage name both packages.

| Module | Holds | From |
| --- | --- | --- |
| `framing.py` | Lines to messages and plain text. | The first half of `tlc/parser.py`. |
| `codes.py` | The message-code table. | `tlc/codes.py`. |
| `values.py` | TLA+ values. | `tlc/values.py`. |
| `model.py` | The result types. | `tlc/models.py`. |
| `tlc.py` | `TlcParser`. | The second half of `tlc/parser.py`. |
| `sany.py` | `SanyParser`. | `tlc/sany.py`. |
| `pcal.py` | `PcalParser`. | New ([21 S2](21-other-tools.md#s2-pcal)). |
| `exit_status.py` | What a TLC exit code means. | New ([02 X1](02-cross-cutting.md#x1-exit-codes)). |

Rules: standard library only; no import of `tlaup`, `rich`, `typer` or `pydantic`; no file, network, clock or environment access; plain dataclasses. The public names are exported from `tlaup_parse/__init__.py`; everything else is private.

The whole public surface:

```python
class TlcParser:
    def __init__(self, *, max_output_lines: int = 10_000): ...
    def feed(self, line: str) -> list[Event]: ...  # one line, with or without its newline
    def close(self) -> list[Event]: ...  # end of input: flush anything still open
    @property
    def result(self) -> RunResult: ...


class SanyParser:  # P8
    def feed(self, line: str) -> SanyStep: ...  # what the line was, and the diagnostics it completed
    def close(self) -> SanyStep: ...  # line_class is None; the diagnostic still open, if any
    @property
    def result(self) -> SanyResult: ...


class PcalParser:  # 21 S2
    def feed(self, line: str) -> list[Diagnostic]: ...
    def close(self) -> list[Diagnostic]: ...
    @property
    def result(self) -> PcalResult: ...


class Framer:  # P4; public so the "nothing is lost" property can be tested
    def feed(self, line: str) -> list[Unframed | TlcMessage]: ...  # only items at the top level; a nested
    def close(self) -> list[Unframed | TlcMessage]: ...  # message arrives inside its parent


def render_framed(item: Unframed | TlcMessage) -> list[str]: ...  # the input lines the item was built from (P4)


def parse_value(text: str) -> Value: ...
def describe_exit_status(code: int) -> ExitStatus: ...


@dataclass(frozen=True)
class ExitStatus:  # 02 X1 holds the table of codes, words and meanings
    code: int
    word: str  # X1's word for the code: "success", "safety failure", "parse error", ... A "failure"
    # means TLC checked the model and found it wrong, an "error" that it could not check (D63).
    # The JSON of milestone 4 carries it (40)
    meaning: str  # one sentence, "an invariant was violated"; the result line of 22 O3 shows it beside the verdict
    known: bool  # False for a code X1's table does not hold; word is then "error" (X1, settled 2026-11-24),
    # and meaning "TLC ended with a code tlaup does not know", or "Java was stopped by a signal (...)" from 129 to 255


@dataclass(frozen=True)
class SanyStep:
    line_class: SanyLineClass | None  # None only from close()
    diagnostics: tuple[Diagnostic, ...]  # usually empty: a diagnostic is returned when it is complete


class SanyLineClass(Enum):  # what the parser used the line as; the table is in P8
    BANNER, PROGRESS, HEADER, STRUCTURE, POSITION, MESSAGE, BLANK, OTHER


@dataclass(frozen=True)
class SanyResult:
    diagnostics: tuple[Diagnostic, ...]
    module_files: dict[str, str]
    other: tuple[str, ...]  # the lines of class OTHER, in order (P8)
    lines_used: int  # how many input lines had another class; `RunResult.sany_lines_used` repeats it (P4)


# Added while building 38a (2026-11-25, a low-impact choice by the stage 5 lead): the reporter's override hint
# asks the code table for a code's kind, so the table is public, read-only.
CODES: Mapping[int, CodeInfo]  # MappingProxyType over the code table (P5)


class CodeInfo: ...  # name, kind
```

`Unframed` is the framer's name for a line outside every message. It is not called `Text`, because the reporters use Rich's `Text` for something else ([22 O3](22-reporters.md#o3-terminal-reporter)).

`describe_exit_status` is the one name for this function. [02 X1](02-cross-cutting.md#x1-exit-codes) holds the table of codes, words and meanings it returns (decision D63); `exit_status.py` is that table as data, and its test is below.

**Rejected.** A sub-package `tlaup.parse`: "imports nothing from tlaup" would then be a convention inside one package rather than a visible boundary, and the later split into its own project would rename every import. A separate distribution now: decision D7 says the same wheel until someone else wants it.

**Tests.** A test starts `python -c "import tlaup_parse"` with a `sys.meta_path` hook that refuses `tlaup`, `rich`, `typer`, `pydantic`, `requests` and `yaml`, and asserts success. The build check ([30 I4](30-ci-and-release.md#i4-build-check)) asserts the wheel contains `tlaup_parse/py.typed`. A unit test of `describe_exit_status` walks every row of X1's table: for each code it returns that row's word and meaning with `known` true; a code the table does not hold (3, 99, -1) gives `known` false, the word `error` and the meaning above. The table in the test is X1's, copied once; a change to either makes it fail.

**Changelog.** Changed: "The TLC output parser is now the import package `tlaup_parse`, shipped with tlaup. `tlaup.tlc.parser`, `tlaup.tlc.models`, `tlaup.tlc.values`, `tlaup.tlc.codes` and `tlaup.tlc.sany` are gone." No alias (D14). The entry describes the release, in which all five are gone. They go one by one as their last importer goes, not all with this item: `tlaup.tlc.models` stays until the old layout code that imports it is replaced ([22 O4](22-reporters.md#o4-live-display)), and the entry is complete only then.

**Depends on.** Nothing; first parser package. **Risks.** A PyPI project named `tlaup-parse` does not exist yet and is only needed at the split; the name was not checked. (Stage 4 review, 2026-11-24: the words of `ExitStatus` follow X1's settled table, and the test over every code is named here, question Q4, decision D63; the changelog entry says when `tlaup.tlc.models` goes, index Clerical; the test expects `error`, not `failure`, for a code the table does not hold, finding E2.)

## P3 Result model

Not a roadmap item of its own; it is the "parsed result" that decision D8 says carries everything any reporter needs, and the thing the golden files expect.

**Problem.** `ModelCheckResult` has fields nothing fills (`workers_count`, `collision_probability`, `trace_file_path`, both `file_path`s), a misnamed type (`InitialStateStatItem` holds progress), values kept only as strings, and `sany_errors: list[Any]`.

**Design.** All in `tlaup_parse/model.py`, frozen where possible, each with `to_dict()` giving plain JSON types. The dictionary form is what the expected files hold and what milestone 4's JSON reporter will publish, so field names are chosen now with that in mind and the names of the tlaplus/Examples manifest are used where they exist (research 10): the keys `totalStates`, `distinctStates`, `stateDepth`, and the two mode words. The manifest's result words belong to the exit code, not to the parser ([02 X1](02-cross-cutting.md#x1-exit-codes)).

```python
@dataclass
class RunResult:
    tool: ToolInfo | None  # from message 2262 (P9)
    mode: str | None  # "exhaustive search" (2187), "simulate" (2188, also -generate): the Examples
    # manifest's words (research 10); "depth-first" (2271, -dfid), tlaup's word,
    # since the manifest has none (top-up, research 22). None for another shape.
    workers: int | None  # from 2187, 2188 or 2271 "with N worker(s)"
    phase: Phase  # where the run is: see below
    status: Status  # "running", "success", "failure"; the runner may set "interrupted"
    verdict: Verdict  # top-up, D54: what the run found, from TLC's messages; see below
    resumed: bool  # top-up, D54: TLC recovered from a checkpoint (2197, 2198)
    counts_approximate: bool  # top-up, D54: resumed, and not with the original -fp and -seed (set by the runner)
    errors: list[TlcError]
    warnings: list[TlcMessage]
    sany: list[Diagnostic]  # P8
    module_files: dict[str, str]  # module name -> path, from SANY's "Parsing file" lines
    overrides_loaded: list[str]  # from 2168 (11 R7)
    progress: list[Progress]  # one per 2200 / 2209 message
    stats: FinalStats | None  # 2199, 2194, 2268, 2193
    coverage: list[CoverageItem]
    output: list[str]  # the spec's own output and unrecognised text, newest max_output_lines
    output_dropped: int  # how many older lines are no longer in `output`
    unframed_lines: int  # text found outside messages: `Unframed` items plus non-empty top-level `before`/`after` (P4)
    sany_lines_used: int  # `SanyResult.lines_used`, or 0 when there was no SANY window (P4)
    unknown_messages: list[TlcMessage]  # codes that are not in codes.py
    info: list[TlcMessage]  # severity 0, in codes.py, with no typed meaning (2212, 2269, ...); see P4
    started: str | None  # as TLC printed it, "2026-11-14 22:26:52"; local time, no zone
    finished: str | None
    duration_ms: int | None


class Phase(Enum):
    NOT_STARTED, PARSING, STARTING, INITIAL_STATES, CHECKING, LIVENESS, FINISHED


class Status(Enum):
    RUNNING, SUCCESS, FAILURE, INTERRUPTED


class Verdict(Enum):
    ERRORS, NO_ERROR, NO_ERROR_BOUNDED, INCOMPLETE, NOT_CHECKED
    # dictionary values: "errors", "no-error", "no-error-bounded", "incomplete", "not-checked"


@dataclass(frozen=True)
class ToolInfo:
    version: str  # "2.19" or "2026.11.15.002146"
    revision: str | None  # "5a47802"
    date: str | None  # "08 August 2024" on 2.x builds, as printed; None on rolling builds
    line: str  # "stable" (a numbered version) or "rolling" (a CalVer): the two words
    # `build.toml` uses for a golden folder (01 T3)
    raw: str  # the whole line


@dataclass(frozen=True)
class TlcMessage:
    code: int
    severity: int  # the number in the marker: 0 info, 1 error, 2 TLC bug, 3 warning, 4 state
    name: str | None  # from codes.py, None if the code is not in the table
    body: tuple["str | TlcMessage", ...]  # in input order: a line exactly as printed, without its newline,
    # or a message that started inside this one (research 1)
    before: str = ""  # text on the start marker's line in front of the marker (": " in the captures)
    after: str = ""  # text on the end marker's line behind the marker ("," in one capture)
    truncated: bool = False  # closed without an end marker of its own: by an outer end marker,
    # or by the end of the input (P4)

    @property
    def lines(self) -> tuple[str, ...]: ...  # the message's own lines: the str items of body
    @property
    def nested(self) -> tuple["TlcMessage", ...]: ...  # the message items of body
    def text_lines(self) -> tuple[str, ...]: ...  # the whole text as it reads with the markers taken out (P4)


@dataclass
class TlcError:
    kind: ErrorKind  # "invariant", "deadlock", "property", "assertion", "assumption",
    # "postcondition", "evaluation", "config", "parse", "exception", "usage",
    # "other"; the table from code to kind is in P5
    name: str | None  # the invariant or property name, where the message has one
    message: TlcMessage  # the message that opened the error
    related: list[TlcMessage]  # later error-severity messages that belong to it (2103, 2121, 2264),
    # in the order they arrived
    trace: Trace | None


@dataclass
class Trace:
    states: list[TraceState]
    loop_to: int | None  # state index the behaviour returns to (2122)
    stuttering: bool  # the behaviour ends by stuttering (2218)


@dataclass(frozen=True)
class TraceState:
    index: int
    action: str | None  # "Next"; None for the initial state
    location: Location | None  # where the action is defined; None for the initial state
    header: str  # the text inside the header's angle brackets, as printed (P5's `inner`); "" for a -dfid header (settled while building 13b)
    variables: tuple[Variable, ...]
    lines: tuple[str, ...]  # the whole message body as printed, blank lines included


@dataclass(frozen=True)
class Variable:
    name: str
    value: Value  # P7
    raw: str  # the text TLC printed, lines joined with "\n"; for a variable carried
    # forward (P5, -difftrace), the text of the state it came from
    printed: bool = True  # top-up: False when TLC left it out of this state and the parser carried it


@dataclass(frozen=True)
class Location:
    module: str
    line: int
    column: int
    end_line: int | None
    end_column: int | None


@dataclass(frozen=True)
class Progress:
    diameter: int
    generated: int
    distinct: int
    queue: int  # -1 kept as -1 (simulation, research 1)
    at: str


@dataclass(frozen=True)
class FinalStats:
    total_states: int | None
    distinct_states: int | None
    queue: int | None
    state_depth: int | None
    collision_probability: str | None
    outdegree: str | None  # the 2268 line as printed ("The average outdegree ... is 1 (minimum is 0, ...)")
    # dictionary keys: totalStates, distinctStates, stateDepth, as in the Examples manifest


@dataclass(frozen=True)
class CoverageItem:
    kind: str  # by code: 2773 "init", 2772 "action", 2774 "property", 2779 "variable"
    # (rolling only), 2221 "expression"
    name: str | None  # the name inside the angle brackets; None for an expression
    location: Location
    sub_location: Location | None  # 2772 only: the second span, printed as "(6 12 6 40)"; it is what tells
    # several rows of one action apart
    count: int | None  # after the colon; for "D:G" forms this is G; None for 2774, which has none
    distinct: int | None  # D of "D:G" (2772, 2773); None otherwise
    depth: int  # 2221 only: the number of "|" before "line"; 0 otherwise


@dataclass(frozen=True)
class Diagnostic:
    tool: str  # "sany" or "pcal"
    severity: str  # "error" or "warning"
    message: str
    module: str | None
    file: str | None  # from the "Parsing file" lines; None if not seen
    location: Location | None
    details: tuple[str, ...] = ()  # lines that belong to the diagnostic but are not its message
    # (the residual stack of a parse error, P8)
```

Events are what the reporter receives as the run goes:

```python
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

Each is a small frozen dataclass. Every event that comes from a framed message carries that message (`message: TlcMessage`, the top-level one, with its nested messages inside it), so a reporter can always fall back to TLC's own text. The fields besides `message`, and what makes the parser emit each:

| Event | Fields | Emitted when |
| --- | --- | --- |
| `VersionSeen` | `tool: ToolInfo` | Message 2262 matches the version pattern (P9). |
| `ModeSeen` | `mode: str \| None`, `workers: int \| None` | Message 2187, 2188 or 2271 (top-up: 2271 starts a `-dfid` run; research 22). |
| `PhaseChanged` | `phase: Phase` | A message that moves the run on: 2220 gives `PARSING`; 2219 and 2185 `STARTING`; 2189 `INITIAL_STATES`; 2190 `CHECKING`; 2192 `LIVENESS`; 2267 `CHECKING` again. Emitted for each of these messages, also when the phase it names is already the current one. 2185 also sets `started`. |
| `ProgressMade` | `progress: Progress` | Message 2200 or 2209. |
| `OutputLine` | `line: str`; no `message` | An unframed line that no parser used: the spec's output, a line of class `OTHER` inside the SANY window (P8), and the `before` or `after` text of a top-level message when it is not empty (never seen at the top level; P4). |
| `DiagnosticFound` | `diagnostic: Diagnostic`; no `message` | The `SanyParser` completed a diagnostic (P8). SANY's text is unframed, so there is no message to carry. |
| `ErrorOpened` | `error: TlcError` | A top-level message whose class is error (P4, rule 1) and that is not a continuation of an error (next row). The error becomes the current error. |
| `ErrorExtended` | `error: TlcError` | A message with one of the continuation codes (2103, 2121, 2264) while there is a current error; the message is appended to `error.related` (P5). With no current error it opens one of kind `other`. |
| `TraceStateAdded` | `error: TlcError`, `state: TraceState` | Message 2217 whose header parses (P5). |
| `TraceClosed` | `error: TlcError`, `trace: Trace` | Once per trace, when its end is known: on 2122 (`loop_to` is set) or 2218 (`stuttering` is set); for a trace with neither, when the first top-level message arrives that is not a state after the trace has one, or at `close()`. |
| `WarningFound` | none | A top-level message whose class is warning (severity 3). |
| `OverrideLoaded` | `operator: str`, `java_class: str` | Message 2168 matching `^Loading (\S+) operator override from (\S+) with signature: `. All 43 instances in the capture files match (counted by script on 2026-11-24; the first count, 37, was made before research 22 and 28 added theirs). `overrides_loaded` gets `"<java_class>.<operator>"`. |
| `CoverageAdded` | `item: CoverageItem` | One per coverage row (2221, 2772, 2773, 2774, 2779). The frame messages 2201 and 2202 are `Information`. |
| `StatsUpdated` | `stats: FinalStats` | Message 2199, 2194, 2268, 2193 or 2210, or 2204 (the end of a `-dfid` run); `stats` is the whole record so far. |
| `CheckpointStarted` | `folder: str` | Message 2195 ("Checkpointing of run <folder>"). Top-up: the runner tells the launcher, which holds a first signal until the checkpoint is written ([20 G3](20-groundwork.md#g3-java-launcher), D52). |
| `CheckpointWritten` | none | Message 2196 ("Checkpointing completed at (...)"). |
| `Recovered` | `examined: int \| None`, `queued: int \| None` | Message 2197 or 2198 ("Starting recovery from checkpoint ...", "Recovery completed. N states examined. M states on queue."); sets `resumed`. |
| `Information` | none | A message of class information that is in `codes.py` and has none of the meanings above (P4, rule 3), and a message with a typed code whose text does not match its pattern (a 2262 in a third shape, P9). |
| `UnknownMessage` | none | A message whose code is not in `codes.py` and whose class is not error or warning (those are `ErrorOpened` and `WarningFound`, which carry the message all the same). Also a state message (2217) whose header matches neither pattern (P5). |
| `Finished` | `duration_ms: int \| None`, `finished: str \| None` | Message 2186, read with `^Finished in (?P<ms>\d+)ms at \((?P<at>.+)\)$`: in `-tool` mode TLC writes the duration in milliseconds, and all 271 messages 2186 in the capture files have this form (counted by script on 2026-11-24). The forms `Finished in 01s at (...)` and `Finished in 02min 13s at (...)` are TLC's plain output, which the parser is never given (a raw run is not parsed). A 2186 whose text does not match is still `Finished`, with both fields `None`: the verdict needs the message, not its text, and the result line then takes the duration from the reporter's clock ([22 O3](22-reporters.md#o3-terminal-reporter)). The phase becomes `FINISHED`. |

**A nested message produces no event of its own.** It is part of its parent's `body`, and the parent's event carries it. This holds whatever its code: a 2154 nested in a 1000 is not a second error, and a progress code nested in something else (not seen) is not progress. The parser reads nested messages for one thing, the class of the parent (P4, rule 1), and the reporter reads them for the override hint ([22 O3](22-reporters.md#o3-terminal-reporter)). In the 117 capture files that hold markers (every file under `tests/fixtures/research/`, counted by script on 2026-11-15), nesting is never deeper than one level, the parent is always an error (1000 or 2154, severity 1) and the nested message always has severity 0 (1000, 2154 or 5006).

`OutputLine` is why the reporter can print everything even though the result keeps only the newest ten thousand output lines (the unbounded list is finding M14 of the code-quality report).

**How `status` is set.** The parser cannot see the exit code, so it reports only what the text shows:

- `RUNNING` from the start.
- `FAILURE` as soon as an error is opened (any message of severity 1 or 2) or a SANY diagnostic of severity `error` is found. It never goes back.
- `SUCCESS` when the finish message (2186) arrives and the status is still `RUNNING`.
- If the input ends with neither, the status stays `RUNNING`: the output stopped without TLC saying it finished. The runner knows the exit code and whether a signal arrived; it sets `INTERRUPTED`.

`status` is what the live display shows while the run goes. What the run found is `verdict`.

**The verdict** (decision D54, top-up; [research 22](../research/22-more-tool-captures.md)). TLC's exit code can mislead in three captured ways: `-deadlock -continue` with two invariant violations exits 0 on both builds; `-dfid` with a start depth too small exits 0 although a violation exists; `-generate` on a correct spec never ends. So the result says what the run found from TLC's messages, and the exit code is a cross-check. The parser decides the verdict at `close()`, in this order, and the first rule that applies wins:

| Verdict | When |
| --- | --- |
| `errors` | An error was opened whose kind is a finding about the model: `invariant`, `deadlock`, `property`, `assertion`, `assumption`, `postcondition`, `evaluation`, or `exception` and `other` once the phase has reached `INITIAL_STATES`. |
| `not-checked` | An error was opened, or a SANY diagnostic of severity `error` found, and none of the row above: a parse, config or usage error, or an exception before the initial states. TLC stopped before it checked the model. |
| `incomplete` | No error, and no 2186: the output ended without TLC saying it finished. The runner also sets it when a signal stopped the run, tlaup failed, or the run was stopped for a closed pipe, unless the verdict is already `errors` or `not-checked`. |
| `no-error-bounded` | 2186 and no error, in a bounded search: mode `simulate` (which includes `-generate`) or `depth-first`. |
| `no-error` | 2186 and no error, in a breadth-first search. |

`resumed` is set by 2197 or 2198. `counts_approximate` is set by the runner, which knows whether the run was resumed with the original `-fp` and `-seed` ([11 R6](11-runner.md#r6-run-folders)); the reporters mark the state counts of such a run as approximate, because every recovery research 35 made that did not repeat them over-counted by 0.1 to 1.7 %.

The result line and the JSON result are built from `verdict` and `resumed`, with TLC's exit code shown beside them, not in their place ([22 O3](22-reporters.md#o3-terminal-reporter)). tlaup's own exit code stays TLC's (D29, the roadmap's "Keep" list). When the two disagree, tlaup prints one warning on stderr that names both: `warning: TLC exited with 0, but its output reports 2 errors` (TLC's code is 0 and the verdict is `errors`, `not-checked` or `incomplete`), or `warning: TLC exited with 255, but its output reports no error` (TLC's code is not 0 and the verdict is `no-error` or `no-error-bounded`). Whether tlaup's own exit code should follow the verdict is left to milestone 4, where the JSON result gives scripts the verdict directly ([40](40-later-milestones.md#milestone-4-automation-surface)). A raw run parses nothing and has no verdict.

Message 2193 ("Model checking completed. No error has been found.") is not the rule: the `simulate` capture ends with exit 0 and has none, and research 2 saw it printed after violations with `-continue`. It feeds `stats` (the collision estimates that follow it) and nothing else; the verdict does not read it.

Dropped: `file_path` on trace and coverage items (a location names its module, and `RunResult.module_files` maps a module to its file), `trace_file_path`, `process_info`, the `CheckStatus` values nothing sets.

**Rejected.** Keeping values as strings with children (today's `TlaValue`): loses whether a collection is a set or a sequence, which the diff display and JSON need. pydantic models: a dependency the package must not have. Timestamps as `datetime`: TLC prints local time with no zone, and inventing one would be wrong; the text is kept.

**Tests.** The expected files of P1 are this model serialised; a schema test asserts `to_dict()` output contains only JSON types and that `from_dict(to_dict(r)) == r` for every golden result. Status: facts for `success` (SUCCESS), `simulate` (SUCCESS with no 2193), `violation` (FAILURE), `sany-semantic-error` (FAILURE), and a synthetic file cut off before 2186 (RUNNING after `close()`). Verdict (top-up): `success` is `no-error`; `simulate` and research 22's `dfid-success` are `no-error-bounded`; `violation` and `deadlock-flag-multierror` (exit 0, two errors) are `errors`; `sany-semantic-error`, the cfg errors `tool-badcfg`, `tool-cfgsyn`, `tool-nocfg` and `tool-cfg-missing` (research 22; 2229, 5003 and 5001 on both builds) and `version-bad-option` are `not-checked`; a false `ASSUME` is `errors`; the synthetic cut-off file is `incomplete`; the `recover` captures have `resumed`. A unit test of the disagreement warning: exit 0 with `errors`, exit 12 with `no-error`, and no warning for exit 0 with `no-error-bounded`. Coverage: facts for `coverage` on both builds, among them that the three `Next` rows differ in `sub_location`.

**Changelog.** With P2. **Depends on.** P2. **Risks.** The names become the JSON schema in milestone 4; renaming later is cheap until 0.9.0 ships and costly after. (Stage 4 review, 2026-11-24: the 2186 pattern and the forms it does not read, the 2168 count, and the real names of the cfg-error cases in the verdict test, index Clerical.)

## P4 Framing and never losing output

Roadmap: "Never lose output (decision D9): anything the parser does not recognise is shown exactly as TLC printed it. This covers unregistered message codes ... add the six missing error codes including 2404. A malformed start marker such as `STARTMSG -1` must not raise."

**Problem.** `_handle_message_end` returns early for an unregistered code before looking at the severity (`tlc/parser.py:120`), so an error TLC marks as severity 1 vanishes; 2404 (false postcondition) is one of six such codes. `MessageStack.start` raises `ValueError` for code -1. A line inside an unknown message is dropped.

**Facts (research 1).** A message is `@!@!@STARTMSG <code>:<severity> @!@!@`, body lines, `@!@!@ENDMSG <code> @!@!@`. Messages nest, and the inner start marker follows `: ` on the same line as outer text. Text outside any message is real: SANY output, the spec's `Print` output, the `CounterExample written` line (research 2). Text after a *start* marker on the same line was never produced by TLC itself; it appears only when a spec prints marker text, inside quotes. Text after an *end* marker is produced by TLC: both builds print `@!@!@ENDMSG 2154 @!@!@,` (the marker, then a comma) in the `method_not_public` override capture of research 13, where a message is nested in the middle of a sentence of its parent. The same capture has a message nested in a message of the same code (2154 in 2154; `ctor_private` has 1000 in 1000). The first version of this design said no text follows any marker; the review of 2026-11-15 found the capture, and the capture wins.

**Design.**

*Framing* (`framing.py`) turns lines into a stream of `Unframed(line)` and `TlcMessage` values with a stack for nesting. With `N` standing for `0|[1-9]\d*`, a number written without leading zeros:

- A **start marker** is recognised only at the end of a line: `^(?P<before>.*)@!@!@STARTMSG (?P<code>N):(?P<sev>N) @!@!@$`. Text before it is kept as the new message's `before`. In the captures it is `: ` in front of 7 of the 23 nested messages and empty everywhere else.
- An **end marker** is recognised only at the start of a line: `^@!@!@ENDMSG (?P<code>N) @!@!@(?P<after>.*)$`, and only when the code matches an open message (the rule two points below). Text after it, such as the comma above, is kept as the closed message's `after`. Today's parser accepts such a suffix as well (`tlc/parser.py:78`), so this keeps what works.
- A line inside an open message that is neither marker is appended to the `body` of the innermost open message. A message that closes while another is open is appended to that one's `body`, after the lines that came before it. So `body` holds a message's own lines and its nested messages in one sequence, in input order. The first revision kept the two in separate tuples, which lost where a nested message stood among the lines; the second check of 2026-11-15 found that the "rebuilt in order" property below could then not hold for exactly the nested cases.
- Nesting uses a stack, so a message nested in one of the same code closes the inner one first.
- The framer returns only top-level items: a nested message is delivered inside its parent, when the parent closes. In the captures a parent closes within a few lines of its nested message, so nothing is held back for long.
- So `"before @!@!@STARTMSG 2185:0 @!@!@ after"` and `"@!@!@STARTMSG 9999:1 @!@!@"` (quoted `Print` output, case `print-marker`) are plain text: neither ends in the start marker. A printed line that *begins* with end-marker text is plain text too unless a message of that code is open at that moment, which for output printed during a run means inside a message body; no capture shows that, and the synthetic cases cover it.
- A start marker that does not match the pattern (`STARTMSG -1`, no severity, letters) is plain text.
- An end marker whose code equals the open message closes it. If it equals an outer open message instead, the inner ones are closed with `truncated=True` and then it closes. If it matches nothing open, it is plain text.
- At end of input (`close()`), every open message is closed with `truncated=True`, with the body it has, innermost first.
- A marker whose number has a leading zero (`STARTMSG 02185:0`) is plain text. TLC never prints one; the rule is there so that the code, kept as an integer, can always be written back as it was read.
- A line is taken with or without its line ending: a trailing `\n` or `\r\n` is removed before any pattern is tried, so the `$` anchors hold for output from Windows as well (decision D15; not tried on Windows).
- Compiled patterns are module constants (finding L16 of the code-quality report: recompiled per line today).

*Never losing output* is then a property of the framing, not a list of special cases, and it is stated at two levels so that it can be tested:

- **Framing: the input can be rebuilt exactly.** `render_framed` writes an item back as the lines it came from:

  ```
  render_framed(Unframed(line)) = [line]
  render_framed(m)              = [m.before + "@!@!@STARTMSG <code>:<severity> @!@!@"]
                                  + for each item of m.body: [item] for a line, render_framed(item) for a message
                                  + ["@!@!@ENDMSG <code> @!@!@" + m.after]        left out when m.truncated
  ```

  For any sequence of lines at all, rendering everything `feed` and `close` returned, in order, gives the input lines without their line endings. Nothing is lost, nothing is moved and nothing is added. `Framer` and `render_framed` are public for this reason. The design agent wrote the rules above as a script and ran it on 2026-11-15: all 117 capture files with markers (114 real `-tool` captures and 3 files that only contain marker text and frame to no message; 1,618 messages) are rebuilt exactly, none has a truncated message, and so are 200,000 random sequences built from marker lines, malformed markers, crossed and unmatched ends and plain text.
- **Interpretation.** Every `Unframed` becomes exactly one `OutputLine` event, except inside the SANY window, where the `SanyParser` either uses the line or gives it the class `OTHER` and it becomes an `OutputLine` (P8); Text before a top-level start marker or after a top-level end marker on the same line (`before`, `after`), when it is not empty, becomes one `OutputLine` as well. `RunResult` carries two counters so the test can check this without reaching into the parser: `unframed_lines`, the number of `Unframed` items plus the non-empty top-level `before` and `after` texts, and `sany_lines_used`, the `lines_used` of the SANY result or 0. The property is: the number of `OutputLine` events equals `unframed_lines - sany_lines_used` ([01 T3](01-testing.md#t3-golden-files)). In the captures no top-level message has a `before` or `after` text (the 9 that exist are on nested messages); the synthetic case with text after a top-level end marker is the one that exercises the term. Every top-level message becomes at least one event that carries it, and with it its nested messages, so no message is swallowed without the reporter being told. The typed events do not repeat every character (a `ProgressMade` carries numbers), which is why they carry the message too.

*Reading a message's text.* `TlcMessage.text_lines()` gives the text as it reads with the markers taken out: the items of `body` in order, a nested message contributing its own `text_lines()` with its `before` put in front of its first line and its `after` behind its last. For the `java-override-exception` capture that is

```
TLC threw an unexpected exception.
...
The exception was a java.lang.RuntimeException
: Attempted to apply the operator overridden by the Java method
public static tlc2.value.impl.Value tlc2.module.Boom.Boom(tlc2.value.impl.Value),
but it produced the following error:
boom from Java override
```

which is line for line what TLC prints for the same run without `-tool`: compared by script with the `plain/` captures of the five research 1 cases that have a nested message (`java-override-exception` and `java-override-stack-trace` on both builds, `postcondition-false` on v1.7.4). It is what a reporter prints when it shows a message "as TLC printed it" ([22 O3](22-reporters.md#o3-terminal-reporter)).

*Interpretation* (`tlc.py`) decides what a message means, in this order:

1. **Severity first.** The severity in the marker decides the class: 1 or 2 is an error, 3 is a warning, 4 is a state of a trace, 0 is information. The code table cannot override an error or a warning into silence. A nested message cannot hide one either: if a message nested at any depth has severity 1 or 2, the top-level message is an error whatever its own severity, and likewise a nested 3 makes it at least a warning. No capture has this (nested messages there are all severity 0); the rule is for the guarantee. Only top-level messages are interpreted (P3, the note under the event table).
2. **Then the code**, for the meanings the parser knows, which are the rows of P3's event table: version (2262), mode (2187, 2188, 2271), phases (2220, 2219, 2185, 2189, 2190, 2192, 2267), progress (2200, 2209), states (2217, 2218, 2122; 2216 on v1.7.4, P5), statistics (2199, 2194, 2268, 2193, 2210, 2204), coverage (2201, 2202, 2221, 2772, 2773, 2774, 2779: the ones in the captures), checkpoint and recovery (2195, 2196, 2197, 2198), finished (2186), override loading (2168). The event table is the authority; this list names the same codes.
3. **A code that is in `codes.py` but has no typed meaning** and has severity 0 becomes an `Information` event and is kept in `info`. Two such codes are in the captures: 2212 ("Implied-temporal checking--satisfiability problem has 1 branches.", every liveness run on both builds) and 2269 ("Computed 1 initial states...", the `simulate` case). The reporter hides them in normal output, as it hides other chatter.
4. **A code that is not in `codes.py`** is kept in `unknown_messages`, and the reporter shows it as TLC printed it. If its class is error or warning (rule 1) it is an error or a warning like any other: it arrives as `ErrorOpened` (kind `other`) or `WarningFound`, and an error sets the run's status to failure. Otherwise it arrives as `UnknownMessage`. "Unknown" always means "not in the table", never "in the table but uninterpreted".

The six missing codes (1003, 2148, 2254, 2256, 2404, 2405) are added to `codes.py` with their upstream names, and 2404 and 2405 map to error kind `postcondition`. With rule 1 they would be shown as errors even without the table entry; the entry gives them a name and a kind.

`codes.py` becomes a plain table `CODES: dict[int, CodeInfo]` with `name` and an optional `kind`; the `Ignore` type goes, because "ignore" was how output got lost. Whether an informational message is shown is the reporter's choice (it shows unknown ones and hides the known chatter such as 2185).

**Rejected.** Recognising markers anywhere in a line: turns quoted `Print` text into a message that never ends, swallowing the rest of the run. (Today's parser already anchors the start marker at the end of the line, `tlc/parser.py:90`; it is the end marker it matches with text on both sides, line 78.) Requiring markers alone on a line: breaks the real nested case `: @!@!@STARTMSG 2154:0 @!@!@` and the real `@!@!@ENDMSG 2154 @!@!@,`. Generating `codes.py` from upstream's `EC.java`: attractive, but it needs the upstream source at build time and the table changes a few times a year; a unit test instead lists the codes seen in the golden files and fails if one has no entry.

**Tests.** Golden: `postcondition-false` on the rolling build has one error of kind `postcondition`; `java-override-exception` has message 1000 whose `body` is four lines and then a 2154 with `before == ": "`, and whose `text_lines()` equal the error's lines in the `plain/` capture of the case; `override-method_not_public` on both builds has its outer 2154 closed, a body of one line, the nested 2154 with `after == ","`, and two more lines, in that order, and the finish time set from the 2186 that follows; `override-ctor_private` has 1000 nested in 1000 and one error, not two; `print-marker` yields the two quoted lines as output and no message 9999; the liveness cases have 2212 in `info` and nothing in `unknown_messages`. Synthetic: `STARTMSG -1`; a marker with a leading zero; a start with no end (`truncated`); an end with no start; crossed ends (the inner one `truncated`); an end marker with text after it at top level (an `OutputLine` after the message's own event); a nested message of severity 1 inside one of severity 0 (one error); a file with `\r\n` endings. Properties: over every golden and synthetic file, the exact rebuild and the event-level count above, and the same result whether lines are fed with their `\n`, without it, or with `\r\n`; a Hypothesis test over generated line sequences (marker lines with small codes, malformed markers, plain text) asserts the exact rebuild ([01 T7](01-testing.md#t7-property-tests-for-values)). A unit test lists every code seen in the golden files and fails if one has no entry in `codes.py`.

**Changelog.** Fixed: "Errors with a TLC message code tlaup did not know (for example a false POSTCONDITION, code 2404) were not shown at all. Every message TLC marks as an error is now shown, and output tlaup does not recognise is printed as TLC wrote it."

**Depends on.** P2. **Risks.** Severity 2 and 5 were never seen (research 1); 2 is treated as an error and 5 as information, by rule 1 and its default. (Stage 4 review, 2026-11-24: rule 2 lists the same typed codes as P3's event table, index Clerical.)

## P5 Error traces

Roadmap: "Fix error-trace parsing so real counterexamples yield states: location inside the angle brackets, no location on the initial state, the `/\ ` prefix, and the 'Back to state' (2122) and stuttering (2218) headers."

**Problem.** `tlc/parser.py:195` expects `1: <Init> line 5, col 1 ... of module M`, with the location after the bracket. Real TLC prints it inside. Line 223 expects `x = 1`; real TLC prints `/\ x = 1` when there is more than one variable. So every real trace has zero states.

**Facts (captures).**

```
1: <Initial predicate>                                            2217:4   no location
2: <Next line 10, col 59 to line 10, col 76 of module Violation>  2217:4
/\ store = [alpha |-> {1}, beta |-> {}, gamma |-> {}]             several variables: "/\ " prefix
/\ log = << [ op |-> "add",                                       a value continues on indented lines
     key |-> "alpha",
x = 0                                                             one variable: no prefix (liveness cases)
1: Back to state: <Next line 5, col 9 to line 5, col 24 of module LiveBack>   2122:4
3: Stuttering                                                     2218:4
```

A blank line ends each state's body. With `-continue`, each error is followed by its own 2121 and its own states (case `multi-error-continue`). A liveness error is 2116, then 2264 "The following behavior constitutes a counter-example", then the states.

**Design.**

- **Header**: the first line of the message, `^(?P<n>\d+): <(?P<inner>.*)>$`. If `inner` matches `^(?P<action>.+?) line (\d+), col (\d+) to line (\d+), col (\d+) of module (?P<module>\S+)(?: \(.*\))?$` the state has an action and a location; otherwise the action is `None` and `inner` is kept in `header` ("Initial predicate"). The action is kept as printed: the operator that holds the action, which is a sub-action of `Next` such as `Pick` rather than `Next`, and on rolling with its arguments (`Step(1)`); in `-simulate` and `-generate` on rolling the first state names `Init` with a location (research 22, both kept as they come). **`-dfid`** (top-up): a header `^(?P<n>\d+): ?$` (no brackets, a trailing space on rolling) is a state with no action and no location, and on v1.7.4 the code 2216 is a state message as 2217 is; nothing more is designed for `-dfid` (D54). A header that matches none of these makes the whole message an `UnknownMessage`, shown as printed.
- **The body as printed** (the message's `lines`) is kept in `TraceState.lines`, so a reporter can show a state exactly as TLC printed it.
- **Variables**: a line starting `/\ <name> = ` begins a variable. If no line of the body starts with `/\ `, the first line `<name> = ` begins the only variable. Following lines up to the next variable start or the end belong to it. Trailing blank lines are dropped. The joined text is `Variable.raw`; `parse_value` (P7) gives `Variable.value`.
- **Back to state** (2122): `^(?P<n>\d+): Back to state: <(?P<inner>.*)>$` sets `trace.loop_to = n`. It adds no state.
- **Stuttering** (2218): `^(?P<n>\d+): Stuttering$` sets `trace.stuttering = True`. It adds no state.
- **Which error a state belongs to**: the most recently opened error. A state that arrives before any error (not seen) opens an error of kind `other`.
- **Error name**: for 2110 `Invariant (?P<name>\S+) is violated\.`, for 2116 `Temporal property (?P<name>\S+) was violated\.`, for 2404 `Postcondition (?P<name>\S+) `. No match leaves the name `None`; the message text is always kept. v1.7.4's liveness message has no name (`Temporal properties were violated.`).
- **Related messages.** An error-severity message that arrives while an error is open and is one of the continuation codes (2103, 2121, 2264) is appended to that error's `related` and announced with `ErrorExtended`; it does not open a new error. In the `assertion-failure` captures the order is 2132, 2121, three states, then 2103, so related messages can come after the trace; the model keeps arrival order and the reporter prints in it.
- **Kind** by code, for the codes the captures show: 2110 invariant; 2114 deadlock; 2116 property; 2112 property (an action property: a trace with no loop line, which the trace itself shows); 2132 assertion; 2104 assumption (a false `ASSUME`, no trace); 2179 evaluation (at the top level, with a trace, when it happens in `Next`); 2404, 2405 postcondition; 5001, 5003, 5006 and 2229 config; 1000, 1005, 2147 (a fingerprint failure after running out of memory), 2154 (the outer error of `override-method_not_public`: a Java override that could not be called) and 2173 (an override class that cannot be read, [11 R7](11-runner.md#r7-override-modules-that-do-not-load)) exception; 3002 parse; 1102 usage (TLC rejected its own command line, case `version-bad-option`). Top-up: 2104, 2112, 2147, 2173, 2179, 5001, 5003 and 2229 come from research 22 and 28, which captured each in `-tool` mode on both builds.
- **A 1000 that holds one message with a kind of its own takes that kind** (top-up). v1.7.4 reports a cfg error as a 1000 with 5001 or 5003 nested at severity 0, where rolling prints the inner code at the top level; an evaluation error in an invariant is a 1000 with 2179 nested on both builds (`tool-eval`; corrected while building 08b, the rule is unchanged). So when a top-level 1000 holds exactly one nested message and that message's code has a kind other than `exception` or `other`, the error takes the nested message's kind: the JSON result is then the same on both builds. The reporter still prints the whole message. With more than one nested message, or none, the kind stays `exception`. v1.7.4's `postcondition-false` becomes `config` by this rule, which is what it is: v1.7.4 does not know the `POSTCONDITION` keyword and reports a cfg error ("It was expecting a keyword") as a 1000 holding a 5006. The override hint keeps its condition on the nested `config` message ([22 O3](22-reporters.md#o3-terminal-reporter)). With these, every error-severity code at the top level of the adopted cases has a kind of its own. Any other error-severity code is `other`, shown in full, which rule 1 of P4 guarantees.
- **Information and warnings the top-up captures added**: all have severity 0 except 2285. Of these, 2195 to 2198 (checkpoint and recovery), 2271 (the mode of a `-dfid` run) and 2204 (its statistics), and 2210 (the statistics of a simulation) have a typed meaning and their own events (P3's table, P4 rule 2); 2205 to 2208 (`-dfid`'s other lines) and 2501 (rolling's path of a trace spec written with `-generateSpecTE`) have none and are `Information`. 2285 (rolling: a `-recover` with other settings than the checkpoint's, naming the flags to repeat) is a warning, shown as one; its upstream name is `TLC_CHECKPOINT_RECOVER_SETTINGS_MISMATCH` (read from `tlc2.output.EC` in the rolling jar of research 22 with `javap -constants`, 2026-11-24), which is the name `codes.py` gives it. A `-generateSpecTE` run on v1.7.4 prints four `1000:0` messages: severity 0, so information, by the severity-first rule of P4.

**`-difftrace`** (top-up, D54; [research 22](../research/22-more-tool-captures.md)). With `-difftrace` TLC prints the first state in full and, after it, only the variables that changed; in a model-checking run the last state is printed in full anyway, in `-simulate` and `-generate` it is not. Carrying every variable a state leaves out forward from the state before rebuilds exactly the trace of the same run without `-difftrace` (10 of 10 pairs, both builds). So the parser does that: a state's missing variables are taken from the previous state, in that state's order, with `printed=False`; the state's `lines` stay as printed. The changed-variable display of the reporter then works with and without the option, and the first design's fallback (print states as TLC printed them when `-difftrace` is among the arguments) goes. With `ALIAS` (rolling only; v1.7.4 reads it as an invariant name and fails with 2229) the variables are the alias record's fields, and the rule is the same. A state that names a variable the previous state did not have is taken as printed; this has not been seen.

**Rejected.** Reading traces from `-dumpTrace json` (P6). Guessing a variable start from `name = ` on any line: a string value containing ` = ` at the start of a wrapped line would split a variable.

**Tests.** Facts for `violation` (4 states, the values above), `deadlock`, `assertion-failure` (one error with 3 states and two related messages, 2121 before the states and 2103 after), `liveness-back-to-state` (3 states, `loop_to == 1`), `liveness-stuttering` (2 states, `stuttering`), `multi-error-continue` (3 errors, each with its own trace), `print-output` (the spec's printed lines are output, not states). Full expected results for all. Top-up, from research 22's captures on both builds: each `-difftrace` capture gives the same variables, values and order as its plain twin (the ten pairs of `verify-difftrace.txt`), with `printed` false exactly where TLC left a variable out; the `dfid-violation-deep` capture (`-dfid 10`) gives a trace of states with no action (`dfid-violation`, `-dfid 2`, finds no error; corrected while building 08b); the simulation and `-generate` violations give their traces; `Step(1)` is kept as the action of the parameterised case; the false `ASSUME` is one `assumption` error with no trace; the evaluation error in `Next` is `evaluation` with a trace, and the one in an invariant is `evaluation` on both builds (a 1000 holding a 2179 on v1.7.4); the action-property violation is `property` with no loop; the three cfg errors are `config` on both builds; the 2285 warning is a warning.

**Changelog.** Fixed: "Counterexample traces were not shown: real TLC output parsed to zero states. Traces now show every state, the action and its location, the loop-back state of a liveness counterexample, and stuttering."

**Depends on.** P4, P7. **Risks.** An action header with a string argument that itself contains ` line 3, col 4 to ...` would break the location pattern; not produced, and the fallback (an unknown message shown as printed) is safe. `-difftrace` with a variable that changes to a value that prints the same, and a liveness trace whose loop state keeps a variable unchanged, were not captured; carrying forward gives the right state in both by construction. `-dfid` is parsed only far enough that its traces are not unknown messages; its early stops (research 22 saw `-dfid 2` and `-dfid 5` stop without finding a violation that exists) are TLC's, and the verdict calls such a run bounded. (Stage 4 review, 2026-11-24: which of the top-up codes are typed and which are information now agrees with P3 and P4, and 2285's upstream name is recorded, index Clerical.)

## P6 JSON traces from TLC

Roadmap: "If TLC can write traces as JSON itself, read traces from that and skip value parsing for traces. Decide in design once the answer is known."

**Decision: not used.** The research contradicts the assumption, and the research wins:

- v1.7.4 has no `-dumpTrace` (research 2), so the text parser is needed for a supported build whatever is done for rolling.
- On rolling builds the JSON loses types: sets, sequences, tuples and functions on `1..n` are all arrays; model values and strings are both strings.
- It says nothing about which error occurred, writes nothing with `-continue`, and nothing for a run that is killed.

So the text is the one source, for both builds, and P5 and P7 are done in full. Nothing in the design prevents a user from passing `-dumpTrace json FILE` after `--`: the unframed `"CounterExample written: FILE"` line it prints is ordinary output (golden case `dump-trace-live`, the one `-tool` capture research 2 made with the flag, on the rolling build). Milestone 4 may use the JSON for the loop edge and action parameters on rolling builds if a need appears; nothing has to be left open for that now.

**Tests.** The `dump-trace-live` golden case asserts the line is kept as output and the trace still parses from the text.

**Depends on.** P4, P5. **Risks.** None: nothing is built.

## P7 Values

Roadmap: "Fix function-valued variables (`(a :> 1 @@ b :> 2)` parses to `a`) and values that TLC wraps across lines, which always fall back to a raw string because the tokenizer does not skip newlines."

**Problem.** `_parse_value` treats `(` as "skip and parse what follows", so a function becomes its first key. The tokenizer skips spaces but the lines it is given end in `\n`, which no token matches, so every wrapped value raises and falls back to raw text. Records and functions are both rendered as `key |-> value`.

**Design.** A new recursive-descent parser over one string.

```python
@dataclass(frozen=True)
class Value:
    kind: str            # "int", "bool", "string", "model", "set", "seq", "record", "function", "interval", "raw"
    text: str            # the source text of this value, as printed (always kept); declared with
                         # field(compare=False), so two values are equal when their trees are equal
    items: tuple["Value", ...] = ()               # set, seq
    fields: tuple[tuple[str, "Value"], ...] = ()  # record
    pairs: tuple[tuple["Value", "Value"], ...] = ()   # function
    scalar: int | bool | str | None = None        # int, bool, string (unescaped), model (its name),
                                                  # raw (the text again, so that two raw values compare by text)
    bounds: tuple[int, int] | None = None         # interval a..b

def parse_value(text: str) -> Value
```

Grammar (whitespace, including newlines, is allowed between any two tokens):

```
value    = int | bool | string | interval | set | seq | record | function | model
int      = ["-"] digits
bool     = "TRUE" | "FALSE"
string   = '"' ( any character except '"' and '\' | '\"' | '\\' )* '"'   (any other escape: the whole value is raw; settled while building 11)
interval = int ".." int
set      = "{" [ value { "," value } ] "}"
seq      = "<<" [ value { "," value } ] ">>"
record   = "[" name "|->" value { "," name "|->" value } "]"
function = "(" value ":>" value { "@@" value ":>" value } ")"
model    = name                      ; an identifier that is not TRUE or FALSE
name     = letter or "_", then letters, digits, "_"
```

- **Total and lossless.** Any failure, at any depth, makes the *whole* value `Value(kind="raw", text=<the input>, scalar=<the input>)`. `text` is left out of comparison on every node, so a raw value repeats its text in `scalar`: without that any two raw values would be equal and the changed-variable mark of [22 O3](22-reporters.md#o3-terminal-reporter) would never show for them (found by the second check of 2026-11-15). `parse_value` never raises and never returns a tree with a hole in it. `text` is kept on every node, so a display can always fall back to what TLC printed.
- Forms TLC prints without enumerating (`[S -> T]`, `SUBSET S`, `{x \in S : P}`, lazily printed sets) are not in the grammar and come out as `raw`. That is correct behaviour, not a gap: nothing is lost and nothing is guessed.
- No recursion limit problem in practice: depth follows the nesting of the value; a guard turns `RecursionError` into `raw`.

**Rejected.** Patching the tokenizer to skip `\n` and adding a function case: the structure/collection code "is a bit simplified" by its own comment and mixes records with functions. Keeping `TlaValue(key, value: str, children)`: see P3.

**Tests.** The golden values (the wrapped sequence of records in `violation`). The property tests of [01 T7](01-testing.md#t7-property-tests-for-values): round trip, whitespace does not matter, total, never a partial tree. Equality in those properties is tree equality: `text` is not compared, since it differs with spacing. Two raw values with different text are unequal (a unit case), and a raw value's equality does depend on spacing, which is right: nothing is known about its structure. Unit cases for each form, including a function with tuple keys, a set of records, an empty set and an empty sequence (the grammar has no empty function; TLC prints one as `<< >>`, which parses as a sequence), a string with escaped quotes and a string that contains `:>`.

**Changelog.** Fixed: "Function values such as `(a :> 1 @@ b :> 2)` were shown as their first key; values TLC wraps over several lines were shown as one raw string."

**Depends on.** P2. **Risks.** How TLC prints a string that contains a newline or a non-ASCII character was not captured; an odd form falls back to `raw`.

## P8 SANY output

Roadmap: "Fix SANY error grouping: errors are flushed after every line, the error block never ends so later TLC messages become SANY errors, and lines keep their newline. Cover `Semantic errors:`, `***Parse Error***` and the 1.8.0 `Linting of module` line."

**Problem.** The runner calls `sany_parser.get_errors()` after every line, and `get_errors` flushes, so a location line and its message become two errors. Once `current_block` is set it is never cleared, so every later line that is not a marker is appended to a SANY error. Lines keep `\n`.

**Facts (research 1 and 12).** Inside TLC, SANY's text sits between message 2220 ("Starting SANY...") and 2219 ("SANY finished."), unframed. Run on its own, SANY prints the same text with a banner. Shapes:

```
Parsing file <path>                                  maps module -> file; 1.8.0 adds " (jar:file:...)" for standard modules
Semantic processing of module M
Linting of module M                                  rolling only
Semantic errors:
*** Errors: 2
line 4, col 13 to line 4, col 13 of module SemErr    then a blank line, the message, blank lines
***Parse Error***
Encountered "Beginning of definition" at line 6, column 1 and token "1"
Residual stack trace follows: ...                    up to
Fatal errors while parsing TLA+ spec in file ParseError
Could not parse module ParseError from file ParseError.tla
Warnings (1) during syntax parsing of Pcal.tla:      rolling;  "!! WARNING: ..." on v1.7.4
Cannot find source file for module X imported in module Y.    no location
File name 'A' does not match the name 'B' of the top level module it contains.   no location
Cannot find the specified file Nope.tla.              no location; the spec file itself is missing
File does not exist: <path> while looking in these directories: ...   printed before the two lines above
```

The two "no location" errors of a spec that parses do not come under `***Parse Error***`. They come in an abort block, which differs by build (captures `sany-missingmod`, `sany-namemismatch`):

```
v1.7.4                                              rolling
Fatal errors while parsing TLA+ spec in file X      Fatal errors while parsing TLA+ spec in file X
tla2sany.semantic.AbortException                    In module X            (or: Unknown location)
*** Abort messages: 1                               <the message>
Unknown location                                    *** Errors: 1
<the message>                                       In module X            (or: Unknown location)
                                                    <the message>          the same message a second time
```

SANY's text gives a module name, never a file name; warnings of level WARNING are printed under "Semantic errors" like errors (research 12).

**Design.**

- **Scope inside TLC.** `TlcParser` owns a `SanyParser`. Unframed text is given to it only between 2220 and 2219. When 2219 arrives the `SanyParser` is closed and its diagnostics are final. After that, unframed text is the spec's output. This ends the "block never ends" defect by construction.
- **Every line gets a class.** `feed` strips trailing white space (SANY ends some lines with a space), acts on the line, and returns a `SanyStep` with the class of the line and the diagnostics the line completed. The class says what the parser used the line as:

  | Class | Lines | What a caller does with it |
  | --- | --- | --- |
  | `BANNER` | `****** SANY2 Version ...` (SANY run on its own; one per file given). | Chatter. |
  | `PROGRESS` | `Parsing file <path>`, `Semantic processing of module M`, `Linting of module M`. | Chatter. |
  | `HEADER` | `Semantic errors:`, `***Parse Error***`, `Residual stack trace follows:`, `Fatal errors while parsing TLA+ spec in file X`, `Warnings (N) during syntax parsing of F:`. | Nothing: the diagnostics carry it. |
  | `STRUCTURE` | `*** Errors: N`, `*** Abort messages: N`, `tla2sany.semantic.AbortException`, and in the tail of a parse error `In module M` and `Could not parse module M from file F`. | Nothing. |
  | `POSITION` | `line L, col C to line L2, col C2 of module M`; in an abort or warning block `In module M` and `Unknown location`. | Nothing. |
  | `MESSAGE` | A line that became part of a diagnostic's message or details, and the two one-line diagnostics (`Cannot find the specified file X.`, `!! WARNING: ...`). | Nothing. |
  | `BLANK` | An empty line, except as in the next row. | Nothing. |
  | `OTHER` | Every line the parser did not use, and an empty line that follows such a line. | Shown as printed. |

  Inside a TLC run the `TlcParser` turns each `OTHER` line into an `OutputLine` and keeps it in `RunResult.output`, like any other unframed text (D9), and drops the rest, which the diagnostics stand for. For `tlaup sany`, [21 S1](21-other-tools.md#s1-sany) routes by the same class, in four groups: the parts of a diagnostic (`HEADER`, `STRUCTURE`, `POSITION`, `MESSAGE`), which it does not print because the diagnostic stands for them; banner and progress (`BANNER`, `PROGRESS`); `BLANK`; and anything else (`OTHER`). It needs nothing else from the parser to tell the four apart. An empty line is `OTHER` only directly after an `OTHER` line, so SANY's help text keeps its paragraphs while the empty lines around the banner and inside error blocks vanish. No look-ahead is needed.
- **The state machine.** States: `preamble`, `semantic_errors`, `parse_error`, `parse_stack`, `parse_tail`, `abort`, `warnings`. At most one diagnostic is *open* (being collected). "Completes" below means: the open diagnostic, if it has a message, is returned and is no longer open; if it has no message it is dropped, and the line that opened it stays counted as used. A position with no text under it says nothing a user could act on. None of the 52 SANY captures (17 on v1.7.4, 35 on rolling) reaches that case (counted by script on 2026-11-16 with the third reviewer's model of these rules: 0 dropped); the v1.7.4 missing-module case was where it could have happened, and research 22 found its message on stdout ("The stderr line" below), so it does not.

  | Line | Effect |
  | --- | --- |
  | The banner | Completes; state `preamble`. A second file on one command line starts again here. |
  | `Parsing file <path>` | Completes; state `preamble`; records `module -> path`, the module name taken from the file name, a trailing ` (jar:...)` dropped. |
  | `Semantic processing of module M`, `Linting of module M` | Completes; state `preamble`. This is what ends a warning block on rolling. |
  | `Semantic errors:` | Completes; state `semantic_errors`. |
  | A location line `line L, col C to line L2, col C2 of module M` (the whole line) | In the three parse states: an ordinary line (last row). Otherwise: completes, and opens a diagnostic at that location, severity `error`. |
  | `***Parse Error***` | Completes; opens the parse-error diagnostic; state `parse_error`. |
  | `Residual stack trace follows:` | In `parse_error`: state `parse_stack`. Otherwise an ordinary line. |
  | `Fatal errors while parsing TLA+ spec in file X` | In `parse_error` or `parse_stack`: state `parse_tail`; the parse-error diagnostic stays open. Otherwise: completes; state `abort`. |
  | `Could not parse module M from file F` | In `parse_tail` with the parse-error diagnostic open: sets its module to `M` and completes it. In `parse_tail` afterwards (rolling prints the line twice): nothing. Otherwise an ordinary line. |
  | `*** Errors: N`, `*** Abort messages: N`, `tla2sany.semantic.AbortException` | In `parse_tail`: nothing. Otherwise: completes. |
  | `In module M`, `Unknown location` | In `parse_tail`: nothing. In `abort`: completes, and opens a diagnostic with no location (module `M`, or none), severity `error`. In `warnings`: the same with severity `warning`. Otherwise an ordinary line. |
  | `Warnings (N) during syntax parsing of F:` | Completes; state `warnings`. |
  | `!! WARNING: <text>` (v1.7.4) | Completes; one finished diagnostic of severity `warning` with message `<text>`, its module from `in module M` in the text when present. |
  | `Cannot find the specified file X.` | Completes; one finished diagnostic of severity `error` with no location. |
  | An empty line | Nothing. It never ends a diagnostic: every capture has one between a position line and its message. |
  | Any other line (an ordinary line) | With a diagnostic open: appended to its details in `parse_stack`, to its message otherwise. With none open: not used, class `OTHER`. |

  `close()` completes.
- **The parse-error diagnostic.** Its message is the lines between `***Parse Error***` and `Residual stack trace follows:`, joined with newlines. Its location is the first `at line L, column C` in the message; failing that, the first `line L, col C to line L2, col C2 of module M` inside it (the precedence-conflict message of the `sany-level` capture has only this form); failing both, none. A location found through `at line L, column C` carries no module of its own: its `module` is the one the tail's `Could not parse` line names, or `""` when the output ends first (settled while building 12, 2026-11-24, a low-impact choice by the stage 5 lead). The residual stack lines are its `details`. Its module comes from the tail's `Could not parse module` line, which is where the two builds differ: v1.7.4 prints the exception name, `*** Abort messages: 1`, `In module M` and the line once; rolling prints `In module M` and the line, then `*** Errors: 1` and both again. In `parse_tail` all of these are structure, so the tail gives the module and no second diagnostic on either build. If the input ends before the tail, `close()` returns the diagnostic without a module.
- **A diagnostic equal to one already returned is not returned again** (same severity, module, location and message). This is the whole rule for rolling's repeated abort block: the copy after `*** Errors: 1` is recognised and dropped. Two real errors cannot be equal in all four, since SANY reports a position once.
- **Severity** (decision D55, top-up; [research 22](../research/22-more-tool-captures.md)). Every diagnostic SANY prints under "Semantic errors", and every diagnostic of an abort block, is an `error`. Only the diagnostics of a warning block and the `!! WARNING` line are warnings; in the captures those are exactly PlusCal's "changed since its last translation" messages, which TLC treats as warnings too (it checks the model and exits 0). The first design kept a table of texts known to be warnings, starting with message 4802 ("Non-unique fields in constructor."), because research 12 read SANY's message table as calling it one. Research 22 found that TLC refuses a spec whose only SANY message is 4802 with 3002 and exit 150, on both builds, and the same for the two stuttering lints (`[] followed by action not of form [A]_v`): SANY prints all three under `Semantic errors:` with `*** Errors: 1`, the frame of a real error. Calling them warnings would make `tlaup sany` exit 0 for a spec `tlaup tlc` refuses with 150, which D29 says must not happen. So the table goes, and 4802 is an error in `tlaup sany` and in `tlaup tlc` alike. (The walk-through notes of 2026-11-20 first recorded the opposite for standalone SANY; the maintainer reversed it after the review.) `tlaup sany` relies on this for its exit code ([21 S1](21-other-tools.md#s1-sany)).
- **The warning forms** (top-up, research 22 captured each on its own). v1.7.4 prints one line, `!! WARNING: <text>`, directly under `Parsing file`; rolling prints a block, `Warnings (1) during syntax parsing of <F>:`, then `In module M` and the text, each separated by blank lines, ended by the next `Semantic processing` line. `<F>` is `PcalStaleAlg.tla` in SANY alone and `PcalStaleAlg`, with no extension, inside TLC, so the parser takes no file from the block header; the file comes from the `Parsing file` lines as for every diagnostic. There are three texts (the algorithm changed, the translation changed, both); v1.7.4's text for "both" is misspelt, and every text is kept as printed.
- `File does not exist: ... while looking in these directories: ...` is an `OTHER` line on purpose: its text differs by build and it adds a path the user wants to see, so it is shown as printed, above the diagnostic it belongs to. So are SANY's own complaints about its command line (`Illegal switch: ...`, `Error: -messagesAsErrors: ...`) and its help text.
- **Diagnostics are completed, not flushed per line**, as the table says: one is returned when the next thing starts, or by `close`.
- **The file** of a diagnostic is `module -> path` from the `Parsing file` lines. The parser does no I/O; if the module was not announced, `file` is `None` and the caller fills it from the command line ([21 S1](21-other-tools.md#s1-sany)).

**Checked by script, 2026-11-15.** The design agent wrote the two tables as a script and ran it over every `sany-*` file of research 12 (17 on v1.7.4 and 36 on rolling, the command and `[exit=N]` lines removed; one rolling file, `sany-message-codes.txt`, is SANY's table of message codes and not a capture, so the captures are 52) and over the SANY window of every TLC capture (110 files). Results: two semantic errors, the two level errors and the two "warning" cases give two diagnostics each with the right positions; every parse-error capture gives one diagnostic with its module and a location, on both builds, among them `sany-level` through the second location form; missing module and name mismatch give one diagnostic on each build (rolling's second copy dropped); the missing file gives one; the 4802 capture gave one warning (since D55 it gives one error); the good specs, `-help`, the option errors and the `-d` sessions give none. Of the 110 TLC captures exactly the four with a SANY or parse error give a diagnostic, one each, and none has an `OTHER` line inside the window. Not covered then, because no capture existed as a file of its own: the warning block and the `!! WARNING` line (they are inside the hand-annotated composite file of research 12, read by eye), and the split between stdout and stderr. Research 22 has since captured both (top-up); the script was not run again over its captures, which the golden tests of S5 cover.

**Rejected.** A regular expression over the whole block: SANY's output arrives line by line during a run and the reporter shows diagnostics as they complete. Treating unframed text after 2219 as SANY output when it "looks like" it: that is the defect being fixed. Ending a diagnostic's message at the first empty line (the first revision, for abort blocks): the empty line comes before the message in every capture, so the diagnostic came out empty. Classing empty lines by looking ahead to the next line: the class of a line would be known only later, and the caller would have to hold lines back.

**The stderr line** (top-up, [research 22](../research/22-more-tool-captures.md), captured with the two streams apart). Inside a TLC run SANY writes every diagnostic to stdout. The one stderr line is v1.7.4's `File does not exist: <path> while looking in these directories: ...` for a missing module; the abort block with `Cannot find source file for module ...` is on stdout, inside the 2220 and 2219 window, on both builds. So nothing in the parser changes: in a TLC run that line reaches the user on stderr, where the launcher passes TLC's stderr, and the diagnostic comes from stdout. SANY alone writes everything to stdout except the same line (v1.7.4: for a missing module and a missing file; rolling: for a missing file only); `tlaup sany` reads the two streams through one pipe ([21 S1](21-other-tools.md#s1-sany)), and the captures stay valid inputs. The 1.8.0 `-help` page carries ANSI bold codes (ESC `[1m`); they are part of its `OTHER` lines and are shown as printed.

**Tests.** Golden, inside TLC: `sany-semantic-error` gives exactly one diagnostic with line 5, column 18 to 31, module `SanyError`, message ``Unknown operator: `undefinedThing'.``, and a file ending in `SanyError.tla`; `parse-error` gives one at line 6, column 1, module `ParseError`, on both builds; in both, the later message 3002 is a TLC error of kind `parse`, not a SANY diagnostic; every other case has no diagnostics although it has unframed text after 2219. Golden, SANY alone (S5): two semantic errors; two level errors with two-line messages (both builds: research 22 captured v1.7.4's, which have the same text and order as rolling's); the precedence conflict (`sany-level`: one diagnostic at line 6, column 27); missing module (one diagnostic with no location on both builds, although rolling prints it twice; the `File does not exist` line in `other` on v1.7.4); name mismatch (one diagnostic); missing file (`Cannot find the specified file`, one diagnostic, the `File does not exist` line in `other`); 4802 (one error, top-up, D55) and the two stuttering lints (one error each); two files on one command line (two banners, the second file's errors found); the help text (no diagnostics, every non-empty line in `other`). For every SANY golden file the classes are part of the expected result, and a property holds: the lines of class `OTHER`, in order, equal `SanyResult.other`, and `lines_used` plus their number is the number of lines fed. The PlusCal "changed since last translation" warning in both spellings, from research 22's captures (`sany-stale-alg`, `sany-stale-tla`, `sany-stale-both`, `sany-stale-two-files`, and the `stale-*-tool` captures inside TLC): one warning each with its module and the text as printed, and the TLC captures exit 0 with a `no-error` verdict. A unit test feeds one diagnostic twice and gets it once.

The golden tests of SANY alone are the SANY parser's own tests, not entries of the facts file of [01 T3](01-testing.md#t3-golden-files), which takes a `RunResult` and holds TLC facts only. They are hand-written assertions on the `SanyResult`, written failing first as the facts are, and the full expected result is `SanyResult.to_dict()`, which gives plain JSON types like the types of P3 and has `from_dict` beside it for the same round-trip test. The cases inside TLC are TLC facts like any other.

**Changelog.** Fixed: "A SANY error was reported twice, and TLC messages printed after it were shown as part of it."

**Depends on.** P2 for the `SanyParser` itself, which can be built and tested on the captures of SANY alone as soon as P2 exists; P4 only for the window inside a TLC run, where the `TlcParser` hands it unframed text. **Risks.** SANY's text is free-form and differs between builds; lines the state machine does not know are kept, not dropped, so a new shape degrades to "shown as printed". (Stage 4 review, 2026-11-24: the SANY tests are the parser's own and `SanyResult` gets `to_dict()`, question Q18; the capture count and the dependency on P4, index Clerical.)

## P9 TLC version

Roadmap: "Read the TLC version from the startup message so one parser can handle several versions (decision D7). Today code 2262 is registered as ignored, so the version is never captured."

**Design.** Message 2262 is parsed with `^TLC2 Version (?P<version>\S+)(?: of (?P<date>.+?))? \(rev: (?P<rev>\w+)\)$` (research 3 and 14: `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)` and `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`). The result gets a `ToolInfo`, with `date` as printed or `None`; `line` is `rolling` when the version starts with four digits and a dot, else `stable`. A `VersionSeen` event is emitted, which is how the reporter prints the version without tlaup starting Java to ask ([13 J3](13-modules-and-java.md#j3-one-java-start)).

**"One parser handles several versions"** is met by tolerance, not by branching on the version: every difference research 1 found between the builds is a message or line that one build prints and the other does not (2779, 2210, 1005, `Linting`, 2404), and the parser accepts each whenever it appears. `ToolInfo` is there for reporters and for the day a real incompatibility needs a branch; there is none today.

A run with no 2262 (the JVM failed before TLC started) has `tool = None` and everything else still works.

**Tests.** Facts for both builds' `success` case; `version-bad-option` (2262 followed by error 1102, exit 1).

**Rejected.** Starting `java -cp ... tlc2.TLC -version` to ask (today): a second JVM start per run, and `-version` is not a TLC option ([13 J3](13-modules-and-java.md#j3-one-java-start)). Branching the parser on the version: no difference found needs it.

**Changelog.** None; shown through [22 O3](22-reporters.md#o3-terminal-reporter).

**Depends on.** P4. **Risks.** A future build may print the line in a third shape; the message is then an `Information` with no `ToolInfo`, and the header shows the build from the store only.

## P10 Error text with the trace

Roadmap: "Show the violated-invariant text together with the trace. Today the text is skipped whenever a trace exists ... Error lines keep a trailing newline and print double-spaced."

**Problem.** `cmd/tlc.py:263-269` prints either the trace or the message lines, never both; so "Invariant Small is violated." is hidden exactly when there is a trace to explain. Lines carry their `\n` and `typer.echo` adds another.

**Design.** Both halves are fixed by the model and the reporter, not by a patch: `TlcMessage.lines` never contain a newline (framing strips it, P4); the terminal reporter prints, for each error, the message text and then everything that belongs to the error in the order it arrived: the states of the trace and the related messages ([22 O3](22-reporters.md#o3-terminal-reporter)). The message text is never skipped because a trace exists.

**Tests.** The expected file for the `violation` scenario contains the line `Invariant Small is violated.` directly above the trace and no blank line between an error's lines that TLC did not print.

**Rejected.** Printing the message after the trace, where the eye ends up: TLC prints it first, and the reporter keeps TLC's order everywhere else.

**Changelog.** Fixed: "The message of a violated invariant or property was hidden when a trace was shown."

**Depends on.** P4, P5, O3. **Risks.** None of its own; the expected files show the result.

## P11 TLC text and Rich markup

Roadmap: "Print TLC text without Rich markup interpretation; today, on a terminal, `[a |-> 1]` prints as an empty line and `[/]` raises an error."

**Problem.** `live.console.print(log.strip())` (`cmd/tlc.py:175`) gives TLC's text to Rich as markup. TLA+ records are written in square brackets, which is Rich's tag syntax.

**Design.** A rule for all printing code, enforced where the text enters: **text that came from outside tlaup is never a markup string.** `tlaup.ui` and the reporters wrap such text in `rich.text.Text(...)` (or pass `markup=False, highlight=False`); only literals written in tlaup's own source may use markup. The reporter's helper for printing a line of tool output takes a `str` and builds the `Text` itself, so a caller cannot forget.

**Tests.** A reporter test feeds `OutputLine` events with `[a |-> 1]`, `[/]`, `[bold]x[/bold]` and `\[` through a console that is a terminal (forced, fixed width, colour on) and asserts the plain text of the output equals the input. The same strings appear as record values in a trace state.

**Changelog.** Fixed: "On a terminal, TLC output containing square brackets (every TLA+ record) was printed as an empty line or made tlaup fail."

**Depends on.** O3. **Risks.** None beyond a missed call site; the test covers each kind of text (output line, error line, value, diagnostic).
