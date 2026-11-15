# 12. SANY, the PlusCal translator and the REPL

## Question

What are the main classes, flags, exit codes and real output of SANY (`tla2sany.SANY`), the PlusCal translator
(`pcal.trans`) and the REPL (`tlc2.REPL`), for v1.7.4 and the rolling 1.8.0 build of `tla2tools.jar`? Does SANY output
give file, line and column for each kind of error? Is there a machine-readable mode? What files does `pcal.trans`
write? Does the REPL need a terminal?

## Source

Everything below was run by hand on 2026-11-14 with `/usr/bin/java` (OpenJDK 25.0.5, Linux). Captured inputs, exact
commands (first line of each output file) and outputs, with `[exit=N]` as the last line, are in
`tests/fixtures/research/12-sany-pcal-repl/{v1.7.4,v1.8.0}/` (`inputs/`, `outputs/`, `pcal-results/`). `README.txt` there
explains the layout and `jar-sha256.txt` lists the jar hashes.

Jars were downloaded with `gh release download <tag> -R tlaplus/tlaplus -p tla2tools.jar`:

| Tag | sha256 (first 12) | Reports itself as |
| --- | --- | --- |
| v1.7.4 (Latest, 2024-08-05) | 936a26206192 | TLC 2.19 of 08 August 2024; SANY 2.1 (24 Feb 2014); pcal.trans 1.11 (31 Dec 2020) |
| v1.8.0 (Pre-release, GitHub lists it as published 2026-11-15T00:29Z) | 7e53aa636dac | TLC 2026.11.15.002146; SANY 2.2 (08 July 2020); pcal.trans 1.12 (01 July 2024) |
| rolling (Pre-release, published 2026-10-23, asset re-uploaded since) | 7e53aa636dac | identical bytes to v1.8.0 today |

So "rolling" and "v1.8.0" are the same jar on 2026-11-14; every 1.8.0 result applies to both. All commands were
`java -cp tla2tools.jar <class> ...` with the process working directory set to the spec's folder.

## Short answer

Main classes: `tla2sany.SANY`, `pcal.trans`, `tlc2.REPL`. The jar's manifest `Main-class` is `tlc2.TLC` in both versions,
so all three need `-cp` and the class name.

**SANY**
- Output is plain text on stdout (one stderr line only for a missing module in 1.7.4). There is no JSON or other
  machine-readable diagnostic mode.
- The only machine-readable output is `tla2sany.xml.XMLExporter`, which dumps the semantic tree as XML. It works in 1.8.0
  and fails in 1.7.4 on Java 25. It does not give errors as XML.
- Exit codes are not usable by default. Parse errors, a missing module and a missing file give 255. Semantic and level
  errors give **0**. 1.8.0 adds `-error-codes`, which turns semantic and level errors into exit 4. A parse error still
  exits 255, not the documented 2.
- Location info differs per error kind:

| Error kind | Where the line and column are | File name on the line? |
| --- | --- | --- |
| Parse | `at line 4, column 9` inside the text | No. The file is named on a separate "Fatal errors ... in file X.tla" line. |
| Semantic and level | `line 4, col 13 to line 4, col 13 of module SemErr` | No. It gives the module name, not the file. |
| Missing imported module | none: "Cannot find source file for module NoSuchModule imported in module MissingMod." | module names only (1.7.4: `File does not exist: <path>` and "Unknown location") |
| File name differs from module name | none ("Unknown location" in 1.7.4) | no |
| Missing input file | none | `Cannot find the specified file Nope.tla.` |

- Several errors: semantic and level errors are all reported in one run. A parse error stops at the first one, so SANY
  reports only one parse error.
- 1.8.0 adds a final `Linting of module X` line on success. It is only a progress line and says nothing about problems.
  With a clean module nothing else is printed.

**PlusCal translator (`pcal.trans`)**
- It rewrites the input `.tla` in place, between `\* BEGIN TRANSLATION` and `\* END TRANSLATION`, and writes `X.cfg`
  unless `-nocfg`.
- It moves the previous file to `X.old` first (confirmed: byte-identical to the original, and mtime kept, so it is a
  rename).
