# 11. TLA+ values

Size: M. Suggested model: most capable. Status: ready.

## Goal

`tlaup_parse.parse_value` turns the text TLC prints for a value into a `Value` tree: functions, records, sets, sequences, intervals and wrapped values parse as what they are, and anything else comes back whole as one `raw` value. It never raises and never returns a partly parsed tree.

## Covers

- Roadmap items:
  - "Fix function-valued variables (`(a :> 1 @@ b :> 2)` parses to `a`) and values that TLC wraps across lines, which always fall back to a raw string because the tokenizer does not skip newlines." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)): the parser side in full. A user sees the fix when package 13 uses it for trace variables and packages 38 and 39 show them.
  - "Move the parser stack ... into its own import package" ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: `values.py`. See [09](09-parse-package-and-model.md).
  - [01 T7](../design/01-testing.md#t7-property-tests-for-values) has no roadmap item of its own ("Roadmap candidate, accepted").
- Design sections:
  - [10 P7](../design/10-parser.md#p7-values): all of it except the `Value` dataclass, which [09](09-parse-package-and-model.md) defines.
  - [01 T7](../design/01-testing.md#t7-property-tests-for-values): the four value properties. Its last paragraph, the framing property, is [10](10-framing-and-codes.md).

## Depends on

- [09](09-parse-package-and-model.md): `src/tlaup_parse/values.py` with the `Value` dataclass (`text` declared with `field(compare=False)`), and `__init__.py`.
- [07](07-golden-files.md): `tests/parse/golden/tlc/<build>/violation.out`, for the wrapped sequence of records.
- [03](03-test-foundation.md): `hypothesis` as a development dependency.

Changed from the draft: 03 is named for Hypothesis; no other change. This package needs nothing from [10](10-framing-and-codes.md) and runs beside it and beside [12](12-sany-parser.md).

## Files

Creates:

- `tests/parse/test_values.py`, `tests/parse/test_values_props.py` (both named in the layout of [01 T3](../design/01-testing.md#t3-golden-files)).

Changes:

- `src/tlaup_parse/values.py`: add `parse_value` and its private helpers beside the `Value` type.
- `src/tlaup_parse/__init__.py`: export `parse_value` (and `Value`, if 09 did not).
- `tests/conftest.py`: the Hypothesis profiles are registered in `tests/stateful/conftest.py` today. If neither package 03 nor package 10 has moved the registration to `tests/conftest.py`, move it there (the same note is in 10; whichever merges second finds it done).

Deletes: nothing. `src/tlaup/tlc/values.py` and `tests/unit/tlc/test_values.py` stay until package 39 (see "Old tests" below).

Shared with 10 and 12, which run beside this package: `src/tlaup_parse/__init__.py` (one import line and one `__all__` entry) and, with 10, the profile move.

## Interfaces

Provides ([10 P7](../design/10-parser.md#p7-values)):

```python
def parse_value(text: str) -> Value
```

Grammar, copied from P7 (white space, newlines included, is allowed between any two tokens):

```
value    = int | bool | string | interval | set | seq | record | function | model
int      = ["-"] digits
bool     = "TRUE" | "FALSE"
string   = '"' ( any character except '"' and '\' | '\' any character )* '"'
interval = int ".." int
set      = "{" [ value { "," value } ] "}"
seq      = "<<" [ value { "," value } ] ">>"
record   = "[" name "|->" value { "," name "|->" value } "]"
function = "(" value ":>" value { "@@" value ":>" value } ")"
model    = name                      ; an identifier that is not TRUE or FALSE
name     = letter or "_", then letters, digits, "_"
```

What each kind fills, from the comments on `Value` in P7:

| `kind` | Filled | Notes |
| --- | --- | --- |
| `int` | `scalar: int` | |
| `bool` | `scalar: bool` | |
| `string` | `scalar: str`, unescaped | |
| `model` | `scalar: str`, the name | |
| `interval` | `bounds: (a, b)` | |
| `set`, `seq` | `items` | An empty set and an empty sequence parse; TLC prints an empty function as `<< >>`, which is a sequence. |
| `record` | `fields: ((name, value), ...)` | The grammar has no empty record. |
| `function` | `pairs: ((key, value), ...)` | Keys are values of any kind, tuples included. |
| `raw` | `scalar: str`, the whole input again | So that two raw values compare by their text. |

Every node has `text`, the source text of that node as printed. For the root it is the input, unchanged; T7's "total" property asserts exactly that. The design does not say whether a node's `text` includes white space around it; take the span from the node's first token to its last, and for the root the whole input.

Rules:

- **Total and lossless.** Any failure at any depth makes the whole result `Value(kind="raw", text=<the input>, scalar=<the input>)`. No exception leaves the function, for any `str`. Text left over after a complete value is a failure too (the grammar is for the whole string).
- A guard turns `RecursionError` into `raw`.
- Forms TLC prints without enumerating (`[S -> T]`, `SUBSET S`, `{x \in S : P}`, lazily printed sets) are not in the grammar and come out `raw`. That is the designed behaviour.

Consumes: `Value` from [09](09-parse-package-and-model.md).

Used by: package 13 calls `parse_value(Variable.raw)` for each trace variable; package 38 compares values of neighbouring states for the changed-variable mark.

## Tests that must pass

Plain pytest and Hypothesis in `tests/parse/`.

`test_values.py`:

- **Unit cases for each form** (P7 Tests): an integer and a negative one, both booleans, a string, a string with escaped quotes, a string that contains `:>`, a model value, an interval, a set, a sequence, an empty set, an empty sequence, a record, a set of records, a function, a function with tuple keys, nesting several deep. Each asserts the tree (kinds and contents), not the text. A single value given to `parse_value` may be typed in the test (T12 rule 3 names this exception).
- **The roadmap's two defects**, as named cases: `(a :> 1 @@ b :> 2)` is a `function` with two pairs; a value wrapped over several lines parses to the same tree as the same value on one line.
- **The golden value**: the `log` variable of the last state of `violation`, a sequence of three records that TLC wraps over several lines, read from `tests/parse/golden/tlc/<build>/violation.out` on both builds and not typed (it is multi-line tool output, T12 rule 3). This package has no trace parser, so the test cuts the text out itself: in the last state message, from the line starting `/\ log = ` to the line before the next line starting `/\ ` or the blank line that ends the state, with the `/\ log = ` prefix removed. Assert kind `seq`, three items, each a `record`, and the fields the capture shows.
- **Raw**: `[S -> T]`, `SUBSET S`, an unbalanced bracket, the empty string and text after a complete value each give one `raw` value whose `text` and `scalar` are the input; two raw values with different text are unequal; a failure deep inside a nested value gives a raw root, not a tree with a raw leaf.
- **Deep nesting**: a value nested deeper than the interpreter's recursion limit returns `raw` and does not raise.
- **The seven cases of `tests/unit/tlc/test_values.py`** (an integer, a string, a boolean, a set, a sequence, a record, a nested value) are among the unit cases above, rewritten for the new tree. T11 keeps them "until P7"; this is where they are carried to.

`test_values_props.py` ([01 T7](../design/01-testing.md#t7-property-tests-for-values)): a strategy builds a value tree (integers, booleans, strings with escapes, model values, sets, sequences, records, functions with non-string keys, intervals, nested to depth 4) and a printer writes it in TLC's notation. Properties:

- `parse_value(print(v)) == v` for every generated value (tree equality; `text` is not compared).
- Inserting newlines and indentation at any token boundary of the printed text gives the same parse.
- For any text at all (`st.text()`), `parse_value` returns without raising and the result's `text` equals the input.
- A parse that fails anywhere yields a single value of kind `raw`: for any text, the result is either `raw` at the root or contains no `raw` node.

Old tests. `tests/unit/tlc/test_values.py` tests the old `tlaup.tlc.values.parse_variable_value`, and that module is still imported by the old parser until package 39. T11's table says the file is kept "until P7"; under the build-beside rule of the cut that reads as: its seven cases move into the new `test_values.py` here, rewritten for `parse_value`, and the old file stays unchanged and green until package 39 deletes it together with `src/tlaup/tlc/values.py`. Deleting it here would leave an old module in `src/` with its tests gone and the coverage figure of `tlaup` lower for no gain in truth (T11: "never earlier, so coverage does not fall in between").

`pending` markers: this package removes none. The value facts of `tests/parse/facts.py` (for example "state 2's `n` is the integer 1", "`log` in state 4 is a sequence of 3 records") are stated on trace states, which need package 13. If package 08 wrote facts that call `parse_value` directly, remove the marker from exactly those as this package's first commit.

## Changelog

None in this package. P7's entry ("Fixed: Function values such as `(a :> 1 @@ b :> 2)` were shown as their first key; values TLC wraps over several lines were shown as one raw string.") describes what `tlaup tlc` shows after the switch; package 39 writes it.

## Context for the worker

- **State of `main`.** `tlaup_parse.values` holds only the `Value` dataclass. The old `src/tlaup/tlc/values.py` (a tokenizer and `parse_variable_value`, returning `TlaValue(key, value, children)`) is in use by the old parser and stays untouched.
- **Nothing of the old code is carried over.** P7 asks for a new recursive-descent parser over one string. The old one treats `(` as "skip and parse what follows" (a function becomes its first key), matches no token for `\n` (every wrapped value falls back to raw text), and renders records and functions alike. Its fallback to raw text on failure is the one idea that stays, made whole-value and total. Patching the old tokenizer is listed under Rejected.
- **Why `text` is not compared and `raw` repeats it in `scalar`.** Tree equality must ignore spacing, so `text` is out of the comparison on every node; without the copy in `scalar` any two raw values would be equal and the changed-variable mark of [22 O3](../design/22-reporters.md#o3-terminal-reporter) would never show for them. A raw value's equality therefore does depend on spacing, which is right: nothing is known about its structure.
- **Decisions.** D9: nothing is lost, so `text` is kept on every node and failure returns the input. D7: standard library only, no I/O.
- **Tokens to watch.** `-` starts an integer only; `..` binds two integers into an interval before `.` could mean anything else; `|->`, `:>`, `@@`, `<<`, `>>` are multi-character tokens and `<<` must be tried before a lone `<` would fail; a `name` that is `TRUE` or `FALSE` is a boolean, any other name a model value; a string may contain every token (`":>"`).
- **Not captured** (P7, Risks): how TLC prints a string that contains a newline or a non-ASCII character. An odd form falls back to `raw`; do not guess an escape syntax beyond `\` followed by any character.
- **The printer in the property test is a second reading of TLC's notation by the same hands** (T7, Risks). The golden value is the check from outside; keep it reading the capture.
- **Hypothesis** runs with the fixed `ci` profile in CI (`derandomize=True`, 200 examples, no example database committed). The first run prints Hypothesis's statistics and the pull request quotes them, so a strategy that rarely produces a deep or odd value is seen.
- **Windows (D15):** nothing here depends on the platform; a value's lines are joined with `\n` by the caller.

## Done when

- `test_values.py` and `test_values_props.py` pass; `uv run poe lint` and `uv run poe test` pass; CI is green; the old `tests/unit/tlc/test_values.py` is unchanged and still passes.
- The tests were committed before `parse_value`, and the pull request shows the red run (T12 rule 6) and the Hypothesis statistics (T7).
- The import-isolation test of 09 still passes.
- No changelog entry; no document to update.

## Out of scope

- Splitting a state's body into variables and joining a variable's lines: [13](13-tlc-parser.md) (P5).
- The value diff and the changed-variable mark: 38.
- Deleting `src/tlaup/tlc/values.py` and `tests/unit/tlc/test_values.py`, and the changelog entry: 39.
- The framing property of T7: [10](10-framing-and-codes.md).

## Risks

- From P7: strings with a newline or a non-ASCII character were not captured; they fall back to `raw`.
- From T7: printer and parser can share a misreading of TLC's notation; a strategy that rarely goes deep passes without testing much.
- From the cut: the golden value is cut out of the capture by a few lines of test code instead of by the trace parser, which does not exist yet. If that slicing is wrong the test fails loudly (the value comes out `raw` or with the wrong count), so the risk is a confusing failure, not a false pass. Package 13's facts check the same value through the real path.
