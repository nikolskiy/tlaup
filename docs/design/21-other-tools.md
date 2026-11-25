# 21. Milestone 1b: sany, pcal, repl

Covers "Other tools (decision D5)". Relies on decisions D5, D22, D29, D30, D45 and research [12](../research/12-sany-pcal-repl.md) and [3](../research/03-jar-identity-and-upstream-cli.md). Everything runs through the launcher ([20 G3](20-groundwork.md#g3-java-launcher)) and uses the preflight steps of `tlc` in the same order ([11 R11](11-runner.md#r11-preflight)): the spec (for `sany` and `pcal`), then the tool build, then Java.

The three commands share one small shape, in `tlaup/tools/`:

```python
@dataclass(frozen=True)
class ToolInvocation:
    build: Build; java: JavaRuntime
    main_class: str
    spec: Path | None
    cwd: Path | None
    classpath: tuple[Path, ...]; tla_library: tuple[Path, ...]; jvm_options: tuple[str, ...]
    args: tuple[str, ...]
    warnings: tuple[str, ...]          # from finding Java (13 J2, J3)

def resolve_tool_invocation(tool: Literal["sany", "pcal", "repl"], spec: str | None, *,
                            java_opts: Sequence[str], extra_args: Sequence[str],
                            paths: AppPaths, settings: Settings, env: Mapping[str, str], cwd: Path,
                            get_build: Callable[[], Build]) -> ToolInvocation
def build_tool_command(inv: ToolInvocation) -> JavaInvocation      # pure
```

`resolve_tool_invocation` is the preflight of these commands: first the checks that need only the command line (the Java options, and for `sany` the refusal of `-d`, S1), so a usage error comes before any prompt ([11 R11](11-runner.md#r11-preflight), step 0); then `resolve_spec` ([11 R5](11-runner.md#r5-spec-names)) when the tool takes one, then `get_build()`, then the capability check (is this tool in this build: `ToolNotInBuild`, code 3), then `require_java`. The capability is stored with the build ([12 V5](12-tools-and-downloads.md#v5-download-and-verify)) and needs no Java, so it is checked as part of the build step and `java` is not started, not even for its version, when the build cannot run the tool. This agrees with decision D45's order (spec, cfg, build, Java): the capability is a fact about the build. `tlc` has no such check, since every build has TLC, so [11 R11](11-runner.md#r11-preflight) is unchanged. As for `tlc`, it takes the pieces it needs and not the whole context, and `get_build` is the command's wrapper round `ensure_tools` ([20 G1](20-groundwork.md#g1-tlc-invocation)).

**Signals.** Each of the three commands runs its tool inside `signals_held` ([20 G3](20-groundwork.md#g3-java-launcher)), entered after the preflight and held until the command has printed what it prints. `sany` and `pcal` enter it plainly and use `run_streaming`, so they behave as a parsed `tlc` run does: the first SIGINT, SIGTERM or SIGHUP terminates the tool, a second one or the grace period kills it, a signal before the tool exists means it is not started, and the command exits with the signal's code from [02 X1](02-cross-cutting.md#x1-exit-codes) (130, 143, 129) whatever the tool returned. The diagnostics the parser had completed by then are printed; no summary line is. What an interrupted PlusCal translator leaves in the `.tla` file is the translator's business and was not tried. `repl` enters the block with `leave_interrupt=True` (S3): a Ctrl-C is never tlaup's to act on, also in the instant between entering the block and the REPL's start, where it is simply dropped and the REPL starts; SIGTERM and SIGHUP in that instant are recorded and the REPL is not started.

All three accept `--java-opt` ([13 J1](13-modules-and-java.md#j1-java-options)) and `--auto-install` ([12 V9](12-tools-and-downloads.md#v9-first-run-prompt)), and pass the tool's own arguments (everything after `--`) to the tool unchanged.

## S1 sany

Roadmap: "`sany` command: parse a spec and report diagnostics with file, line and column. Reuses the fixed SANY parser."

**Problem.** There is no way to check a spec for syntax and semantic errors with the pinned jar short of starting a model-checking run, and SANY's own exit code says 0 for a spec with semantic errors.

**Facts (research 12).** SANY has no machine-readable diagnostics. Its error lines carry a module name and a line and column, never a file; some errors have no location. Semantic and level errors exit 0; parse errors, a missing module and a missing file exit 255. Rolling builds have `-error-codes`, which makes semantic errors exit 4; v1.7.4 rejects it. Output is on stdout, with one exception: for a missing module v1.7.4 writes one line to stderr. The captures were made with the two streams joined (`2>&1`), so they do not record which line that is. The runs were made in the spec's folder with the file name and the jar alone on the classpath. With `-d` and no input SANY prints its prompt in a loop for ever (143 MB before the research run was killed).

**Facts (top-up, 2026-11-20).** Research 22 captured the two streams apart: the v1.7.4 stderr line is `File does not exist: ...`, not the diagnostic, which is on stdout. SANY refuses grouped flags (`-dl`, `-ls`) itself, with exit 255 and without starting the explorer. A spec whose only message is 4802 makes TLC exit 150 ([research 22](../research/22-more-tool-captures.md)). Standalone SANY honours `-DTLA-Library` and the classpath exactly as TLC does, on both builds, and searches the working folder, then the library folders, then the standard modules in the jar, then the classpath ([research 27](../research/27-sany-library-path.md)). It does not search the spec's folder: started elsewhere with an absolute spec path, it does not find the modules beside the spec, and a module of the same name in the starting folder would win ([research 32](../research/32-sany-pcal-working-folder.md)).

**Design.** `tlaup sany SPEC [-- SANY arguments]`.

1. Preflight: the command line (step 7), spec ([11 R5](11-runner.md#r5-spec-names)), build, Java.
2. Run `tla2sany.SANY <extra args> <Spec.tla>` with the working folder set to the spec's folder, and the same classpath and `-DTLA-Library` a TLC run of that spec would get, so that modules resolve the same way in both commands.

   **The spec's folder, not D34's** (top-up, research 32). `tlc` runs in the folder tlaup was started from with the spec as an absolute path (D34); `sany` cannot, because SANY looks for the modules a spec extends in its working folder and not beside the spec. Putting the spec's folder on `-DTLA-Library` instead would rank it below the starting folder, so a stray module there would still win. Running in the spec's folder is also what TLC does inside a run (it searches the spec's folder first), so `tlaup sany` and `tlaup tlc` see the same modules. "The spec's folder" is the folder as the user named it, links not resolved, as R4 does for TLC. The help of `sany` says in one line that it reads the spec from the spec's own folder.

   **The same library path and classpath as `tlc`** (top-up, research 27). Registered modules, a project's `modules/` folder and a CommunityModules jar on the classpath are all found by standalone SANY, so `sany` passes exactly what a TLC run of that spec would get. The help can give the search order: the spec's folder, then the library folders, then the standard modules, then the classpath. A jar named as a library folder is useless to both tools; jars go on the classpath, which is where tlaup puts them. v1.7.4 copies every module it reads from a jar or the classpath to `<java.io.tmpdir>/<Module>.tla`, a fixed name, so two v1.7.4 runs at once write the same files; that is a known gap, postponed until after the first implementation ([13 J1](13-modules-and-java.md#j1-java-options)).
3. SANY's two streams are read through one pipe (`run_streaming(..., merge_stderr=True)`, [20 G3](20-groundwork.md#g3-java-launcher)), which is how the research captured them, and fed to a `SanyParser` ([10 P8](10-parser.md#p8-sany-output)). The parser then sees the lines in the order SANY wrote them, and the v1.7.4 line that goes to stderr is not lost or reordered.

   The parser gives every line it is fed a class; the table of classes is P8's and is the authority, and this command only routes by it:

   | The line is | The command |
   | --- | --- |
   | Part of a diagnostic | Prints nothing for the line; the diagnostic is printed whole (step 4) |
   | SANY's banner, or a progress line (`Parsing file ...`, `Semantic processing of module ...`) | Writes it to stderr as SANY wrote it (D30: progress) |
   | Blank | Drops it |
   | Anything else, which is every line the parser does not recognise | Writes it to stdout as SANY wrote it (D9: nothing TLC or SANY printed is lost) |

   The command decides nothing about a line itself: it never matches SANY's text. If P8 names its classes differently or has more of them, each of them falls in one of these four rows, and a class P8 adds later is routed as "anything else" until this table says otherwise.

   **Checked by research 22** (top-up). With the two streams recorded apart, the only stderr line is `File does not exist: ...` (v1.7.4: for a missing module and a missing file; rolling: for a missing file), and the diagnostic is on stdout. So reading the streams through one pipe loses nothing and keeps the order, and the captures stay valid inputs; the design holds as written. Reading them apart, like TLC's, would also work; one pipe is kept because it is what the golden files hold.
4. Print each diagnostic on stdout in the editor form (D22, D30):

   ```
   SemErr.tla:4:13: error: Unknown operator: `y'.
   ParseErr.tla:4:9: error: Was expecting "Expression or Instance"; Encountered "Beginning of definition" at line 4, column 9 and token "=="
   MissingMod.tla: error: Cannot find source file for module NoSuchModule imported in module MissingMod.
   Pcal.tla: warning: The PlusCal algorithm in module Pcal has changed since its last translation.
   ```

   The path is the file SANY announced for the diagnostic's module, written relative to the folder tlaup was started from when it is beneath it, else absolute. A diagnostic whose module was not announced gets the spec's own path. A diagnostic with no location has no `:line:col`. The lines of a message are joined with `; `, as SANY wrote them, so one diagnostic is one line for tools that read this format; what the parser keeps apart from the message (the residual stack of a parse error) follows indented, after the source excerpt.

   **The source excerpt** (decision D66). Under the editor-form line of a diagnostic that has a location, the command prints the lines of the spec it points to, so that a reader in a terminal sees the offending text without opening the file. For `SemErr.tla` of research 12:

   ```
   SemErr.tla:4:13: error: Unknown operator: `y'.
        2 | EXTENDS Naturals
        3 | VARIABLE x
        4 | Init == x = y
          |             ^
          | Error here: line 4, col 13 to 13
        5 | Next == x' = x + 1 + Foo(2)
        6 | ====
   SemErr.tla:5:22: error: Unknown operator: `Foo'.
        3 | VARIABLE x
        4 | Init == x = y
        5 | Next == x' = x + 1 + Foo(2)
          |                      ^^^
          | Error here: line 5, col 22 to 24
        6 | ====
   ```

   - The two lines before the location's first line (fewer at the top of the file), that line, a line of marks and the `Error here` line, then the rest of the location's lines when it spans several, and the two lines after its last line (fewer at the end of the file), in the order 0.8 printed them. Each line is indented by two spaces, with the line number right-aligned in four columns and ` | ` before the text as it is in the file.
   - The marks are `^` under the columns of the location on its first line: from its column to its end column when it ends on that line, to the end of the line when it ends on a later one, and one mark when it has no end (the `at line L, column C` form of a parse error, [10 P8](10-parser.md#p8-sany-output)). The space in front of the marks copies each tab of the source line in front of the column, so the marks stand under their columns in a terminal.
   - The line after the marks is `Error here: line L, col A to B`, `line L, col A to line L2, col B` for a location over several lines, or `line L, col A` with no end.
   - The file is the one the editor-form line names, read as UTF-8 with undecodable bytes replaced. There is no excerpt, and no note about it, when the diagnostic has no location, the file cannot be read, or the line is not in it: the editor-form line already says where to look.
   - The excerpt is text from outside tlaup and is printed as text, never as markup ([10 P11](10-parser.md#p11-tlc-text-and-rich-markup)). It goes to stdout with its diagnostic.

   One pure function makes it, `source_excerpt(text: str, location: Location) -> list[str]`, in `tlaup/reporters/text.py` beside the function that writes the editor-form line. That function gives the whole diagnostic in the order above, so neither caller splices: `format_diagnostic(d: Diagnostic, *, cwd: Path, spec: Path, source_text: str | None) -> list[str]` returns the editor-form line, then the excerpt (from `source_excerpt`, when `source_text` is given and the diagnostic has a location the text holds), then the details the parser kept apart, indented. Its caller reads the file (`None` when it cannot be read) and prints the list. `tlaup sany` and the terminal reporter of `tlaup tlc` ([22 O3](22-reporters.md#o3-terminal-reporter)) are its two callers, so the two commands print a diagnostic the same way. The excerpt is terminal output only: the JSON of milestone 4 carries the file, line and column, for programs that open the file themselves, and never the excerpt ([40](40-later-milestones.md#milestone-4-automation-surface)). tlaup 0.8 printed such an excerpt for a SANY error in a `tlc` run, with `▲` marks and box characters; the marks are now `^` and the gutter `|`, which read the same in a CI log and on a console without those glyphs. 0.8's "(Source code unavailable)" note for a file it could not read is dropped. (Settled with the maintainer on 2026-11-24: the two lines after are kept, and the note is dropped.)
5. A last line on stderr: `1 error, 0 warnings` or `no errors`.
6. **Exit code** (D29): 150 if any diagnostic has severity `error`; otherwise SANY's own code. A warning alone does not change the code. The severity is the parser's (P8). No `-error-codes` is added: one rule for both builds, from the parsed output.

   **4802 is an error** (decision D55, top-up). SANY prints its message 4802 ("Non-unique fields in constructor.") under "Semantic errors" with nothing in the text to tell it from an error, and TLC refuses a spec whose only finding is that message with 3002 and exit 150, on both builds (research 22); the two stuttering lints behave the same. So P8 classes all three as errors, and `tlaup sany` exits 150 for them, the number `tlaup tlc` exits with for the same spec, which is D29's promise. A user who runs `tlaup sany` as a quick check in CI then sees it fail where the model check would. Only PlusCal's "changed since its last translation" messages are warnings: TLC checks the model and exits 0. The first design classed 4802 as a warning by its text, from research 12's reading of SANY's message table, and the walk-through notes of 2026-11-20 first kept that for `tlaup sany`; the maintainer reversed it after the review.
7. **`-d` is refused.** `tlaup sany SPEC -- -d` is a `UsageError`: the command runs SANY with no input, where `-d` loops for ever. The hint names the way to run it in this release: Java directly, on the jar `tlaup tool path` prints. It names no command the release does not have; when milestone 4 adds the generic exec command ([40](40-later-milestones.md#milestone-4-automation-surface)), the hint names that command from then on. This is the only SANY argument tlaup looks at, and it is looked at before anything else is checked, so the refusal comes before a first-run prompt.

   The refusal matches an argument that is exactly `-d`. Matching more loosely, on any dash group that holds a `d`, would refuse `-error-codes`. SANY itself refuses grouped flags such as `-dl` and `-ls` on both builds, with exit 255 and without starting the explorer (research 22, top-up), so exactly `-d` is the right width and no grouped form needs a rule. The 1.8.0 synopsis, `SANY [-dls] ...`, is misleading on that point and is not copied into tlaup's help. `-D` was not tried; SANY's synopsis lists no such switch.

One spec per invocation in the first wave. SANY accepts several files, but they can be in different folders and step 2 depends on the folder.

**Thin, as decision D5 asks.** The command has no logic beyond reading SANY's output, and for the excerpt the lines of the spec a diagnostic points to: it does not decide which messages matter, filter warnings, or re-check anything. The one judgement it makes is the exit code, which the research shows SANY's own cannot provide.

**Rejected.** `-error-codes` on builds that have it: two behaviours to test, and a parse error is 255 with it anyway. `tla2sany.xml.XMLExporter` for structure: it gives errors as the same text, and fails on v1.7.4 with Java 25 (research 12). Several specs per call: see above; `xargs` or a shell loop does it. Reading stdout only: drops the v1.7.4 stderr line, and the replayed golden file, which holds both streams, would still pass. Passing `-d` through: floods the terminal until killed.

**Tests.** `sany.feature`, in-process, with the fake `java` replaying the SANY golden outputs: a good spec gives exit 0 and an empty stdout; two semantic errors give two lines in the editor form and exit 150 although the replayed exit code is 0; a parse error gives one line and 150; a missing module gives a line with no position and 150, on the replay of each build; the PlusCal warning alone gives a warning line and exit 0; `-- -xy` passes through and SANY's 255 with its own text comes back on stdout (`sany-grouped-unknown`: `Invalid option: -xy` on rolling, `Illegal switch: -xy` on v1.7.4); `-- -d` exits 2 and starts nothing, also with no build installed (no prompt); the banner and progress lines of a replay are on stderr and not on stdout. The Java command logged has the file name as its last argument, and the fake `java` logs the folder it was started in, which is the spec's folder (this needs the fake to record its working folder, [01 T4](01-testing.md#t4-fakes-at-the-edges)). The replays carry `<tmp>` in place of the capture's folders, so the features assert the message, the position and the file name; the rule for the path in front (relative when beneath the starting folder) is a unit test of the formatting function with hand-built diagnostics. The excerpt (D66): a unit test of `source_excerpt` on hand-written text gives, for a location on line 4, lines 2 to 4, the marks and the `Error here` line, exactly as above; on line 1, that line alone before the marks; over two lines, marks to the end of the first and `line 4, col 13 to line 5, col 2`; with no end, one mark and `line 4, col 13`; a tab in front of the column, a tab in the mark line; a line past the end of the text, nothing. Feature, in-process: the `sany-semerr` replay with `replace` mapping the capture's folder to the scenario's folder, where the scenario writes research 12's `SemErr.tla`, gives on stdout the two editor-form lines, each followed by its excerpt as above, and exit 150; the replay without the file there gives the two editor-form lines alone, exit 150 and no `error:` line of tlaup's own. Feature, in-process (top-up): the 4802 replay gives one `error:` line and exit 150 although the replayed exit code is 0; the stale-PlusCal replay gives one `warning:` line and exit 0. Integration: real SANY on both builds, including a semantic error run through the command itself (`tlaup sany` as a real process, or its output path with `format_diagnostic`, not the parser alone), whose excerpt comes from the real file under each editor-form line, the missing module on v1.7.4, which is the run that shows the stderr line is not lost, a spec that extends a registered module, which research 27 showed SANY finds, and a spec beside which a module lies while a module of the same name lies in the starting folder: the spec's own is used.

**Changelog.** Added: "`tlaup sany SPEC` runs the SANY parser and prints its findings as `path:line:col: severity: message`, each followed by the lines of the spec around it with `^` under the columns. It exits 150 when the spec has errors."

**Depends on.** G3, P8, R5, R11. **Risks.** SANY leaves an empty temporary folder per run on rolling builds (research 12); tlaup does not clean the system's temporary folder. Two v1.7.4 runs at once share its temporary module copies (step 2; a known gap, read from the source and not tried). A spec reached through a symbolic link to its folder was not tried with SANY alone. With the two streams joined, a line the JVM itself writes to stderr (a warning about an option) reaches the parser, is not recognised, and is printed on stdout with SANY's other unrecognised lines. SANY's columns were read as counting characters, a tab as one; if SANY counts a tab otherwise, the marks of an excerpt on a line with tabs stand in the wrong place, and the editor-form line is still right. (Stage 4 review, 2026-11-24: the source excerpt under the editor-form line, decision D66; the passthrough test uses the capture that exists, and the `-d` hint names no command of a later milestone, index Clerical; the line after the marks named as such, finding G13; `format_diagnostic` returns the excerpt in its place, finding H4; the excerpt's integration test goes through the command, finding H3.)

## S2 pcal

Roadmap: "`pcal` command: run the PlusCal translator; passthrough for its flags."

**Problem.** The translator is in the pinned jar and nothing in tlaup can start it.

**Facts (research 12).** `pcal.trans` rewrites the `.tla` file in place, moves the previous file to `X.old`, and writes `X.cfg` unless `-nocfg`. An existing `X.cfg` is rewritten with no backup: the lines after its marker line are kept; in a cfg with no marker line the user's lines survive under a new marker but the generated `SPECIFICATION` line is dropped. Success is exit 0, failure 255, all text on stdout (stderr was empty in every run). Errors give a line and column but no file, and end in two full stops. `-writeAST` exits 255 after succeeding. It does not check TLA+ expressions inside the algorithm.

**Design.** `tlaup pcal SPEC [-- translator arguments]`.

1. Preflight: spec, build, Java.
2. Run `pcal.trans <extra args> <Spec.tla>` in the spec's folder, with the jar alone on the classpath, the two streams read through one pipe as for `sany`. **The spec's folder, as for `sany`** (top-up, [research 32](../research/32-sany-pcal-working-folder.md)). The translator could follow D34: started elsewhere with an absolute spec it writes `X.old`, `X.cfg` and the new `X.tla` beside the spec all the same; only `-writeAST` writes `AST.tla` into the working folder, and the file names in its messages follow the argument as given. Running it in the spec's folder gives the two tools that read a spec on their own one rule, keeps `AST.tla` beside the spec and the messages short, and needs no rule for names in messages. The help of `pcal` says in the same line as `sany`'s that it reads the spec from its own folder. Research 21 found that v1.7.4's translator on Java 11 under a C locale writes non-ASCII comments back into the spec as `?`; the launcher's encoding options prevent it ([20 G3](20-groundwork.md#g3-java-launcher), D56).
3. Feed the output to a `PcalParser`:

   ```python
   @dataclass
   class PcalResult:
       version: str | None
       files_written: list[str]              # from "New file X written."
       labels_added: list[tuple[str, int, int]]   # (name, line, column), in the translator's order
       diagnostics: list[Diagnostic]         # tool="pcal"
       other: list[str]                      # lines not recognised, kept

       def to_dict(self) -> dict[str, object]: ...   # plain JSON types, as the types of 10 P3; from_dict beside it
   ```

   Recognised: the banner; `Parsing completed.`; `Translation completed.`; `New file X written.`; `Unrecoverable error:` followed by ` -- <message>` and optionally `line L, column C.` or `at line L, column C.`; `The following label was added:` or `The following labels were added:`, and under it one line per label, `  <name> at line L, column C` (only the singular was captured, by research 12's `pcal-label`; the plural is the translator's other text, read from its classes in the rolling jar of research 22).
4. Print: each diagnostic on stdout in the editor form with the spec's path (`Pcal.tla:6:20: error: Expected "do" but found ":="`), the doubled full stop trimmed; each label the translator added (`-label`, reported with `-reportLabels`) on stdout, one per line, in the translator's order, as `<spec>:<line>:<col>: label <name> added` with the spec's path as for a diagnostic (`PcalNoLabel.tla:7:3: label Lbl_1 added`; decision D67): the labels are part of the result ([02 X2](02-cross-cutting.md#x2-stdout-and-stderr)), and the position form lets an editor jump to each; unrecognised lines as written. On success a note on stderr per file: `Pcal.tla translated (previous version saved as Pcal.old)`, `Pcal.cfg written`.
5. **Exit code**: the translator's, unchanged (D29), including 255 after `-writeAST`.

`pcal` changes the user's files. That is what the command is for, and decision D23 adds no prompts. The first lines of the help text say what is written: the spec is rewritten in place and the previous version kept as `SPEC.old`; `SPEC.cfg` is written or rewritten with no backup, and `-- -nocfg` leaves it alone. tlaup adds no `-nocfg` itself.

**Rejected.** Passing the output straight through with no parser: the roadmap asks for golden tests of PlusCal output, and the editor form is what lets an editor jump to the error. Copying the spec, translating the copy and comparing: logic the tool does not have upstream. Adding `-nocfg` by default to protect a hand-written cfg: changes what the translator does for everyone, and a first translation would then produce no cfg.

**Tests.** `pcal.feature`, in-process, with the fake `java` replaying the pcal golden outputs: success gives exit 0 and the two notes; a syntax error gives one editor-form line and 255; `-- -nocfg` is in the logged command; the `pcal-label` replay with `-- -label -reportLabels` gives exactly `PcalNoLabel.tla:7:3: label Lbl_1 added` on stdout, the two notes on stderr and exit 0 (D67). A unit test of `PcalParser` feeds the lines of `pcal-label` and gives one label, and the same lines with the plural heading and a second label line give both, in order. The fake does not write files; that the three files appear, and what happens to an existing cfg with and without the marker line, is an integration test on a copy of a PlusCal spec, on both builds.

**Changelog.** Added: "`tlaup pcal SPEC` runs the PlusCal translator. It rewrites the spec in place and keeps the previous version as `SPEC.old`, as the translator does. It also writes `SPEC.cfg`, replacing an existing one without a backup; pass `-- -nocfg` to keep yours. With `-- -label -reportLabels` it prints each label the translator added as `Spec.tla:7:3: label Lbl_1 added`."

**Depends on.** G3, P2, R5. **Risks.** The `chksum` and the order of `VARIABLES` in the translation differ between builds (research 12); tlaup does not read the translated file, so only the golden outputs differ per build. Only two cases of an existing cfg were run by the research (with the marker line, and without). The plural label heading was not captured; if its label lines differ from the singular's, they are kept in `other` and printed as written. (Stage 4 review, 2026-11-24: the added labels are printed on stdout, question Q13, decision D67; `PcalResult` gets `to_dict()`, question Q18.)

## S3 repl

Roadmap: "`repl` command: interactive, so no output parsing; the terminal is passed straight through."

**Problem.** The REPL is in rolling builds and nothing in tlaup can start it.

**Facts (research 12, 3).** `tlc2.REPL` is in rolling builds and absent from v1.7.4, where starting it ends with the JVM's "Could not find or load main class" and exit 1. It works with piped input and exits 0 at end of input. It writes its history to `~/.tlaplus/history.repl`.

**Design.** `tlaup repl [-- arguments]`.

1. Preflight: the build, its capability, then Java. If the build lacks the capability `repl` ([00](00-overview.md#what-a-build-can-do)): `ToolNotInBuild` (code 3), "the pinned build v1.7.4@5a47802 has no REPL" / "install a rolling build: `tlaup tool install rolling`".
2. Inside `signals_held(leave_interrupt=True)`: `run_passthrough(..., forward_interrupt=False)` of `tlc2.REPL` in the folder tlaup was started from, with the same classpath and `-DTLA-Library` as a TLC run without a spec (the registered modules and the config paths).
3. Exit with the REPL's code.

Nothing is read or parsed. tlaup does not act on Ctrl-C while the REPL runs: in a terminal the REPL receives it itself and decides what it means, and tlaup's handler only keeps tlaup alive until the REPL ends ([20 G3](20-groundwork.md#g3-java-launcher) says why this is a handler and not "ignore"). The handler records nothing: after any number of Ctrl-C, a REPL that is quit normally exits with its own code, not 130, and a SIGTERM that comes later is treated as the first signal. SIGTERM and SIGHUP are forwarded. The history file is the REPL's own and stays where upstream puts it; the help text names it.

**Rejected.** Reading the REPL's output to add colour or history of tlaup's own: it is an interactive program with its own line editor. Forwarding SIGINT as for `tlc --raw`: the REPL would be terminated by a Ctrl-C meant to cancel a line.

**Tests.** `repl.feature`. In-process: with v1.7.4 pinned, exit 3 and `java` was not started. Real process (the child inherits the real file descriptors, which the in-process runner does not capture): with a rolling build, tlaup is started with `1+1` on its stdin and a fake `java` that copies its stdin to its stdout; the scenario sees the text on tlaup's stdout and the fake's exit code. One more real-process scenario sends SIGTERM to tlaup and asserts the fake has exited. That a Ctrl-C left to the REPL is not recorded is a unit test of the launcher (G3: after a SIGINT with `forward_interrupt=False` the outcome has the child's own code, and a SIGTERM after it terminates and gives 143); from outside the process "SIGINT, then end of input" could be written only with a step that signals and then closes stdin, which the step list does not have. Integration: real REPL with piped `1+1` prints `2`, exit 0, with `--java-opt=-Duser.home=<a temporary folder>` so the history file is not written to the real home folder (the JVM does not take its home from the `HOME` variable).

**Changelog.** Added: "`tlaup repl` starts the TLA+ REPL of the pinned build (rolling builds only)."

**Depends on.** G3, V1. **Risks.** How the REPL behaves on a real terminal (prompt, history keys, Ctrl-C) was not tested by the research; tlaup passes the terminal through and adds nothing, so whatever it does is upstream's behaviour. A SIGINT sent to tlaup alone, not from the terminal, does not reach the REPL.

## S4 Keeping them thin

Roadmap: "Keep all three thin: no logic beyond reading their output, everything through the shared launcher. Check which jar build is running, so the tool can switch to upstream's own entry point when it exists and fall back for older jars."

**Problem.** TLC's main class is a setting today (`tlc.java_class`) and is also written out in `versioning/metadata.py`; nothing records what a build can do. Three more commands would add three more names and three more guesses.

**Facts (research 3).** Upstream's proposed command (pull request 1371) is an unmerged shell script outside the jar; the maintainers asked for a new Java entry point first and nothing has happened since April 2026. There is nothing to hand off to.

**Design.**

- **One table of entry points**, `tlaup.tools.ENTRY_POINTS`: `{"tlc": "tlc2.TLC", "sany": "tla2sany.SANY", "pcal": "pcal.trans", "repl": "tlc2.REPL"}`. Nothing else names a main class.
- **Which build is running** is known without starting it: the capabilities stored with the build at install, decided from the jar's file list and manifest ([12 V5](12-tools-and-downloads.md#v5-download-and-verify)). Research 3 recommends exactly this: test for a class in the jar, not a version string.
- **The hand-off, when upstream ships an entry point**: add a capability (the new class is in the jar) and make the table's lookup prefer it for builds that have it. The commands, the launcher and the parsers do not change. Until upstream picks a class name, nothing more can be designed (research 3, open follow-up).
- **What "thin" forbids**: a command of this group does not add tool flags of its own beyond `--java-opt` and `--auto-install`; does not reinterpret the tool's result except the `sany` exit code; does not look at the tool's arguments except to refuse `sany -d`; does not write files; does not retry.

**Rejected.** Comparing version strings to decide what a build has: research 3 advises against it, and rolling builds have no version to compare. Designing the hand-off now against pull request 1371: it is a shell script outside the jar and may never merge.

**Tests.** A unit test asserts every value of `ENTRY_POINTS` is a class present in the recorded file list of the rolling jar, and that `tlc2.REPL` is absent from v1.7.4's. The file lists are captured once into `tests/unit/data/` (class names only).

**Changelog.** None.

**Depends on.** V1, V5, G3. **Risks.** An upstream rename of a main class breaks the command for builds after it; the unit test catches it only when the recorded file list is refreshed, and the weekly integration run ([30 I1](30-ci-and-release.md#i1-integration-job)) catches it on the live rolling build.

## S5 Golden files for SANY and PlusCal

Roadmap: "Golden-file tests for SANY and PlusCal output per TLC version; passthrough after `--` for each."

**Problem.** The SANY parser has two known defects and no test against real output; PlusCal output has no parser at all.

**Design.** Most of the captures exist for both builds (research 12) and move to `tests/parse/golden/sany/<build>/` and `pcal/<build>/` ([01 T3](01-testing.md#t3-golden-files)). Each case gets hand-written assertions and a full expected result, as a TLC case does; the assertions are the SANY and PlusCal parsers' own tests, not entries of T3's facts file, which takes a `RunResult` and holds TLC facts only, and they are written failing first in the same way. The expected result is `SanyResult.to_dict()` ([10 P8](10-parser.md#p8-sany-output)) or `PcalResult.to_dict()` (S2):

| Tool | Cases |
| --- | --- |
| SANY | success; parse error; several parse errors (only the first is reported); two semantic errors; level errors, on both builds; message 4802 printed under "Semantic errors", an error (D55), and the two stuttering lints; missing module; missing file; file name differs from module name; the PlusCal "changed since last translation" warning, as v1.7.4's `!! WARNING` line and as rolling's warning block, for each of its three texts; `-help` (rolling: a 45-line page with ANSI codes; v1.7.4: `Illegal switch: -help`, 255); grouped flags refused (`-dl`, 255); no arguments on rolling (usage text, 255). |
| PlusCal | success; `-nocfg`; syntax error; assignment to an undeclared variable; no algorithm; missing label; `-label -reportLabels`; missing file; unknown option; `-writeAST`. |

**The captures research 22 added** (top-up, `tests/fixtures/research/22-more-tool-captures/`). The three things the first captures did not give now exist on both builds: the "changed since last translation" warning as single-command captures (`sany-stale-alg`, `sany-stale-tla`, `sany-stale-both`, `sany-stale-two-files`), which replace the composite, hand-annotated `pcal-retranslate-and-lint.txt` as golden input; SANY `-help` (`sany-help`, `sany-h`); and the two streams apart for every SANY and PlusCal case, which confirmed S1's choice. Also v1.7.4's level errors, the 4802 and stuttering-lint specs and the grouped-flag refusals. They follow T3's rules like the rest: the time-dependent values are normalised as research 1's were.

Passthrough is tested in the three feature files (an argument after `--` appears in the logged Java command unchanged, in order).

The REPL has no golden files: its output is not parsed.

**Rejected.** Hand-written SANY output as golden input: the two known parser defects came from guessing at the format. Cutting the composite capture apart by hand: the file is annotated and has lines filtered out, so the pieces would not be what SANY printed.

**Tests.** The golden cases are the tests; they follow T3's rules (assertions per case written first, a full expected result, an update flag), with the parsers' own assertions in place of facts.

**Changelog.** None.

**Depends on.** T3, P8, S2. **Risks.** Rolling's SANY text can change with any upstream commit; the weekly integration run shows it, and the golden folder for a new build is a new capture, not an edit. (Stage 4 review, 2026-11-24: the facts file is TLC's only, and these cases have their parsers' own assertions and a dictionary form, question Q18.)
