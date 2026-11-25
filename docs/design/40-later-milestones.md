# 40. Milestones 3 to 5: sketch

Not a design. The roadmap says milestones 3 to 5 are designed in a second wave, after the first wave is built, because building it will change what they need; milestone 3 also needs its own design note. This document records, for each, the direction the first wave assumes, the questions still open, and what the first wave leaves room for so the second wave does not have to undo it.

## Milestone 3: reproducibility

Goal (roadmap): a repository can declare its TLA+ toolchain and get the same bytes everywhere.

### Direction

- **The project file** is found by walking up from the spec. It names the pinned build by name, commit, CalVer and SHA-256, the project's modules, and possibly project settings. It is one more layer of configuration (D10) and the marker of the project root. It arrives with a cloned repository, so it is not trusted with everything: it can never set `tool.repository` or `tool.token_hosts`, the two settings that decide where requests and the GitHub token go (decision D41).
- **Version choice order**: flag, then environment variable, then project file, then the global pin (roadmap).
- **Builds are compared by SHA-256.** `rolling` and `v1.8.0` with the same bytes are one build with two names.
- **What tlaup promises to reproduce** (decision D65). tlaup installs the tool jars upstream publishes, and reproduces a build on another machine when a project file names it: the project file is the promise. A build upstream no longer publishes (an older `rolling` build, or one whose release was deleted) that no project file names has no promise of being installable again; an installed build whose tag upstream no longer lists is shown as `installed, not upstream` ([12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache), D64), and nothing more is owed to it. So the milestone does not try to mirror upstream, keep every build ever installed, or rebuild an arbitrary CalVer on request; it makes the build a project file names come back.
- **A named build that upstream no longer publishes** is built from source at the commit the project file records (D12), recording the exact build tools (D28). The commit, not a CalVer tag: every release jar since v1.5.6 carries `X-Git-Revision` ([research 26](../research/26-old-jar-commits.md)) and every installed build records its commit ([12 V1](12-tools-and-downloads.md#v1-version-store)), so the commit is always known, and a release tag upstream deletes or moves does not stop the rebuild. Research 6: Ant, a full clone, 15 to 35 seconds, offline after the clone; never byte-identical to upstream's jar.
- **Community modules** are pinned release downloads chosen by date (D11). Research 4: most TLC builds have no CommunityModules release in their window, so the rule needs a fallback.
- **Storage** moves tools, the pin and modules out of the cache folder into the data folder, as a clean break (D14), with a level reserved for other distributions (D17) and a layout marker.

### What the first wave already did

| Roadmap item (milestone 3) | State after the first wave |
| --- | --- |
| Version identity as a type; typed metadata; one version store | Done ([12 V1](12-tools-and-downloads.md#v1-version-store), decision D37). The second wave changes the layout under the same interface. |
| Record SHA-256 for every installed jar; verify against the `digest` field | Recorded and verified at download where GitHub has a digest ([12 V5](12-tools-and-downloads.md#v5-download-and-verify)). Left: trust for v1.7.4 and older, which have none; `install --locked`. |
| `tools meta sync` | Removed ([23 C1](23-command-layout.md#c1-command-tree)). |
| `tool upgrade` compares only the first of several builds | Fixed ([12 V4](12-tools-and-downloads.md#v4-upgrade-and-pin)). |
| Module build as callable domain code | Done ([13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder)). |

### What the first wave leaves room for

| Need | Where the room is |
| --- | --- |
| The project file as a config layer | `load_settings` merges a list of layers; the project file is one more ([14 F1](14-config-and-cli.md#f1-layered-configuration)). |
| Settings a project file must not set | The schema marks `tool.repository` and `tool.token_hosts` as not settable by a project layer, and the loader already drops them from a layer of that kind with a warning, with a test ([14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay), decision D41). The second wave decides whether more keys join them (`java.opts` runs arbitrary JVM options from a cloned repository and is the obvious candidate). |
| The build chosen from a file found beside the spec | The preflight resolves the spec and a named cfg **before** the tool build and Java (decision D45, [11 R11](11-runner.md#r11-preflight), [02 X1](02-cross-cutting.md#x1-exit-codes) rule 5). The order therefore does not change in milestone 3, and neither does the exit code when two things are wrong at once: a missing spec is 4 in both waves. `sany` and `pcal` use the same order. |
| The project file as the root marker | `find_project_root` keeps its signature; its body changes from the folder heuristic to "walk up to the file" ([11 R10](11-runner.md#r10-project-root)). |
| The data folder | `AppPaths.data` and `TLAUP_DATA_DIR` exist; the store and the registry take their paths from `AppPaths` ([14 F2](14-config-and-cli.md#f2-folder-overrides)). |
| A level for other distributions | Build ids are opaque and made only by the store; the folder shape can change without touching callers. |
| A layout marker | `build.json` and `module.json` carry `schema`; a store-level marker file is one more. |
| One build under two names | Every build records its SHA-256, and the first wave stores one build per name and SHA-256 ([12 V12](12-tools-and-downloads.md#v12-install)), so two names for one jar are two folders today. Making them one is `Build.name` becoming a list of names: a schema change in one reader and one writer, a change to the id rule inside the store, and a decision about what the pin names. |
| A build made from source | `Source.kind` is a field (`github-release` today); `built-from-source` with the toolchain record of D28 is another value. `VersionSpec` already accepts a bare CalVer ([02 X3](02-cross-cutting.md#x3-version-syntax)). |
| Per-project modules | `ClasspathResolver` asks the registry for module folders; "only the modules the project declares" is a filter on that call, and the classpath order is unchanged (roadmap, "Keep"). Override warnings already name the module ([11 R7](11-runner.md#r7-override-modules-that-do-not-load)). |
| "No version" means "what the project asks for" | `tool install` with no version is already not "latest stable" ([12 V12](12-tools-and-downloads.md#v12-install)). |
| Decision D26, the pin follows a newer build of its tag | `install` and `upgrade` are functions over the store; the first wave's `install` leaves the pin where it is and says so ([12 V12](12-tools-and-downloads.md#v12-install)). The rule is a few lines there. |
| Keeping the build that `upgrade` replaces | `upgrade` has a `keep_old` parameter, false for now. |
| `module_path` and `module_lib_path` | Unchanged at run time and undocumented until the design note decides ([14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay)); `module add` never compiles against them (D61, [13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder)). |

### Open questions for the design note

The roadmap's list stands (name and format of the file; whether locked values live in it or beside it; classpath with no project file; where jars live; trusting a digest for v1.7.4 and for a source build; the file as root marker; whether `upgrade` keeps the old build). The first wave adds:

1. **What becomes of the global pin** once a project file exists: the fallback when there is none, or removed in favour of a user-level default?
2. **Two layout breaks in one release.** The first wave changes the store's layout and milestone 3 changes it again. Both are unreleased until 0.9.0, so users see one. If milestone 3 slips to a later release, the second break needs its own changelog entry and reinstall.
3. **Trust for a release without a digest.** Research 18 gives SHA-256 values for v1.7.4 and three older releases from one download each. A small table shipped with tlaup, trust on first use, or both?
4. **A source build's identity.** It has the recorded commit but its own build time and bytes (research 6). Is it the same build as the one upstream published at that CalVer, for the purposes of a project file? Decision D28 says behaviour, not bytes; the file format has to say how that is written.
5. **The CommunityModules fallback rule** when no release falls in the TLC build's window (research 4), and whether date matching is needed at all (research 4's open follow-up: test whether a release built against one rolling jar works on another).
6. **Does the override-class limitation of v1.7.4 need the collecting class after all** (decision D35 chose a warning)? Per-project modules make "one generated class per project" simpler than it is today.
7. **Capabilities for builds between the two supported ones.** A source build of an arbitrary CalVer tag is such a build; the two guessed capability rules ([00](00-overview.md#what-a-build-can-do)) then matter and may need a real check.
8. **When settings are loaded, once the project file is a layer.** In the first wave `AppContext.settings` is loaded once per process, on first use ([00](00-overview.md#application-context)), and nothing it reads depends on the spec. With a project file found by walking up from the spec, the settings of a run command depend on which spec was named, so they cannot be loaded before the spec is resolved, and "once per process" becomes "once per project". The preflight order (D45) already resolves the spec first; what is open is the interface: whether the context holds user-level settings and the preflight returns the merged ones, or the context is built after the spec. Commands with no spec (`tool`, `config`, `doctor`) need a rule too: the project file in or above the working folder, or none.
9. **What a project file may set.** Two keys are excluded already (D41). `java.opts`, a module path outside the repository and anything else that makes a cloned repository run code or reach the network on `tlaup tlc` needs the same question asked of it.
10. **Which build a name means when several are installed.** The first wave lets `install` add a second build of a moving tag beside the first and leaves the pin alone (D26 pending). With a project file naming a build exactly, the leftover builds are cache, and whether tlaup prunes them belongs with "does `upgrade` keep the old build". The roadmap's milestone 3 item on removing the builds nobody needs (added at the stage 3 sign-off, 2026-11-18) is decided with both.
11. **How a build that a project file names is obtained on another machine** (D65). The obvious order is: the store, when a build with the recorded SHA-256 is installed; upstream's release, when it still publishes those bytes under any name (a moved `rolling` no longer does); otherwise a build from source at the recorded commit. Open: what the project file must record for the last step (the commit always; the build tools of D28 once a source build exists; the CalVer for display only); whether a rebuilt jar, whose bytes differ from upstream's, satisfies a file that names upstream's SHA-256 (question 4); whether falling back to a source build is automatic or asked for, since it needs a JDK, Ant, a full clone and the network; and what `tool install --locked` does when only the rebuild is possible.

(Stage 4 review, 2026-11-24: the scope of reproducibility, D65, written into the direction; a rebuild starts from the recorded commit, not from a CalVer tag; question 11 added; `module add` compiles against neither module setting, D61.)

## Milestone 4: automation surface

Goal (roadmap): CI pipelines, editors and coding agents can consume results without scraping.

### Direction and state

| Roadmap item | Direction | State after the first wave |
| --- | --- | --- |
| JSON reporter; `--json` for `tool list`, `module list`, `tool path`; a published schema | A third `Reporter` that prints `RunOutcome` as one JSON document on stdout at the end. The document is `RunResult.to_dict()` plus the exit code, its meaning, the stop reason and the warnings of the preflight. A SANY diagnostic in it carries its file, line and column for the program that reads it, and never the source excerpt (the two lines before, the line with carets, "Error here: ...") that the terminal reporter prints under the editor-form line (decision D66, [22 O3](22-reporters.md#o3-terminal-reporter)); a reader that wants the text has the file. | The model, its `to_dict()`, the Examples-manifest names for outcome and counts, and `describe_exit_status` exist ([10 P3](10-parser.md#p3-result-model), [02 X1](02-cross-cutting.md#x1-exit-codes)). The fields the roadmap says must not be always empty are filled or gone. `make_reporter` is where `--json` attaches ([22 O1](22-reporters.md#o1-reporter-interface)). |
| Editor-style diagnostics in plain output | | Done in the first wave ([22 O3](22-reporters.md#o3-terminal-reporter), [21 S1](21-other-tools.md#s1-sany)). |
| stdout and stderr; `--quiet`, `--verbose`, `--color`; `NO_COLOR`; durations; narrow terminals; glyphs | Root options that set `Ui`'s policy. | The stream rule, the two consoles, `NO_COLOR`, readable durations and no glyphs are done ([02 X2](02-cross-cutting.md#x2-stdout-and-stderr), [14 F6](14-config-and-cli.md#f6-messages)). Left: the three options, and what "verbose" adds (the header details, SANY's progress lines, `javac` warnings, the project root and classpath). `-v` is free ([23 C4](23-command-layout.md#c4-version-flag)). A root option is accepted only before the command on the Typer in use ([14 F10](14-config-and-cli.md#f10-no-tracebacks)); `tlaup tlc Spec --quiet` would be rejected, so the second wave decides between declaring the three on every command and an environment variable for each, as `TLAUP_DEBUG` does for `--debug`. |
| Non-interactive version selection | | `tag@commit` is accepted everywhere; several matches without a terminal is an error for `pin` and `path`, and for `uninstall` means all builds of the name (decision D43); `--yes` covers every prompt of `uninstall`; `tool path` checks the jar and does not pick the first of several ([02 X3](02-cross-cutting.md#x3-version-syntax), [12 V3](12-tools-and-downloads.md#v3-uninstall)). Left: nothing known; the folder-name form is dropped (README, departures). |
| Exit codes | Documentation, and the meaning printed and in JSON. | The scheme is built and tested; the meaning is printed by the terminal reporter. Left: the reference page and the JSON field. |
| `tool list` display | | Installed rows sit next to their upstream row with "update available"; releases with no `tla2tools.jar` are not listed, and an installed build whose tag upstream no longer lists is `installed, not upstream` (D64); `--installed` works offline ([12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache)). Left: a column for stable or prerelease, and showing one build under two names (milestone 3). |
| A generic exec command and jar-path output | `tlaup exec MAIN_CLASS [-- ARGS]` on `run_passthrough` with the tool's classpath. | The launcher and `tool path` exist. |
| A GitHub Action | Its own repository, built after 0.9.0 is published. Research 9: nothing existing runs TLC or makes annotations. | Needs: `tool install` with a token (done), `--auto-install` or a locked install (milestone 3), the JSON result (above). |

### Open questions

1. **Schema naming.** The dictionary keys of the first wave follow the Examples manifest where it has a name (`totalStates`, `distinctStates`, `stateDepth`) and are otherwise chosen here. Camel case throughout, or snake case with the three manifest names as the documented exception? To be settled before the schema is published; renaming is free until then.
2. **`unknown` as an outcome.** In the manifest it means "not recorded" (research 10). A tlaup result that is neither success nor one of the four failures (a parse error, a crash, an interrupt) needs words of its own. Top-up: the first wave now has the verdict (`errors`, `no-error`, `no-error-bounded`, `incomplete`, `not-checked`, and `resumed`; decision D54, [10 P3](10-parser.md#p3-result-model)), which gives those words; how it maps onto the manifest's outcome vocabulary is this question now.
3. **Does the JSON reporter stream?** Decision D22 puts a streaming progress mode after the roadmap; one document at the end is the first-wave assumption, and the event set would serve a streaming form later.
4. **`--json` and progress.** With the stream rule, progress stays on stderr while JSON goes to stdout. The live layout is drawn only when both streams are terminals (decision D40, [02 X2](02-cross-cutting.md#x2-stdout-and-stderr)); whether `--json` to a terminal should draw it, print plain progress lines, or print nothing but the document is open.
5. **Where a root option may be written.** See the row on `--quiet`, `--verbose` and `--color` above.
6. **Should tlaup's own exit code follow the verdict?** Added 2026-11-20 with decision D54. In the first wave tlaup's exit code stays TLC's (D29, the roadmap's "Keep" list), the result line and the JSON are built from the verdict, and when the two disagree tlaup prints one warning naming both ([10 P3](10-parser.md#p3-result-model)). Research 22 captured the disagreements: `-deadlock -continue` with two invariant violations exits 0; `-dfid` with a start depth too small exits 0 while a violation exists. The alternative is a code of tlaup's own when they disagree (for example 12 when TLC says 0 and errors were parsed): it protects a CI script that reads only the exit code, at the cost of the rule that tlaup's code is TLC's, and raw runs, which parse nothing, would then answer differently from parsed runs for the same spec. It is settled here, with the JSON result, because scripts that read the verdict directly change what the exit code needs to carry.

(Stage 4 review, 2026-11-24: no SANY source excerpt in the JSON, D66; the `tool list` state after D64.)

## Milestone 5: structure

The roadmap says to do these when behaviour is pinned down by tests, and that some will fall out of earlier milestones. This is the state the first wave leaves.

| Roadmap item | After the first wave | Left |
| --- | --- | --- |
| One registry for paths and config, built once and passed in; path functions out of `versioning` | `AppContext` and `AppPaths` exist; new and rewritten code takes paths and settings as arguments; `versioning/paths.py` is gone ([00](00-overview.md#application-context), [14 F2](14-config-and-cli.md#f2-folder-overrides)). | Any untouched call site that still reaches for the context from domain code; a lint or test that forbids it. |
| Module build in a modules domain package | Done ([13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder)). | Nothing. |
| Use-case functions in versioning | `install`, `upgrade`, `uninstall`, the remote listing are functions over the store and the client ([12](12-tools-and-downloads.md)). | Nothing known. |
| No printing from domain code | New and rewritten code returns values or raises; the `T20` rule bans `print` ([30 I8](30-ci-and-release.md#i8-lint-rules)). | A check that only `ui`, reporters and commands import the consoles. Download progress is passed in as a callback already. |
| TLATeX and further jar tools | One row in `ENTRY_POINTS` and a thin command each ([21 S4](21-other-tools.md#s4-keeping-them-thin)). | The commands themselves. |
| Reorganise tests to mirror the source tree | The new layout is by boundary, not by source tree: `features/`, `parse/`, `unit/`, `integration/` ([01](01-testing.md)). `unit/` mirrors the source. | The item's intent is met; it can be closed or reworded in the second wave. |
| Housekeeping | Done in passing: explicit command registration; `tlc/compiler.py`, `cache/github.py`, the private names exported for tests, the unused parameters (`asset_name`, `jar_name`, `base_dir`), the cache-file name nothing writes, `InitialStateStatItem`, the duplicated build-selection prompt, the complexity markers, `SanyParser.get_warnings`, compiled regexes. | `versioning/app_version.py` keeps its name; tests stay outside mypy; the ruff groups PERF and FBT stay off. |

### What to check before the second wave designs this

Whether anything is left that is worth a milestone. If the table above holds after the build, milestone 5 is a short list of checks and one or two new thin commands, and could be folded into milestone 4.

## The documentation track

Not designed in this wave; the brief was milestones 1, 1b and 2 in full. What the first wave fixes for it:

- Every item's changelog entry is written in its design section, in the form the conventions require.
- The CLI reference is generated and checked for drift ([23 C5](23-command-layout.md#c5-help-and-the-cli-reference)).
- Reference pages have their content decided: every setting and its environment variable ([14 F1](14-config-and-cli.md#f1-layered-configuration), [F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay)); how a spec, a cfg and the project root are found ([11 R4](11-runner.md#r4-spec-cfg-and-working-folder), [R5](11-runner.md#r5-spec-names), [R10](11-runner.md#r10-project-root)); where state is stored ([00](00-overview.md#where-state-lives-first-wave)); exit codes and streams ([02](02-cross-cutting.md)).
- The examples run in the integration job from a manifest, `docs/examples/examples.toml`, whose format (spec, cfg, expected outcome word, expected state counts) follows the Examples manifest ([01 T9](01-testing.md#t9-integration-tests)). Writing the manifest and the per-example READMEs is the documentation track's work.
- Two README points of the package-metadata item (absolute links, `pipx` and `uvx`) are done in milestone 2 ([30 B3](30-ci-and-release.md#b3-package-metadata)), and the two changelog typos in milestone 1 ([14 F8](14-config-and-cli.md#f8-wording)); the README rewrite and the changelog-history item of this track keep them and have nothing to add for them.
- Things the reference pages must say because the design decided them: `tlaup config set` does not keep comments ([14 F1](14-config-and-cli.md#f1-layered-configuration)); the GitHub token goes to `api.github.com` and to hosts listed in `tool.token_hosts` only ([12 V7](12-tools-and-downloads.md#v7-github-client)); exit code 1 comes from Java or the wrapped tool, never from tlaup ([02 X1](02-cross-cutting.md#x1-exit-codes)); `--debug` goes before the command.
- Limits to document, found by the research and kept by design: v1.7.4 loads overrides only from `tlc2.overrides.TLCOverrides` (D35); GitHub's digest does not protect against a compromised release (research 18); older rolling builds cannot be downloaded (research 5); `pcal` rewrites the spec in place; the REPL's history file is outside tlaup's folders.