- It reports success with exit 0 and failure with exit 255, with the error on stdout.
- It does not parse TLA+ expressions, so `x := x + ;` translates fine; SANY finds that afterwards.
- `-writeAST` exits 255 even though it succeeded. That is a real quirk.
- Between 1.7.4 and 1.8.0 the only observable difference is the banner version and the order of variables in the
  translation (`VARIABLES x, pc` became `VARIABLES pc, x`), so the `chksum(tla)` in the BEGIN TRANSLATION line differs.
  The `chksum(pcal)` is the same.

**REPL (`tlc2.REPL`)**
- It exists only in 1.8.0. In 1.7.4 the class is not in the jar (`Could not find or load main class tlc2.REPL`, exit 1).
  `tlc2.TLC -repl` does not exist in either version.
- It uses jline. It does not need a terminal: with piped stdin it falls back to a dumb terminal and prints a jline
  `WARNING: Unable to create a system terminal` line. It also works on a pty.
- The prompt is `(tla+) `. The banner is `Welcome to the TLA+ REPL!`, then `TLC2 Version <build>`, then
  `Enter a constant-level TLA+ expression.`
- Exit is by end of input (Ctrl-D, or stdin closing). Exit code 0. There is no `exit`, `quit` or `:q` command (each is
  evaluated as an expression and gives an error). Errors in an expression do not change the exit code.
- It writes the history to `~/.tlaplus/history.repl`.

## Confidence

Verified for everything run here. Not verified, listed in follow-ups: Windows and macOS behaviour, `pcal.trans -spec`,
`-myspec`, `-spec2` (they need resource files that the jar does not ship, see below), and the REPL under a real
interactive terminal beyond one pty session.

## Evidence

### SANY: flags

v1.7.4 has no help. `SANY` with no arguments prints nothing and exits 0. `-help` gives `Illegal switch: -help` (exit
255). `-error-codes` gives `Illegal switch: -error-codes`. `-s` and `-l` are accepted and work (`v1.7.4/outputs`, run by hand; `-l` output not saved), but are not documented. `-d` was not tried on 1.7.4.

v1.8.0 prints a man-page-style help when run with no arguments (exit 255) or with `-help` (exit 0). The text contains
ANSI bold escapes (`[1m`) even when piped. Synopsis:

```
SANY [-dls] [-error-codes] [-messagesAsErrors codes] [-suppressMessages codes] FILE...
```

- `-d`: semantic graph explorer prompt (`cst`, `dot`, `mt`, `mt*`), or `SANY -d Module.tla cst` for one command.
  Stdin at EOF makes it loop forever printing the prompt (143 MB of output before I killed it). Scripted with
  `printf 'mt\nquit\n' | ...` it worked and exited 0 (`outputs/sany-d-scripted.txt`).
- `-error-codes`: exit 4 on a semantic or level error (help says 2 for parse errors; not observed, see below).
- `-l`: skip level checking. `-s`: skip semantic analysis and level checking (a spec with unknown operators then
  prints only the banner and exits 0).
- `-messagesAsErrors codes`, `-suppressMessages codes`: comma-separated **integers**, not names. Names give
  `Error: ...: not an integer: NAME`, unknown numbers give `unknown message code: 1`, both exit 255. The numbers are
  `ErrorCode.getStandardValue()` values; I listed all 66 in `outputs/sany-message-codes.txt` (for example 4200
  SYMBOL_UNDEFINED, 4310 and 4311 the stuttering-sensitivity ones, 4802 RECORD_CONSTRUCTOR_FIELD_NAME_CLASH, 4803 to
  4805 the PlusCal "changed since last translation" warnings). Only the six 48xx codes are level WARNING; the rest are
  ERROR.
- Multiple files are accepted and each gets its own banner. With `-error-codes`, Good.tla then SemErr.tla gave exit 4;
  ParseErr.tla then Good.tla gave 255 (`sany-badthengood.txt`).
- Unknown option in 1.8.0: `Invalid option: -bogus` and `Try 'SANY -help' for more information.`

### SANY: outputs

Full text in the fixture folders. Condensed from `outputs/sany-*.txt`.

