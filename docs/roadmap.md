# Roadmap

Drafted 2026-11-09 from the [project analysis](analysis/00-summary.md), against release 0.8.1. Revised 2026-11-14 by the completeness pass (pipeline stage 1, see "How the work is done"): the decisions from the maintainer's walkthrough of the analysis and the report findings that were missing are now written into this file. The pass was reviewed by three fresh agents and signed off by the maintainer on 2026-11-14.

This file is the single source of truth. The [walkthrough notes](analysis/07-walkthrough-notes.md) are history and nothing in them is needed to read this file; "(note N)" after an item only records which note a decision came from, and "(raised list)" marks a point that came up in the walkthrough without being settled there and was settled by the completeness pass. Items link to the report section that holds the evidence. The reports describe release 0.8.1, so check a line number against the source before relying on it.

The project moved from `tlaplus-cli` to this repository and was renamed to `tlaup` in 0.8.2 (2026-11-14). Items finished since then are ticked with the date. Apart from ticked items, nothing here has been implemented or tested. Effort sizes are rough: carried over from the reviews where they gave one, estimated by the completeness pass otherwise (S = hours, M = one to three days, L = a week or more).

## Purpose

`tlaup` brings the TLA+ tools together and helps them work together (note 7):

- version management for `tla2tools.jar`, including the rolling builds upstream republishes under one tag;
- managing your own modules with Java operator overrides (add, list, remove), which no other tool does ([merit 5](analysis/01-merit-and-landscape.md));
- running TLC and the other tools in the jar, with readable and machine-readable results.

A reproducible toolchain (the same jar and the same modules on every machine) is an important promise, and the one the tool does not keep yet, but it is not the only purpose.

Today the tool delivers a labelled local cache and a TLC runner that mis-parses real output. The order of work is therefore:

1. Stop being wrong (runner correctness, data safety).
2. Stop shipping blind (tests and CI that would have caught the above).
3. Deliver the promise (project file, digests, builds that can be obtained again).
4. Then restructure and widen.

The VS Code extension is an inspiration for readable TLC output, not a parity target: the tool can go beyond it, and missing some of its features is fine (note 10).

## How the work is done

### One release

Everything on this roadmap ships as one release, 0.9.0, not as one release per milestone (decision D6). The one exception is the GitHub Action in milestone 4, which is built after the release it needs is published. The milestones below are groups of work, not versions, and they are not strictly ordered: the parts of milestone 2 that do not depend on milestone 1 land early, even though nothing is published (milestone 2 says which). Milestone 3 needs a design note before it starts and is the part most likely to hold the release up.

### Agent pipeline

The work goes through five stages (note 4).

1. **Completeness pass.** One agent reads the six reports, this roadmap and the walkthrough notes, and makes sure everything worth acting on is on the roadmap. Obvious decisions go straight in; uncertain ones are settled with the maintainer; factual questions go on the investigation list instead of being guessed. Done, reviewed and signed off 2026-11-14.
2. **Investigation.** Small spikes answer the factual questions under "Investigation list" before anything is designed on assumptions. No product code is written; captured data such as TLC output may go under `tests/fixtures`, where the testing design later confirms or moves it, and the expected parsed results are written in milestone 1. Each question runs in its own agent, so contexts stay separate, and each agent gives `tlaup` its own config and cache folders (`XDG_CONFIG_HOME`, `XDG_CACHE_HOME`) so parallel runs do not share a cache. Set the two variables on the `tlaup` commands only, not for the agent's whole shell: `gh` reads `XDG_CONFIG_HOME` too and is logged out when it is moved (checked 2026-11-14), and `git` and `uv` read these variables as well. Each result goes in its own file, `docs/research/NN-short-name.md`, where NN is the question's number in the investigation list, with the question, its source, a short answer, a confidence (verified, partly verified, or not answered), the evidence (links, commands run, captured output, versions and dates checked), the implications for the roadmap and open follow-ups; it says plainly when a question could not be answered. `docs/research/README.md` indexes the results, and each roadmap item a question serves gets a one-line answer and a link to its result file. Contacting upstream (an issue, a discussion post) is the maintainer's call; a spike only searches what already exists.
3. **Design, in waves.** An agent designs or confirms a solution for each roadmap item, in light of the decisions and the investigation results. The testing approach (decision D16) is designed first, since every work package writes tests. The first wave designs milestones 1, 1b and 2 in full and only sketches milestones 3 to 5. Those are designed in a second wave after the first wave is built, because building it will change what the project file and structure work needs. Milestone 3 also needs its own design note. Four things that sit in later milestones are decided in the first wave, because milestones 1, 1b and 2 build on them: the exit-code scheme; which output goes to stdout and which to stderr; the `tag@sha` syntax for naming one build; and which upstream tag "rolling" means and how it sorts. Where the design documents live is chosen at the start of this stage.
4. **Work packages.** An agent cuts the designed work into packages without implementing. Each package states its goal, the files it touches, its dependencies on other packages, the tests that must pass, and all the context a worker needs, so a worker never has to read the analysis.
5. **Workers.** Separate agents build one package each, in its own worktree, ending in a pull request. A worker that finds the design wrong or incomplete stops and reports instead of improvising; the fix goes into the design and the package before work continues.

Review gates: after stages 1, 3 and 4 a fresh agent that did not produce the output reviews it against its inputs (for stage 1, the reports against the roadmap; for stage 3, the decisions against the design), and the maintainer signs off before the next stage starts. Each stage 5 pull request needs green CI and a review by a separate agent before it merges. The green CI part will be enforced by a ruleset on `main` once it is set (decision D21, milestone 2).

Later stages read this roadmap and the design documents, not the walkthrough notes.

Suggested models: the most capable model at high effort for stages 1, 3 and 4, since their output steers everything after them and their volume is small. Stage 2 questions are narrow and factual, and the recorded evidence lets stage 3 check a doubtful answer, so a mid-tier model with several spikes in parallel is enough. Workers use a mid-tier model for clearly specified packages and the most capable model for the hard ones, such as the TLC output parser and the project file. Mechanical lookups inside a stage, such as checking that a line reference still points at the right code, can go to a cheaper subagent.

## Decisions

D1 to D5 were made on 2026-11-10 and revised during the walkthrough. D6 to D18 were made during the walkthrough (2026-11-10 to 2026-11-14). D21 to D24, D26, D27 and the marked parts of D7, D13 and D14 were settled with the maintainer on 2026-11-14, during the completeness pass and its review. D19, D20 and D25 were written in by the completeness pass from the notes and reports; the stage 1 review checked them and the maintainer's sign-off covers them. D28 was settled with the maintainer on 2026-11-15, during the walkthrough of the stage 2 results.

