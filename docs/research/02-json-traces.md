# 02: Can TLC write traces as JSON itself?

## Question

Can TLC write error traces as JSON (`-dumpTrace json`), so tlaup can skip value parsing for traces? For both supported
builds (v1.7.4 and the rolling 1.8.0 build): does the flag exist, what does the file look like for an invariant
violation, a liveness violation (back-to-state and stuttering) and a deadlock, how are values encoded, does it work with
`-tool` and several workers, when is the file written, can it go to stdout, and what other trace formats exist.

## Source

- Jars downloaded with `gh release download` from github.com/tlaplus/tlaplus:
  - `v1.7.4` (published 2024-08-05), sha256 `936a2620...e050e88`, banner `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`.
  - `rolling` (pre-release, published 2026-10-23 per `gh release list`; the jar I fetched shows banner
    `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`) and `v1.8.0` (pre-release, "The Clarke release", published
    2026-11-15 UTC). Both jars have the same sha256 `7e53aa63...fb84f`, and both tags point at commit
    `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`, which was also `master` HEAD (committed 2026-11-15T00:05:18Z) when checked.
    So "rolling" and "1.8.0" are the same build today. Java 25.0.5 (`/usr/bin/java`).
- Upstream source read at `bc1b506` through `gh api`: `tlatools/org.lamport.tlatools/src/tlc2/TLC.java`,
  `tlc2/module/Json.java`, `tlc2/module/TLCExt.java`, `tlc2/tool/impl/Tool.java`, and the modules shipped inside the
  jar (`tla2sany/StandardModules/_JsonTrace.tla`, `Json.tla`, `_TLCTrace.tla`, `_TLAPlusCounterExample.tla`).
- Upstream issues and commits (read-only): tlaplus/tlaplus#1467, #753, #853, #1073, #1216; commits `386eaa19f`, `1eb815620`.
- Specs and captured output are in `tests/fixtures/research/02-json-traces/` (each `X.tla`/`X.cfg` produced `X.json`).
  The CommunityModules were not downloaded (see Open follow-ups).

## Short answer

- v1.7.4: no. `-dumpTrace` does not exist. TLC prints `Error: unrecognized option: -dumpTrace` and exits.
  The 1.7.4 source at the tag has no `dumpTrace` in `TLC.java`. The jar has no `Json`, `TLCExt` or `_JsonTrace` modules.
- 1.8.0 / rolling: yes. `-dumpTrace json FILE` writes one JSON file for the (single) error trace. It works with `-tool`,
  several workers, `-simulate` and ALIAS. It does not work with `-continue` (no file at all).
- But the JSON is a lossy encoding of TLA+ values. Sets, sequences, tuples and functions with domain `1..n` are all JSON
  arrays; model values are JSON strings, the same as strings; records and functions on other domains are both JSON
  objects. It also does not say what kind of error it is. So JSON removes the need for a text value parser only if
  tlaup does not need to tell those types apart. For display tlaup would have to re-print values in TLA+ syntax, and
  it could not do that faithfully (`{1,2}` and `<<1,2>>` look the same).
- Because 1.7.4 has nothing, tlaup still needs the text parser for 1.7.4 output in any case.

## Confidence

Verified for the flag, file layout, value encodings, `-tool`/workers/simulate/stdout/relative-path behaviour and for
the `-continue` limitation, all by running the two jars. Partly verified for "when is the file written" (shown
from output order and the source path, but I did not kill a run to confirm that nothing is written) and for the
other formats (`json` and `tlc` ran; `tla`, `tlcplain`, `tlcTESpec`, `tlcaction`, `dot`, `cbor` need the
CommunityModules, which I did not download, so only their names and requirements come from the source and help text).
Not tested: upstream issue #753 (file may differ from the console trace with several workers); I ran one 4-worker
invariant case and the JSON equalled the 1-worker one.

## Evidence

### 1. Flag and history

- `java -cp v1.7.4/tla2tools.jar tlc2.TLC -dumpTrace json x.json ...` prints
  `Error: Error: unrecognized option: -dumpTrace`. 1.7.4's `-h` has `-dump [dot ...] file` (a state dump) and no `-dumpTrace`.