Success, 1.7.4 (exit 0):
```
****** SANY2 Version 2.1 created 24 February 2014
Parsing file /.../Good.tla
Parsing file /tmp/Naturals.tla
Semantic processing of module Naturals
Semantic processing of module Good
```
Success, 1.8.0 (exit 0):
```
****** SANY2 Version 2.2 created 08 July 2020
Parsing file /.../Good.tla
Parsing file /tmp/tlc-63845959683670018/Naturals.tla (jar:file:/.../tla2tools.jar!/tla2sany/StandardModules/Naturals.tla)
Semantic processing of module Naturals
Semantic processing of module Good
Linting of module Good
```

Parse error (`x == ` with no expression), exit 255 in both, same text in the middle:
```
***Parse Error***
Was expecting "Expression or Instance"
Encountered "Beginning of definition" at line 4, column 9 and token "==" 

Residual stack trace follows:
Definition starting at line 4, column 1.
...
Fatal errors while parsing TLA+ spec in file ParseErr.tla
```
1.7.4 then prints `tla2sany.semantic.AbortException`, `*** Abort messages: 1`, `In module ParseErr`, `Could not parse
module ParseErr from file ParseErr.tla`. 1.8.0 prints the "In module" and "Could not parse" lines and then repeats them
under `*** Errors: 1`. With several parse errors in one file (`Multi.tla`, three bad definitions) only the first was
reported, and the message was a reported parse error at line 7, column 6, which was the first definition with a bad
syntax (the earlier `x = y` lines are semantic, not parse errors).

Semantic error (two unknown operators), exit **0** in both without `-error-codes`, exit 4 with it in 1.8.0:
```
Semantic errors:

*** Errors: 2

line 4, col 13 to line 4, col 13 of module SemErr

Unknown operator: `y'.


line 5, col 22 to line 5, col 24 of module SemErr

Unknown operator: `Foo'.
```
Level errors (`LevelErr.tla`: `ASSUME x = 1` and `x'' = 1`) print under the same header with the same location format,
and exit 0, or 4 with `-error-codes`. `[](x' = x + 1)` ("[] followed by action not of form [A]_v.") is also listed
under "Semantic errors", exit 0 in 1.7.4 and 1.8.0, exit 4 with `-error-codes`. So SANY gives no separate warning
severity in text: even the WARNING-level 4802 (`[a |-> 1, a |-> 2]`, "Non-unique fields in constructor.") is printed under
"Semantic errors / *** Errors: 1". With `-error-codes -messagesAsErrors 4802` it exits 4; without `-messagesAsErrors`
(`-error-codes` alone not run for this case) the plain run exits 0. `-suppressMessages 4802` did not remove the message
in my run (`sany-warning-recclash-suppress.txt`: still printed, exit 0); I did not find out why.

Missing module (`EXTENDS NoSuchModule`), exit 255:
- 1.7.4: `File does not exist: .../NoSuchModule.tla while looking in these directories: jar:file:...`, then `Unknown
  location`, then `Cannot find source file for module NoSuchModule imported in module MissingMod.` (one stderr line).
- 1.8.0: `Cannot find source file for module NoSuchModule imported in module MissingMod.` preceded by `In module
  MissingMod`, repeated under `*** Errors: 1`. Nothing else, no line or column.

Missing input file, exit 255 in both: `File does not exist: <cwd>/Nope.tla while looking in these directories: ...` then
`Cannot find the specified file Nope.tla.`

File name differs from the module name (`NameMismatch.tla` containing `MODULE Other`), exit 255:
`File name 'NameMismatch' does not match the name 'Other' of the top level module it contains.` with `Unknown location`.

PlusCal warnings (see below): in 1.7.4 a line `!! WARNING: The PlusCal algorithm in module Pcal has changed since its
last translation.` after the banner, exit 0. In 1.8.0:
```
Warnings (1) during syntax parsing of Pcal.tla:
In module Pcal
The PlusCal algorithm in module Pcal has changed since its last translation.
```
exit 0. With `-error-codes` still 0, so a warning is never fatal unless named in `-messagesAsErrors`
(I did not run 4803 to 4805 in `-messagesAsErrors`).

Where output goes: all on stdout in every case above (the exception is the single stderr line for a missing module in
1.7.4). That is what `sany-*` outputs were captured with (`2>&1`), and I checked the split separately.