| # | Question | Decision | Consequence |
| --- | --- | --- | --- |
| D1 | Keep the `tla` binary name? | **Package, command and repository are all `tlaup`; `tlaplus-cli` is retired.** Done (note 8). | `tla` collided with a crates.io project, `tla-cli`, an asdf shim and open upstream PR 1371 ([merit 4.1](analysis/01-merit-and-landscape.md)). `tlaup` 0.8.2 is on PyPI with no `tla` alias. `tlaplus-cli` 0.8.3 depends on `tlaup`, prints a one-line notice and forwards to it; its repository is archived. Marking the PyPI project as archived is left to the maintainer. Old versions are not yanked. |
| D2 | Branch model? | **Trunk plus tags.** Done 2026-11-14. | Only `main` exists; CI runs on every push to `main` and on pull requests; releases are tags on green commits. [packaging 6](analysis/05-packaging-ci-release.md) |
| D3 | Rich live display: finish, freeze, or remove? | **Finish it, as one reporter among several** (note 9). The analysis recommended freezing. | The live terminal display is a reporter that reads the parsed result and run events (decision D8). It never parses, so it is not coupled to parser internals. [architecture 1](analysis/02-architecture-and-organization.md) |
| D4 | Default version when none is pinned? | **Ask on first run** between stable and rolling, **then install the choice** (note 27). | One prompt replaces both the version question and the offer to install. A flag and an environment variable answer it so CI and scripts never see a prompt; without a terminal and without an answer it is an error with a hint. |
| D5 | Scope beyond TLC? | **Dedicated `sany`, `pcal` and `repl` commands now, kept thin** (note 15). The analysis recommended passthrough plus a generic exec first. | The commands hold no logic beyond reading their tool's output, and everything launches through the shared Java launcher, so handing over to an official upstream command stays cheap (see Risks). |
| D6 | One release or several? | **One release, 0.9.0, for the whole roadmap** (note 3). | Few users, so a big step from 0.8 is fine. Milestones are work groups, not versions. The CI and test fixes from milestone 2 still land early, without publishing. |
| D7 | Where does the TLC output parser live? | **Its own import package in this repository, shipped inside the `tlaup` wheel** (note 12; packaging settled 2026-11-14). | It imports nothing from `tlaup`. One parser handles several TLC versions by reading the version TLC prints at startup; nothing is fetched per TLC version at run time. Golden files are kept with the parser's tests, filed by TLC version. It is split into its own PyPI project, and later its own repository, when an editor or another tool wants it. |
| D8 | How does TLC output reach the user? | **Through reporters** (notes 9 and 14). | Reporters read the parsed result and run events and never parse; the result carries everything any reporter needs, such as file and line for errors. In this roadmap: the terminal reporter (live on a terminal, plain when piped) and JSON. An AI-facing reporter comes later as a plug-in; file output and others are possible later. |
| D9 | What does the parser do with output it does not recognise? | **Never lose output** (note 13). | Anything unrecognised is shown exactly as TLC printed it. |
| D10 | How is configuration resolved? | **Layers: packaged defaults, then the user file, then the project file, then environment variables, then flags** (note 17). | Config commands keep working when the file is broken. No config file is written until the user changes a setting. |
| D11 | How are community modules provided? | **As pinned downloads of the published release jars**, not compiled from a checkout (note 16). | The tool picks the CommunityModules release built against the user's TLC build by date (published after that TLC build and before the next one) and writes the choice into the project file; after that everyone reads the file. On a TLC upgrade it picks again and updates the file. `modules add` stays for the user's own modules. |
| D12 | How is an older rolling build obtained again? | **Build it from source at its CalVer tag** when it cannot be downloaded (note 21). | The mirror repository and Maven snapshots are dropped: retention on Maven is unclear and the Maven jar is stripped of bundled dependencies, so it is not the same bytes. The Java build tools needed are fetched automatically. Only the official sources and the local cache are used. The logic is removed if upstream starts publishing a jar per tag. |
| D13 | Installs from a URL? | **Dropped for now** (note 22). | Removes the colon timestamps in folder names, the upgrade mis-split, `meta sync` overwriting URL installs and the plain-HTTP path. Nothing handles URL-installed builds left on disk: no released version can put one in the `tlaup` folders (settled 2026-11-14). Importing a jar from a local path, which [ux 6.3](analysis/06-cli-ux-and-docs.md) suggested, is likewise out for now. |
| D14 | Old names, commands, folders and layouts? | **Clean breaks: no aliases, no compatibility shims, no migrations** (notes 8 and 44; storage move settled 2026-11-14). | Config, toolsets, modules and the run cache live in `tlaup` folders since 2026-11-14 with nothing moved over. The storage move in milestone 3 is also a clean break. The changelog and README say what to reinstall. All of it lands in 0.9.0, so users reinstall once. |
| D15 | Windows? | **Not officially supported and no Windows CI, but code is written so it should work there** (note 38). | The README says exactly that. The "OS Independent" classifier becomes Linux and macOS. |
| D16 | Testing approach? | **Redesigned from scratch, as the first design task** (note 5). | See milestone 2. The report's techniques, anti-patterns and coverage policy are inputs, not a fixed plan. |
| D17 | Apalache and TLAPS? | **After this roadmap** (note 18). | The storage layout in milestone 3 leaves room for other distributions, since the on-disk layout is the expensive part to change later. |
| D18 | Other distribution channels? | **Homebrew tap after this roadmap; Docker image dropped; no docs site yet** (notes 19, 50, 51). | See "After this roadmap" and "Deliberately not planned". The GitHub Action covers the main CI case. |
| D19 | Supported TLC builds? | **The latest stable release (v1.7.4 today) and the current rolling build (1.8.0 builds today).** Restates the test targets of the golden-file and CI items as a support policy. | Golden files and the integration job cover both. Output from other versions still appears, because of D9, but is not tested. |
| D20 | Environment variable names? | **The tool's own variables start with `TLAUP_`** (note 28 for Java options; applied to all of them by the completeness pass). | The generic `JAVA_OPTS` is no longer read; its replacement adds to the configured options instead of replacing them. Standard variables keep their names: `JAVA_HOME`, `GITHUB_TOKEN` and `GH_TOKEN`, `NO_COLOR`, `EDITOR` and `VISUAL`. |
| D21 | Release and merge gates? | **Annotated tags, not signed. The `pypi` environment requires the maintainer's approval. A ruleset on `main` requires pull requests with a passing Test check, with a bypass for the maintainer.** Settled 2026-11-14. | A tag pushed by mistake or by an agent cannot publish on its own. The maintainer can still push docs and the release commit directly. Review by a separate agent stays a convention. |
| D22 | Which machine-facing outputs? | **JSON, editor-style diagnostics (`path:line:col: severity: message`) and GitHub Actions annotations.** Settled 2026-11-14. | The diagnostics format is part of plain terminal output for SANY and parse errors. Annotations are produced by the GitHub Action from the JSON result. JUnit output and a streaming NDJSON progress mode wait until someone asks. |
| D23 | Confirm destructive actions? | **No new prompts; safer mechanics instead.** Settled 2026-11-14. | Naming a version to uninstall is the confirmation, as in uv and rustup. `modules add` builds in a temporary folder, swaps only on success, and says when it replaced a module of the same name. `uninstall --all` keeps its prompt. |
| D24 | First-class TLC options? | **`--workers` is the only new first-class option; every other TLC flag goes after `--`.** Settled 2026-11-14. | The existing `--cfg` and `--coverage` stay. `--deadlock`, `--simulate` and `--depth` are not added as `tlaup` options. Fewer options to keep in step with TLC. |
| D25 | Folder locations overridable? | **Yes: one environment variable that moves all of the tool's folders (its "home"), and one each for the config folder, the cache folder and the data folder that milestone 3 adds.** From the raised list; recommended by the architecture and UX reports, and test isolation leans on it. | Tests and CI redirect all state without patching, and runners that do not use XDG folders get one switch. [architecture 3](analysis/02-architecture-and-organization.md), [ux 6.2](analysis/06-cli-ux-and-docs.md) |
| D26 | Installing a newer build of a tag while an older build of that tag is pinned? | **The pin moves to the newer build, and the tool says so.** Settled 2026-11-14. | Today the new build is installed beside the old one and runs keep using the old one with no notice. The pin moves only when the pinned build is an older build of the same tag. [ux 9](analysis/06-cli-ux-and-docs.md) |
| D27 | Version numbers? | **From 0.9.0 on, minor versions carry breaking changes and features, and patch versions carry only fixes.** Settled 2026-11-14. | The project had not followed this consistently: breaking changes and features shipped in patch releases. Goes into the conventions in `AGENTS.md` at sign-off. [packaging 2.4](analysis/05-packaging-ci-release.md) |
| D28 | What should a build from source reproduce? | **The same behaviour on every machine that builds the same tag with the same build tools, not the jar upstream published at the time.** Settled 2026-11-15. | Upstream keeps no jar for old CalVer tags and does not record which JDK built them, so the old jar cannot be matched; even with the same JDK major version the manifest and zip timestamps differ (investigation question 6). The working assumption is that the same source built with exactly the same tools behaves the same. So a build from source records every tool that affects its result, such as the exact JDK and Ant versions, with the build and in its manifest, and two machines can compare them. tlaup keeps no table of which JDK upstream used for each tag. The design note of milestone 3 and the user docs describe the problem (old builds and their JDKs cannot be matched) and this approach, and say that someone who wants the historical jar has to find out what built it and install that themselves. [Result](research/06-build-from-source.md) |

## Keep

Things the reviews found well done. Design and workers should preserve them.

- The parser stack does no I/O, imports nothing outside itself and is line-driven. [architecture, what is good](analysis/02-architecture-and-organization.md)
- No domain package imports `cmd`; commands depend on domain code, never the reverse.
- `find_project_root` and `ClasspathResolver` take their inputs as arguments; the classpath precedence is explicit (command line, then project, then config, then managed modules). The order is what to keep; milestone 3 changes which managed modules take part.
- Two builds of one tag never overwrite each other, and `tools list` shows which build is installed against what is current. Any renaming in milestone 3 must preserve this. [merit 3.3](analysis/01-merit-and-landscape.md)
- `os.pathsep` is used for the classpath, the library path and the overrides property, which matters for decision D15.
- `--cfg` accepts a name or a path and is searched next to the spec, in the working folder and in the project root; `tools path` prints one clean line. [ux 2.5, 5](analysis/06-cli-ux-and-docs.md)
- The tool's version has one static source and is read at run time from package metadata. Pre-commit hooks are local and take their tool versions from `uv.lock`. [packaging 2.1, 9.3](analysis/05-packaging-ci-release.md)
- The tests that exercise real behaviour on temporary folders with few or no mocks: the classpath resolver, version resolution and URLs, project root, the pin-state assertions in the install tests, uninstall. Input for deciding which existing tests are worth keeping. [testing 4](analysis/04-testing.md)
- Remote version fetching separates fetch from transform and has an explicit online, cached, stale and unavailable status, so most commands work offline.
- Typed configuration with pydantic, platform folders through `platformdirs`, packaged defaults read through `importlib.resources`.
- The pin is a plain text file, not a symlink. Each spec gets its own TLC `-metadir`, keeping TLC state out of the user's project.
- Every subprocess call uses an argument list, never a shell. Every HTTP call sets a timeout; TLS verification uses the OS trust store. YAML is loaded with the safe loader. [quality, what is done well](analysis/03-code-quality-and-correctness.md)
- TLC's exit code is passed through to the shell.
- A value that cannot be parsed falls back to the raw string instead of crashing.
- Strict mypy, a broad ruff rule set and bandit are all clean.
- PyPI trusted publishing with no long-lived token, provenance attestations, a publish job that never checks out or runs project code, and one build whose files go to both GitHub and PyPI. [packaging 3.2](analysis/05-packaging-ci-release.md)

## Milestone 1: a runner you can trust

Goal: `tlaup tlc` shows correct results for real TLC output, and no command destroys data it was not asked to.

Parser

- [ ] Capture real `-tool` output from TLC 1.7.4 and the current rolling build (investigation list, first item) as golden files kept with the parser's tests, filed by TLC version (decision D7), for: success, invariant violation with wrapped multi-line values, deadlock, liveness with back-to-state and stuttering, SANY semantic error, parse error, assertion failure, coverage. Add expected parsed results. Drive the parser exactly as the runner does, with lines that keep their newline. These tests should fail first. (M) [testing 9.1](analysis/04-testing.md)
  - Answer (question 1): 20 cases per version captured under `tests/fixtures/research/01-tlc-output/`; messages nest on one line, v1.7.4 has no `POSTCONDITION`, severity 2 was never produced, Java 11 not run. [Result](research/01-tlc-output.md)