- Rolling `-h` documents `-dumpTrace format file` with formats `json`, `tlc`, `tla`, `tlcplain`, `tlcTESpec`,
  `tlcaction`, `dot`, `cbor`; "All but json and tlc require the CommunityModules"; "the parameter may appear multiple
  times". The same build also has `-loadTrace format file` (`tlc` and `json`) and `-postCondition`.
- Upstream history: commits `386eaa19f`/`1eb815620` (2022-02-17) "Ability to save TLC error trace in JSON format".
  `gh api repos/tlaplus/tlaplus/compare/v1.7.4...386eaa19f` says `diverged` (634 ahead, 59 behind), so the 1.7.4 tag was
  cut from a line that does not contain it. Later: action parameters added 2023-12-16 (#853), `tlcplain`
  2023-06-22, `tlcaction` 2024-12-12, `-loadTrace` 2026-01-29, `cbor` and the format table 2026-11-06.
- In `TLC.java` the flag is implemented as a post-condition: `-dumpTrace fmt file` adds
  `PostCondition(module, operator, constant, file)` for the format. For `json` it is `_JsonTrace!_JsonTrace` with
  `_JsonTraceFile = file`. `_JsonTrace.tla` evaluates `JsonSerialize(file, [counterexample |-> CounterExample, vars |-> vars])`
  and then `PrintT("CounterExample written: " \o file)`. It does nothing when `CounterExample.state = {}` (no trace).
- Help text says "The file is relative to the same directory as the main spec". That is wrong in practice, see 5.

### 2. File layout

Top level: `{"counterexample": {"action": [...], "state": [...]}, "vars": [...]}`, a single line of JSON, no trailing
newline, UTF-8, no HTML escaping (`<`, `>`, `&`, `'`, `é`, `日本` stay literal; `"` `\` and tab are JSON-escaped; fixture `Esc.json`).

- `state`: array of `[index, {var: value, ...}]`, index from 1. Keys inside the state object are in hash order, not
  declaration order. `vars` (declaration order of the variables that appear, or the ALIAS field names) is the stable
  order.
- `action`: array of edges `[[i, state_i], {name, location, context?, parameters?}, [j, state_j]]`. `location` has
  `beginLine`, `beginColumn`, `endLine`, `endColumn`, `module`. For parameterised actions (spec `Par`):
  `"name":"Inc", "context":{"n":1}, "parameters":["n"]`. A trace of one state has `"action":[]` (fixtures `Val.json`, `Esc.json`).
- Invariant violation (`Inv.json`, 4 states): 3 edges, indexes 1->2->3->4.
- Deadlock (`Dead.json`): states 1..3, 2 edges. Nothing in the file says the end is a deadlock. The error kind, the
  violated invariant or property name, and the TLC error code are not in the file at all.
- Liveness with back-to-state (`Live.json`; console says `Back to state 1`): 3 states, 3 edges; the last edge is
  `[[3,{x:2}], {...}, [1,{x:0}]]`, i.e. target index 1 < source index 3. The "back to" state is not in `state` twice
  and there is no `loop` field.
- Liveness with stuttering (`Stut.json`; console says `State 4: Stuttering`): 3 states, 3 edges; the last edge is
  `[[3,...], {...}, [3,...]]`, target index equals source index.
  This is the rule TLC's own `-loadTrace` uses (comment in `_JsonTrace.tla`: closing edge is the one where
  `target[1] <= source[1]`; `<` back-to-state, `=` stuttering). The action name on the closing edge is whatever
  action TLC found (here `Next`, even for stuttering), so stuttering is only recognisable from the indexes.
- ALIAS is applied (`ParAlias.json`: `vars` is `["x","sum","label"]`, the alias fields, not the spec variables).

### 3. Value encoding (spec `Val`, fixture `Val.json`, state 1 of 1)

From `tlc2/module/Json.java` (`getNode`) and observed output:

| TLA+ value | JSON written | Observed |
| --- | --- | --- |
| integer | number (32-bit only; TLC itself rejects larger ones) | `2147483647`, `-5` |
| `TRUE`/`FALSE` | boolean | |
| string | string | `"hi"`, `"1"` |
| model value / symmetry-set element | string of its name | `M = m1` gives `"m1"`; same as string `"m1"` |
| record `[a |-> 1]` | object | `{"a":1}` |
| function with domain `1..n` (also `<<>>`, tuples) | array | `[10,20]`, `["a","a"]`, `[]` |
| sequence / tuple | array | `[1,"a",true]` |
| set | array of elements, in TLC's normalised (sorted) order | `{1,2}` gives `[1,2]`; `{}` gives `[]` |
| set of sets, set of records | array of arrays / objects | `[[],[1],[2,3]]` |
| function on string domain | object, same as a record | `{"b":1,"a":1}` |
| function on any other finite domain | object; keys are the TLA+ text of the key | `(3 :> 3 @@ 4 :> 4)` gives `{"3":3,"4":4}`; domain `{{1},{2,3}}` gives `{"{1}":0,"{2, 3}":0}`; domain `<<1,2>>` gives `"<<1, 2>>"`; `BOOLEAN` gives `"TRUE"`/`"FALSE"` |
| empty function `[i \in {} |-> 0]` | `[]` | same as empty set, empty sequence |

Consequences, all seen in the captured output: set versus sequence versus tuple versus `1..n` function cannot be
told apart; model value versus string cannot be told apart; a record versus a string-domain function cannot be told
apart; a function with integer domain `{1,3}` becomes an object with string keys `"1"`, `"3"` (same as a function on
the strings `"1"`,`"3"`). Upstream says the same in #1467 ("`-dumpTrace json` loses type information", filed
2026-10-05, closed 2026-10-13); the maintainer's fix was the typed `cbor` format (needs CommunityModules), not a change
to JSON. Source comment in `_JsonTrace.tla` also says that JSON has no set type "so on the wire every set is an ordered sequence".

### 4. `-tool`, workers, simulation, `-continue`

- `-tool -workers 4`, invariant (`Inv`): file identical (as parsed JSON) to the single-worker, non-tool run.
- `-tool -workers 4`, liveness (`Live`): JSON written; `Live.tool.1.8.0.out` is the tool output.
  In tool mode the line `"CounterExample written: FILE"` is printed bare (with the quotes), outside any
  `@!@!@STARTMSG ... @!@!@ENDMSG` block, right after the trace messages (2217 states, then 2122 for "Back to state"
  or 2218 for "Stuttering" in the 1.8.0 output). A tool-mode parser must tolerate that unwrapped line.
  1.8.0 tool mode still uses the same message codes 2217/2122/2218/2121/2114 as 1.7.4 (`Live.tool.1.7.4.out`).
- `-simulate num=3` with an invariant violation: file written.
- `-continue`: no file is written even though 12 violations were reported (run with a bounded spec, `Par`). TLC
  prints `Model checking completed. No error has been found.` at the end and the post-condition has no
  `CounterExample` to serialise. Upstream #1467 says the same: with `-continue` only the deadlock trace was written
  for some runs and "writing every counterexample is a separate change"; in my run nothing was written. With several
  violations tlaup would have no JSON.
- No error: the file is not created and an existing one is left untouched (a file containing `STALE` was unchanged).
- Several `-dumpTrace` flags are allowed (documented). `-dumpTrace tlc FILE` (binary) printed
  `CounterExample written: ./<Spec>_TTrace_<n>.bin` and did not create the file I named, so the file argument was not
  honoured for `tlc` in this build when the trace-exploration spec is also generated (observed once; not investigated).

### 5. When written, where, stdout

- Written at the end of the run, when TLC reports the error, after the trace has been printed and before the closing
  statistics (`4 states generated...`). It is a post-condition, so a run that is killed or times out writes nothing
  (inferred from the source path `Tool.checkPostConditionWithCounterExample`, called from `ModelChecker`, `Worker`,
  `LiveCheck`, `LiveWorker`, `Simulator`; I did not test a kill).
- The file name is resolved against the process working directory, not against the spec directory: with the spec in
  `../w` and cwd `cwd/`, `-dumpTrace json rel.json` created `cwd/rel.json` and nothing in `w/`. A relative subfolder
  `sub/rel.json` worked when `sub/` was created by TLC (it existed afterwards). Absolute paths work. The help text
  ("relative to the same directory as the main spec") does not match this.
- stdout: `-dumpTrace json /dev/stdout` works on Linux: the JSON is printed as one line, with no newline, with the
  line `"CounterExample written: /dev/stdout"` glued to its end, and with the stderr/stdout order not guaranteed.
  In `-tool` mode the JSON line sits between the last 2217 message and the next message block. There is no `-` stdout
  convention: `-dumpTrace json -` created a file named `-`. `/dev/stdout` does not exist on Windows (not tested).
  A temp file next to the run is the robust option.
- Side effect in 1.8.0: by default TLC also writes `<Spec>_TTrace_<timestamp>.tla` and `.bin` next to the spec on every
  error (1.8.0 has `-noGenerateSpecTE`; 1.7.4 lists `-generateSpecTE`). `-noGenerateSpecTE` suppresses it (verified).

### 6. Other formats and mechanisms

- `tlc`: binary `_TLCTrace` (Java serialisation of the same `counterexample`/`vars` record), used by `-loadTrace tlc`.
- `tla`, `tlcplain`, `tlcTESpec`, `tlcaction`: need CommunityModules `IOUtils`; `dot` needs `GraphViz`; `cbor` needs `CBOR`.
  TLC checks for the module at startup and fails with `-dumpTrace tlcplain requires the CommunityModules (...)`
  (verified for `tlcplain` and `tla`; without them TLC exits with "Parsing or semantic analysis failed"). `tla` writes
  `CounterExample == ...` as TLA+ text (`_TLAPlusCounterExample.tla`), i.e. TLA+ syntax again, not simpler to parse.
- `-dump FILE` in 1.7.4 and 1.8.0 dumps all states (text/dot), not a trace (#1216 asks for a machine-readable one, open).
- ALIAS works with JSON (shown above). In 1.7.4 there is no way to get JSON for the trace only: the `Json` module and
  `CounterExample` (TLCExt) are not in the 1.7.4 jar; a CommunityModules `ndJsonSerialize` call from ALIAS would run
  on every state, not only the trace.
- `-loadTrace json FILE` (1.8.0) re-checks a spec against a dumped trace; not needed by tlaup.
- Open upstream issues of interest: #753 (the dumped trace can differ from the console trace, reported 2022, open),
  #1073 (robust export format, open), #1467 (typed format, closed by adding `cbor`).

## Implications for the roadmap

- The Milestone 1 idea "skip value parsing for traces" does not hold as stated:
  - 1.7.4 has no flag, so the text parser must stay for 1.7.4 and for any run without `-dumpTrace`.
  - On 1.8.0 the JSON is lossy for display (set versus sequence versus function, model value versus string), so tlaup
    could not print values the way TLC does without extra information. It also carries no error kind or property name.
  - It is missing for `-continue` and for killed runs.
- It can still be useful on 1.8.0 as a cross-check or as the source for structure that is hard in text: the state
  index, variable names (`vars`), action names/locations/parameters, and the lasso closing edge (target index `<=` source index)
  without relying on the message codes. It could make the 2122 and 2218 header fixes unnecessary on 1.8.0 only.
- Even there the stdout parse is still required for the error kind (invariant name, property, deadlock) and for
  `-continue`; JSON cannot replace it.
- If a design wants typed values from TLC, `-dumpTrace cbor` is upstream's answer, but it needs CommunityModules on the
  classpath and was only added 2026-11-06; not evaluated here.
- Practical rules if the JSON is used: give TLC an absolute path in a temp folder (relative paths are against cwd);
  expect the `"CounterExample written: ..."` line unwrapped in `-tool` output; pass `-noGenerateSpecTE` if the
  `_TTrace_` files in the spec folder are unwanted; expect no file if no error or `-continue`.

## Open follow-ups

- Download CommunityModules (needs permission) and run `-dumpTrace tla`, `tlcplain`, `cbor`, to see whether `cbor`
  keeps sets and model values distinct, and what `tlcplain` looks like.
- Check #753 properly: compare console trace and JSON on a larger spec with many workers and several shortest paths.
- Test a killed run, Windows (`/dev/stdout`, backslash paths), and a trace of 10000+ states for size and time.
- Check whether the `tlc` format ignores its file argument in this build.
- Check the rolling build again when 1.8.0 is released as a normal release; flags and the JSON layout are still changing
  (post-condition and `-loadTrace` changes landed in 2026).

## Date checked

2026-11-14 (rolling build with banner `2026.11.15.002146`, rev `bc1b506`; the maintainers' timestamps are UTC and run one day ahead of the local date).