Temporary files: 1.7.4 extracts standard modules to `/tmp/<Name>.tla` and removes them again (none left over). 1.8.0
extracts to a fresh `/tmp/tlc-<number>/` and leaves the empty directory behind: the count of `/tmp/tlc-*` went 276 to
277 for one run of 1.8.0 and stayed 277 for one run of 1.7.4. Other agents were running TLC at the same time, but the
step from my own single run matches the pattern in every case I counted.

### SANY: machine-readable output

No flag in either help or in the 1.7.4 behaviour. `tla2sany.xml.XMLExporter` exists in both jars:
- v1.7.4: any module fails with `XMLExportingException: failed to validate XML` (the schema validation tries to load a
  W3C DTD, `The declaration for the entity "ContentType" must end with '>'`), exit 1, on Java 25. Not tested on other
  JDKs.
- v1.8.0: `-help` lists `-I dir`, `-o` (skip schema validation), `-r`, `-t` (terse), `-u`. Good.tla gives about 2500
  lines of XML on stdout (`xml-good.txt`), exit 0, with `<location>` elements holding column and line ranges. For
  errors it prints SANY's usual text and `ERROR: Failed to parse module.` and exits 2 (also for a missing module or file).
  It has its own `XMLExporterExitCode` class. So it is machine-readable for a valid spec only, not for diagnostics.

### PlusCal translator

`java -cp tla2tools.jar pcal.trans -help` (exit 0, identical text in both versions except the banner). Options:
`-help`, `-wf`, `-sf`, `-wfNext`, `-nof`, `-termination`, `-nocfg`, `-label`, `-reportLabels`, `-labelRoot name`,
`-lineWidth n`, `-version`, `-unixEOL`, `-spec name`, `-myspec name`, `-spec2 name`, `-myspec2 name`, `-writeAST`, `-debug`.
No arguments: `Unrecoverable error: -- Command-line error: No arguments specified..`, exit 255.

Success (both versions, exit 0):
```
pcal.trans Version 1.11 of 31 December 2020      (1.8.0: Version 1.12 of 01 July 2024)
Parsing completed.
Translation completed.
New file Pcal.tla written.
New file Pcal.cfg written.
```
Files, verified in a fresh folder per case (`pcal-results/`): after a run the folder has `X.tla` (rewritten), `X.cfg`
(new) and `X.old` (the previous `X.tla`). With `-nocfg` there is no `.cfg` and no "New file ... .cfg" line. The
translation is inserted between `\* BEGIN TRANSLATION (chksum(pcal) = "de419bca" /\ chksum(tla) = "...")` and
`\* END TRANSLATION`. The default `.cfg` content is:
```
SPECIFICATION Spec
\* Add statements after this line.
```
Running it a second time keeps the lines after the marker (a `\* user edit` line I appended survived), overwrites
`X.old` with the previous translation, and prints "New file Pcal.cfg written." again. When the existing `.cfg` has no
marker (`SPECIFICATION Foo / INVARIANT Bar`), the result was the marker line followed by those two lines, and the
generated `SPECIFICATION Spec` line was gone (both versions). So a hand-edited `.cfg` without the marker line is not
safe, and the cfg is rewritten even though only "New file" is printed.

Other runs (both versions, same text except banner):
- Extension optional: `pcal.trans Pcal` works. Missing file: 1.7.4 `Command-line error: Input file Nope.pcal and
  Nope.tla.tla not found..`, 1.8.0 `Input file Nope.tla not found.`; exit 255.
- Unknown option: `Command-line error: Unknown command-line option: -bogus..`, 255.
- PlusCal syntax error (`while x < 3 x := x + 1;`): `Unrecoverable error: -- Expected "do" but found ":="` and
  `line 6, column 20.`, exit 255, input left untouched, nothing written.
- Semantic error (`y := 1` with no `y`): `Parsing completed.` then `Assignment to undeclared variable y` and `at line 6,
  column 6.`, 255, nothing written.
- No algorithm: `Beginning of algorithm string --algorithm not found..`, 255.
- Missing label: `Missing label at the following location: line 7, column 3.`, 255. With `-label -reportLabels` it adds
  the label and prints `The following label was added:` and `  Lbl_1 at line 7, column 3`, exit 0. So the PlusCal
  errors give line and column, but not the file name, and the message ends in two dots.
