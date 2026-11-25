# 13. The TLC parser

Size: L, as two pull requests (13a L, 13b M). Suggested model: most capable. Status: 13a built, 13b ready.

## Goal

`tlaup_parse.TlcParser` turns the lines of a `-tool` run into events and a `RunResult`: every message becomes at least one event, real counterexamples yield their states with parsed values, SANY's text is read only where SANY wrote it, the TLC version is captured, and the result carries a verdict. Every hand-written fact of every TLC golden case passes on both builds, and the two event-level properties of the golden files hold for every capture.

## Covers

- Roadmap items, all under [milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust):
  - "Fix error-trace parsing so real counterexamples yield states: location inside the angle brackets, no location on the initial state, the `/\ ` prefix, and the 'Back to state' (2122) and stuttering (2218) headers": in full on the parser side.
  - "Read the TLC version from the startup message so one parser can handle several versions (decision D7)": in full.
  - "If TLC can write traces as JSON itself (investigation list), read traces from that and skip value parsing for traces": closed by the design's decision not to use it ([10 P6](../design/10-parser.md#p6-json-traces-from-tlc)); this package adds its one test.
  - "Never lose output (decision D9) ...": in part, the interpretation level. Framing and the code table are [10](10-framing-and-codes.md); printing is package 38.
  - "Fix SANY error grouping ...": in part, the SANY window inside a TLC run. The SANY parser is [12](12-sany-parser.md); the runner's calling pattern is package 37.
  - "Capture real `-tool` output ... as golden files ... Add expected parsed results ... These tests should fail first.": in part. Packages 07 and 08 moved the files and wrote the failing facts; this package makes the TLC facts pass; 15 adds the expected results.
  - "Move the parser stack ... into its own import package": in part, `tlc.py`. See [09](09-parse-package-and-model.md).