- [ ] Move the parser stack (message framing, codes, values, models, SANY parser) into its own import package that imports nothing from `tlaup` (decision D7). (M)
- [ ] Never lose output (decision D9): anything the parser does not recognise is shown exactly as TLC printed it. This covers unregistered message codes, which are dropped today even when their severity is error; add the six missing error codes including 2404. A malformed start marker such as `STARTMSG -1` must not raise. (S-M) [quality H6, L16](analysis/03-code-quality-and-correctness.md)
- [ ] Read the TLC version from the startup message so one parser can handle several versions (decision D7). Today code 2262 is registered as ignored, so the version is never captured. (S) [testing 3.1](analysis/04-testing.md)
- [ ] Fix error-trace parsing so real counterexamples yield states: location inside the angle brackets, no location on the initial state, the `/\ ` prefix, and the "Back to state" (2122) and stuttering (2218) headers (`tlc/parser.py:195,223`). (S-M) [quality H1](analysis/03-code-quality-and-correctness.md)
- [ ] If TLC can write traces as JSON itself (investigation list), read traces from that and skip value parsing for traces (note 13). Decide in design once the answer is known.
  - Answer (question 2): only 1.8.0 has `-dumpTrace json`, and it is lossy (sets, sequences and tuples are all arrays), so it cannot replace value parsing; at most it adds state indexes, action names and the loop edge on 1.8.0. [Result](research/02-json-traces.md)
- [ ] Fix function-valued variables (`(a :> 1 @@ b :> 2)` parses to `a`) and values that TLC wraps across lines, which always fall back to a raw string because the tokenizer does not skip newlines. (S-M) [quality M11](analysis/03-code-quality-and-correctness.md), [testing 3.1](analysis/04-testing.md)
- [ ] Fix SANY error grouping: errors are flushed after every line, the error block never ends so later TLC messages become SANY errors, and lines keep their newline (`tlc/runner.py:246`, `tlc/sany.py`). Cover `Semantic errors:`, `***Parse Error***` and the 1.8.0 `Linting of module` line. (S) [quality H2](analysis/03-code-quality-and-correctness.md)
- [ ] Show the violated-invariant text together with the trace. Today the text is skipped whenever a trace exists; the trace bug hides this. Error lines keep a trailing newline and print double-spaced. (S) [quality M12](analysis/03-code-quality-and-correctness.md) (note 23)
- [ ] Print TLC text without Rich markup interpretation; today, on a terminal, `[a |-> 1]` prints as an empty line and `[/]` raises an error (`cmd/tlc.py:175`; reproduced with Rich alone, not in a full run). (S) [quality H7](analysis/03-code-quality-and-correctness.md)

Runner

- [ ] Report run errors as what they are. Today every `OSError` during a run, including a broken pipe from `--raw | head`, becomes "'java' not found". (S) [quality M2](analysis/03-code-quality-and-correctness.md) (note 23)
- [ ] Forward SIGTERM to the JVM so a CI timeout does not leave TLC running; exit 130 on Ctrl-C; survive a second Ctrl-C while draining output. That the JVM keeps running today is from reading the code, not from a run (investigation question 15). (S) [quality M3](analysis/03-code-quality-and-correctness.md)
  - Answer (question 15): confirmed: SIGTERM to tlaup leaves the JVM running under PID 1; one Ctrl-C makes tlaup exit 143, not 130, and a second ends quietly with 130. [Result](research/15-exit-codes-and-signals.md)
- [ ] Do not crash on non-UTF-8 bytes in TLC output. (S) [quality M1](analysis/03-code-quality-and-correctness.md)
- [ ] Pass a `--cfg` file outside the project root to TLC so that TLC reads the file that was validated; today only its name is passed. Depends on how TLC resolves `-config` (investigation list). (S) [quality M13](analysis/03-code-quality-and-correctness.md) (note 23)
  - Answer (question 16): a relative `-config` is looked up in TLC's working folder, then the spec's folder; tlaup passing only the name made TLC read a different file. An absolute path works except on v1.7.4 with an absolute spec and a cfg outside its folder. [Result](research/16-config-path.md)
- [ ] Spec names: a dot in the name is mangled by `with_suffix` (`Foo.v2` becomes `Foo.tla`), `.` raises an error, and any existing file such as a `.cfg` is accepted as the spec. (S) [quality L14](analysis/03-code-quality-and-correctness.md) (note 24)
- [ ] Stop run-cache cleanup from deleting other specs' directories: it matches by name prefix across all projects, can delete the directory of a run in progress, and `modules add` and `modules remove` wipe every run directory (`tlc/run_cache.py:29-40`). TLC also adds a timestamped folder per run that is never removed; define when those are cleaned up. (S-M) [quality H5](analysis/03-code-quality-and-correctness.md)
  - Answer (question 17): reproduced the prefix match deleting another spec's folder; TLC keeps its timestamped folder after a violation (1.8.0), a signal or a crash; two v1.7.4 runs in one metadir collide; deleting during a run can crash TLC. [Result](research/17-metadir.md)
- [ ] Report clearly when an override module fails to load (raised list). Depends on what TLC prints in that case (investigation list). (S)
  - Answer (question 13): most failures are silent (exit 0, the TLA+ body runs); a broken class gives `1000` and exit 255 without naming it; v1.7.4 ignores the overrides property, so a `modules add` module whose class is not `TLCOverrides` does not load there. [Result](research/13-override-loading.md)

Problems recorded without a solution; the design stage decides the fix (note 25):

- [ ] The project-root rule counts a parent folder that has `lib/`, `modules/` or `classes/`, so a spec under `~/work` with `~/lib` present runs with `~` as its root and every jar in `~/lib` on the classpath. The search does not walk further up and there is no marker file; the project file in milestone 3 is a candidate marker. [quality M17](analysis/03-code-quality-and-correctness.md), [ux 6.3](analysis/06-cli-ux-and-docs.md) (note 23)
- [ ] The run-cache fingerprint covers the default `.cfg` only, not a `--cfg` file or extended modules. [quality L15](analysis/03-code-quality-and-correctness.md)
- [ ] The module build strips `//` comments with a regex that corrupts string literals; `javac` runs with no `-encoding` and no timeout. [quality L17](analysis/03-code-quality-and-correctness.md)
- [ ] Unknown config keys are silently ignored, so a typo has no effect and no warning. [quality L8](analysis/03-code-quality-and-correctness.md)

Reaching TLC

- [ ] Pass everything after `--` to TLC. Add `--workers`, defaulting to `auto`, as the only first-class TLC option (decision D24). The existing `--cfg` and `--coverage` stay; `--coverage` remains hard-coded to `-coverage 1`, and anything else goes through `--`. (S) [ux 10.2](analysis/06-cli-ux-and-docs.md)
- [ ] Make `--show-command` print the exact command that would run, including `-tool`, shell-quoted, without creating or deleting anything in the run cache. Built on the invocation object in milestone 1b. (S) [architecture 2](analysis/02-architecture-and-organization.md), [quality L1](analysis/03-code-quality-and-correctness.md)

Safety

- [ ] Reject module names containing path separators or `..`, absolute paths, `.` and an empty name in `modules remove` and `modules add`; `modules remove ../tools` deletes the tools folder today. (S) [quality M10](analysis/03-code-quality-and-correctness.md)
- [ ] `modules add` builds in a temporary folder and swaps it in only when compilation succeeds, so a `javac` error no longer destroys the working build; it says when it replaced a module of the same name (decision D23). (S-M) [quality M10](analysis/03-code-quality-and-correctness.md)
- [ ] Fix `tools uninstall --all`, which stops after removing the pinned version; the same happens with several named versions when the pinned one is not last (`cmd/tools/uninstall.py:95`). (S) [quality H3](analysis/03-code-quality-and-correctness.md)
- [ ] A failed uninstall exits non-zero and does not move the pin; the build-selection prompt rejects negative indexes. (S) [quality L12](analysis/03-code-quality-and-correctness.md) (note 24)
- [ ] Concurrent installs: write the pin and metadata atomically and take a lock, so two installs of one version do not collide. (S-M) [quality L10](analysis/03-code-quality-and-correctness.md) (note 24)

Downloads and GitHub

- [ ] Remove installs from a URL (decision D13). Do this first; it removes cases the items below would otherwise handle. (S)
- [ ] Download to a temporary file, check it is a valid jar, then rename. A folder without a jar and its metadata does not count as installed. `--force` keeps the old build until the new one is verified. Never report a truncated jar or a proxy's HTML page as installed. (S-M) [quality H4](analysis/03-code-quality-and-correctness.md)
- [ ] Refuse unencrypted addresses and any redirect to one. (S) [quality M9](analysis/03-code-quality-and-correctness.md) (note 26)
- [ ] After download, compare the commit the jar reports about itself with the expected commit, since the tag and the jar are fetched separately and upstream moves both. How to read it, ideally without starting a JVM, is on the investigation list. (S-M) [quality M6](analysis/03-code-quality-and-correctness.md), [merit 3.3](analysis/01-merit-and-landscape.md) (note 26)
  - Answer (question 14): `X-Git-Revision` in the manifest holds the full commit and is readable without a JVM. [Result](research/14-jar-manifest.md)
  - Answer (question 7): upstream windows are seconds for `rolling` and about 4.5 minutes for `v1.8.0`; tlaup's one-hour lookup cache is the largest window. [Result](research/07-rolling-race.md)
- [ ] Read all pages of tags and releases; choose "latest stable" by version, not by API order; never install a prerelease while saying "stable". Depends on the API ordering answer (investigation list). (S-M) [quality M7](analysis/03-code-quality-and-correctness.md) (note 23)
  - Answer (question 8): releases sort by `created_at`, tags by a version-aware name sort; 114 tags today, and tlaup's single page of 30 loses `rolling` at the next `v1.x` tag. [Result](research/08-github-api-ordering.md)
- [ ] GitHub token support (`GITHUB_TOKEN`, `GH_TOKEN`), `Accept` and `User-Agent` headers, retry with backoff, and a clear message when rate-limited. The token is never printed, including by `--show-command` and `--debug`, and is sent only to the GitHub API host. Moved up from milestone 3 because the CI integration job and the GitHub Action depend on it. (S-M) [quality M8](analysis/03-code-quality-and-correctness.md), [ux 10.17](analysis/06-cli-ux-and-docs.md)
- [ ] Do not crash on a non-JSON or non-list API response. Key the remote-version cache on the request, not only the asset name, and write it atomically. `tools upgrade`, and an install of a moving tag, check the remote again instead of trusting the one-hour cache; today `upgrade` can say "already up to date" for an hour after a new build. (S) [quality M1, M6, L9](analysis/03-code-quality-and-correctness.md)