- Error in a TLA+ expression inside the algorithm (`x := x + ;`) is not detected: exit 0, translation written. SANY
  on the result then fails with a parse error.
- `-wf` and `-termination` change the generated `Spec` and `.cfg`; I only checked that they run, exit 0, and write
  the three files.
- `-writeAST`: prints `Wrote file AST.tla.` and exits **255**. `-spec Foo`: writes `AST.tla`, then `Could not find
  resource file Foo.tla. There is probably something wrong with the way the +cal translator is installed.`, 255.
  `-spec`, `-myspec` and `-spec2` rely on a spec that is not in the jar, so I could not test a successful run.
- stdout: all messages, including errors, go to stdout, stderr was empty.

Difference 1.7.4 vs 1.8.0: banner only, `Input file ... not found` wording, and the order of variables in the generated
`VARIABLES` line (`x, pc` vs `pc, x`), which changes `chksum(tla)` and makes golden files per version necessary.

Interaction with SANY 1.8.0: after translation SANY prints no PlusCal warning. After editing the algorithm text or the
translation block without re-running `pcal.trans`, it prints the warnings 4803 to 4805 shown above (exit 0). In 1.7.4 the
same check gives the `!! WARNING` line.

### REPL

v1.7.4: `java -cp tla2tools.jar tlc2.REPL` gives `Error: Could not find or load main class tlc2.REPL`, exit 1. The jar
holds only `tlc2.REPLSpecWriter` helper classes. `tlc2.TLC -repl` gives `Error: unrecognized option: -repl`, exit 1,
in both versions.

