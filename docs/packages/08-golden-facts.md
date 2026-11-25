# 08. Golden facts

Size: L, as two pull requests of size M (08a, 08b). Suggested model: most capable. Status: ready.

## Goal

`tests/parse/facts.py` holds hand-written facts, read from the captures, for every TLC case of both golden builds, and `tests/parse/test_facts.py` runs them against the parser. Every fact is marked `pending` and fails when run, because the parser does not exist yet; `main` stays green because pending tests are deselected by default. The parser packages remove the markers as they make the facts pass.

## Covers

- Roadmap items:
  - "Capture real `-tool` output from TLC 1.7.4 and the current rolling build ... Add expected parsed results. Drive the parser exactly as the runner does, with lines that keep their newline. These tests should fail first." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust), line 156), in part: the tests that fail first, and the driving of the parser. The files are [07](07-golden-files.md); the full expected results are [15](15-golden-expected-results.md); the parser is [09](09-parse-package-and-model.md) to [13](13-tlc-parser.md).
- Design sections:
  - [01 T3](../design/01-testing.md#t3-golden-files): "Two kinds of expectation", item 1 (the facts) and the sentence on `facts.py` and the integration tests, which now says that the file holds TLC facts only (question Q18); "How the parser is driven" for the facts. The three properties are [10](10-framing-and-codes.md) and 13; item 2 is 15.
  - [10 P1](../design/10-parser.md#p1-golden-files): "every TLC case that has a capture has facts".
  - [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings): the `pending` marker on the facts, which T10 now names beside the stateful tests.
  - Preserved-behaviour row R30 (start time, progress, finish time and duration, and coverage read from TLC's messages), with package 13: the facts are its test ([inventory](../design/preserved-behaviour-2026-11-22.md)).
  - The facts that the Tests parts of [10 P3](../design/10-parser.md#p3-result-model), [P4](../design/10-parser.md#p4-framing-and-never-losing-output), [P5](../design/10-parser.md#p5-error-traces), [P6](../design/10-parser.md#p6-json-traces-from-tlc), [P8](../design/10-parser.md#p8-sany-output) ("Golden, inside TLC") and [P9](../design/10-parser.md#p9-tlc-version) name, written as facts. The code that makes them pass is 13.

## Depends on

- [07](07-golden-files.md): `tests/parse/golden/tlc/<build>/` with the `.out` files, `cases.toml` (the case names) and `build.toml` (the `line` of each folder).
- [03](03-test-foundation.md): the pytest settings of [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings) (`testpaths = ["tests"]`, the `pending` marker and `-m 'not pending'`), and the isolation fixture under which the tests run.

Unchanged from the draft except that 03 is named. Not a dependency: [09](09-parse-package-and-model.md). The facts are written against [10 P3](../design/10-parser.md#p3-result-model) as designed; if 09 is merged when this package starts, write them against its actual names.

## Files

Creates:

- `tests/parse/facts.py`: the facts. Imports nothing from `tlaup_parse` at run time (only under `TYPE_CHECKING`), so that it loads while the parser does not exist, and nothing from pytest, so that the integration tests can use it.
- `tests/parse/test_facts.py`: runs every fact on every build folder whose line it holds for; the `pending` markers; four checks of the facts themselves that pass now.
- `tests/parse/drive.py` (stage 4's name; T3's layout lists none): how a golden file is read and fed, shared with 13 and 15. It imports `tlaup_parse` only inside the function that parses, with `importlib.import_module`, as the stateful tests do (`tests/stateful/test_signals.py`).
- `tests/parse/__init__.py`, empty, if no earlier package created it.

Changes: none. Deletes: none.

Shared within the parser track: `tests/parse/__init__.py` (whoever creates `tests/parse/` first); `drive.py`, which 10, 11 and 12 may not use (they read files their own way and may switch later) and which 13 and 15 use; `facts.py` and `test_facts.py`, which 13 edits (the markers, and facts a capture proves wrong). 08a creates the files and 08b adds to them ("Pull requests" below).

## Interfaces

Provides (all written by stage 4; T3 gives the content of a fact, not its form):

```python
# tests/parse/facts.py
LINES = frozenset({"stable", "rolling"})      # the two values of `line` in build.toml (01 T3)

@dataclass(frozen=True)
class Fact:
    case: str                                 # a case of cases.toml, e.g. "violation"
    topic: str                                # "run", "errors", "sany" or "traces" (below)
    name: str                                 # short and unique within the case, e.g. "four-states"
    check: Callable[[RunResult], None]        # raises AssertionError with a message that names what differs
    lines: frozenset[str] = LINES             # the release lines it holds for; never an exact build (T3)

    @property
    def id(self) -> str: ...                  # "<case>:<topic>:<name>"

FACTS: tuple[Fact, ...]
def facts_for(case: str, line: str) -> tuple[Fact, ...]   # used by test_facts.py and by the integration tests (01 T9)

# tests/parse/drive.py
def golden_root() -> Path                     # tests/parse/golden, from __file__ (the isolation fixture changes the cwd)
def build_folders(tool: str) -> list[Path]    # the folders of tlc/, sany/ or pcal/ that have a build.toml
def line_of(folder: Path) -> str              # build.toml's `line`
def cases_of(folder: Path) -> dict[str, dict[str, object]]   # cases.toml; `plain` cases left out
def read_lines(path: Path) -> list[str]       # binary read, split keeping each line's ending, each decoded as
                                              # UTF-8 with errors="replace": as the launcher decodes (20 G3)
def parse_tlc(path: Path) -> RunResult        # a new TlcParser, feed() once per line, close(), .result
```

A registering decorator in `facts.py` (`@fact("violation", "errors", "one-invariant-small")`) is a convenient way to build `FACTS`; the tuple must be complete once the module is imported.

**Topics** say which part of the parser a fact needs, so that package 13 can be split in two pull requests (messages, then traces) and remove markers from exactly the facts each makes pass:

| Topic | What its facts assert |
| --- | --- |
| `run` | `status`, `verdict`, `resumed`, `mode`, `workers`, `phase` at the end, `tool` (from 2262), the final statistics, coverage rows, `output`, `info`, `unknown_messages`, `warnings`, `overrides_loaded` |
| `errors` | The errors: how many, their kinds, names, related messages, and the shape of the message that opened each (body, nesting, `before`, `after`) |
| `sany` | The SANY diagnostics inside a TLC run (`RunResult.sany`), including "none" |
| `traces` | Everything inside a `Trace`: states, actions, locations, headers, variables, values, `printed`, `loop_to`, `stuttering` |

**Pending markers sit on each fact**, not on a module or a case. `test_facts.py` holds one constant:

```python
PENDING: tuple[str, ...] = ("*",)  # fnmatch patterns over Fact.id; a fact whose id matches one is marked pending
```

Each parametrised test gets `pytest.mark.pending` exactly when its fact's id matches a pattern. A parser package narrows the tuple as its first commit: package 13's first pull request could leave `("*:traces:*",)`, its second `()`. A pattern may name one case (`"tool-oom:*"`) when a capture shows a fact to be unreachable for a reason the package states. When the tuple is empty the constant stays, empty, until package [59](59-closing.md) removes the marker and its `-m` option.

**`test_facts.py`** parametrises over every pair (build folder of `tlc/`, case of its `cases.toml` that is not `plain`, fact of `facts_for(case, line_of(folder))`), with the id `<build>/<fact id>`, and runs `fact.check(parse_tlc(folder / f"{case}.out"))`. Parsing per test is fast enough (the largest file has about 1,100 lines); no module-level cache (T12 rule 8).

Consumes: from 07, the layout and the two TOML files. At run time of a fact, not at import: `tlaup_parse.TlcParser` and `RunResult` and its parts (09, 13). Compare an enum by the form 09 defines (a member taken from the result's own field, or its dictionary value), never by importing `tlaup_parse` at the top of `facts.py`.

## Tests that must pass

In `tests/parse/test_facts.py`, not pending, passing in this pull request:

- Every case of every `tlc/` build folder (not `plain`) has at least one fact for that folder's line (P1: "every TLC case that has a capture has facts"). In 08a the check covers the cases whose `source` in `cases.toml` names research 1, 2, 13 or 28, through one constant in `test_facts.py` (`COVERED_SOURCES`); 08b removes the constant, so the check covers every case.
- Every fact names a case that exists in a folder of every line in its `lines`, so a typo or a fact for a build-only case without `lines` fails.
- Fact ids are unique.
- Every pattern in `PENDING` matches at least one fact, so a stale pattern is noticed.

Pending, failing in this pull request: `test_fact`, one test per fact and build. The pull request shows the run `uv run pytest -m pending tests/parse/test_facts.py` failing (an import error while `tlaup_parse` does not exist, or the missing `TlcParser` if 09 is in): that is the "fail first" of the roadmap item and of T12 rule 6, and the parser packages show the same run turning green.

Which facts belong to which later package, as far as the design lets one tell:

| Package | Facts it makes pass |
| --- | --- |
| [10](10-framing-and-codes.md) | None. Every fact is an assertion on a `RunResult`, which only `TlcParser` builds. The four golden shapes of P4 that need only the `Framer` (`java-override-exception`, `override-method_not_public`, `override-ctor_private`, `print-marker`) are 10's own tests in `test_framing.py`; here they are `errors` and `run` facts on the result. |
| [11](11-values.md) | None directly. Values reach a fact only through a trace, so the value facts are `traces` facts, made to pass by 13 with 11's `parse_value`. |
| [12](12-sany-parser.md) | None. SANY's diagnostics inside a TLC run are `sany` facts, which need `TlcParser`'s window (13). |
| [13](13-tlc-parser.md) | All of them: `run`, `errors` and `sany` first, then `traces`. |
| [14](14-pcal-parser.md) | None. |

So "each parser package removes the markers of the cases it makes pass" comes down to one package, 13, in two pull requests.

**What gets no facts.** SANY run on its own and PlusCal ([01 T3](../design/01-testing.md#t3-golden-files), [21 S5](../design/21-other-tools.md#s5-golden-files-for-sany-and-pluscal), question Q18): a `Fact` takes a `RunResult`, and `facts.py` is shared with the integration tests, which run TLC. The hand-written assertions of those cases are their parsers' own tests, in `test_sany.py` ([12](12-sany-parser.md)) and `test_pcal.py` ([14](14-pcal-parser.md)), written failing first in the same way. The synthetic cases (10 and 13 test them one by one) and the `plain/` captures (not parsed) get none either.

Preserved-behaviour row R30: its test is the facts that a finished run has `started`, `finished` and `duration_ms` set and its progress read (that they are set, never their values, which a live run changes; see "Facts must hold for a live run too"), and the coverage rows of `coverage`, on both builds; the pull request that writes them (08a for research 1's cases, which hold all four) names the row. 13 makes them pass.

## Changelog

None.

## Context for the worker

**State of `main`.** 07 is in: the golden folders, `cases.toml`, `build.toml`. `tlaup_parse` may not exist, or 09 may have added the model with no parser; 10, 11 and 12 may be in flight beside this package. The old parser stays until package 39; its old tests went in 03b.

**Why pending, and lazy.** The design's order is "the golden move and `facts.py` (T3), failing. Then the parser work" ([01](../design/01-testing.md#order-of-work)). `main` must be green between packages, so the facts carry the `pending` marker that is registered in `pyproject.toml` since 2026-11-18 ("written before the code it tests; the work package that builds the code removes the marker") and deselected by `-m 'not pending'` ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)). A deselected test is still collected, so collection must not import `tlaup_parse`: the tests of `tests/stateful/` solve the same problem with `importlib.import_module` inside the code that runs, and so does `drive.parse_tlc`.

**The size.** About 93 TLC cases on v1.7.4 and 92 on rolling, about 95 distinct names, counted from 07's tables: research 1's 20 per build, research 2's three, research 13's ten, research 28's two (about 35 names, 08a), and about 59 of research 22's per build (08b). With several facts per case, several hundred facts. Most cases have the same facts on both lines; read both captures before deciding.

**How to read a capture and write a fact.** T3's example for `violation` is the pattern: "one error of kind `invariant` named `Small`; a trace of 4 states; state 1 has no location; state 2's action is `Next` at line 10, column 59; state 2's `n` is the integer 1; `log` in state 4 is a sequence of 3 records." Read the file, not the parser and not the design's summary:

1. Take the case's command and exit code from `cases.toml`, and open `<case>.out` of both builds side by side.
2. List the messages: every `STARTMSG <code>:<severity>` and its `ENDMSG`, with what is nested in what. Severity decides the class (1 or 2 error, 3 warning, 4 state, 0 information), and a nested error makes its parent an error (P4, rule 1). A top-level 1000 that holds exactly one nested message with a kind of its own takes that kind (P5).
3. Map each to the result with P3's event table and P5's kind table: which code opens an error, which codes continue it (2103, 2121, 2264), where 2122 and 2218 end a trace, which codes are information (`info`) and which are not in the table at all (`unknown_messages`).
4. Read the states: the header line (`2: <Next line 10, col 59 to line 10, col 76 of module Violation>`), the variables (`/\ name = ` starts one when there are several; the single variable of a one-variable spec has no prefix), a value continued on indented lines, the blank line that ends a state. For `-difftrace`, a variable missing from a state is carried from the state before, with `printed` false (P5).
5. The unframed lines between 2220 and 2219 are SANY's; after 2219 they are the spec's output.
6. Decide the verdict by P3's table, in its order.
7. Write each fact as an exact assertion (a count, a name, a kind, a line and column, a value's kind and contents), with a comment naming the capture line it was read from (`# violation.out:41`). A fact that would differ between the builds gets `lines`.

Every case gets at least, from stage 4: its verdict and status (`run`); the number of errors and their kinds in order, with names where the message has one (`errors`); the number of SANY diagnostics, usually none (`sany`); and for each trace the number of states and whether it loops or stutters (`traces`). On top of that, the facts the design names, all of which 13's package file lists by group; the main ones: status for `success`, `simulate` (no 2193), `violation`, `sany-semantic-error`; verdicts (`success` `no-error`; `simulate` and `dfid-success` `no-error-bounded`; `violation` and `deadlock-flag-multierror` `errors`; `sany-semantic-error`, `version-bad-option` and the cfg errors `tool-badcfg`, `tool-cfgsyn`, `tool-nocfg` and `tool-cfg-missing` `not-checked`; `tool-assum` `errors`; `checkpoint-recover` `resumed`); coverage rows of `coverage`, with the three `Next` rows differing in `sub_location`; P4's message shapes; P5's traces and the research 22 trace cases (the ten `-difftrace` pairs, the `-dfid` states with no action, `Step(1)`, the evaluation errors, the action property, the cfg errors, the 2285 warning); P8's diagnostics inside TLC (`sany-semantic-error`: line 5, columns 18 to 31, module `SanyError`, message ``Unknown operator: `undefinedThing'.``, a file ending in `SanyError.tla`; `parse-error`: line 6, column 1, module `ParseError`; the later 3002 is an error of kind `parse`, not a diagnostic); P9's version for both `success` cases and `version-bad-option`; P6's `dump-trace-live` keeping the `CounterExample written:` line as output.

**Facts must hold for a live run too** (T3, T9): the same facts later run against a live TLC run of a newer rolling build, with real paths. So never assert a time, a duration, a date, a pid, a seed, an `fp` number, heap sizes, rates, intermediate progress counts, or a path with `<tmp>` or `<repo>` in it (assert the file name, as P8 does: "a file ending in `SanyError.tla`"). Assert final state counts only for exhaustive search, and not for a resumed run (D54: its counts can be approximate). Wording is asserted only where it is the fact (an invariant's name, a diagnostic's message the design quotes), per T12 rule 4.

**Line, not build.** Facts are keyed by case, and by case and line where the lines differ, never by an exact build (T3). The known differences: `postcondition-false` (rolling 2404, kind `postcondition`; v1.7.4 a 1000 holding 5006, kind `config`), `stack-overflow` (v1.7.4 a raw Java stack inside 1000; rolling 1005), `coverage` (2779 on rolling only); and from research 22, the cfg errors (5001 and 5003 at the top level on rolling, nested in a 1000 on v1.7.4; kind `config` on both), the `-dfid` state messages (2216 with header `1:` on v1.7.4, 2217 with `1: ` on rolling), `ALIAS`, `-generate` and `-noGenerateSpecTE` (refused on v1.7.4), and the override cases (v1.7.4 does not honour the overrides property for these, research 13).

**Case names** are 07's, after T3's five placements (no `tool-live`, no `q01-*` or `q12-*`, the two `override-class-too-new-*` cases of research 28); read the folders, not 07's package file.

**Decisions this rests on.** D7 (the parser's tests live with it), D9 (nothing is lost: facts on `output`, `info` and `unknown_messages` are the check), D19 (two lines), D54 (the verdict comes from TLC's messages, not the exit code; the facts never read the exit code, which the parser cannot see).

## Done when

- `facts.py` has facts for every TLC case of both builds (after 08b; after 08a, for the cases of research 1, 2, 13 and 28); the four non-pending tests pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- Each pull request shows `uv run pytest -m pending tests/parse/test_facts.py` failing, with its summary line.
- Every fact carries the comment naming its capture line, so the reviewer can check it against the file; the pull request says which facts are per line and why.
- A separate review agent checks every fact of a pull request against its capture, one pull request at a sitting.
- The pull request that writes the facts R30 rests on (08a, research 1's finished runs) names inventory row R30 and those facts.

## Out of scope

- The SANY-alone and PlusCal golden assertions: [12](12-sany-parser.md), [14](14-pcal-parser.md).
- The framing shapes and the synthetic cases' tests: [10](10-framing-and-codes.md), [13](13-tlc-parser.md).
- The three properties of T3 (rebuild in `test_framing.py`, 10; event-level count, line endings and the dictionary round trip in `test_golden.py`, 13) and the expected JSON files (15).
- Running the facts against live TLC runs: [52](52-integration-tests.md).
- Removing the `pending` marker and the `-m` option: [59](59-closing.md).

## Risks

- From T3: the facts are what fails first; a weak fact ("at least one error") passes against a wrong parser. Facts are exact.
- From the cut: the facts are written against P3's names before 09 or 13 may have adjusted one. A parser package that changes a name changes the facts with it, in its own commit, and says so; it does not weaken a fact to fit. If a fact is wrong against the capture, the capture wins (13's package says the same).
- A fact that depends on a volatile value passes on the capture and fails on every live run (T9). The rule above is the guard; the reviewer checks it.
- The size. Several hundred facts read from about 12,000 lines of captures is a long review; hence the two pull requests below, along the seam by origin. Both are pending, so the split costs nothing on `main`.
- A `PENDING` pattern left in place hides facts. The check that every pattern matches something does not catch a pattern that is too wide; package 13 empties the tuple, and 59 removes the marker.

## Pull requests (decided by stage 4)

This package is delivered as two pull requests along the seam by origin (review finding A1); the index lists them as 08a and 08b, each reviewed on its own.

- **08a** (M): `drive.py`, `facts.py` and `test_facts.py` with the four self-checks (the completeness check limited by `COVERED_SOURCES`), and the facts of the cases of research 1, 2, 13 and 28 on both builds (about 35 names, the ones the design names facts for). Depends on 03 and 07.
- **08b** (M): the facts of research 22's cases on both builds (about 59 names: `-difftrace` and its twins, simulation and `-generate`, `-dfid`, `ALIAS` and parameters, the deadlock flags, the `tool-*` errors, the stale-PlusCal and lint cases, checkpoint and recover), and the removal of `COVERED_SOURCES`. Depends on 08a.

A package that names 08 as a dependency waits for 08b.
