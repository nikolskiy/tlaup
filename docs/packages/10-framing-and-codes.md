# 10. Framing and the code table

Size: M. Suggested model: most capable. Status: built.

## Goal

`tlaup_parse` can turn any sequence of lines into plain text and framed TLC messages and write them back exactly as they came, and it has the table of TLC message codes with a name and, for errors, a kind. The exact rebuild is proved over every golden and synthetic file and by a Hypothesis test.

## Covers

- Roadmap items:
  - "Never lose output (decision D9): anything the parser does not recognise is shown exactly as TLC printed it. This covers unregistered message codes ... add the six missing error codes including 2404. A malformed start marker such as `STARTMSG -1` must not raise." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the framing level and the code table. The interpretation level (severity first, an event for every message) is [13](13-tlc-parser.md); showing the text is package 38.
  - "Move the parser stack (message framing, codes, values, models, SANY parser) into its own import package" ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: `framing.py` and `codes.py`. See [09](09-parse-package-and-model.md) for the other parts.
  - The framing property test is the last paragraph of [01 T7](../design/01-testing.md#t7-property-tests-for-values), which has no roadmap item of its own ("Roadmap candidate, accepted").
- Design sections:
  - [10 P4](../design/10-parser.md#p4-framing-and-never-losing-output): "Facts", "Framing", the framing half of "Never losing output" (the exact rebuild), "Reading a message's text" as a test against the captures (the method itself is 09's), and `codes.py`. The part headed "Interpretation" (rules 1 to 4) and the event-level count are package 13.
  - [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package): `Framer`, `render_framed`, `Unframed` of the public surface.
  - [10 P5](../design/10-parser.md#p5-error-traces): only the data of its "Kind" bullet, as the `kind` column of the code table, and the upstream name of 2285 its information bullet records. The behaviour built on it is 13.
  - Preserved-behaviour row R29 (a message's severity, not its code, decides whether it is an error or a warning), with package 13: the framing half ([inventory](../design/preserved-behaviour-2026-11-22.md)).
  - [01 T7](../design/01-testing.md#t7-property-tests-for-values): the framing property in `test_framing_props.py`.
  - [01 T3](../design/01-testing.md#t3-golden-files): the first of the three properties ("nothing is lost at the framing level"), over every file. Stage 4 gives it to this package and not to 15, because it needs only the `Framer` and is the proof of this package's work.

## Depends on

- [09](09-parse-package-and-model.md): the package skeleton and `__init__.py`; `TlcMessage` with `lines`, `nested` and `text_lines()`; `ErrorKind`; the import-isolation test, which covers the two new modules without change.
- [07](07-golden-files.md): `tests/parse/golden/tlc/<build>/*.out` and `plain/*.out`, `sany/`, `pcal/`, and `synthetic/` with its `.why` files.
- [03](03-test-foundation.md): `hypothesis` as a development dependency, its profiles in `tests/conftest.py`, and the mechanical check that no `.py` file under `tests/` contains `@!@!@STARTMSG`.

Changed from the draft: 03 is named because the Hypothesis dependency and profiles come from it; no other change. This package runs beside [11](11-values.md) and [12](12-sany-parser.md).

## Files

Creates:

- `src/tlaup_parse/framing.py`: `Unframed`, `Framer`, `render_framed`.
- `src/tlaup_parse/codes.py`: `CodeInfo`, `CODES`.
- `tests/parse/test_framing.py`, `tests/parse/test_framing_props.py` (both named in T3's layout).
- `tests/parse/test_codes.py` (stage 4's name; the layout lists none): the table tests.

Changes:

- `src/tlaup_parse/__init__.py`: export `Framer`, `Unframed`, `render_framed`. `CODES` and `CodeInfo` are not in P2's public surface and stay private to the package.
- `.pre-commit-config.yaml`: the hook `no-typed-tool-output` gets `tests/parse/test_framing_props.py` in its `exclude`, by exact path, with a comment naming [01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 3, which exempts Hypothesis strategies (03's rule for these exceptions).

Deletes: nothing. `src/tlaup/tlc/codes.py` and `parser.py` stay until package 39.

Shared with 11 and 12, which run beside this package: `src/tlaup_parse/__init__.py` (one import line and `__all__` entries each).

## Interfaces

Provides ([10 P2](../design/10-parser.md#p2-the-tlaup_parse-package), [P4](../design/10-parser.md#p4-framing-and-never-losing-output)):

```python
@dataclass(frozen=True)
class Unframed:  # a line outside every message; written by stage 4 from "Unframed(line)" in P4
    line: str  # without its line ending


class Framer:
    def feed(self, line: str) -> list[Unframed | TlcMessage]: ...  # one line, with or without its line ending;
    def close(self) -> list[Unframed | TlcMessage]: ...  # only top-level items are returned


def render_framed(item: Unframed | TlcMessage) -> list[str]: ...  # the input lines the item was built from


@dataclass(frozen=True)
class CodeInfo:  # written by stage 4 from "a plain table CODES: dict[int, CodeInfo] with name and an optional kind"
    name: str  # the upstream constant's name
    kind: ErrorKind | None = None


CODES: dict[int, CodeInfo]
```

The framing rules are the twelve bullets under "Framing" in P4, and they are complete; build them as written. The points that are easy to get wrong:

- With `N` for `0|[1-9]\d*`: a start marker is `^(?P<before>.*)@!@!@STARTMSG (?P<code>N):(?P<sev>N) @!@!@$`, recognised only at the end of a line; an end marker is `^@!@!@ENDMSG (?P<code>N) @!@!@(?P<after>.*)$`, only at the start of a line and only when its code matches an open message. Both are module constants, compiled once.
- A trailing `\n` or `\r\n` is removed before any pattern is tried.
- A line that is neither marker goes to the `body` of the innermost open message, or is returned at once as `Unframed` when none is open. A message that closes while another is open is appended to that one's `body` in its place among the lines. Only the top-level message is returned, when it closes.
- An end marker for an outer open message closes the inner ones first with `truncated=True`. An end marker that matches nothing open is plain text. `close()` closes every open message with `truncated=True`, innermost first, and returns the top-level one.
- A start marker that does not match (a negative code, no severity, letters, a leading zero) is plain text, as is marker text that does not sit at its end of the line.
- The framer sets `TlcMessage.name` from `CODES` (`None` for a code that is not in the table) and keeps `severity` as the number in the marker.

`render_framed` is P4's definition:

```
render_framed(Unframed(line)) = [line]
render_framed(m)              = [m.before + "@!@!@STARTMSG <code>:<severity> @!@!@"]
                                + for each item of m.body: [item] for a line, render_framed(item) for a message
                                + ["@!@!@ENDMSG <code> @!@!@" + m.after]        left out when m.truncated
```

**The code table.** `CODES` replaces `TLC_CODES`, `TlcCode`, `TlcCodeType` and the 240 module constants of `src/tlaup/tlc/codes.py`:

- Every code of the old table is carried over with its name (the old constants are the upstream names). The old `Info`, `Warning`, `Error` and `Ignore` types are not carried over: the class of a message comes from the severity in its marker (package 13), and `Ignore` "was how output got lost" (P4).
- The six missing codes are added with their upstream names: 1003 `SYSTEM_OUT_OF_MEMORY_LIVENESS`, 2148 `TLC_STATE_NOT_COMPLETELY_SPECIFIED_LIVE`, 2254 `SYSTEM_FINGERPRINT_OVERFLOW_ERROR`, 2256 `TLC_NO_STATES_SATISFYING_INIT_AND_CONSTRAINT`, 2404 `TLC_POSTCONDITION_FALSE`, 2405 `TLC_POSTCONDITION_EVALUATION_ERROR`.
- Code 2285 is added as `TLC_CHECKPOINT_RECOVER_SETTINGS_MISMATCH`: the rolling build prints it (severity 3, `-recover` with other settings than the checkpoint's) and the old table does not have it. The name was read from `tlc2.output.EC` in the rolling jar of research 22 with `javap -constants` ([10 P5](../design/10-parser.md#p5-error-traces)).
- `kind`, from P5's "Kind" bullet: 2110 `invariant`; 2114 `deadlock`; 2116 and 2112 `property`; 2132 `assertion`; 2104 `assumption`; 2179 `evaluation`; 2404 and 2405 `postcondition`; 5001, 5003, 5006 and 2229 `config`; 1000, 1005, 2147, 2154 and 2173 `exception`; 3002 `parse`; 1102 `usage`. Every other code has `kind = None`, which package 13 reads as `other` when the message is an error. Stage 4 puts this data here because the table is this package's file; 13 owns what is done with it.

Consumes: `TlcMessage`, `ErrorKind` from [09](09-parse-package-and-model.md).

## Tests that must pass

All plain pytest in `tests/parse/`; the golden files are read from disk, in binary, split into lines that keep their line ending, each line decoded as UTF-8 with `errors="replace"` (how the launcher decodes, [01 T3](../design/01-testing.md#t3-golden-files)).

`test_framing.py`:

- **The exact rebuild over every file** (P4 Tests, "Properties"; T3's first property): parametrised over every `.out` file under `tests/parse/golden/` (the `tlc`, `sany` and `pcal` folders of every build, the `plain/` captures, and `synthetic/`): feeding the lines to a `Framer` and rendering everything `feed` and `close` returned, in order, gives the file's lines without their line endings. The parameter list is built by globbing, so a capture added later is covered.
- **Line endings**: for the same files, feeding each line with `\n`, without it, and with `\r\n` gives equal items.
- **Golden shapes** (P4 Tests, the ones that need no interpretation), on both builds unless said:
  - `java-override-exception`: the message 1000 has a `body` of four lines and then a 2154 with `before == ": "`.
  - `override-method_not_public`: the outer 2154 is closed (not truncated); its body is one line, the nested 2154 with `after == ","`, and two more lines, in that order; the 2186 after it is a message of its own.
  - `override-ctor_private`: a 1000 nested in a 1000, one top-level message.
  - `print-marker`: the quoted marker lines are `Unframed`, and no message with code 9999 exists.
  - `text_lines()` against the `plain/` capture, for the five cases P4 names (`java-override-exception` and `java-override-stack-trace` on both builds, `postcondition-false` on v1.7.4): the lines of the error message equal the same error's lines in the plain capture. In the plain captures TLC puts `Error: ` in front of the first line (seen in `java-override-exception`); the test strips that prefix and nothing else.
- **Synthetic cases**, one test each, on the files of `synthetic/` that package 07 wrote (never typed into the test): `STARTMSG -1` is plain text and nothing raises; a marker with a leading zero is plain text; a start with no end gives a `truncated` message from `close()`; an end with no start is plain text; crossed ends close the inner one `truncated`; an end marker with text after it at the top level gives a message whose `after` holds the text; a severity-1 message nested in a severity-0 one frames as one top-level message with the nested one in its body (that it counts as one error is 13's test); the `\r\n` file frames like its `\n` twin; quoted `Print` marker text with text after it is plain text; `invalid-utf8.out` frames and rebuilds (after decoding with replacement, compared with the decoded lines).

`test_framing_props.py` ([01 T7](../design/01-testing.md#t7-property-tests-for-values), last paragraph): a Hypothesis test over sequences of lines drawn from start markers and end markers with small codes (so that they often match), markers with text before or after them, malformed markers (a negative code, a leading zero, no severity) and plain text asserts the exact rebuild, and that `feed` and `close` never raise. T12 rule 3 exempts Hypothesis strategies from the ban on typed marker text, so the strategy may write the marker literally; the file is excluded from the mechanical check by its exact path (Files), which is the one way rule 3's exceptions are made. Do not split the marker into pieces to get past the check.

`test_codes.py`:

- Every code of a message framed from any golden file under `tests/parse/golden/tlc/` (top level or nested) has an entry in `CODES` (P4 Tests, last sentence). Collect the codes through the `Framer`, not with a text search: `print-marker` contains quoted marker text with code 9999 that is not a message.
- The six added codes and 2285 are present with their names; 2404 and 2405 have kind `postcondition`; the kinds listed under Interfaces are as listed; no name occurs twice.
- Row R29, the framing half: `CodeInfo` holds a name and a kind and nothing that says error, warning or information, so no table entry can decide a message's class; and in `test_framing.py`, the framed messages of `synthetic/unknown-code.out` keep the severities 1, 3 and 0 of their markers. That the severity then decides the class, whatever the code, is 13's half of the row.

Old tests: none are left (03b).

`pending` markers: the facts are assertions on a `RunResult` (08), so none of them can pass on the `Framer` alone, and this package removes none.

## Changelog

None in this package. P4's entry ("Fixed: Errors with a TLC message code tlaup did not know (for example a false POSTCONDITION, code 2404) were not shown at all. Every message TLC marks as an error is now shown, and output tlaup does not recognise is printed as TLC wrote it.") describes what `tlaup tlc` does after the switch; package 39 writes it.

## Context for the worker

- **State of `main`.** `tlaup_parse` has `model.py`, `values.py` (the type only) and `exit_status.py`. The old `src/tlaup/tlc/parser.py` and `codes.py` are in use by the old runner and stay untouched.
- **What is carried over from `tlc/parser.py`.** The idea of a stack, and the start pattern's anchor at the end of the line (old line 90). Not carried over: the end pattern with text allowed on both sides (old line 78), which is how quoted `Print` text could close a message; `MessageStack.start` raising `ValueError` for code -1; a marker with no severity being accepted (`(:\d+)?`); patterns compiled per line; lines kept with their newline; and dropping a line that belongs to no known message.
- **Why the rules are what they are.** D9: nothing is lost, stated so it can be tested as an exact rebuild. Both anchors come from captures: TLC really prints `: @!@!@STARTMSG 2154:0 @!@!@` (text before a start marker) and `@!@!@ENDMSG 2154 @!@!@,` (text after an end marker), and never the other two positions. A message can be nested in one of the same code (2154 in 2154, 1000 in 1000), so nesting is a stack, not a lookup by code.
- **What was checked before.** The design agent ran these rules as a script on 2026-11-15: 117 capture files with markers (1,618 messages) rebuilt exactly, none with a truncated message, nesting never deeper than one level, and 200,000 random sequences rebuilt. The captures of research 22 (about as many files again, among them a run stopped by a signal) were not run through that script. So do not assert "no real capture has a truncated message" or "nesting depth is at most one" over all files; the rebuild is the property.
- **The leading-zero rule** exists so that the code, kept as an integer, can be written back as read. Do not relax it to be friendly.
- **Codes in the captures today** (counted over the research folders that become golden files): all are in the old table except 2285 and 2404. 9999 appears only as quoted text.
- **`codes.py` is not generated** from upstream's `EC.java` (P4, Rejected); the test over the golden codes is the guard.
- **Windows (D15):** the `\r\n` rule is for output read there; it was not tried on Windows.
- **Hypothesis** (T7): the profile is fixed in CI; the first run prints Hypothesis's statistics and the pull request quotes them, so a strategy that rarely nests or rarely matches an end to a start is seen.
- **Performance** is not a goal here beyond compiled patterns; the framer handles one line per call and keeps only open messages.

## Done when

- The three test files pass, with the rebuild parametrised over every golden and synthetic file; `uv run poe lint` and `uv run poe test` pass; CI is green.
- The tests were committed before the code, and the pull request shows the red run and the Hypothesis statistics (T12 rule 6, T7).
- The import-isolation test of 09 still passes with the two new modules.
- No changelog entry; no document to update. The pull request names the rows it covers (R29, its framing half).

## Out of scope

- Deciding what a message means (severity first, typed codes, `Information`, `UnknownMessage`), the event-level count `OutputLine == unframed_lines - sany_lines_used`, and "one error, not two" for the nested cases: [13](13-tlc-parser.md).
- `test_golden.py` and the expected JSON: 13 starts the file with the two event-level properties, 15 adds the expected results.
- The reporter that prints unknown messages and `text_lines()`: 38.
- Removing `src/tlaup/tlc/codes.py` and `parser.py`, and their test: 39.

## Risks

- From P4: severities 2 and 5 were never seen; nothing in framing depends on the severity's value, so the risk is 13's.
- From T7: the strategy and the framer are written by the same hands; the golden files are the check from outside, which is why the rebuild runs over all of them here.
- From the cut: the `kind` data sits in this package and its use in 13. If 13 finds a kind wrong, it corrects the table in its own pull request.
- From the cut: a capture that package 07 normalised (placeholders for paths) is still rebuilt exactly, since the rebuild compares the file with itself; but a file whose line endings a hook changed would no longer be the `\r\n` case. The test for that case asserts that the file really contains `\r\n`.