v1.8.0, piped stdin (`outputs/repl-stdin-eof.txt`), input `1+1`, `2*3`, `{1,2,3} \cup {4}`, `x`, `1+`:
```
Nov 14, 2026 10:24:26 PM org.jline.utils.Log logr
WARNING: Unable to create a system terminal, creating a dumb terminal (enable debug logging for more information)
Welcome to the TLA+ REPL!
TLC2 Version 2026.11.15.002146
Enter a constant-level TLA+ expression.
(tla+) 2
(tla+) 6
(tla+) {1, 2, 3, 4}
(tla+) Error evaluating expression: 'x'
[line 6, col 14 to line 6, col 14 of module tlarepl

Unknown operator: `x'.]
(tla+) Error evaluating expression: '1+'
[In module tlarepl

Could not parse module tlarepl from file tlarepl.tla]
(tla+) 
```
Exit 0 on end of input. The WARNING line is jline's, written when stdout is not a terminal; it is on stderr or stdout
indistinguishably in that capture (I did not split them). `EXTENDS Naturals` on a line is evaluated as an expression and
fails; `exit`, `quit` and `:q` are not commands (they get an error, and the session continues). Evaluating errors
never changes the exit code.

On a pty (`script -qec`, `outputs/repl-pty-session.txt`): the banner and the results printed, the session ended with
Ctrl-D (EOT) with exit 0. The captured text had terminal control sequences (`ESC[?2004h`, bracketed paste) and the
prompt text was not readable in that capture, so I did not confirm how the prompt looks on a real terminal. History
goes to `~/.tlaplus/history.repl`; it also recorded lines I piped in.

### Differences between the two versions, in one place

| Item | v1.7.4 | v1.8.0 (= rolling) |
| --- | --- | --- |
| SANY help | none; `-help` is an illegal switch, no args exit 0 | man-page help, exit 0 for `-help`, 255 for no args |
| SANY version line | `SANY2 Version 2.1 created 24 February 2014` | `SANY2 Version 2.2 created 08 July 2020` |
| `Linting of module X` | absent | printed after the semantic lines on success |
| `-error-codes`, `-messagesAsErrors`, `-suppressMessages`, `-d`, `-l`, `-s` documented | no (`-error-codes` illegal) | yes (`-l` and `-s` also work in 1.7.4; `-d` untested there) |
| Exit on semantic error | 0 | 0, or 4 with `-error-codes` |
| Exit on parse error / missing module or file | 255 | 255 (also with `-error-codes`) |
| Standard module path in output | `/tmp/Naturals.tla` | `/tmp/tlc-N/Naturals.tla (jar:file:...!/...)`, empty `/tmp/tlc-N` left behind |
| Parse error tail | `AbortException`, `*** Abort messages: 1` | no exception text, repeats under `*** Errors: 1` |
| PlusCal "changed since translation" | `!! WARNING: ...` line | `Warnings (1) during syntax parsing of X.tla:` block |
| Missing module message | has `File does not exist` and `Unknown location` | single `Cannot find source file ...` line |
| XMLExporter | fails on Java 25 | works, exit codes 0 and 2 |
| `pcal.trans` banner | 1.11 of 31 December 2020 | 1.12 of 01 July 2024 |
| Order of `VARIABLES` in translation | `x, pc` | `pc, x` |
| `tlc2.REPL` | not in jar | present |

## Implications for the roadmap

- `sany` command (thin, D5/D22): there is no machine-readable diagnostics mode, so `path:line:col: severity: message`
  has to be produced by parsing text. That is logic beyond reading the tool's output only in the sense that the formats
  are fixed text, but there is no alternative. The input file name must come from the command line, not from the
  output: parse errors and semantic errors carry line and column but no file, only "of module X" (semantic) or the
  later `in file X.tla` line (parse). Missing module, name mismatch and missing file have no location at all. Severity:
  everything is an error in the text, including WARNING-level codes; PlusCal warnings in 1.8.0 are a separate block.
- Exit codes cannot be passed through: semantic errors exit 0 in both versions unless `-error-codes` (1.8.0 only), and
  even then a parse error is 255 not 2. A `sany` command needs to decide success from the output ("Semantic errors:" or
  "Fatal errors while parsing" or "***Parse Error***") or use `-error-codes` on 1.8.0 plus 255, and have a rule for
  1.7.4. That is a decision for design, not a fact.
- Golden files per version are needed, and the version-dependent parts are the banner, `Linting` line, the temp path of
  standard modules, the `/tmp/tlc-N` number (random per run) and absolute paths. Those would have to be normalised.
- 1.8.0 leaves an empty `/tmp/tlc-N` directory per SANY run; a long test loop would accumulate them.
- `pcal` command (passthrough): the flags are plain; the translator writes into the user's source folder (`X.tla`,
  `X.old`, `X.cfg`), so running it on a file is a modification of the user's file. `-writeAST` exit 255 is not an error.
  Exit 255 plus `Unrecoverable error:` is the only failure signal; there is no file name on errors.
  The `-spec`, `-myspec` and `-spec2` options cannot be relied on with the jar alone.
- `repl` command: only on 1.8.0; the command must fail clearly for 1.7.4 pins (class missing, exit 1). Terminal passed
  through works; non-terminal stdin also works (dumb terminal) and exits 0 at end of input. History file is outside
  the tlaup folders (`~/.tlaplus/history.repl`).
- Version differences (the table above) mean `tlaup` needs the toolset version at hand to know which flags exist
  (`-error-codes`, REPL).

## Open follow-ups

- `-suppressMessages 4802` did not suppress the 4802 message in 1.8.0. Needs a look at the SANY source to see whether
  that is the intended behaviour (the help says only non-error messages can be suppressed, and 4802 is a WARNING).
- `-messagesAsErrors 4803/4804/4805` for the PlusCal warnings was not run.
- `-error-codes` documents exit 2 for parse errors but 255 was observed; check whether another path (for example
  `SANY` called through a different entry) yields 2 or whether the help is wrong.
- `pcal.trans -spec`, `-myspec`, `-spec2`, `-myspec2` successful runs were not tested (`-myspec` needs a user-supplied
  translator spec).
- The exact rule by which `pcal.trans` rewrites an existing `.cfg` was only checked with two cases.
- REPL on a real terminal (prompt rendering, history keys, Ctrl-C) and the REPL with a loaded module/config were not
  tested; the REPL help or source for any other commands was not read.
- XMLExporter 1.7.4 failure was seen on Java 25 only; try Java 11 or 17 to see if it is a JDK issue.
- Windows and macOS were not checked; ANSI escapes in the SANY help may differ.
- `SANY -d` with stdin at EOF loops forever; relevant if `tlaup` ever runs `sany` without a terminal and `-d` is
  passed through.

## Date checked

2026-11-14.