First run and failures

- [ ] One preflight used by every `tlaup tlc` path, checking jar, Java, spec and cfg in that order, each failure a one-line error naming the next command. Print nothing, including "Starting TLC", until the checks pass. (S) [ux 10.1](analysis/06-cli-ux-and-docs.md) (note 27)
- [ ] No tracebacks for users: missing Java, missing jar with `--raw` or `--show-command`, a broken config, an unreadable pin file. Turn off Typer's decorated crash reports, add one top-level handler that prints a one-line error, and add `--debug` to show the full traceback. (S) [quality M1](analysis/03-code-quality-and-correctness.md) (note 27)
- [ ] First-run prompt (decision D4): when nothing is pinned, ask once between stable and rolling, then install the choice. A flag and an environment variable answer it; error with a hint when there is no terminal. Which upstream tag "rolling" means is decided in the first design wave (see "Design, in waves"). (S-M) [ux 10.21](analysis/06-cli-ux-and-docs.md)
  - Answer (question 3): upstream means `rolling` as the name that survives version bumps; `v1.8.0` moves too, on every master push. [Result](research/03-jar-identity-and-upstream-cli.md)
- [ ] Remove the legacy fallback jar path, so it is never shown as the expected location, and all other legacy-layout code (pin migration, flat module form): the `tlaup` folders have never held the old layouts (decision D14). A pin that points at a missing build is a clear error with a hint, not a silent fallback. (S) [architecture 4](analysis/02-architecture-and-organization.md), [quality L11](analysis/03-code-quality-and-correctness.md) (note 27)

Java (note 28)

- [ ] Java options: a `TLAUP_`-prefixed variable and a repeatable flag, both adding to the configured options instead of replacing them; quoted values split correctly; `JAVA_OPTS` is no longer read (decision D20). (S) [quality L7](analysis/03-code-quality-and-correctness.md), [ux 2.4](analysis/06-cli-ux-and-docs.md)
- [ ] Use `JAVA_HOME` when set, falling back to `PATH`, for both `java` and `javac`. (S) [quality L6](analysis/03-code-quality-and-correctness.md)
- [ ] One Java start per run: read the TLC version from saved metadata instead of launching Java, and remember the Java version check. Report a timeout as a timeout, not as "not installed". One function reads the TLC version instead of two. Define what an install records when Java is absent or the read fails (today it writes an empty string, with no timeout on the call) and what a run does with empty metadata. (S-M) [quality L5, L6](analysis/03-code-quality-and-correctness.md), [architecture 4](analysis/02-architecture-and-organization.md)
  - Answer (question 14): the commit and build time can be read from the manifest without starting Java; CalVer is `Build-TimeStamp` reformatted, and v1.7.4 has none. [Result](research/14-jar-manifest.md)

Configuration

- [ ] Layered configuration (decision D10): packaged defaults, user file, environment, flags; the project file joins the chain in milestone 3. Every section has defaults, so an old or trimmed file still loads. No file is written until the user changes a setting. (M) [architecture 3](analysis/02-architecture-and-organization.md), [ux 10.13](analysis/06-cli-ux-and-docs.md)
- [ ] `config` commands work when the file is broken, and a broken file gives a readable validation message instead of a traceback. (S) [quality M1](analysis/03-code-quality-and-correctness.md)
- [ ] Remove settings nothing reads (`workspace.root`, `workspace.spec_dir`, the unread `tla.community_modules` block, `save_config`) and the comment describing behaviour that no longer exists. For each hard-coded value that config appears to control (`"spec"`, `"modules"`, `"classes"`, `"lib"`, the TLC and overrides class names), either read the setting or remove it. Decide whether `module_path` and `module_lib_path`, which are read but only settable by hand and documented nowhere, are documented or folded into the project file. (S-M) [architecture 3, 8](analysis/02-architecture-and-organization.md), [ux 6.1](analysis/06-cli-ux-and-docs.md)
- [ ] Environment overrides for the tool's folders (decision D25). Lands early, with the test isolation work in milestone 2. (S)
- [ ] `config edit`: accept `$VISUAL` and `$EDITOR` values with arguments such as `code --wait`, have a default that exists on the platform, and validate the file after editing. (S) [quality M18](analysis/03-code-quality-and-correctness.md) (note 23)

Messages and help

- [ ] Error messages (raised list): list the locations searched when a spec is not found; "did you mean v1.8.0" for a version typed without the `v`; say when GitHub rate-limited the request and how to give a token; add the next command to "no pinned version" errors; drop "Successfully installed" after "already installed" and mention `--force`; show the classpath when `javac` fails. (S) [ux 4](analysis/06-cli-ux-and-docs.md)
- [ ] Route every message through the one UI helper; there are 21 hand-written error prints and a warning printed to stdout in `tools list`. (S) [architecture 6](analysis/02-architecture-and-organization.md), [ux 10.8](analysis/06-cli-ux-and-docs.md)
- [ ] Help text (raised list): what `upgrade` means (newest build of the same tag, not a newer version); what `install` does with no version and that the first install is pinned; `modules` wording and the folder layout `modules add` expects; the `SPEC` argument accepts a name, a file or a path; plain wording for `--raw`; the scope of `--yes`; missing help on `tools path VERSION`; "TLC" where the whole toolset is meant; one summary line shared by `--help` and `--version`; root help ordered by importance; examples or a longer description on the main commands, since none has any and the generated reference is built from help. (S) [ux 7](analysis/06-cli-ux-and-docs.md)
- [ ] Wording: one word for a stopped run ("canceled" and "stopped" are both used); module timestamps with a time zone; the typos listed in the report. (S) [ux 7](analysis/06-cli-ux-and-docs.md)

Startup cost (note 29)

- [ ] Skip the `git rev-parse` call on normal installs; load heavy libraries (requests, Rich progress, pydantic schema) only in the commands that need them; set up the OS trust store where the network is used, not as a side effect of importing the package. `tlaup --help` took about a third of a second when measured. (S-M) [quality L18, L20](analysis/03-code-quality-and-correctness.md), [packaging 2.1](analysis/05-packaging-ci-release.md)

Exit criteria: golden-file tests pass for both TLC versions; a spec with a violated invariant shows its message and its full trace; `tlaup tlc Spec -- -workers 4 -deadlock` runs; no listed failure path prints a traceback; a truncated download is never reported as installed.

## Milestone 1b: other tools, reporters, command layout

Goal: carry out decisions D3, D5 and D8 on top of a correct runner, and settle the command layout before 0.9.0 fixes it. Do not start the reporter work before the golden-file tests from milestone 1 pass, since reporters render what the parser produces.

Shared groundwork

- [ ] A single TLC invocation value (spec, cfg, project root, working folder, jar, run folder, flags) resolved once per run and shared by the show-command, raw and formatted paths; today the spec is resolved up to five times and the config loaded four times per run. Building the command from it is a pure function and the only place flags are assembled. One process loop instead of two copies. SANY errors in the result are typed and are filled in on the Ctrl-C path too. (M) [architecture 2](analysis/02-architecture-and-organization.md)
- [ ] A small family of domain errors (spec not found, tool not installed, Java missing or too old) mapped to exit codes in one place. (S) [architecture 2](analysis/02-architecture-and-organization.md)
  - Answer (question 15): TLC uses 0, 1, 10 to 14, 75 to 77, 150, 151 and 255; 3 to 9 are free. [Result](research/15-exit-codes-and-signals.md)
- [ ] A generic Java tool invocation (jar, classpath, JVM options, main class, arguments, working folder) with a streaming runner, used by TLC and every other tool. (M) [architecture 7](analysis/02-architecture-and-organization.md)

Other tools (decision D5)

- [ ] `sany` command: parse a spec and report diagnostics with file, line and column. Reuses the fixed SANY parser. (S-M)
  - Answer (question 12): SANY error lines carry no file name and some carry no location; semantic errors exit 0 unless 1.8.0's `-error-codes` is given. [Result](research/12-sany-pcal-repl.md)
- [ ] `pcal` command: run the PlusCal translator; passthrough for its flags. (S-M)
  - Answer (question 12): pcal rewrites the `.tla` in place, keeps the old file as `X.old` and writes `X.cfg` unless `-nocfg`; failure exits 255. [Result](research/12-sany-pcal-repl.md)
- [ ] `repl` command: interactive, so no output parsing; the terminal is passed straight through. (S)
  - Answer (question 12): `tlc2.REPL` exists in 1.8.0 only; it works on a pipe and exits on end of input. [Result](research/12-sany-pcal-repl.md)
- [ ] Keep all three thin (note 15): no logic beyond reading their output, everything through the shared launcher. Check which jar build is running, so the tool can switch to upstream's own entry point when it exists and fall back for older jars. Depends on the upstream state answer (investigation list). (S-M)
  - Answer (question 3): PR 1371 is an unmerged bash script, not an entry point in the jar, so there is nothing to hand off to yet; the TLC banner or the manifest tells which build is running. [Result](research/03-jar-identity-and-upstream-cli.md)
- [ ] Golden-file tests for SANY and PlusCal output per TLC version; passthrough after `--` for each. (M)
  - Answer (question 12): captures for both versions are under `tests/fixtures/research/12-sany-pcal-repl/`. [Result](research/12-sany-pcal-repl.md)

Reporters (decisions D3 and D8)

