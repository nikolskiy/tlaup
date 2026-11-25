# 02. Cross-cutting decisions

The roadmap names four things that sit in later milestones but must be decided in the first wave, because milestones 1, 1b and 2 build on them. All four were settled with the maintainer on 2026-11-15 (decisions D29 to D32).

## X1 Exit codes

Decision D29. Relies on research [15](../research/15-exit-codes-and-signals.md), [12](../research/12-sany-pcal-repl.md), [10](../research/10-examples-manifest.md). Serves the roadmap items "A small family of domain errors ... mapped to exit codes in one place" (milestone 1b, [20 G2](20-groundwork.md#g2-domain-errors)) and "Exit codes" (milestone 4).

**Problem.** Today every tlaup failure is 1, which TLC also returns for a bad flag; hand-written usage errors return 1 instead of 2; a failed uninstall returns 0; Ctrl-C returns 143 or 130 depending on a race (research 15).

**Facts (research 15).** TLC returns 0; 1 for its own usage errors; 10 to 14 for violations; 75 to 77 for evaluation failures; 150 for a spec that does not parse; 151 for a config error; 255 for anything unclassified. A missing cfg is 255 on v1.7.4 and 151 on rolling. The JVM exits 130 after SIGINT and 143 after SIGTERM. Codes 3 to 9 are unused by TLC, the shell and sysexits.

**The scheme.**

| Code | Meaning | Examples |
| --- | --- | --- |
| 0 | Success. | |
| 2 | Usage error. | Unknown option; a missing argument; no command at all; an invalid module name; a version that matches several builds where tlaup does not ask (`tool path`, and `pin` without a terminal); `--workers` together with `-workers` after `--`; `latest`; an address given as a version; a value given to `config set` that does not fit its key; `uninstall --all` without a terminal and without `--yes`. |
| 3 | Not set up. Something about the installation has to be fixed before this can work. | No tools installed; nothing pinned; the pinned build is missing or damaged; Java not found (missing, or a file without the execute bit) or older than the minimum; `javac` not found; the config file is invalid; the first-run question cannot be asked; the pinned build has no REPL. |
| 4 | Not found. Something the command named does not exist. | The spec; the cfg; a version, locally or upstream; a module; a path given to `module add`; a config key. |
| 5 | Failed. The operation was valid and did not succeed. | Network error; GitHub rate limit; a download that does not verify; a `javac` error; a file that cannot be removed or written; the store is locked by another tlaup; the editor exited with an error; an internal error. |
| 130 | Interrupted by Ctrl-C (SIGINT). Set by tlaup, not passed through. | |
| 143 | Stopped by SIGTERM. 129 for SIGHUP. | |
| 141 | The reader of tlaup's output went away (`tlaup tool list \| head -1`, `tlaup --help \| head -1`). Set by tlaup (rule 8; [14 F10](14-config-and-cli.md#f10-no-tracebacks)). | |
| other | The wrapped tool's own code, unchanged. | `tlaup tlc`: 1, 10 to 14, 75 to 77, 150, 151, 255. |

Rules:

1. **tlaup never returns 1 itself.** So 1 from a run command comes from the wrapped process, not from tlaup. For `tlaup tlc` that is usually TLC rejecting the arguments after `--` (research 15), but not only: the JVM itself returns 1 for an option it does not accept (`--java-opt`) and for a main class it cannot find (research 12, the REPL on v1.7.4), and TLC returned 1 for the same-second metadir collision and for a run whose folder was deleted under it (research 17). The documentation says "1 comes from Java or the tool", not "1 is a usage error".
2. **The wrapped tool's code passes through unchanged** (roadmap, "Keep"), with two exceptions.
   - A run that tlaup stopped because of a signal returns the signal's code from the table, whatever the JVM returned. A Ctrl-C that tlaup leaves to the child (the REPL) is not recorded: a REPL that is quit normally afterwards exits with its own code, and a later SIGTERM is the first signal ([20 G3](20-groundwork.md#g3-java-launcher)).
   - `tlaup sany` returns **150** when SANY reported an error, although SANY itself returns 0 for semantic errors and 255 for parse errors (research 12). 150 is the number `tlaup tlc` returns for the same spec, so "150 means the spec does not parse" holds for both commands. When SANY reports no error, its own code passes through.
3. **A child killed by a signal tlaup did not send** (for example the kernel's out-of-memory killer) gives 128 plus the signal number, the shell's convention.
4. **`pcal` and `repl` pass the tool's code through** with no exception. The PlusCal translator's 255 after a successful `-writeAST` (research 12) passes through too and is documented.
5. **Checks happen in a fixed order** (preflight, [11 R11](11-runner.md#r11-preflight); decision D45): first what needs only the command line and the environment (options that conflict, the value of `--workers`, the quoting of Java options, `sany -- -d`), then the spec, then a cfg that was named, then the tool build, then Java. What the user typed is checked before the state of the machine, so two conflicting options report 2 and a mistyped spec name reports 4 at once, before any first-run question or download, also on a machine with nothing installed. This departs from the roadmap's wording, which lists the build first; it is also the order milestone 3 needs, where the build is chosen by a project file found from the spec ([40](40-later-milestones.md#milestone-3-reproducibility)).
6. An internal error (a bug) is 5 with the line `error: internal error: ...` and a pointer to `--debug`.
7. **Two kinds of usage error, one code.** A usage error tlaup raises itself (`UsageError` and its subclasses, [20 G2](20-groundwork.md#g2-domain-errors)) is one `error:` line. A usage error Typer raises while parsing the command line (unknown option, missing argument, unknown command) keeps Typer's own form: a usage line, then the message. Both exit 2 and write nothing to stdout. Tried on the locked Typer 0.29.1 ([14 F10](14-config-and-cli.md#f10-no-tracebacks)). **One exception: no command.** `tlaup` alone, and a group alone (`tlaup tool`), print the help of that level on stdout and exit 2. That is what Typer does with `no_args_is_help` (tried on 0.29.1: help on stdout, nothing on stderr, exit 2), and it is kept: the help is what the user needs, and the code still says that the command line was incomplete, as `uv` does. A root option with no command (`tlaup --debug`) is Typer's ordinary "Missing command" error: stderr only, exit 2.
8. **A closed output pipe is 141, whoever was printing, on every system** (top-up: on Windows too, decision D57). Three things make that true, each tried on the locked Typer 0.29.1 and Rich 13.9.4, and later on every Typer from 0.22.0 to 0.29.2 and every Rich from 13.8.0 to 15.0.0, on Linux and macOS ([research 23](../research/23-typer-versions.md), [research 30](../research/30-library-behaviours.md); [14 F10](14-config-and-cli.md#f10-no-tracebacks) has the code). On Windows a write to a pipe whose reader has gone raises `OSError` with `EINVAL` instead of `BrokenPipeError`; tlaup treats that error, raised while a standard stream is a pipe, as a closed pipe there and exits 141 (F10). A raw TLC run whose stdout's reader goes is stopped too, and exits 141 (decision D58, [11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are)); not on Windows, where tlaup cannot see it. tlaup's own consoles hand the pipe error to the root handler instead of letting Rich exit with 1. Help and Typer's usage errors are printed by Typer through a console tlaup does not own, where Rich points stdout at the null device and exits 1; `main()` recognises a 1 that comes with a closed pipe and exits 141. And `main()` flushes both streams itself, so the interpreter's flush at exit cannot change the code. Tried as real processes: `--help | head -1`, a subcommand's `--help | head -1`, no arguments `| head -1`, a command printing through tlaup's console `| head -1`, a usage error with `2>&1 | head -1`, and a usage error with stdout already on the null device and stderr a closed pipe, all gave 141; `--help | cat` gave 0; a usage error with nothing closed gave 2. An error that tlaup reports while stderr is the closed pipe is 141 as well: the reporting is guarded, since the third check of this design found it exiting 1 (tried after the fix: a domain error and an internal error with stderr's reader gone, with stdout open, on the same pipe, and on the null device, all 141). So rule 1 has no exception for a closed pipe. Two neighbours of this rule, both tried: output that cannot be written for another reason (a full disk under `> out.txt`) is code 5, with `error: cannot write output: ...` on stderr when the failure is seen inside a command, and it never replaces a code other than 0 found at the last flush; and after a signal (129, 130, 143) tlaup does not wait to flush stdout to a reader that is not reading. `tlaup tlc --raw Spec | head` is covered as said above: tlaup prints nothing there and the JVM writes into the pipe itself, and the JVM does not stop when its reader leaves (research 31), so tlaup watches the pipe and stops TLC (D58). The wrapped tool's own code is never changed by this rule: a tool that exits 1 while the reader has gone still gives 1.

**A cfg file is checked only when it was named.** `--cfg FILE` that does not exist is code 4 before TLC starts. With no `--cfg`, tlaup does not look for `Spec.cfg`: a missing default cfg is TLC's to report, and its code depends on the build (255 on v1.7.4, 151 on rolling; research 15). tlaup does not check the default itself because a build of the 1.8.0 line can read a cfg embedded in the spec file, and that path was not run by any research (research 16 lists it as not tested); a check here could refuse a spec TLC would accept. A cfg that exists and is wrong is TLC's to report too.

**The meaning of a code** is data in the parser package: `tlaup_parse.describe_exit_status(code)` returns an `ExitStatus(code, word, meaning, known)` for each TLC code ([10 P2](10-parser.md#p2-the-tlaup_parse-package)), from the table below. The words follow one rule (decision D63): a **failure** is TLC having checked the spec and found something wrong; an **error** is TLC not having been able to check it. For 0 and 10 to 13 the word is the outcome word of the tlaplus/Examples manifest (research 10); the rest are this design's, and 152 and 153 carry upstream's names (`ERROR_STATESPACE_TOO_LARGE`, `ERROR_SYSTEM`; research 15). These words become the JSON of milestone 4, so they are kept stable like the codes.

| Code | Word | Meaning | Known |
| --- | --- | --- | --- |
| 0 | success | TLC checked the spec and found nothing wrong. | yes |
| 1 | usage error | TLC rejected its command line, or the JVM could not start it for an option it does not accept or a main class it cannot find (rule 1). | yes |
| 10 | assumption failure | An assumption of the spec is false; on rolling also a postcondition. | yes |
| 11 | deadlock failure | A reachable state has no successor. | yes |
| 12 | safety failure | An invariant was violated. | yes |
| 13 | liveness failure | A temporal property or an action property was violated. | yes |
| 14 | assertion failure | An `Assert` in the spec failed. | yes |
| 75 | evaluation failure | Evaluating the spec failed, for example while computing the initial states, or Java ran out of memory. | yes |
| 76 | evaluation failure | Evaluating an invariant failed. | yes |
| 77 | evaluation failure | Evaluating a liveness property failed. | yes |
| 150 | parse error | The spec does not parse, or fails SANY's semantic checks. | yes |
| 151 | configuration error | The cfg file is wrong, or on rolling missing. | yes |
| 152 | state space too large | Upstream's name for a code TLC declares; no supported build returns it. | yes |
| 153 | system error | Upstream's name for a code TLC declares; no supported build returns it. | yes |
| 255 | error | TLC stopped on an error it does not classify, for example a missing cfg on v1.7.4. | yes |
| any other | error | TLC returned a code it does not document. | no |

Each meaning is one sentence; the terminal reporter shows it with no full stop and with a lower-case first letter, unless its first word is an acronym (`TLC`, `JVM`), which stays as it is: `TLC returned a code it does not document`. The last row's word is `error`, not the first design's `failure`: for a code TLC does not document nobody can say that something was checked and found wrong (settled with the maintainer on 2026-11-24). The code alone cannot tell a false assumption from a false postcondition, which rolling also reports as 10 (research 15); when the first error's kind is `postcondition`, the terminal reporter shows the meaning of 10 as "a postcondition was false" ([22 O3](22-reporters.md#o3-terminal-reporter)). The terminal reporter prints the meaning beside the verdict in its result line (22 O3); the JSON of milestone 4 carries the word. Printing and JSON are designed in [22](22-reporters.md) and sketched in [40](40-later-milestones.md); the table itself is built in milestone 1b. (Stage 4 review, 2026-11-24: the full table of words and meanings and its unit test were missing, question Q4, decision D63; the test is P2's, and the postcondition case and where the meaning is printed now follow 22 O3; an initial acronym keeps its capitals, finding G5.)

**Rejected.** Three codes (2, 3, 4): a script could not tell "you named something that does not exist" from "try again later". Using 1 for failures: clashes with TLC's 1. Codes from sysexits (64 to 78): TLC uses 75 to 77. A separate code for internal errors: one more number to keep stable for something a script cannot act on.

**Tests.** `errors.feature` has one scenario per example of rows 2 to 5, run in-process ([01 T5](01-testing.md#t5-feature-files-and-steps)): each asserts the code and an empty stdout; for an error tlaup raises, exactly one `error:` line on stderr; for an error Typer raises (unknown option, missing argument, unknown command), that stderr names the problem, with no assertion on Typer's layout. The 141 row is five scenarios run as real processes. One is a parsed run whose fake `java` prints far more than a pipe holds, piped into a reader that exits after one line ([11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are)). The other four give the process a pipe whose reader has already gone, so that the first write fails whatever the size of the output and the timing of the reader: `tlaup tool list` with two builds installed, which prints through tlaup's own console; `tlaup --help`; an unknown option with both streams on the closed pipe; and an unknown option with stdout on the null device and stderr on the closed pipe. Each asserts 141; the three whose stderr can still be read also assert that it has no `Traceback`. Three more cases come from the third check. One is a real-process scenario: a command that raises a domain error (`tlaup tool pin nosuch`) with both streams on the closed pipe gives 141. Two are plain pytest that start a child process themselves, since the step vocabulary has nothing for them ([01 T5](01-testing.md#t5-feature-files-and-steps)): `tlaup tool list` with stdout opened on `/dev/full` (Linux only, skipped elsewhere) gives 5 and `cannot write output` on stderr; and a child process that runs `main()`'s body on a small app whose command prints without end into a pipe nobody reads, then gets SIGINT, exits 130 within a few seconds ([14 F10](14-config-and-cli.md#f10-no-tracebacks)). The no-command case is two in-process scenarios (`tlaup`, `tlaup tool`): exit 2, the help on stdout, nothing on stderr. The signal rows are the real-process scenarios of [11 R2](11-runner.md#r2-signals). A unit test walks every subclass of `TlaupError` and asserts its code is one of 2, 3, 4, 5. The unit test of `describe_exit_status` over every row of the meaning table, and over codes it does not hold, is [10 P2](10-parser.md#p2-the-tlaup_parse-package)'s. `tlc_run.feature` replays each golden case and asserts its code passes through. One scenario has no build installed and a spec that does not exist, and asserts 4.

**Changelog.** Breaking: "Exit codes changed. tlaup's own errors now return 2 (usage), 3 (not set up), 4 (not found) or 5 (failed) instead of 1; Ctrl-C returns 130 (was 143 or 130); a closed output pipe returns 141 (was 1); `tlaup tool uninstall` returns 5 when a build could not be removed (was 0)."

**Risks.** The codes seen by in-process tests rest on how Typer handles exceptions, and the 141 also on how Rich handles a closed pipe (it points stdout at the null device and raises `SystemExit(1)`, which rule 8 recognises). Both were tried on one version each, on Linux; questions 23 (Typer) and 30 (Rich) cover the rest of the allowed ranges, and macOS is first seen in CI ([14 F10](14-config-and-cli.md#f10-no-tracebacks)). The four real-process scenarios above are what fails if either library changes. A future TLC may start using 3 to 9; research 15 found no sign of it and the upstream table has a note that error classes are not yet allocated. The table is in one place ([20 G2](20-groundwork.md#g2-domain-errors)), so a renumbering is one change and one changelog line.

## X2 stdout and stderr

Decision D30. Serves the reporters of milestone 1b ([22](22-reporters.md)) and the milestone 4 item "Results on stdout, diagnostics and progress on stderr".

**Problem.** Today the verdict goes to stderr and the trace to stdout; `--raw` merges TLC's stderr into stdout; a warning in `tools list` goes to stdout; 21 error prints bypass the UI helper.

**The rule.**

> **stdout carries the result. stderr carries everything about getting there.**
>
> The test: if it would be in the JSON result of milestone 4, it goes to stdout.

| stdout | stderr |
| --- | --- |
| The verdict line and the meaning of the exit code. | "Starting TLC ..." and the header naming the build, Java and the spec. |
| Each TLC error with its text; each trace. | Progress lines, or the live layout when both streams are terminals. |
| TLC's warnings. | tlaup's own `error:`, `warning:` and `hint:` lines. |
| SANY, parse and PlusCal diagnostics, as `path:line:col: severity: message`. | Download progress. |
| The spec's own output (`Print`, `PrintT`) and any output tlaup did not recognise (decision D9). | Notices about what tlaup did ("Pinned v1.7.4", "Checkpoint kept at ..."). |
| Final statistics and coverage. | Prompts. The answer is read from stdin. |
| For other commands, what was asked for: the table of `tool list`, the path of `tool path`, the text of `config show`, the command of `--show-command`, the version of `--version`. | Lines TLC wrote to its own stderr, unchanged. |

Details that follow from the rule:

- **`--raw`** starts the tool with tlaup's own stdout and stderr; nothing is read, merged or decoded.
- **Two pipes in parsed mode.** For TLC the launcher reads the tool's stdout and stderr separately ([20 G3](20-groundwork.md#g3-java-launcher)). For `sany` and `pcal` it reads both through one pipe, which is how the research captured them, which keeps the order of v1.7.4's one stderr line, `File does not exist: ...`, among the rest ([21 S1](21-other-tools.md#s1-sany); research 22 recorded the streams apart and found that line the only one). For TLC: stdout lines go to the parser; stderr lines are never parsed, are written to tlaup's stderr as they arrive, and the last 50 are kept in the run outcome so the final error can quote them. Research 22 captured the two streams apart for every case (top-up): in `-tool` mode TLC writes nothing to stderr except v1.7.4's `File does not exist` line for a missing module.
- **Where the live layout is drawn** (decision D40). The live display is the full-screen layout of [22 O4](22-reporters.md#o4-live-display). It is a live status, so it is drawn on stderr, and only when **both** stdout and stderr are terminals and `TERM` is not `dumb`. When the layout closes at the end of the run, the final result is printed on stdout as plain output, so it stays in the scrollback and is the same text a redirected run produces. In every other case output is plain: the result on stdout as it arrives, and one progress line on stderr per TLC progress message. So `tlaup tlc Spec > out.txt` and `tlaup tlc Spec | less` show plain progress lines on the terminal and put the result in the file or the pipe, and `--raw` draws nothing. This is the roadmap's wording ("fall back to plain streamed output when stdout is not a terminal or `--raw` is given") with one addition: stderr must be a terminal too, since that is where the layout is drawn.
- **Colour** is decided per stream: stdout is coloured only when stdout is a terminal, stderr likewise, and `NO_COLOR` switches both off. The `--color` option of milestone 4 overrides both.
- **Nothing is printed before the checks pass** ([11 R11](11-runner.md#r11-preflight)): a failed preflight gives one `error:` line (and at most one `hint:` line) on stderr and an empty stdout.
- **One place prints.** `tlaup.ui` owns the two consoles; commands and reporters print through it; domain code does not print ([14 F6](14-config-and-cli.md#f6-messages)).

**Rejected.** Diagnostics on stderr like a compiler: a spec that fails to parse would leave stdout nearly empty, and `tlaup sany` would have no result at all on stdout. Merging TLC's stderr into its stdout (today): keeps the order of lines but puts JVM warnings into the parser and breaks `--raw 2>/dev/null`. A one-line footer on stderr that stays up while stdout is redirected (the first version of this design): decision D40 keeps the roadmap's full-screen layout, and progress is not lost with stdout redirected, because the plain progress lines still go to stderr.

**Tests.** Every feature scenario can assert on the two streams separately. `tlc_run.feature` (in-process): a violation has the verdict, error text and trace on stdout and nothing but the header and progress on stderr. `tlc_raw.feature` (real process, because the child inherits tlaup's real streams and an in-process runner cannot see them; [01 T5](01-testing.md#t5-feature-files-and-steps)): the fake `java` writes distinct text to each stream and each arrives on the matching stream unchanged, byte for byte. `errors.feature` (in-process): stdout is empty for every tlaup error. Where the layout is drawn is tested with a pty, as a real process ([22 O4](22-reporters.md#o4-live-display)): both streams on the pty draws it; stdout redirected to a file gives plain progress lines on the pty and the result in the file.

**Changelog.** Breaking: "Output streams are now consistent: results go to stdout; progress, the live display and tlaup's own messages go to stderr. The verdict line moved from stderr to stdout. `--raw` no longer merges TLC's stderr into stdout."

**Risks.** A stack trace TLC writes to stderr can appear before or after the stdout text it belongs with, because the two pipes are read independently. Accepted: it is the same when Java is run by hand with the streams separated.

## X3 Version syntax

Decision D31. Serves "Typing versions" (milestone 1b, [23 C2](23-command-layout.md#c2-typing-versions)) and "Non-interactive version selection" (milestone 4). Relies on research [3](../research/03-jar-identity-and-upstream-cli.md) and [14](../research/14-jar-manifest.md).

**Problem.** Only the exact tag string is accepted. `1.8.0` without the `v` fails with no hint. One of two installed builds of a tag cannot be named: the tool prints `v1.8.0-4ba7d88` and does not accept it back.

**Facts.** A build's identity is its build time, which rolling builds print as a CalVer (`2026.11.15.002146`); its commit is an attribute, and one commit can have two builds (research 3). v1.7.4 has a commit but no build time in its manifest (research 14). Upstream's CalVer tags are git tags with nothing to download (research 5).

**The syntax.**

```
spec    = name [ "@" build ]
        | calver
name    = "stable" | "rolling" | tag
tag     = 1*( letter | digit | "." | "_" | "-" | "/" | "+" )      ; never starts with "-"; no "@"; no white space
build   = commit | calver | "sha256:" digest
commit  = 7 to 40 hexadecimal digits
calver  = 4 digits "." 2 digits "." 2 digits "." 6 digits
digest  = 8 to 64 hexadecimal digits
```

| Typed | Means |
| --- | --- |
| `v1.7.4`, `1.7.4` | The tag `v1.7.4`. A name is tried as typed first, then with `v` in front. |
| `stable` | The release with the highest version number among those that are not prereleases, not drafts and have a `tla2tools.jar` (research 8). Among installed builds: the highest-numbered build recorded as not a prerelease. |
| `rolling` | The release tagged `rolling` (X4). |
| `rolling@bc1b506`, `v1.8.0@bc1b506` | The build of that name built from that commit. A prefix of 7 or more digits is enough. |
| `rolling@2026.11.15.002146` | The build of that name with that build time; needed only when one commit has two builds. |
| `rolling@sha256:7e53aa636dac` | The installed build of that name whose jar's SHA-256 starts with those digits. Needed, and printed, only when neither the commit nor the build time tells two installed builds of one name apart (the printing table below). It names installed builds only: nothing can be fetched by it. |
| `2026.11.15.002146` | The build with that build time, whatever name it was installed under. In the first wave it must already be installed; milestone 3 can build it from source. |
| `latest` | Refused (code 2): "`latest` is not a version here. Use `stable` (v1.7.4) or `rolling` (the newest build)." The tag after `stable` is the stable release of the cached release list ([12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache)), whatever its age, when a cache file exists; otherwise the highest-numbered installed build that is not a prerelease (X4); with neither, the brackets after `stable` are left out. No request is made to fill it in: the refusal is a usage error and costs no network. (Stage 4 review, 2026-11-24: "filled in when known" said not from where, finding B16.) |
| `https://...`, or anything else outside the grammar | Refused (code 2). No tag contains a colon, so an address is never looked up as a name; for one, the hint says that installing from an address is not supported ([12 V6](12-tools-and-downloads.md#v6-remove-installs-from-a-url)). |

A hexadecimal string never contains a dot, a CalVer always does, and the third form starts with `sha256:`, so the part after `@` is unambiguous. A commit prefix that fits two installed builds of the name with different commits matches both, like any other spec that matches several builds (below).

**A bare CalVer is always a build time, never a tag.** This is intended. `2026.11.15.002146` alone is never looked up as a release tag, so a release whose tag has that shape cannot be installed by its tag in the first wave. Upstream has such tags, and they carry nothing to download (research 5). If upstream ever attaches a jar to one, that jar is the build with that build time, so the bare form would name the same build either way; fetching it is milestone 3's "older rolling builds" item. Before `@` the shape is an ordinary tag (`2026.11.15.002146@bc1b506` parses as a name and a commit), which matters only for the round-trip rule below. Likewise a release tagged literally `stable` or `latest` could not be named; none exists (research 8). A tag is whatever upstream named a release; every upstream tag today is letters, digits and dots (research 8), and the grammar also lets through the hyphen, slash and plus that git allows in a tag, so that a future tag does not need a tlaup release. The store never uses a tag as a folder name ([12 V1](12-tools-and-downloads.md#v1-version-store)), and the client percent-encodes it in an address ([12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache)).

Decision D31's row in the roadmap names a tag with or without the `v`, `stable`, `rolling`, `tag@commit`, `tag@CalVer` for a commit with two builds, and the refusal of `latest`. Two forms are this design's additions to it: the bare CalVer, because a build time alone identifies a build (research 3), and `name@sha256:...`, so that every installed build has a form that can be typed even when its jar carries neither a commit nor a build time. The README lists both.

**Where it is accepted:** everywhere a version is: `tool install`, `upgrade`, `pin`, `uninstall`, `path`. `install rolling@bc1b506` succeeds if that build is already installed or is what upstream publishes now; otherwise it fails with code 4 and says that older rolling builds cannot be downloaded.

**What is printed:** a build is shown by `format_build`, in `tool list`, `tool current`, the pin message and every error, with the CalVer beside it where known:

The rows are tried in this order, and "another build" always means another installed build of the same name:

| The build | Printed as |
| --- | --- |
| Has a commit that no other build of its name has | `name@commit`, with the shortest prefix of its commit, 7 digits or more, that no other build of that name shares: `rolling@bc1b506`, or `rolling@bc1b506a` when another rolling build's commit starts with the same seven. |
| Otherwise, has a build time that no other build of its name has | `name@calver`, for example `rolling@2026.11.15.002146`. This is the row for two builds of one commit, and for a build with no commit that has a build time. |
| Otherwise, is the only build of its name | The bare `name`. It then has neither a commit nor a build time in its manifest. |
| Otherwise | `name@sha256:` and the first 12 digits of the jar's SHA-256, more when another build of that name shares them: `v1.6.0@sha256:7e53aa636dac`. This is the row for two builds of one name and commit with no build time, and for a build with no commit beside any other build of its name. |

The store never holds two builds with the same name and the same SHA-256 ([12 V1](12-tools-and-downloads.md#v1-version-store)), so the last row always tells a build apart. **Every printed form is accepted as input and finds exactly the build it was printed for**, as long as the store has not changed in between. The form depends on what else is installed: after another rolling build is installed, `rolling@bc1b506` can match two builds and is then answered like any ambiguous spec.

**A published jar always has a commit** (top-up, [research 26](../research/26-old-jar-commits.md)). Every release with a `tla2tools.jar` asset, back to v1.5.6, carries `X-Git-Revision` in its manifest; older releases have no jar at all. So the last two rows are never reached by a release in upstream's list, only by a jar tlaup builds or one a future upstream publishes without the entry; they stay, with their unit tests, for that. What is common is the other side: every release before v1.8.0 has a commit and no build time, so each prints as `name@commit`. Only v1.8.0 and rolling builds have a build time.

**When a spec matches several installed builds:**

| Command | On a terminal | Not on a terminal |
| --- | --- | --- |
| `pin` | Lists them and asks which (it does today; no new prompt, decision D23). | Code 2, candidates listed. |
| `uninstall` | Lists them and asks which, or all (decision D43). `--yes` answers "all". | Removes all of them: naming the name is the confirmation (D23, D43; [12 V3](12-tools-and-downloads.md#v3-uninstall)). |
| `path` | Code 2, candidates listed. It never asks: its output is meant for scripts. | The same. |
| `upgrade` | Takes a name only and compares with the newest build of that name ([12 V4](12-tools-and-downloads.md#v4-upgrade-and-pin)). | The same. |

Candidates are listed in their printed form, so the next attempt can be exact. A bare CalVer can match builds of two names: `rolling` and `v1.8.0` hold the same jar today (X4), so both installed have the same build time. That is a spec matching several builds, and this table applies to it as to any other; the candidates are then `rolling@bc1b506` and `v1.8.0@bc1b506`.

**Not accepted: folder names.** The roadmap's milestone 4 item says "accept `tag@sha` and the folder name". The version store ([12 V1](12-tools-and-downloads.md#v1-version-store)) makes folder names internal, and they are no longer printed, so there is nothing to copy. This departs from the roadmap and is listed in the README.

**Interfaces.**

```python
@dataclass(frozen=True)
class VersionSpec:
    name: str | None      # "stable", "rolling" or a tag as typed; None when only a CalVer was given
    commit: str | None    # lower-case hex prefix
    calver: str | None
    sha256: str | None    # lower-case hex prefix, from "@sha256:..."

def parse_version_spec(text: str) -> VersionSpec      # raises UsageError
def format_build(build: Build, others: Sequence[Build] = ()) -> str
    # the printing table; `others` is every installed build, and only those with the build's name are looked at
```

Lookup against installed builds and against upstream is in [12 V2](12-tools-and-downloads.md#v2-version-order-and-lookup).

**Rejected.** `tag#sha` (a comment in shells), `tag+sha` (reads as a local version), `tag-sha` (the folder name; ambiguous for a tag that contains a hyphen). `latest` as `stable` or as `rolling`: it is ambiguous here, since GitHub's "latest" is the 2024 stable release and most TLA+ users mean the newest build. Naming builds by commit alone: two builds of one commit exist.

**Tests.** A parametrised unit test over the table above and over malformed input (`@abc`, `v1.7.4@`, `rolling@xyz`, a 6-digit prefix, an empty string, a tag starting with `-`, a tag containing `@` twice). A Hypothesis round trip over generated stores: for every build `b` in a store, `store.find(parse_version_spec(format_build(b, store.builds())))` is exactly `[b]`, with no exception. The generator makes what a store can hold: names that fit the `tag` grammar and are not `stable`, `latest` or of CalVer shape (none of the three can be installed as a name); no two builds with the same name and SHA-256; commits, build times and SHA-256 values drawn from small pools, so that shared commits, shared seven-digit prefixes, shared build times and shared twelve-digit SHA-256 prefixes all occur; builds with no commit, with no build time, and with neither. The printing and lookup rules were run as a small model over 200,000 generated stores of that kind while this section was revised, with no build that failed to come back alone; the model is not the code, and the property test is what holds the code to it. A unit test of `format_build` for each row of the printing table, including two commits that share seven digits, a build with no commit beside one with a commit, and two builds of one name and commit with no build time. Malformed `@sha256:` forms (seven digits, a non-hexadecimal digit, `sha256:` with nothing after it) join the malformed input above. Feature scenarios: `tool pin 1.7.4`; two builds of `rolling`, `tool path rolling` exits 2 and lists both; `tool install latest` exits 2 and sends no request to GitHub, naming the stable tag of the cached release list when one exists, `v1.7.4` when only that is installed and nothing is cached, and no tag with neither.

**Changelog.** Added: "Versions can be typed without the `v`, as `stable` or `rolling`, and as `tag@commit` to name one build." Breaking: "With several builds of one tag installed, `tlaup tool path TAG` now fails and lists them (it printed the first)."

## X4 Rolling

Decision D32. Serves the first-run prompt ([12 V9](12-tools-and-downloads.md#v9-first-run-prompt)), "Typing versions", and milestone 3's "Adopt upstream's `rolling` release". Relies on research [3](../research/03-jar-identity-and-upstream-cli.md) and [8](../research/08-github-api-ordering.md).

**Facts (research 3).** Upstream moves both the `v1.8.0` tag and the `rolling` tag on every build of its main branch, and both releases hold the same jar. `rolling` is the name upstream created to survive version bumps; `v1.8.0` is expected to stop moving at the next bump. Both are marked as prereleases. The `rolling` release's `published_at` is the day it was first created and says nothing about the jar (research 8).

**What it means.** `rolling` is the upstream release whose tag is `rolling`. Nothing else is called rolling: `v1.8.0` is an ordinary tag that happens to move today, and tlaup has no table of which tags move. Instead, **no tag is assumed to stay put**: every build is identified by what its jar says (commit, build time) and by its SHA-256, and `tool upgrade` works for any tag by comparing the installed jar with the published one. (Stage 4 review, 2026-11-24: the command's name made singular, as decision D47 has it; clerical.)

**How it sorts.**

1. `rolling` sorts **above every numbered version**.
2. Numbered tags sort by version number, highest first. The number is read as integers with an optional suffix (`v1.5.0rc1` sorts below `v1.5.0`); a tag that is not a number and not `rolling` sorts last, by name.
3. Builds of one name sort by build time, newest first. A build with no build time in its manifest (v1.7.4 and older) sorts after those that have one, then by install time.
4. Nothing sorts by GitHub's order, by `published_at`, or by a folder's modification time.

Where the order is used: the rows of `tool list`; the candidate list when a spec matches several builds; "the newest installed build of this tag" in `upgrade`. It is **not** used to choose a default: `stable` is rule 2 restricted to non-prereleases, and nothing ever picks `rolling` unless the user typed it or chose it at the first-run prompt.

**`stable` among installed builds can lag behind upstream.** A build's `prerelease` flag is recorded when it is installed and not looked up again. If upstream later clears the flag on a release (as it will for v1.8.0 one day), an installed build of it still counts as a prerelease locally, so `tool pin stable` with no network keeps naming the older release until that build is installed again or upgraded; `tool upgrade` and `tool install NAME` refresh the flag ([12 V12](12-tools-and-downloads.md#v12-install)). `tool list` shows upstream's current flag for the release row. Accepted: the local answer is never a build the user did not install, and the alternative is a network request inside `pin`.

**Rejected.** Ordering every build purely by build time: a later v1.7.5 maintenance release would sort above an older rolling build although rolling carries newer code. Rolling below numbered versions (today, by accident of the sort key): lists the newest code last. Treating `v1.8.0` as an alias of `rolling`: true today, false after the next bump, and the tool must not hard-code it (research 8).

**Left to milestone 3.** `rolling` and `v1.8.0` holding the same bytes should appear as one build with two names and be downloaded once. The first wave records each build's SHA-256, so the second wave can do this without reinstalling ([40](40-later-milestones.md)). Until then installing both stores the jar twice, as two builds: the store treats a build as "already there" only when both the name and the SHA-256 match ([12 V12](12-tools-and-downloads.md#v12-install)).

**Interfaces.** `sort_key(build) -> tuple` and `stable_of(releases) -> Release | None` in `tlaup.versioning.order`; see [12 V2](12-tools-and-downloads.md#v2-version-order-and-lookup).

**Tests.** A unit test with the recorded release list shuffled 20 ways gives the same order and the same `stable`. A list with only prereleases has no `stable`. `tool_list.feature` checks the row order against an expected file.

**Changelog.** Changed: "`rolling` is listed first in `tlaup tool list`, then versions by number." Fixed: "`tlaup tool install` could offer a prerelease as the stable version when no stable release was in the first page of results."
