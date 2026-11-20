# 32. SANY and the PlusCal translator: working folder against spec path

## Question

Do standalone SANY (`tla2sany.SANY`) and the PlusCal translator (`pcal.trans`), started in some other folder with the
spec as an absolute path, behave as they do when started in the spec's folder with the bare file name, on v1.7.4 and on
1.8.0 (rolling)? For SANY: where it looks for the modules the spec EXTENDS (beside the spec, in the working folder, on
`-DTLA-Library`), what wins when the working folder and the spec's folder both hold a module of that name, and whether its
messages name files differently. For the translator: where it writes `X.old`, `X.cfg` and the rewritten `.tla`, whether the
file names in its messages change, and the same with a relative path such as `../dir/Spec.tla`. The answer decides whether
`sany` and `pcal` can follow decision D34 like `tlc` ([21 S1](../design/21-other-tools.md#s1-sany),
[21 S2](../design/21-other-tools.md#s2-pcal)).

## Source

- Roadmap investigation list, question 32; [research 12](12-sany-pcal-repl.md) (ran both tools in the spec's folder only),
  [research 16](16-config-path.md) (how TLC resolves modules), decision D34.
- Jars, as given for the top-up round:
  - v1.7.4: sha256 `936a2620...`, commit `5a47802b5c391f59ecdd44117981f4ff8c0656ba`, SANY 2.1 (24 Feb 2014), pcal.trans 1.11.
  - 1.8.0 (rolling): v1.8.0 and `rolling` are byte-identical, sha256 `7e53aa63...`, commit
    `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`, SANY 2.2 (08 July 2020), pcal.trans 1.12.
- Java: OpenJDK 25.0.5 for the kept captures; the whole matrix was also run with OpenJDK 21 (rolling) and Temurin 11
  (v1.7.4) and gave the same results. Linux x86-64, 12 cores. Other agents were running at the same time (see the noise
  note below); no timings are reported.
- Upstream source, pinned: `pcal/trans.java` builds `X.old`, `X.tla` and `X.cfg` from the input argument
  ([1.8.0 lines 393-404, 441, 453](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/pcal/trans.java#L393-L404);
  [v1.7.4 lines 388-399](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/pcal/trans.java#L388-L399))
  and writes `AST.tla` under a bare name ([1.8.0 line 1077](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/pcal/trans.java#L1077)).
  `tla2sany/drivers/SANY.java` at 1.8.0 never sets `ToolIO.userDir` (no `userDir` in the file), which is what makes TLC
  search beside an absolute spec path (research 16).

## Short answer

**SANY does not behave the same. It cannot follow D34. The translator is the same apart from one file, and could.**

**SANY (both versions, same behaviour).** Given the spec as an absolute path or as `../spec/Main.tla` from another folder,
SANY does **not** look beside the spec for the modules it EXTENDS. Its search order is the working folder, then
`-DTLA-Library` entries, then the standard modules in the jar, then the classpath. The spec's own folder is not in the
list unless the spec is in the working folder or something puts it there.
- Module beside the spec only (the normal case): found when started in the spec's folder; **"Cannot find source file for
  module Helper", exit 255**, when started elsewhere.
- Module in the working folder only: not found from the spec's folder, found from the other folder. So starting folder
  decides which modules a spec sees: loose modules in the folder tlaup was started from would be picked up, those next to
  the spec would be lost.
- Module in both the working folder and beside the spec: the working folder's copy wins (started elsewhere); only the
  spec's copy exists for SANY when it was started in the spec's folder.
- Module in `-DTLA-Library` (a folder given absolutely or relative to the working folder): found in every mode, same
  output. It loses to a working-folder copy (which wins over the library), and in the spec's folder mode a copy beside the
  spec (the working folder there) wins over the library.
- Putting the spec's folder on `-DTLA-Library` (or on the classpath) restores the lookup, but at the library's or
  classpath's rank: a same-named module in the working folder still wins, and on v1.7.4 a classpath folder is copied to
  `/tmp/<Name>.tla` and SANY announces that copy.
- Messages: the "Fatal errors while parsing TLA+ spec in file X" and "Could not parse module M from file X" lines, and the
  `Cannot find the specified file X` line, print the file name **as given on the command line** (`Main.tla`, the absolute
  path, or `../spec/Main.tla`). The `Parsing file <path>` lines, the semantic-error lines (`line L, col C to ... of module
  M`) and the parse-error line and column are the same in all modes. `Parsing file` is already absolute in every mode,
  except that with a relative path 1.8.0 appends a second path to the first line: `Parsing file <w>/spec/Main.tla
  (file:<w>/other/../spec/Main.tla)`.

**PlusCal translator (both versions, same behaviour).**
- `X.old`, `X.cfg` and the rewritten `X.tla` are written **beside the input file**, wherever the translator was started
  (the code builds the names from the argument). Absolute and `../spec/Pc.tla` give the same files, with the same
  contents, as the bare name in the spec's folder; nothing is written in the working folder.
- A `.cfg` or `.old` that already exists in the working folder is never read or touched; only the ones beside the spec
  count. The existing-cfg rules of research 12 hold unchanged.
- Messages: the file names in `New file X written.`, `File X.cfg already contains SPECIFICATION statement,` and the
  not-found line (`Input file X not found.` in 1.8.0, `Command-line error: Input file X does not exist...` in 1.7.4) are
  the path as given. Everything else (version banner, labels added, errors with line and column, exit codes) is the same.
- One exception: `-writeAST` writes `AST.tla` into the **working folder** (a bare name in the code), so it lands beside
  the spec only when the translator was started there.

## Confidence

Verified, for Linux, on both versions: every scenario in the tables was run in the three modes and the outputs compared by
diff; the two Java versions agree. Not verified: macOS and Windows (path separators, the `Parsing file` format with
backslashes; the Windows branch of `TLAFile` noted in research 16); symlinked spec folders; SANY with several input files;
`pcal.trans -spec`, `-myspec`, `-spec2`; SANY resolution when `ToolIO.userDir` is set by an embedding program (not relevant
to a command line). I did not trace the SANY lookup in source beyond the absence of a `userDir` assignment; the behaviour is
established by the runs.

## Evidence

All commands: `java [-DTLA-Library=...] -cp tla2tools.jar <class> [args] <spec>`, run by `run.py` (in the fixtures folder)
in a fresh tree per run, `<w>/spec` (the spec and its modules), `<w>/other` (the other working folder), `<w>/lib` (a
library folder). Modes:

- **A**: working folder `<w>/spec`, argument `Main.tla` (how research 12 ran).
- **B**: working folder `<w>/other`, argument `<w>/spec/Main.tla` (D34's shape).
- **C**: working folder `<w>/other`, argument `../spec/Main.tla`.

Captures: `tests/fixtures/research/32-sany-pcal-working-folder/{v1.7.4,v1.8.0-rolling}/` (`sany/`, `pcal/`, `diffs.txt`,
`sany-summary.txt`; `README.txt` explains the layout). Paths in captures are written `<w>` and `<jar>`.

### SANY: which `Helper.tla` is parsed (identical on v1.7.4 and 1.8.0 unless noted)

`Main` EXTENDS `Naturals, Helper`. Exit codes in brackets.

| Scenario | A: in spec folder, bare name | B: elsewhere, absolute | C: elsewhere, `../spec/Main.tla` |
| --- | --- | --- | --- |
| Helper beside the spec only | spec/Helper [0] | **not found [255]** | **not found [255]** |
| Helper in the working folder only (`other/`) | not found [255] | other/Helper [0] | other/Helper [0] |
| Helper beside the spec and in `other/` | spec/Helper [0] | other/Helper [0] | other/Helper [0] |
| Helper only in `lib/`, `-DTLA-Library=<lib>` | lib [0] | lib [0] | lib [0] |
| Helper in `lib/` and beside the spec | spec | lib | lib |
| Helper in `lib/` and in `other/` | lib | other | other |
| `-DTLA-Library=../lib` (relative to the working folder) | lib | lib | lib |
| Spec's folder on `-DTLA-Library` | spec [0] | spec [0] | spec [0] |
| Spec's folder on `-DTLA-Library`, copy in `other/` too | spec | other | other |
| Spec's folder on the classpath | spec [0] | spec [0] (v1.7.4: `/tmp/Helper.tla`, a copy) | same as B |
| Spec's folder on the classpath, copy in `other/` | spec | other | other |
| Helper nowhere | not found [255] | not found [255] | not found [255] |

(`sany-summary.txt` in each version folder has the full list. The lines "lib" in row 5 mean that in mode A the working
folder is the spec's folder, whose copy beats the library; in B and C the library's copy is the first one on the path.)

Failure text for the first row, mode B, 1.8.0:

```
Parsing file <w>/spec/Main.tla
Parsing file /tmp/tlc-<n>/Naturals.tla (jar:file:<jar>!/tla2sany/StandardModules/Naturals.tla)

Fatal errors while parsing TLA+ spec in file <w>/spec/Main.tla

In module Main

Cannot find source file for module Helper imported in module Main.
```

v1.7.4 prints the same in its older shape (`tla2sany.semantic.AbortException`, `Unknown location`) plus the stderr line
`File does not exist: <w>/other/Helper.tla while looking in these directories: jar:file:<jar>!/tla2sany/StandardModules/`.
The directory it names there is the working folder, which shows what SANY searched.

### SANY: file names in messages

From `diffs.txt` (A against B and C), 1.8.0; v1.7.4 shows the same pattern:

| Message | A | B | C |
| --- | --- | --- | --- |
| `Fatal errors while parsing TLA+ spec in file ...` | `Main.tla` | `<w>/spec/Main.tla` | `../spec/Main.tla` |
| `Could not parse module Main from file ...` (parse error in the spec) | `Main.tla` | `<w>/spec/Main.tla` | `../spec/Main.tla` |
| `Cannot find the specified file ...` | `Nope.tla` | `<w>/spec/Nope.tla` | `../spec/Nope.tla` |
| `Parsing file ...` for the spec | `<w>/spec/Main.tla` | same | 1.8.0 adds ` (file:<w>/other/../spec/Main.tla)` |
| `Parsing file ...` for an extended module | absolute | absolute | absolute |
| Parse-error line and column, `line L, col C ... of module M` | same | same | same |

Messages about a parse error in `Helper` name `Helper.tla` (bare) in A; in B and C the spec's folder is not searched, so
there is no such message (the module is not found, see above). So the file name on those two lines is whatever tlaup
passes; with the absolute path of D34 it is the absolute path, and tlaup's own path rule (relative to where tlaup was
started when beneath it, S1 step 4) can be applied to it as it is today to the `Parsing file` lines.

### PlusCal translator

`Pc.tla` has a small algorithm. Files after each run, in `<w>`; the same set and the same bytes in A, B and C (checked by
the hash of every created or changed file in the captures), on both versions:

| Scenario | Files created or changed (all modes) | Differences between modes |
| --- | --- | --- |
| plain | `spec/Pc.tla` rewritten, `spec/Pc.old` (the original), `spec/Pc.cfg` | only the file name in `New file X written.` |
| existing `spec/Pc.cfg` | cfg kept after its marker line, as research 12 | file name in the two cfg messages |
| `Pc.cfg` in the working folder only | new `spec/Pc.cfg`; the working folder's one untouched | file names in messages |
| `-nocfg` | no cfg | file name |
| existing `spec/Pc.old` | overwritten | file names |
| name without `.tla` (`Pc`, `<w>/spec/Pc`, `../spec/Pc`) | same files | file names (always shown with `.tla`) |
| translator error (`goto` to a missing label) | nothing written | **none**: the message has no file name (`goto to non-existent label `Zzz' at line 6, column 6.`), identical in all modes |
| labels added | same | file names |
| translated twice | same | file names |
| a different `Pc.tla` in the working folder | the one named by the argument is read | file names |
| missing input | nothing | the not-found line carries the path as given |
| `-writeAST` | `AST.tla` created in the **working folder** (`spec/` in A, `other/` in B and C), exit 255 as before | where `AST.tla` is, and the file name |

The not-found line is `-- Input file Pc.tla not found.` in 1.8.0 and `-- Command-line error: Input file Pc.tla does not
exist...` in 1.7.4; both print the path as given.

### Noise

v1.7.4 extracts the standard modules it needs to `/tmp/Naturals.tla` and, when runs of it overlap (here with other agents),
prints `Encountered an exception while attempt to validate /tmp/Naturals.tla - /tmp/Naturals.tla (No such file or
directory)` on a few runs (the kept capture has one, in `sany/s11-parse-error-in-helper.C.txt`). It is not related to the
working folder. It is a point for tlaup's v1.7.4 SANY golden files: capture them with no other 1.7.4 run in progress.

## Implications for the roadmap

- **`sany` cannot follow D34.** Started elsewhere with an absolute spec path, SANY loses every module that lies beside the
  spec and finds loose modules in the folder it was started from instead. The S1 step 2 stays as designed: run in the
  spec's folder with the file name. Question 32's premise ("if they behave the same") is false for SANY, so it stays
  "two rules, not one" for `sany` against `tlc`.
- **`pcal` could follow D34**: the three files land beside the spec in every mode, and only the file names in messages
  differ. The one difference is `-writeAST` (`AST.tla` goes to the working folder). The cost of following is a parser rule
  for names in messages (take the path as passed) and either accepting or refusing `-writeAST` in the starting folder.
  Whether the translator should follow D34 or share the spec's-folder rule with `sany` is a design call; with `sany`
  fixed to the spec's folder, running `pcal` there too gives the two standalone tools one rule and keeps `AST.tla` beside
  the spec, and it needs no change to S2.
- A stray `Helper.tla` or `Pc.cfg` in the folder tlaup was started from has no effect on the translator, and does on SANY
  only if SANY is started there.
- Design 21 S1 asserts the folder in its tests ("the fake `java` logs the folder it was started in, which is the spec's
  folder"); that stays true. S2 can keep the same assertion.
- Side finding for question 27 (SANY and `-DTLA-Library` / classpath): standalone SANY honours `-DTLA-Library` on both
  versions, whatever the working folder, absolute or relative to it, and it finds modules in a classpath folder on both
  (1.7.4 through a `/tmp` copy). So `tlaup sany` can pass the same library setting as TLC. Order of precedence is
  working folder, then library, then jar standard modules, then classpath, unlike TLC's absolute-path case where the spec's
  folder comes first (research 16).

## Open follow-ups

- macOS and Windows were not run (no script prepared; the result is a Linux and Java fact about the lookup order, but a
  Windows run would show the format of `Parsing file` and the messages with backslashes). If wanted, `run.py` in the
  fixtures folder is portable Python and could be added to the CI matrix as is.
- Whether to give `pcal` the starting folder anyway (design call above).
- If a later design adds the spec's folder to `-DTLA-Library` for SANY to make "start anywhere" work: it ranks below the
  working folder, so a loose module in the folder tlaup was started from still shadows the spec's own; that is a weaker
  rule than TLC's and was not chosen here.

## Date checked

2026-11-18, Linux x86-64, OpenJDK 25.0.5 (also 21 and Temurin 11), jars as listed under Source.