- [ ] A reporter interface fed by the parsed result and run events. Move the streaming state and the final summary out of the command into it; the command shrinks to option parsing, error mapping and the exit code. Terminal and non-terminal output differ only in where they write and in the footer. (M) [architecture 1](analysis/02-architecture-and-organization.md)
- [ ] Delete display code that nothing in `src/` references (`StatusFooterComponent`, `TlcDisplayComposer`, the `TlcComponent` protocol, `info_dedup`, `_show_diagnostic_info`) and the tests that pin it. Remove the duplicated callback (`cmd/tlc.py:157-238`) and the three copies of the elapsed-time logic. (S-M) [architecture 1](analysis/02-architecture-and-organization.md), [quality L2, L4](analysis/03-code-quality-and-correctness.md)
- [ ] Live terminal reporter: render the layout on a terminal; fall back to plain streamed output when stdout is not a terminal or `--raw` is given. (M)
- [ ] Make `--refresh-interval` and the matching config key take effect. (S) [ux 10.7](analysis/06-cli-ux-and-docs.md)
- [ ] Fix the per-line re-rendering cost, which grows with the square of the output, and the unbounded list of output lines kept in memory. (S-M) [quality M14](analysis/03-code-quality-and-correctness.md)
- [ ] Snapshot tests through a fixed-width, colourless console with an injected clock, replacing assertions on Rich internals. (M) [testing 9.8](analysis/04-testing.md)

Command layout (notes 44 to 46)

- [ ] Review the layout of every command so it follows the most common CLI patterns and users can guess commands from other tools. No aliases for old command names (decision D14). Starting point is the tree suggested in [ux 2.2](analysis/06-cli-ux-and-docs.md): a `doctor` command that checks Java, `javac`, the pinned jar, config and folders and absorbs `check-java`; one `cache` command replacing `fetch-cache clear` and the `tlc --cleanup` flag; `config path`, `show`, `get`, `set`, with `show` printing the effective configuration; `completion`. Also settle: `tools meta sync` sitting three levels deep; the different meanings of `tools dir`, `tools path` and `modules path`; the editor as a positional argument of `config edit`; the two `--version` flags; whether short forms such as `ls` and `rm` are offered. (M) [ux 2.2](analysis/06-cli-ux-and-docs.md)
- [ ] Typing versions (note 45): accept a version without the `v`; the shortcuts `latest`, `stable` and `rolling`; a command that shows what is pinned; fix the "Tag/SHA" column label, which holds a commit. (S) [ux 2.3](analysis/06-cli-ux-and-docs.md)
  - Answer (question 3): `rolling`, `v1.8.0` and the CalVer tags all name master builds; one commit can carry two CalVer tags. [Result](research/03-jar-identity-and-upstream-cli.md)
- [ ] Shell completion, with completers for installed versions and module names. (S) [ux 7](analysis/06-cli-ux-and-docs.md), [packaging 7](analysis/05-packaging-ci-release.md)
- [ ] Move the version flag to `-V` so `-v` can mean verbose (note 42). (S) [ux 2.2](analysis/06-cli-ux-and-docs.md)

New name (decision D1)

- [x] Choose the command name: `tlaup`. On 2026-11-10 the name was unused on PyPI, crates.io, npm and Homebrew.
- [x] Ship the `tlaup` entry point; update README, help text and examples. Done 2026-11-14 in 0.8.2: package, command and import package renamed, new repository with the full history, no `tla` alias.
- [x] Retire `tlaplus-cli`: 0.8.3 forwards to `tlaup` with a notice; the old repository is archived. Done 2026-11-14.
- [x] Own folders: config, toolsets, modules and the run cache live under `tlaup` folders, with nothing moved over. Done 2026-11-14, unreleased.

Exit criteria: `sany`, `pcal` and `repl` run against the pinned jar; a long TLC run shows a live status on a terminal and clean line output when piped; the command tree is reviewed and signed off; completion works in bash, zsh and fish.

## Milestone 2: a feedback loop that catches this

Goal: a broken parser or a broken release is caught before a tag exists.