- Design sections:
  - [10 P5](../design/10-parser.md#p5-error-traces): all of it. The `kind` data of its "Kind" bullet is already in `codes.py` (package 10); the behaviour is here.
  - [10 P6](../design/10-parser.md#p6-json-traces-from-tlc): nothing is built. The decision is "not used": the text is the one source of traces for both builds. This package only adds the `dump-trace-live` assertions.
  - [10 P9](../design/10-parser.md#p9-tlc-version): all of it.
  - [10 P3](../design/10-parser.md#p3-result-model): the "Emitted when" column of the event table, the rule that a nested message produces no event, "How `status` is set", "The verdict" as far as the parser decides it, and `resumed`. The types are 09's. What the runner sets (`INTERRUPTED`, `counts_approximate`, `incomplete` after a signal) is package 37; the disagreement warning is 39.
  - [10 P4](../design/10-parser.md#p4-framing-and-never-losing-output): "Interpretation" (rules 1 to 4), the interpretation half of "Never losing output" (the two counters and the event-level count), and the golden and synthetic tests that need a result.
  - [10 P8](../design/10-parser.md#p8-sany-output): the bullet "Scope inside TLC" and the tests headed "Golden, inside TLC".
  - [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package): `TlcParser` of the public surface.
  - Preserved-behaviour rows R29 (severity, not the code, decides error or warning; with 10) and R30 (start, progress, finish and coverage read from TLC's messages; with 08, whose facts are its test) ([inventory](../design/preserved-behaviour-2026-11-22.md)).
  - [10 P1](../design/10-parser.md#p1-golden-files) and [01 T3](../design/01-testing.md#t3-golden-files): the facts made to pass, and the second and third of T3's three properties ("nothing is lost at the event level", "line endings do not matter"). Stage 4 gives these two to this package and not to 15: they need the parser and no expected file, and without them this package would be merged with its D9 guarantee checked on the fact cases only.

## Depends on

- [09](09-parse-package-and-model.md): `RunResult` and every part of it, the twenty events, `to_dict()` and `from_dict()`.
- [10](10-framing-and-codes.md): `Framer`, `Unframed`, `CODES` with names and kinds.
- [11](11-values.md): `parse_value`.
- [12](12-sany-parser.md): `SanyParser`, `SanyStep`, `SanyLineClass`, `SanyResult`.
- [08](08-golden-facts.md) (both pull requests): `tests/parse/facts.py` and `tests/parse/test_facts.py`, every case marked `pending`.
- [07](07-golden-files.md): `tests/parse/golden/tlc/<build>/` with `cases.toml` and `build.toml`, and `synthetic/` with T3's twelve cases, `cut-off` and `unknown-code` among them.

Changed from the draft: 07 and 09 are named (the draft had them through 10 and 08); nothing else.

## Files

Creates:

- `src/tlaup_parse/tlc.py`: `TlcParser`.
- `tests/parse/test_golden.py`: the per-file properties (below). Package 15 adds the comparison with the expected JSON to this file.
- `tests/parse/test_tlc.py` (stage 4's name; the layout of T3 lists none): the tests on synthetic cases and on parser behaviour that is not a fact about one capture.

Changes:

- `src/tlaup_parse/__init__.py`: export `TlcParser`.
- `tests/parse/test_facts.py`: the `PENDING` patterns, narrowed as the first commit of each pull request; `tests/parse/facts.py` only where a capture proves a fact wrong.
- `src/tlaup_parse/codes.py`, only if a fact shows a `kind` of package 10's table to be wrong; say so in the pull request.

Deletes: nothing. `src/tlaup/tlc/parser.py` and the other old modules stay until package 39; their old tests went in 03b.

Shared: `src/tlaup_parse/__init__.py` with package 14 (one line each); `tests/parse/test_golden.py` is created here and extended by 15, which comes later.

## Interfaces

Provides ([10 P2](../design/10-parser.md#p2-the-tlaup_parse-package)):

```python
class TlcParser:
    def __init__(self, *, max_output_lines: int = 10_000): ...
    def feed(self, line: str) -> list[Event]: ...  # one line, with or without its newline
    def close(self) -> list[Event]: ...  # end of input: flush anything still open
    @property
    def result(self) -> RunResult: ...
```

`result` is the same object for the life of the parser, filled as lines arrive; a reporter is handed it with every event ([22 O1](../design/22-reporters.md#o1-reporter-interface)).

**The path of a line.** The parser owns one `Framer` and one `SanyParser`.

1. The line goes to the `Framer`. Each item it returns is handled in order.
2. An `Unframed` item adds 1 to `result.unframed_lines`. Between message 2220 and message 2219 (the SANY window) it goes to the `SanyParser`: each diagnostic the step completed is appended to `result.sany` and announced with `DiagnosticFound`; a line of class `OTHER` becomes an `OutputLine`; a line of any other class produces nothing. Outside the window it becomes an `OutputLine`.
3. When 2219 arrives the `SanyParser` is closed: a diagnostic still open is announced, `result.module_files` and `result.sany_lines_used` are taken from its result, and the window is shut for good. Unframed text after that is the spec's output, whatever it looks like.
4. A top-level `TlcMessage` is interpreted (below). A non-empty `before` adds 1 to `unframed_lines` and becomes an `OutputLine`; so does a non-empty `after`, and its `OutputLine` comes after the message's own events (P4's synthetic case). That `before`'s line comes ahead of them is stage 4's reading by symmetry; no capture has either at the top level.
5. Every `OutputLine`'s text is appended to `result.output`; when that list is longer than `max_output_lines` the oldest line is dropped and `result.output_dropped` grows by one. The event is emitted all the same, which is how a reporter prints everything while the result stays bounded.

**Interpreting a message** ([10 P4](../design/10-parser.md#p4-framing-and-never-losing-output), rules 1 to 4, and the event table of [10 P3](../design/10-parser.md#p3-result-model), which is the specification of every row below):

- Only top-level messages are interpreted. A nested message produces no event, whatever its code.
- **Severity first.** The class is error for severity 1 or 2, warning for 3, a trace state for 4, information for 0 (and for anything else, by default). If a message nested at any depth has severity 1 or 2 the top-level message is an error; a nested 3 makes it at least a warning.
- **Error.** With one of the continuation codes 2103, 2121, 2264 and a current error: appended to that error's `related`, `ErrorExtended`. Otherwise a new `TlcError` is appended to `result.errors` and becomes the current error, `ErrorOpened`; its kind is the code's `kind` in `CODES`, or `other`; a continuation code with no current error opens an error of kind `other`. `status` becomes `FAILURE`.
- **Kind of a 1000 that holds one message** (P5, top-up): when a top-level 1000 has exactly one nested message and that message's code has a kind other than `exception` or `other`, the error takes the nested message's kind. So v1.7.4's cfg errors (1000 holding 5001 or 5003), its evaluation error in an invariant (1000 holding 2179) and its `postcondition-false` (1000 holding 5006, kind `config`) get the kind rolling gives them at the top level.
- **Error name** (P5): 2110 `Invariant (?P<name>\S+) is violated\.`; 2116 `Temporal property (?P<name>\S+) was violated\.`; 2404 `Postcondition (?P<name>\S+) `. No match leaves `None` (v1.7.4's liveness message has no name).
- **Warning.** Appended to `result.warnings`, `WarningFound`.
- **Typed information**, by code: 2262 `VersionSeen` (P9); 2187, 2188, 2271 `ModeSeen`; 2220, 2219, 2185, 2189, 2190, 2192, 2267 `PhaseChanged` (2185 also sets `started`); 2200, 2209 `ProgressMade`; 2199, 2194, 2268, 2193, 2210, 2204 `StatsUpdated`; 2221, 2772, 2773, 2774, 2779 `CoverageAdded`; 2168 `OverrideLoaded`; 2195 `CheckpointStarted`; 2196 `CheckpointWritten`; 2197, 2198 `Recovered` (sets `resumed`); 2186 `Finished` (phase `FINISHED`, `finished`, `duration_ms`, and `status = SUCCESS` if it was still `RUNNING`).
- **A typed code whose text does not match its pattern** is an `Information` and is kept in `result.info`. Nothing is dropped because a pattern failed.
- **Any other code that is in `CODES`**: `Information`, kept in `result.info` (2212 and 2269 in the first captures; 2201, 2202, 2205 to 2208, 2501 and the four `1000:0` messages of a `-generateSpecTE` run on v1.7.4 are of this kind).
- **A code that is not in `CODES`** is appended to `result.unknown_messages` in every class; as information it arrives as `UnknownMessage`, as an error or warning it arrives as `ErrorOpened` (kind `other`) or `WarningFound` like any other. `unknown_messages` holds only such codes (P3: "codes that are not in codes.py"): a message whose code is in `CODES` and that comes out as `UnknownMessage` for another reason (a state header that matches no pattern, and in 13a every state message) is not added to it.

**Trace states** ([10 P5](../design/10-parser.md#p5-error-traces)):

- State messages are 2217 on both builds and 2216 on v1.7.4 (`-dfid`). The header is the first line: `^(?P<n>\d+): <(?P<inner>.*)>$`; if `inner` matches `^(?P<action>.+?) line (\d+), col (\d+) to line (\d+), col (\d+) of module (?P<module>\S+)(?: \(.*\))?$` the state has an action and a location, otherwise no action and `inner` stays in `header`. The `-dfid` header `^(?P<n>\d+): ?$` is a state with no action and no location. A header that matches none of these makes the message an `UnknownMessage`.
- The action is kept as printed: a sub-action's name (`Pick`), with its arguments on rolling (`Step(1)`).
- `TraceState.lines` is the whole message body as printed. Variables: a line starting `/\ <name> = ` begins one; if no line of the body starts with `/\ `, the first line `<name> = ` begins the only one; following lines belong to it up to the next start or the end; trailing blank lines are dropped. `Variable.raw` is the value's text with its lines joined by `\n`; `Variable.value` is `parse_value(raw)`.
- 2122 (`^(?P<n>\d+): Back to state: <(?P<inner>.*)>$`) sets `trace.loop_to = n`; 2218 (`^(?P<n>\d+): Stuttering$`) sets `trace.stuttering`. Neither adds a state.
- A state belongs to the current error; its `trace` is created with the first state. `TraceStateAdded` for each state.
- `TraceClosed`, once per trace: on 2122 or 2218 (the event carries that message); for a trace with neither, when the first top-level message arrives that is not a state after the trace has one (the event carries no message and comes before that message's own events), or at `close()`.
- **`-difftrace`**: a variable a state leaves out is taken from the previous state of the same trace, in that state's order, with `printed=False` and the `raw` and `value` of the state it came from; the state's `lines` stay as printed. A variable the previous state did not have is taken as printed. With `ALIAS` the variables are the alias record's fields and the rule is the same.

**Version** ([10 P9](../design/10-parser.md#p9-tlc-version)): 2262 is matched with `^TLC2 Version (?P<version>\S+)(?: of (?P<date>.+?))? \(rev: (?P<rev>\w+)\)$`; `ToolInfo.line` is `rolling` when the version starts with four digits and a dot, else `stable`; `raw` is the whole line. A run with no 2262 has `tool = None`.

**Status and verdict** ([10 P3](../design/10-parser.md#p3-result-model)):

- `status`: `RUNNING` from the start; `FAILURE` as soon as an error is opened or a SANY diagnostic of severity `error` is found, and it never goes back; `SUCCESS` at 2186 if still `RUNNING`; otherwise it stays `RUNNING` after `close()`.
- `verdict` is decided in `close()`, first rule that applies: `errors` if an error was opened whose kind is `invariant`, `deadlock`, `property`, `assertion`, `assumption`, `postcondition` or `evaluation`, or is `exception` or `other` and the phase had reached `INITIAL_STATES` when it was opened; `not-checked` if any other error was opened or a SANY diagnostic of severity `error` found; `incomplete` if there was no 2186; `no-error-bounded` if the mode is `simulate` or `depth-first`; else `no-error`. Message 2193 is not read for the verdict.

**`close()`** closes the framer (messages still open come out `truncated` and are interpreted like any other), closes the SANY parser if the window is still open, closes an open trace, decides the verdict, and returns the events all of that produced.

Consumes: everything listed under Depends on, by the names given there.

Used by: `run_tlc` (package 37) feeds it the launcher's stdout lines and hands each event to the reporter; it tells the launcher about `CheckpointStarted` and `CheckpointWritten` (D52). The reporters (36, 38, 40) read the events and the result. The integration tests (52) run `facts.py` against live results.

## Tests that must pass

All in `tests/parse/`. Every capture is driven as the runner will drive it ([01 T3](../design/01-testing.md#t3-golden-files)): read in binary, split into lines that keep their newline, each decoded as UTF-8 with `errors="replace"`, fed one line per call, then `close()`.

**`test_facts.py` (package 08): each pull request's first commit narrows `PENDING` (13a to `("*:traces:*",)`, 13b to `()`), on both builds, and the pull request shows that run red (T12 rule 6).** As far as the design names them, the groups are:

- Status (P3): `success`, `simulate` (success with no 2193), `violation`, `sany-semantic-error`.
- Verdict (P3, D54): `success` is `no-error`; `simulate` and `dfid-success` are `no-error-bounded`; `violation` and `deadlock-flag-multierror` (exit 0, two errors) are `errors`; `sany-semantic-error`, the cfg errors `tool-badcfg`, `tool-cfgsyn`, `tool-nocfg` and `tool-cfg-missing`, and `version-bad-option` are `not-checked`; the false `ASSUME` is `errors`; the `recover` captures have `resumed`.
- Coverage (P3): `coverage` on both builds, among them that the three `Next` rows differ in `sub_location`.
- Messages (P4): `postcondition-false` on rolling has one error of kind `postcondition`; `java-override-exception` has one error whose message is the 1000 with the nested 2154; `override-method_not_public` has its finish time from the 2186 after the nested messages; `override-ctor_private` has one error, not two; `print-marker` has the two quoted lines as output and no message 9999; the liveness cases have 2212 in `info` and nothing in `unknown_messages`.
- Errors and traces (P5): `violation` (4 states; state 1 has no location; state 2's action is `Next` at line 10, column 59; the values T3 quotes), `deadlock`, `assertion-failure` (one error, 3 states, two related messages: 2121 before the states and 2103 after), `liveness-back-to-state` (3 states, `loop_to == 1`), `liveness-stuttering` (2 states, `stuttering`), `multi-error-continue` (3 errors, each with its own trace), `print-output` (printed lines are output, not states).
- Top-up cases (P5, research 22's captures): each `-difftrace` capture gives the same variables, values and order as its plain twin, with `printed` false exactly where TLC left a variable out (ten pairs); `dfid-violation-deep` gives states with no action (`dfid-violation` finds no error); the simulation and `-generate` violations give their traces; `Step(1)` is the action of the parameterised case; the false `ASSUME` is one `assumption` error with no trace; the evaluation error in `Next` is `evaluation` with a trace and the one in an invariant is `evaluation` on both builds; the action-property violation is `property` with no loop; the three cfg errors are `config` on both builds; 2285 is a warning.
- SANY inside TLC (P8): `sany-semantic-error` has exactly one diagnostic (line 5, columns 18 to 31, module `SanyError`, the message ``Unknown operator: `undefinedThing'.``, a file ending in `SanyError.tla`); `parse-error` has one at line 6, column 1, module `ParseError`; in both the later 3002 is a TLC error of kind `parse`, not a diagnostic; every other case has no diagnostics although it has unframed text after 2219; the `stale-*-tool` captures have one warning each, exit 0 and verdict `no-error`; 4802 and the stuttering lint inside TLC are errors.
- Version (P9): both builds' `success` (a `ToolInfo` with `line` `stable` and a date, or `rolling` and none); `version-bad-option` (2262, then error 1102 of kind `usage`).
- JSON traces (P6): `dump-trace-live` (rolling) keeps the `CounterExample written: ...` line as output and still parses the trace from the text.

If a fact is wrong against the capture, the capture wins: correct the fact in its own commit and say so; do not weaken a fact to fit the parser.

Rows R29 and R30: the facts of the groups above are R30's test (08 wrote them), and `unknown-code.out` below is R29's (severity decides the class whatever the code); the pull request that makes them pass names both rows.

**`test_golden.py`**, parametrised by globbing over every `.out` file of `tests/parse/golden/tlc/<build>/` (not `plain/`) and of `synthetic/`:

- **Nothing is lost at the event level** (T3, P4): the number of `OutputLine` events equals `result.unframed_lines - result.sany_lines_used`; `unframed_lines` equals the count obtained a second way, by running the public `Framer` over the file and counting `Unframed` items plus non-empty top-level `before` and `after` texts; and every top-level message that `Framer` run returned is carried by at least one event (`event.message == m`).
- **Line endings do not matter**: feeding each line with `\n`, without it, and with `\r\n` gives equal `result.to_dict()` and equal event lists.
- **The dictionary form holds** (P3): `to_dict()` passes `json.dumps`, and `RunResult.from_dict(r.to_dict()) == r`.
- No file makes `feed` or `close` raise.

**`test_tlc.py`**:

- Synthetic cases that need a result (P3, P4): the cut-off file ends with `status` `RUNNING` and verdict `incomplete`, and its last message is `truncated` and still has its event; a severity-1 message nested in a severity-0 one is one error; an end marker with text after it at the top level gives an `OutputLine` after the message's own event, and the count above is one higher than the number of `Unframed` items; `STARTMSG -1` and the leading-zero marker are output lines; `invalid-utf8.out` parses, with the replacement character in the unframed line, which falls inside the SANY window and is counted as SANY's, not as an output line (13a; reworded while building it) and in the value (13b); `unknown-code.out` gives one `ErrorOpened` of kind `other`, one `WarningFound` and one `UnknownMessage`, all three messages in `unknown_messages`, and `status` `FAILURE`.
- The output bound: a parser built with a small `max_output_lines` (for example 2), fed a capture with more unframed lines (`print-output`), keeps the newest lines in `output`, counts the rest in `output_dropped`, and still emits one `OutputLine` per line.
- Events in order, for one capture each: `assertion-failure` gives `ErrorOpened`, `ErrorExtended` (2121), three `TraceStateAdded`, `TraceClosed`, `ErrorExtended` (2103); `liveness-back-to-state` ends its trace with a `TraceClosed` that carries the 2122 message; `multi-error-continue` closes each trace before the next `ErrorOpened`; the SANY window of `sany-semantic-error` gives `DiagnosticFound` before the `PhaseChanged` of 2219.
- The reading-after-every-line check for the roadmap's SANY defect: reading `result.sany` after every `feed` changes nothing.
- A checkpoint capture gives `CheckpointStarted` with the folder and `CheckpointWritten`; the `recover` capture gives `Recovered` with the two numbers of 2198.

Which tests are 13b's: in `test_facts.py`, every fact of the topic `traces`; in `test_tlc.py`, the event orders of `assertion-failure` (its three `TraceStateAdded` and `TraceClosed`), `liveness-back-to-state` (the `TraceClosed` that carries 2122) and `multi-error-continue` (each trace closed before the next `ErrorOpened`), and the value half of `invalid-utf8.out`. Everything else above is 13a's, and `test_golden.py`'s properties hold in both: in 13a a state message is an `UnknownMessage`, which carries its message.

Old tests: none are left (03b).

## Changelog

None in this package. The entries of the sections it covers describe what `tlaup tlc` shows and are written by package 39 at the switch:

- P5, Fixed: "Counterexample traces were not shown: real TLC output parsed to zero states. Traces now show every state, the action and its location, the loop-back state of a liveness counterexample, and stuttering."
- P4, Fixed (shared with package 10): "Errors with a TLC message code tlaup did not know (for example a false POSTCONDITION, code 2404) were not shown at all. Every message TLC marks as an error is now shown, and output tlaup does not recognise is printed as TLC wrote it."
- P8, Fixed (shared with package 12): "A SANY error was reported twice, and TLC messages printed after it were shown as part of it."
- P9 and P6: none.

## Context for the worker

- **State of `main`.** `tlaup_parse` has the model, framing, the code table, `parse_value` and `SanyParser`. Nothing in `tlaup` imports it; the old parser stack under `src/tlaup/tlc/` runs every `tlaup tlc` and stays untouched until 39. So this package can be merged with any of its parts imperfect only in the sense that its own tests allow; no command reaches it.
- **What is carried over from the old `TlcParser`.** The patterns for 2185 (`Starting... (<time>)`) and 2200 parse the real captures and can be taken as a start. Not carried over: the trace header pattern (it expects the location after the bracket, so every real trace has zero states); variables matched as `^(\w+) = ` on any line (no `/\ ` prefix, and a wrapped string containing ` = ` would split a variable); the coverage pattern (it reads the two numbers after the colon the wrong way round, knows only 2772 and 2773, and has no second span); `datetime` timestamps; the early return for an unregistered code before the severity is looked at (old line 120), which is the defect D9 names; the unbounded `output_lines`; and the 2186 pattern, which knows only `Finished in <n>ms`.
- **Shapes in the captures that the design does not spell out.** Read them in the golden files; these are the ones seen when the package was cut:
  - 2186 ([10 P3](../design/10-parser.md#p3-result-model), `Finished`): read with `^Finished in (?P<ms>\d+)ms at \((?P<at>.+)\)$`, which all 271 messages 2186 in the captures match (`Finished in 725ms at (2026-11-14 22:27:03)`). `Finished in 01s at (...)` and `02min 13s` are TLC's plain output, which the parser is never given. A 2186 that does not match is still `Finished`, with both fields `None`.
  - 2200: `Progress(7) at <time>: 26 states generated (2,160 s/min), 16 distinct states found (1,329 ds/min), 0 states left on queue.`, also without the rates; numbers have thousands separators. 2209 (simulation): `Progress(-1) at <time>: 61 states generated, -1 distinct states found, -1 states left on queue.`; -1 stays -1.
  - 2199: `26 states generated, 16 distinct states found, 0 states left on queue.` 2204 (`-dfid`): `7 states generated, 7 distinct states found.` 2210 (simulation): `The number of states generated: 61` and a second line. 2194: `The depth of the complete state graph search is 7.` 2268: kept as printed.
  - Coverage: `<Init line 5, col 1 to line 5, col 4 of module M>: 1:1` (2773, distinct then count); `<Next line 6, col 1 to line 6, col 4 of module M (6 12 6 40)>: 3:12` (2772, with the second span); `<TypeOK line 4, col 1 to line 4, col 6 of module M>` (2774, no count); `<x line 3, col 11 to line 3, col 11 of module M>: 4` (2779, rolling only); `  |line 6, col 12 to line 6, col 12 of module M: 16` (2221; `depth` is the number of `|`). Each row is its own message.
  - 2187: `Running breadth-first search Model-Checking with fp 22 and seed ... with 1 worker on 12 cores ...`; 2188: `Running Random Simulation with seed ... with 1 worker ...`; 2271: `Running depth-first search Model-Checking ...`. The mode words of the result are P3's (`exhaustive search`, `simulate`, `depth-first`), not TLC's. P3 names 2187 as the source of `workers`; the other two lines carry the same words. All three set it from the `with <n> worker(s)` in their text; a line without it leaves `workers` as it was.
  - 2195: `Checkpointing of run <folder>`; 2196: `Checkpointing completed at (<time>)`; 2197: `Starting recovery from checkpoint <folder>/`; 2198: `Recovery completed. N states examined. M states on queue.`
- **Order of messages a worker could assume wrongly.** 2187 comes before the SANY window. In `assertion-failure` the order is 2132, 2121, the states, then 2103, so related messages can follow the trace. With `-continue` each error is followed by its own 2121 and states. A liveness error is 2116, 2264, the states, then 2122 or 2218. In `-simulate` and `-generate` on rolling the first state names `Init` with a location.
- **Nested messages in the captures** are never deeper than one level, the parent is always a severity-1 1000 or 2154, and the nested one is severity 0 (1000, 2154, 5006; with research 22 also 2179, 5001, 5003). The escalation rule for a nested error exists for the guarantee and is tested on the synthetic case only.
- **Decisions.** D9: nothing is lost; here that means every unframed line is an `OutputLine` unless the SANY parser used it, and every message has an event that carries it. D54: the verdict comes from the messages because the exit code misleads in three captured ways (`-deadlock -continue` with two violations exits 0; a too-shallow `-dfid` exits 0; `-generate` on a correct spec never ends), and `-difftrace` states are completed by carrying variables forward (10 of 10 pairs rebuilt exactly). D55: SANY's 4802 is an error. D19: two builds are supported, and "one parser handles several versions" is met by tolerance, never by branching on `ToolInfo`. D8: reporters never parse, so whatever a reporter needs must be in the result or the event.
- **The verdict's phase condition.** "`exception` and `other` once the phase has reached `INITIAL_STATES`" means the phase at the moment that error was opened, not at `close()` (the same rule as the override hint of [22 O3](../design/22-reporters.md#o3-terminal-reporter), "the phase was still `STARTING` when the error opened"). `TlcError` has no field for it; keep it as private state of the parser.
- **`OverrideLoaded`.** The pattern `^Loading (\S+) operator override from (\S+) with signature: ` matches all 43 messages 2168 in the captures (P3), but the second group has two shapes: a class name (`tlc2.overrides.TLCOverrides`) and, for an override found as a class file beside the module (12 of the 43), a `file:` address ending in `.class`. P3 calls the group `java_class` and builds `overrides_loaded` as `"<java_class>.<operator>"` from it. Keep the group as printed in both shapes; do not derive a class name from the address.
- **The collision estimate.** `FinalStats.collision_probability` is one string, and message 2193 prints one estimate (`calculated (optimistic):  val = 8.7E-18`) or two (a second line `based on the actual fingerprints:  val = ...`). Keep the value of the `calculated (optimistic)` line, which every 2193 in the captures has, as printed.
- **A few cases the design calls "not seen" and gives no rule for**: a second SANY window in one run; a state message arriving after its trace was closed by 2122 or 2218; a severity-4 message whose code is not a state code; `feed` after `close()`. None occurs in a capture. Whatever the code does there, it must not raise and must not lose the message (it has an event that carries it); say in the pull request what it does. Do not add fields or events for them.
- **Typed codes.** P3's event table, P4's rule 2 and P5 now list the same typed codes (2271, 2204, 2210 and 2195 to 2198 among them); 2205 to 2208 and 2501 are `Information`.
- **`-dfid` is parsed only far enough** that its traces are not unknown messages (D54). Its early stops are TLC's; the verdict calls such a run bounded. Nothing more is designed.
- **Known gaps the design postpones; do not close them here:** whether tlaup's exit code should follow the verdict (milestone 4); using `-dumpTrace json` for the loop edge on rolling (milestone 4, if a need appears); an action header whose string argument contains ` line 3, col 4 to ...` (falls back to an unknown message); how TLC prints a string with a newline (falls back to a `raw` value).
- **A suggested order of commits**, which also gives the seam of the two pull requests: 13a is (1) the markers off except `*:traces:*`, red; (2) the path of a line, the classes, the typed information, status, verdict, the SANY window, the version, with state messages still arriving as `UnknownMessage`; (3) error kinds, names and related messages; (4) `test_golden.py` over every file. 13b is (5) the `traces` markers off, red; (6) trace states, `TraceClosed`, loop and stuttering; (7) `-difftrace` and `-dfid`.
- **Golden files are not to be edited to make a test pass.** A capture is evidence. If the rolling folder's facts fail in a way that points at the capture, say so; a new capture is package 07's script, not a hand edit.
- **Windows (D15):** lines may arrive with `\r\n`; the framer removes it. Nothing else here depends on the platform.
- **mypy strict:** dispatch on the code with a table or `match`; the union `Event` is closed, and package 09's test counts its members.

## Done when

- Every TLC case of `test_facts.py` passes on both builds with no `pending` marker left on a TLC case (after 13b; after 13a, every fact outside `*:traces:*`); `test_golden.py` and `test_tlc.py` pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- The first commit is the removal of the markers, and the pull request shows the red run it produced (T12 rule 6).
- The import-isolation test of 09 still passes.
- The pull request lists every fact that was corrected and why, what the code does in the "not seen" cases, any `kind` changed in `codes.py`, and the inventory rows it covers (R29, R30).
- No changelog entry. No document to update; if a signature of P2 or P3 was adjusted, the pull request says so (the design's rule for signatures).

## Out of scope

- `PcalParser`: 14. The full expected JSON per case, `--update-expected` for them and their review against the captures: 15.
- Calling the parser from a run, telling the launcher about a checkpoint, setting `INTERRUPTED`, `counts_approximate` and the runner's `incomplete`: 37.
- Everything a user sees. [10 P10](../design/10-parser.md#p10-error-text-with-the-trace) (the error text shown with the trace) and [10 P11](../design/10-parser.md#p11-tlc-text-and-rich-markup) (TLC text never read as Rich markup) are rules for the terminal reporter and are built and tested in package 38; the parser's share of P10 is only that no line carries a newline, which the framer already gives. The result line, the override hint and the changed-variable mark are 38 as well.
- The warning when TLC's exit code and the verdict disagree, and its unit test (P3, Tests): `print_run_notes`, package 39.
- Running the facts against a live TLC: 52.
- Deleting `src/tlaup/tlc/parser.py`, `codes.py`, `models.py`, `values.py`, `sany.py`, and the changelog entries above: 39.

## Risks

- From P1: the golden files may reveal more breakage than the known cases. The per-file properties over every capture are where that shows.
- From P4: severities 2 and 5 were never seen; 2 is treated as an error and 5 as information.
- From P5: an action header with a string argument that contains location-like text would break the location pattern (not produced; the fallback is safe). `-difftrace` with a variable that changes to a value that prints the same, and a liveness trace whose loop state keeps a variable unchanged, were not captured. `-dfid` is parsed only as far as its traces.
- From P9: a future build may print the version line in a third shape; it is then an `Information` and `tool` is `None`.
- From P3: the names are milestone 4's JSON schema.
- From the cut: this is the largest package of the track and the first place the model of 09, the kinds of 10 and the facts of 08 meet real code. Expect corrections to all three in this pull request; each is listed in its description. It is split into two pull requests, messages and events first, traces second (below); 13a is still a week of work and a long review.
- From the cut: facts were written by another hand before any parser existed. A fact that fails may be wrong; the rule above (the capture decides, the correction is its own commit) keeps that from turning into weakened facts.

## Pull requests (decided by stage 4)

This package is delivered as two pull requests, along the seam of the suggested order of commits above; the index lists them as 13a and 13b.

- **13a** (L): the path of a line, message classes, typed information, status, verdict, the SANY window, the version (P9), error kinds and related messages. Every state message arrives as an `UnknownMessage` here, which P5 allows, so every per-file property holds; it is not added to `unknown_messages`, since its code is in `CODES`. It removes the `pending` patterns of package 08 except `*:traces:*`. Depends on 07, 08, 09, 10, 12.
- **13b** (M): trace states, `TraceClosed`, loops and stuttering, `-difftrace`, `-dfid`, the one P6 test, and the tests listed above as 13b's; it empties `PENDING`. Depends on 13a and 11.

A package that names 13 as a dependency waits for 13b.