Order (decision D6): the parts that do not depend on milestone 1 land early, even though nothing is published. Those are test isolation with the folder overrides from decision D25, the network and subprocess guard, the coverage policy, the CI, dependency and hygiene items, the build check, the release script and workflow, and the rulesets. The tests that exercise parser and runner behaviour (golden-file replay, assertions on parsed results, the integration job's parsed-result checks) are written with or after the milestone 1 item they test.

Testing approach (decision D16)

- [ ] Design the testing approach from scratch before any other design work: where tests give most value, whether the existing unit tests are worth keeping and in what form, and how tests are written from now on. Check whether one approach can cover the whole program (preferred); if not, choose one per part. Lean on documentation tests and example tests rather than many small unit tests. Consider human-readable scenarios (behave or pytest-bdd, "given, when, then") for CLI behaviour; the cost is step definitions to maintain, and they suit parser internals less. (M) [testing 9](analysis/04-testing.md) (note 5)

  Inputs from the report, per part: golden TLC output for the parser; property-based tests for the value parser; snapshots for rendering; recorded GitHub responses for downloads; a fake `java` replaying recordings for end-to-end runs; a Java and TLC matrix for integration.

  Anti-patterns to avoid, all found in the current suite: patches that never take effect (import by name, the no-op `mock_load_config`, wrong patch targets in module tests); mocking until only a list index is under test; invented TLC output; assertions on Rich internals and on help-text wording; checking messages instead of the resulting state; dependence on the wall clock and on file modification times; tests that cannot fail; state leaking between tests (direct `os.environ` edits, the cached config, mutually exclusive `shutil.which` fixtures, module-level runners); real `java` and `git` started by unit tests with unchecked results; tests writing to and deleting from the real config and cache; duplicated tests and three copies of the GitHub fixtures; integration tests with broken skip guards, Linux-only jar discovery and no assertions on parsed results; no markers, no branch coverage, no threshold. [testing 4 to 7](analysis/04-testing.md)

The next four items are outcomes the approach must deliver, whatever form it takes.

- [ ] Isolation is automatic and total: every test runs with the tool's folders pointed at a temporary folder (decision D25 makes this one switch), the config cache reset, and a fixed terminal environment (no colour, fixed width); forced colour in CI is what broke the 0.8.0 release. The unit suite passes on a machine with nothing installed and writes nothing outside temporary folders. Remove the no-op `mock_load_config`, the hand-kept patch list and the wrong patch targets. (S-M) [testing 9.2, 9.8](analysis/04-testing.md)
- [ ] Unit tests cannot reach the network or start an unmocked subprocess; the 23 real subprocess starts in the unit suite (22 `java`, one `git`) go away. (S) [testing 9.5](analysis/04-testing.md)
- [ ] The `tlaup tlc` command path is tested end to end: exit codes, raw mode, missing Java and Ctrl-C. `cmd/tlc.py` is 45 percent covered today; the report's target is above 80. (M) [testing 9.4](analysis/04-testing.md)
- [ ] Download and GitHub failure modes are tested: failure mid-stream, 403 and 404, short body, non-list JSON, release without the jar, tag without a commit, pagination, and a forced reinstall that fails. (M) [testing 9.6](analysis/04-testing.md)

The techniques the report proposes for these are candidates; the design decides whether to use them: a fake `java` that replays golden files for the end-to-end tests; recorded real GitHub responses for the download tests; property-based tests for the value parser (never raises, never loses text, round-trips records, sets, sequences, functions, ranges and strings with escapes, unchanged by TLC-style line wrapping) [testing 9.7](analysis/04-testing.md); and snapshot tests for reporters (milestone 1b). Golden files of real output for the parser are not open: decision D7 fixes them.

- [ ] Integration tests: registered markers with strict checking; working skip guards; the jar supplied through a fixture or an environment variable, not found under the home folder; assertions on parsed results, including a failing spec, a trace, a SANY error and a coverage run. (S-M) [testing 9.3](analysis/04-testing.md)
- [ ] Coverage policy: branch coverage on; a `fail_under` near the current 83 percent; coverage only in the full-suite task, not on every single-test run; randomised test order; warnings as errors. (S) [testing 9.10](analysis/04-testing.md) (note 5)

CI

- [x] Move to trunk plus tags (decision D2). Done 2026-11-14 with the move to this repository: only `main` exists, the test workflow runs on every push to `main` and on every pull request, and a ruleset protects `v*` tags from moving or deletion with no bypass, not even for admins, so a bad tag means a new version number. [packaging 10.1](analysis/05-packaging-ci-release.md)
- [ ] Integration job on every push, with a matrix over Java 11 and 25 (oldest and newest; widen later if other versions need support) and both supported TLC builds, on GitHub-hosted runners, macOS included (free for public repositories); cache the jar. v1.7.4 can be pinned exactly. A rolling build cannot be downloaded again once upstream replaces it, so until milestone 3 the job runs against the current rolling build and records which build that was. (M) [packaging 10.10](analysis/05-packaging-ci-release.md) (note 31)
- [ ] Unit job on Python 3.11 and the newest release, plus one macOS job; select Python through `uv`, dropping the separate setup step; remove Java and the jar download from the unit job once the suite no longer needs them. Add a classifier for each Python version that is tested. (M) [packaging 10.11](analysis/05-packaging-ci-release.md)
- [ ] One job that installs the newest dependency versions the ranges allow, since users get those and CI tests only the lock file. (S) [packaging 1.2](analysis/05-packaging-ci-release.md) (note 33)
- [ ] Build check on every push: build, `twine check`, install the wheel and run `tlaup --version`, so a packaging break is not first seen at release. (S) [packaging 3.4](analysis/05-packaging-ci-release.md)
- [ ] Enforce `ruff format --check`; `uv sync --locked`; an explicit read-only `permissions` block, `timeout-minutes` and a concurrency group in each workflow; `shellcheck` on the release script. Confirmed 2026-11-14: the repository default for workflow tokens is read-only. (S) [packaging 10.6](analysis/05-packaging-ci-release.md)
- [ ] Run the pre-commit hooks in CI, without the test hook, so the secret, YAML, TOML and large-file checks do not depend on a local install. (S) [packaging 10.16](analysis/05-packaging-ci-release.md)
- [ ] Ruleset on `main`: changes arrive by pull request with the Test check passing; the maintainer can bypass (decision D21). Set once the check names are stable. (S) [packaging 10.13](analysis/05-packaging-ci-release.md)
- [ ] Lint rules: enable ruff's blind-except, naive-datetime and print rule groups (BLE, DTZ, T20) and fix what they flag, including the two `except Exception: pass`; review the global `PLW1510` ignore and the bandit skips B404, B603 and B607; replace the `Any` escape hatches in the formatter and models. (S-M) [quality, typing and lint](analysis/03-code-quality-and-correctness.md)

Release

- [ ] Harden `scripts/release.sh`: on `main`, clean tree, `HEAD` equal to `origin/main` after a fetch, the tag absent both locally and on the remote, CI green for `HEAD`, lock file version equal to the project version, a proper `## [X.Y.Z] - date` changelog heading with nothing left under Unreleased, an annotated tag (decision D21), an atomic push, and the local tag removed if the push fails. Read the version robustly. (S-M) [packaging 10.2](analysis/05-packaging-ci-release.md) (note 36)
- [ ] Restructure `release.yml` into three jobs: a read-only build (lint, test, build, `twine check`, wheel smoke test), then PyPI publish with the id-token permission only, then the release page with write access and no project code. Fail if the tag does not match the project version or the commit is not on `main`. Attach only the wheel and sdist; the 0.8.2 page carries a stray `default.gitignore`. Set `persist-credentials: false` on checkout. Pin the actions that hold write access by SHA, or replace the third-party release action with `gh release create`. (M) [packaging 10.9](analysis/05-packaging-ci-release.md) (note 34)
- [ ] Release pages: each page gets that version's changelog section as its text; backfill the existing pages from the changelog (release pages did not travel with the pushed history, so probably only 0.8.2 has one here; not checked, and whether older tags get pages is decided then); PyPI's changelog link points at the GitHub releases page. No "what's new" section in the README. (S) (note 35)
- [ ] A `poe` task around `uv version --bump`, so `pyproject.toml` and `uv.lock` move together. (S) [packaging 10.19](analysis/05-packaging-ci-release.md) (note 36)
- [ ] `pypi` environment: add the maintainer as required reviewer and switch off admin bypass (decision D21). Deploying only from `v*` tags is in place since 2026-11-14. (S) [packaging 8](analysis/05-packaging-ci-release.md)
- [ ] Before each release, refresh the lock file and let CI run before tagging. Done for 0.8.2. (note 32)
- [ ] Follow the version rule of decision D27 from 0.9.0 on.

Dependencies and build

- [x] Dependabot alerts and security updates. On since 2026-11-14.
- [ ] `.github/dependabot.yml` for the `uv` and `github-actions` ecosystems: one monthly run that groups all version updates into one pull request. (S) [packaging 4.6](analysis/05-packaging-ci-release.md) (note 32)
- [ ] Build fixes (note 33): `setuptools>=77.0.3`, which the SPDX licence string needs; a real Pydantic minimum instead of the locked version; remove the `rich<14` cap; raise the `pre-commit<4` cap; delete the redundant `MANIFEST.in`. (S) [packaging 1.1 to 1.3](analysis/05-packaging-ci-release.md)
- [ ] PyPI and GitHub metadata (note 37): keywords; the missing classifiers (Console, Developers, Science/Research, a quality-assurance or scientific topic, Typing :: Typed); replace the "Build Tools" topic; Linux and macOS instead of "OS Independent" (decision D15); GitHub topics; absolute links in the README; `pipx` and `uvx` install options. (S) [packaging 10.15](analysis/05-packaging-ci-release.md)

Repository hygiene (raised list)

- [ ] Pre-commit: move the test hook to pre-push; add a format hook; run mypy on the whole project instead of on staged files. (S) [packaging 9.3](analysis/05-packaging-ci-release.md)
- [ ] `poe clean` also removes `build` and the egg-info folder, since a stale `build/lib` can bring removed modules back into a locally built wheel; add `htmlcov/`, `coverage.xml`, `.direnv/` and editor folders to `.gitignore`. (S) [packaging 9.1, 9.2](analysis/05-packaging-ci-release.md)
- [ ] One story for Python versions: `.python-version`, the CI matrix, the classifiers and the mypy and ruff targets agree, and every advertised version is tested. Which Python CI ran on could never be confirmed (the logs had expired); it is inferred as 3.13. (S) [packaging 9.4](analysis/05-packaging-ci-release.md)
- [ ] A two-line `SECURITY.md` pointing at GitHub private vulnerability reporting, which is on since 2026-11-14, as is secret scanning with push protection. (S) [packaging 9.4](analysis/05-packaging-ci-release.md)

Nix

- [x] Nix flake removed in 0.8.2 (2026-11-14) instead of fixed: it was a one-off and never kept up to date (note 30). [packaging 5](analysis/05-packaging-ci-release.md)

Exit criteria: a clean checkout passes unit tests with no jar installed and no writes outside temporary folders; a pull request that breaks trace parsing fails CI; a release cannot be tagged from a red commit; a pushed tag does not publish without the maintainer's approval.

## Milestone 3: reproducibility

Goal: a repository can declare its TLA+ toolchain and get the same bytes everywhere.

- [ ] Design note before anything else; this milestone has the most open questions. It must settle at least: the name and format of the project file and whether the locked values live in it or in a second file; the order in which a version is chosen (flag, then environment variable, then project file, then global pin); what goes on the classpath when there is no project file; where jars live, given an old rolling jar cannot be downloaded again; how a digest is trusted for v1.7.4, for which GitHub published none on 2026-11-09 (investigation question 18), and for a jar built from source; whether the project file doubles as the project-root marker; whether `tools upgrade` keeps the build it replaces, since today it deletes it and a rolling build cannot be downloaded again. (M) (note 3)
  - Answer (question 18): v1.7.4 has no GitHub digest, but its release notes give a matching SHA-1. [Result](research/18-digest-field.md)
  - Answer (question 6): a jar built from source never matches the published digest, so trust for it has to be per entry without the manifest, or tlaup's own digest. [Result](research/06-build-from-source.md)
- [ ] Version identity as a type, not a parsed folder name. Typed metadata is the source of truth, with one writer, one reader and a schema version. One version store (list, get, add, remove, pin, unpin) is the only code that composes or parses folder names; today that happens in eight places with two rules that disagree, and a tag containing a hyphen or a slash breaks them. Prerequisite for the rest. (M) [architecture 4](analysis/02-architecture-and-organization.md), [quality M4](analysis/03-code-quality-and-correctness.md)
- [ ] Storage layout: reserve a level for other distributions (decision D17), without knowing more about them yet: the shape of the Apalache and TLAPS distributions (archive type, per-platform files, version scheme) was not verified and is looked at when they are scheduled; move the pin and registered modules out of the cache folder, which cleaners and CI runners wipe, as a clean break with no migration (decision D14); folder names without characters that are invalid on Windows; a layout-version marker so a later change can be detected. (M) [ux 10.18](analysis/06-cli-ux-and-docs.md), [quality L19](analysis/03-code-quality-and-correctness.md) (notes 18 and 40)
- [ ] Record SHA-256 for every installed jar; verify against the `digest` field the GitHub releases API returns. On 2026-11-09 the field was present for `v1.8.0` and `rolling` and empty for older releases. (M) [merit 3.1, 6.4](analysis/01-merit-and-landscape.md), [ux 10.23](analysis/06-cli-ux-and-docs.md)
  - Answer (question 18): still true on 2026-11-14: present and correct for `v1.8.0` and `rolling`, null for v1.7.4 and older. [Result](research/18-digest-field.md)
- [ ] Project file discovered by walking up from the spec, holding the pinned build with its tag, commit, CalVer and digest; `tlaup tools install --locked` fails loudly on a mismatch; `tools install` with no version installs what the file asks for; `tools pin --local` writes the file; environment and flag overrides. The file becomes a layer of the configuration (decision D10). (M-L) [ux 10.12](analysis/06-cli-ux-and-docs.md)
- [ ] Adopt upstream's `rolling` release and immutable CalVer tags for naming builds. `rolling` and `v1.8.0` hold the same bytes today and must not appear as two unrelated versions or be downloaded twice; `rolling` must sort correctly although it has no version number. (M) [merit 3.3](analysis/01-merit-and-landscape.md)
  - Answer (question 3): both tags move on every master push and hold the same bytes; CalVer tags are git tags only, with no download. [Result](research/03-jar-identity-and-upstream-cli.md)
- [ ] Obtain an older rolling build by building it from source at its CalVer tag, with the Java build tools fetched automatically, when it cannot be downloaded (decision D12), recording the exact build tools it used (decision D28). Depends on the build-from-source answers (investigation list). (L) [merit 6.4](analysis/01-merit-and-landscape.md)
  - Answer (question 6): Ant, 15 to 35 seconds, offline after a full clone; with the CI's JDK major version only the manifest and zip timestamps differ. [Result](research/06-build-from-source.md)
  - Answer (question 5): no jar on any CalVer tag and no stated plan to add one. [Result](research/05-jar-per-calver-tag.md)
- [ ] Per-project override modules declared in the project file; only declared modules go on the classpath, so a module left over from another project cannot change results. Module names no longer collide across projects by folder name. The run header shows which modules are active. This needs the module build as callable domain code, so the extraction listed in milestone 5 is done here. (M) [merit 6.4](analysis/01-merit-and-landscape.md), [ux 10.20](analysis/06-cli-ux-and-docs.md)
- [ ] Community modules as pinned release downloads matched to the TLC build by date and written into the project file with their digest (decision D11). Depends on the CommunityModules trigger answer (investigation list). (M) (note 16)
  - Answer (question 4): TLC builds fire the dispatch, but CommunityModules releases only on push, so matching stays by date and needs a rule for a TLC build with no release in its window. [Result](research/04-communitymodules-trigger.md)
- [ ] `tools meta sync` matches by tag name only, so an older rolling build gets the current build's commit, date and address. Fix it, or remove the command if typed metadata makes it unnecessary. (S) [quality M5](analysis/03-code-quality-and-correctness.md) (note 39)
- [ ] `tools upgrade` by name compares only the first of several installed builds of that tag. (S) [ux 9](analysis/06-cli-ux-and-docs.md)
- [ ] Installing a newer build of a tag while an older build of that tag is pinned moves the pin to the newer build and says so (decision D26). (S) [ux 9](analysis/06-cli-ux-and-docs.md)

Exit criteria: clone a repository with a project file on a fresh machine, run one install command, and get a jar whose digest matches; a mismatched jar is refused; an older rolling build can be obtained again.

## Milestone 4: automation surface

Goal: CI pipelines, editors and coding agents can consume results without scraping.

- [ ] JSON reporter for `tlaup tlc` serialising the parsed result (status, exit code and its meaning, errors, traces, SANY diagnostics with file, line and column, statistics, coverage), plus `--json` for `tools list`, `modules list` and `tools path`. Publish a schema. Study the tlaplus/Examples manifest format first and aim for compatible results (outcome vocabulary, state counts). No field that is always empty: populate or remove `workers_count`, `collision_probability`, `trace_file_path` and the `file_path` fields. (M) [ux 10.11](analysis/06-cli-ux-and-docs.md), [architecture 8](analysis/02-architecture-and-organization.md) (note 41)
  - Answer (question 10): outcomes are `success`, `assumption failure`, `deadlock failure`, `safety failure`, `liveness failure`, `unknown`, from exit codes 0 and 10 to 13; state counts are optional integers. [Result](research/10-examples-manifest.md)
- [ ] Editor-style diagnostics in plain output: SANY and parse errors as `path:line:col: severity: message`, replacing the `file://...#L` links (decision D22). (S) [ux 10.24](analysis/06-cli-ux-and-docs.md)
- [ ] Results on stdout, diagnostics and progress on stderr, one console for each; today the verdict goes to stderr and the trace to stdout, and `--raw` merges TLC's stderr into stdout. `--quiet`, `-v/--verbose`, `--color auto|always|never`; honour `NO_COLOR` in the UI helper, which ignores it today (from reading the code, not run on a terminal); durations in readable units; decorations that fit narrow terminals; no crash when the output encoding cannot represent a glyph. The stdout and stderr rule itself is decided in the first design wave, since the reporters in milestone 1b follow it. (M) [ux 10.14](analysis/06-cli-ux-and-docs.md), [quality M15](analysis/03-code-quality-and-correctness.md)
- [ ] Non-interactive version selection: accept `tag@sha` and the folder name wherever a version is accepted; error instead of prompting when stdin is not a terminal; `--yes` covers every prompt. The `tag@sha` syntax is decided in the first design wave, with the command layout. `tools path` checks that the jar exists and does not silently pick the first of several builds. (S) [ux 10.4](analysis/06-cli-ux-and-docs.md), [quality L13](analysis/03-code-quality-and-correctness.md)
- [ ] Exit codes: documented; a separate code for the tool's own setup errors, so a script can tell "not set up" from "TLC failed"; 2 for usage errors that are hand-written today; non-zero when an operation failed; the meaning of TLC's code printed and included in JSON. The scheme is decided in the first design wave, because milestones 1, 1b and 2 already return and test exit codes; what remains here is the documentation and the printed and JSON meaning. Depends on the TLC exit-code answer (investigation list). (S) [ux 10.5](analysis/06-cli-ux-and-docs.md) (note 42)
  - Answer (question 15): TLC's codes are 0, 1, 10 to 14, 75 to 77, 150, 151 and 255; a missing cfg is 255 on v1.7.4 and 151 on 1.8.0; 3 to 9 are free for a setup error. [Result](research/15-exit-codes-and-signals.md)
- [ ] `tools list` shows rolling versus tagged and "update available" on the installed row, keeps an installed build next to its remote counterpart, and `--installed` works offline. (S-M) [ux 10.6](analysis/06-cli-ux-and-docs.md)
- [ ] A generic exec command and jar-path output so scripts can use the managed jar without the formatter. (S) [merit 6.4](analysis/01-merit-and-landscape.md)
- [ ] A GitHub Action that restores the locked toolchain, runs TLC and turns the JSON result into annotations (decision D22). First check whether such an action already exists (investigation list). It lives in its own repository and is built after the `tlaup` release it needs is published. (L) [packaging 10.23](analysis/05-packaging-ci-release.md)
  - Answer (question 9): no existing action runs TLC or makes annotations; one tiny action only installs a jar. [Result](research/09-nightly-and-setup-tools.md)

## Milestone 5: structure

Do these when the behaviour above is pinned down by tests, not before. Some will fall out of earlier milestones naturally. The target shape and order in [architecture, suggested target shape](analysis/02-architecture-and-organization.md) are a direction, not a prescription.

- [ ] One application-level registry for paths and config, built once and passed in rather than imported per site; domain code stops loading config itself. Path functions move out of `versioning`, which removes the odd imports from classpath and run-cache code. (M) [architecture 3](analysis/02-architecture-and-organization.md)
- [ ] Move the module build pipeline out of `cmd/modules/add.py` into a modules domain package that owns the managed-module layout and raises errors instead of printing; the classpath resolver asks it for folders instead of walking the cache. Done in milestone 3 if per-project modules are built first. (S-M) [architecture 5](analysis/02-architecture-and-organization.md)
- [ ] Use-case functions in the versioning code (install, upgrade, uninstall with pin fallback, remote listing) so the `tools` commands are argument parsing plus printing; the same fetch call and error block are repeated in four commands today. (S-M) [architecture 5](analysis/02-architecture-and-organization.md)
- [ ] No printing from domain code: it reports through return values, errors, logging or a progress callback; only commands and reporters print. (S-M) [architecture 6](analysis/02-architecture-and-organization.md)
- [ ] TLATeX and any further jar tools as thin additions on the generic invocation from milestone 1b. (S)
- [ ] Reorganise tests to mirror the source tree and merge duplicated tests and fixtures. (S-M) [testing 9.9](analysis/04-testing.md)
- [ ] Housekeeping (raised list), done when each area is touched: merge the tiny files and one-command packages; one command registration style, the explicit one; rename or remove misnamed modules (`tlc/compiler.py` holds no compiler, `versioning/app_version.py` is the tool's own version, `tlc/sany.py` parses another tool); fold `cache/github.py` into versioning and break the package-level import cycle; no private names exported for tests; remove parameters no caller passes (`asset_name`, `jar_name`, `base_dir`) and the cache-file name nothing writes; remove scaffolding comments and the reference to a document that does not exist. Smaller still: the unused `SanyParser.get_warnings` (the `sany` command decides whether warnings are shown); regexes recompiled on every line; the misnamed `InitialStateStatItem`, to rename before the JSON schema is published; the build-selection prompt written twice; tests left out of mypy; the `noqa` complexity markers on the three functions where most defects cluster. The ruff groups PERF and FBT stay off unless they turn out cheap. (S-M) [architecture 4, 5, 7, 8 and the import graph](analysis/02-architecture-and-organization.md), [quality L2, L16, typing and lint](analysis/03-code-quality-and-correctness.md)

## Documentation track (parallel, start with milestone 1)

- [ ] README rewrite: the broader purpose with rolling builds as one important part; prerequisites (Java 11 or newer, a JDK for modules, Python 3.11 or newer); install before usage; a five-line quick start with expected output, shown as an animated terminal recording (asciinema, or VHS, which renders a GIF that plays on GitHub and PyPI); the full command table; config location; exit codes; what is and is not supported on Windows (decision D15). The current README covers about a third of the commands. (S-M) [ux 10.3](analysis/06-cli-ux-and-docs.md) (notes 47 and 48)
- [ ] Concepts page: the broader purpose, the rolling-release problem and what the tool does about it. (S-M) [ux 8.4](analysis/06-cli-ux-and-docs.md) (note 48)
- [ ] Examples: a top-level run guide; a short README per example; one pure TLA+ example with a violated invariant, plus coverage and `--cfg` examples; consistent names, since the folder name becomes the module name; say that the `commons-lang3` jar is committed and where it comes from; point the `sequences-ext` example at the community modules workflow once it exists. Each example runs in CI with its expected result. (S-M) [ux 10.9](analysis/06-cli-ux-and-docs.md) (note 49)
- [ ] CLI reference generated from the code, with CI failing when the checked-in copy drifts. Run the README quick start commands in CI. (M) [ux 10.22](analysis/06-cli-ux-and-docs.md) (note 49)
- [ ] Reference pages: configuration (every key, default, environment variable and file location per platform); how a spec, a cfg file and the project root are found, and where toolsets, modules and run data are stored; exit codes with output modes. (M) [ux 8.4](analysis/06-cli-ux-and-docs.md)
- [ ] Guides (raised list): installation; custom modules (folder layout, how overrides are found, global and project modules, classpath order); a CI recipe. (M) [ux 8.4](analysis/06-cli-ux-and-docs.md)
- [ ] Troubleshooting: GitHub rate limit, proxy and custom CA support through the OS trust store, jar not found, `javac` missing, Java too old. (S) [ux 8.4](analysis/06-cli-ux-and-docs.md)
- [ ] Contributing guide for people, holding the same conventions as the agent instructions. Architecture notes (package map, the output pipeline, the storage layout), written after milestone 5 settles the structure. (S-M) [ux 8.4](analysis/06-cli-ux-and-docs.md) (note 49)
- [x] Project instructions file for AI agents (`AGENTS.md`). Added 2026-11-14.
- [x] Changelog process: an Unreleased section; the entry written in the same commit as the change; fixed headings including Breaking and Removed; a before and after line for every rename or removal. In place since 2026-11-14 as conventions in `AGENTS.md`.
- [ ] Changelog checks: CI warns when code changes without a changelog change (the release script's heading check is in milestone 2). (S) (note 49)
- [ ] Changelog history: mark 0.4.0 and 0.8.0 as never published and correct the two wrong 0.3.1 entries (the cache path and the meaning of `--all`). Leave the rest of the history alone and do not move old tags; the rename is a natural fresh start. (S) [packaging 2.3](analysis/05-packaging-ci-release.md) (note 36)

## Investigation list (pipeline stage 2)

Factual questions the design depends on. Each answer goes in its own file under `docs/research/`, and the item it serves gets a one-line answer and a link to that file (see "Agent pipeline", stage 2). Questions 1 to 11 came from the walkthrough, with additions by the completeness pass inside 1, 3 and 6; questions 12 to 18 were added by the pass.

1. Real TLC output for each supported version (success, violation, deadlock, liveness, SANY and parse errors, assertion failure, coverage), captured as golden files. Also capture: a run with several workers; simulation mode; the version line at startup; a runtime error with a Java stack trace; several errors in one run; a false postcondition (code 2404); progress lines above 999,999 states; and, where they can be provoked, a message nested inside another, text before or after a marker on the same line, and a warning forced by its severity. Milestone 1, first item.
2. Whether TLC can write traces as JSON itself (`-dumpTrace json`), which would avoid value parsing for traces. Milestone 1, parser.
3. How to tell which jar build is running; the state of upstream's official command (open PR 1371) and its entry point, for the hand-off; and which of the `v1.8.0` and `rolling` tags upstream intends to keep moving. Milestone 1, first-run prompt; milestone 1b, thin tools and version shortcuts; milestone 3, naming builds.
4. Whether upstream TLC builds fire the CommunityModules `repository_dispatch` trigger, which would tighten matching module releases to TLC builds by date. Checked so far: CommunityModules releases have empty notes, the build compiles against whatever the `rolling` jar is at that moment, and a release is made on every push to their main branch. Milestone 3, community modules.
5. Whether upstream attaches, or plans to attach, a jar to each CalVer tag; search existing issues and discussions. Milestone 3, older rolling builds.
6. Building `tla2tools.jar` from source at a CalVer tag: build tool, required Java version, time taken, network access needed, and whether the result matches the published jar byte for byte. Also whether a build older than the first CalVer tag (2026-04-27) can be built at its commit with the same result. Milestone 3, older rolling builds.
7. The tag and asset race on rolling builds: whether the jar can change while a download or a version lookup is in progress. Reasoned from code in [merit 3.3](analysis/01-merit-and-landscape.md), not reproduced. Milestone 1, downloads.
8. GitHub tags and releases API ordering and pagination, which "latest stable" depends on today. Milestone 1, downloads.
9. The current state of `nightly.tlapl.us`, and whether a setup GitHub Action, a jbang alias or a mise plugin for the TLA+ tools already exists. Milestone 4, GitHub Action.
10. The tlaplus/Examples manifest format: outcome vocabulary and state counts, as input to the JSON schema. Milestone 4, so it can wait for the second design wave.
11. Sources for download numbers: pypistats or the BigQuery dataset, GitHub release asset counts, repository traffic. Input for the usage statistics session.
12. SANY run on its own, the PlusCal translator and the REPL: main class names, flags, exit codes, and real output for each supported version. Milestone 1b, other tools.
13. What TLC prints when an override class loads, when it fails to load, and when an override does not match its operator. Milestone 1, runner.
14. Whether the commit and CalVer a jar reports about itself can be read without starting a JVM (a manifest entry or a file inside the jar), and what v1.7.4 reports. Milestone 1, downloads and Java.
15. TLC's exit codes for each supported version, what the JVM returns after SIGINT and SIGTERM, whether the JVM keeps running after its parent receives SIGTERM, and which codes are free for the tool's own setup error. [ux 3.4](analysis/06-cli-ux-and-docs.md) and [quality M3](analysis/03-code-quality-and-correctness.md) state these from reading, not from running. Milestone 1, runner; milestone 1b, domain errors; milestone 4, exit codes.
16. How TLC resolves a relative `-config` path (against its working folder or the spec's folder) and whether it accepts an absolute one. Milestone 1, runner.
17. What TLC writes under `-metadir` on each run, whether two runs can share one folder, and what is safe to delete while a run is in progress. Milestone 1, run cache.
18. Whether the GitHub `digest` field is still present for `v1.8.0` and `rolling` and empty for v1.7.4. [quality H4](analysis/03-code-quality-and-correctness.md) calls it unverified; [merit 3.1](analysis/01-merit-and-landscape.md) saw it on 2026-11-09. Milestone 3, digests.

Behaviour on macOS and Windows is not a spike: the CI matrix in milestone 2 answers it for macOS, and Windows is covered by decision D15.

## Maintainer actions and sessions

Things only the maintainer can do, or that are a conversation rather than a work package.

- [x] At sign-off of the completeness pass, update `AGENTS.md`: the broader purpose, the roadmap as the only required reading besides the summary, decisions D1 to D27, and the version rule of decision D27 in its conventions. Done 2026-11-14.
- [ ] Mark the `tlaplus-cli` project as archived on PyPI (decision D1).
- [ ] Confirm two-factor authentication on the GitHub and PyPI accounts; with trusted publishing, account security is the remaining risk. Not verified by any review. [packaging 8](analysis/05-packaging-ci-release.md)
- [ ] Decide, once investigation question 5 is answered, whether to ask upstream to attach a jar to each CalVer tag. A TLA+ maintainer asked for such an archive in 2024. [merit 3.2](analysis/01-merit-and-landscape.md)
  - Answer (question 5): upstream attaches no jar to CalVer tags, and a maintainer said in #1380 that releases are not a package store. [Result](research/05-jar-per-calver-tag.md)
- [ ] Thinking session on usage statistics, carefully, with nothing sent from users' machines without consent (note 6). Starting points: a script that collects download numbers from PyPI (pypistats or the public BigQuery dataset; PyPI's own API no longer gives counts), GitHub release asset counts and repository traffic (views and clones are kept only 14 days, so they must be saved regularly). Later a docs site could add an indirect signal: visits and returning visitors to specific pages, compared with installs, through a cookie-less counter such as GoatCounter or Plausible.
  - Answer (question 11): pypistats, GitHub asset counts and traffic work without new accounts; BigQuery needs a Google Cloud project; `tlaup` is not in pypistats yet. [Result](research/11-download-numbers.md)
- [ ] Capture CI logs soon after a failure worth diagnosing: GitHub's log retention had already expired for every failed run of the old repository when they were checked on 2026-11-14.

## After this roadmap

- Apalache and TLAPS (decision D17). They are separate distributions, not classes in the jar, and need the distribution level reserved in milestone 3.
- Homebrew tap, aimed at macOS users who have Java but do not use Python (note 19). Ship completions with it.
- An AI-facing reporter as a plug-in; a file reporter and others if wanted (decision D8).
- JUnit output and a streaming NDJSON progress mode (decision D22).
- Run the examples straight from the tlaplus/Examples manifest (note 43). The runner skips models that need unsupported tools and reports them as skipped, not failed (note 18).
- Installs from a URL (decision D13), and importing a jar from a local path such as a CI cache, which [ux 6.3](analysis/06-cli-ux-and-docs.md) suggested.
- A docs site, reconsidered once there are eight to ten pages or as a usage signal (note 50).
- nixpkgs and conda-forge packages, once the dependency caps are fixed and the tool is past alpha. [packaging 7](analysis/05-packaging-ci-release.md)

## Deliberately not planned

- Standalone binaries: Java is required anyway.
- SBOM generation, attestations on GitHub release assets and heavier release tooling: disproportionate for one maintainer, and PyPI already carries provenance for the same files.
- An MCP server: four already exist; a clean JSON interface is the less crowded position.
- A Docker image: dropped; reconsider only if users of CI systems other than GitHub ask (note 51).
- A mirror repository that republishes rolling jars, and Maven snapshots as a source (decision D12).
- A Nix flake (removed in 0.8.2).
- First-class `tlaup` options for TLC flags other than `--workers` (decision D24).
- Signed tags (decision D21).
- Windows CI (decision D15).
- Changelog compare links and entries for old versions that have none: history is left alone (note 36).
- Tests inside the sdist for downstream packagers: revisit with nixpkgs or conda-forge.
- Code scanning, and a repository rule that every action is pinned by SHA: neither is set and neither was asked for. The actions with write access are pinned in milestone 2.

## Risks to the plan

- **Upstream ships an official `tla` command.** The rename (decision D1) removed the name clash, and the tool focuses on what an upstream wrapper will not do: locking, digests, override modules. The hand-off: the tool supplies the jar, the classpath, the locked build from the project file and the modules, and upstream's entry point runs on top of it; the tool checks which jar build is running and uses upstream's entry point when it exists (notes 15 and 20). The dedicated `sany`, `pcal` and `repl` commands are the part most likely to be duplicated, which is why they stay thin.
- **Milestone 3 holds the release up.** With one release (decision D6), the order of milestones 1b and 3 matters less than before, but the design note and the build-from-source work are the least certain parts of the roadmap and everything else waits for them.
- **Building from source may not reproduce the published jar.** If the bytes differ (investigation question 6), a digest cannot tie a rebuilt jar to the original, and identity for old rolling builds rests on the commit and CalVer instead. If upstream attaches jars to its CalVer tags, building from source can be skipped altogether; whether to ask is the maintainer's call.
- **Every TLC output change reaches the parser.** Reporters do not parse (decision D8), so only one place needs to follow TLC; the golden files and the never-lose-output rule (decision D9) keep that affordable.
- **Golden files reveal more parser breakage than the two known cases.** The reviews tested one spec per TLC version, so milestone 1 may grow.
- **Matching community modules to a TLC build by date is unconfirmed.** It rests on how CommunityModules releases are triggered (investigation question 4).
- **A long stretch without a release.** Everything accumulates on `main` until 0.9.0; CI on every push, the integration job and the build check are what keep `main` releasable.
