# Behaviour of tlaup 0.8.x to preserve: the inventory

Written 2026-11-22; reviewed with the maintainer on 2026-11-24.

## What this is

The old tests (`tests/unit/`, `tests/integration/`) are deleted in the first testing package (03b), not one by one as each command is rewritten (decision D62, [01 T11](01-testing.md#t11-the-existing-tests)). This file lists what a user can observe in tlaup 0.8.x, so that the rewrite does not drop any of it by accident. Each row says whether the redesign keeps the behaviour, and where it is specified, or changes it on purpose.

From the review on, this file is the list of requirements that D62 names. Every row that is kept has an owner package and a test in 01's forms; the owner writes the test and its pull request names the rows it covers. Package 59 closes the wave by checking that every kept row has a test that exists and passes (01 T11). A change to a row's outcome is a design change and goes to the maintainer.

Statuses:

- **kept, specified**: a design section specifies it. The note says whether that section names a test.
- **kept, not specified**: the design does not mention it and nothing replaces it, so it survives. The note gives the owner package and the test, confirmed by the maintainer on 2026-11-24.
- **changed on purpose**: the design changes or removes it, with the section or decision cited.
- **decided (Dnn)**: the draft found the design silent or contradictory here; the maintainer settled it on 2026-11-24 by the decision named. The words after the colon give the outcome, and the note gives the decision, the owner and the test.

Links are relative to `docs/design/`, where the file now sits. Package numbers are those of [the packages index](../packages/README.md). "Feature" means a pytest-bdd scenario (01 T5), in-process unless it says "real process"; "unit" means plain pytest on real files in a temporary folder with no patching (01 T1, T12).

### What was read

- All of `src/tlaup/`: `cli.py`, every command under `cmd/`, and `versioning/`, `java/`, `config/`, `project/`, `tlc/`, `cache/`, `ui.py`, the packaged `default_config.yaml`, and `pyproject.toml`.
- Every file of `tests/unit/` and `tests/integration/`, with their conftests and the `naming_*` fixtures, read for what each test tries to protect. None was run.
- `docs/roadmap.md`, section "Keep"; [01](01-testing.md) T1, T5 (start), T7 to T12, including T11's list of behaviour with no test.
- The design index (decisions and departures tables); [02](02-cross-cutting.md) X2 to X4; [11](11-runner.md) R4 to R12, with R1, R2 and R6 in part; [12](12-tools-and-downloads.md) in full; [13](13-modules-and-java.md) in full; [14](14-config-and-cli.md) F1 to F11; [20](20-groundwork.md) G1 and G2; [21](21-other-tools.md) S1 in part; [22](22-reporters.md) O2, O3, O5; [23](23-command-layout.md) C1 to C4; one line of [30](30-ci-and-release.md) H3; [00](00-overview.md) headings and the run pipeline only.
- The packages index (package table, design-section traceability, questions and readings), and, for single points, parts of packages 03, 25, 29, 30, 31, 33, 45 and 52.

### What was not read

`docs/analysis/` and `docs/research/` (as instructed); `tests/stateful/` (new tests of the formal check, not old tests); `tests/fixtures/research/`; design 10 apart from searches, 40, and the review and top-up files; most package files. Claims about a package come from the parts named above. Where a row rests on inference rather than on code or text that was read, it says "(inferred)".

## Inventory

### Tool versions and the store

| # | Behaviour | Where it is today | Status | Note |
| --- | --- | --- | --- | --- |
| T1 | `tools install VERSION` downloads that release's `tla2tools.jar` from GitHub and installs it. | `cmd/tools/install.py` `install`; `versioning/downloader.py` `download_version`; `tools/test_install.py` | kept, specified | V12, with `tool_install.feature` named. The version is now also accepted without the `v` (X3). |
| T2 | The first build installed is pinned automatically; later installs, `--force` included, never move an existing pin. | `install._auto_pin_if_needed`; `test_tlc_install_auto_pins_first`, `test_install_second_version_does_not_move_pin`, `test_install_force_does_not_move_pin` | kept, specified | V12 "The pin"; test named ("first install pins, second does not"). |
| T3 | An install treats a missing pin file, or a pin naming a folder that is gone, as "nothing pinned" and pins. | `versioning/paths.py` `get_pinned_version_dir`; `test_install_auto_pins_when_pin_file_missing`, `..._when_pinned_dir_deleted` | kept, specified | V12 and V3 (review finding FC5, decision D50). No feature naming the dangling-pin case for `install` was found in V3 or V12; the store's stateful test models it (inferred from V12's note on the spec's `PinStep`). |
| T4 | An empty pin file counts as "nothing pinned", for install and for every reader. | `get_pinned_version_dir` (empty text returns `None`); `test_install_auto_pins_when_pin_file_empty` | kept, specified | [12 V1](12-tools-and-downloads.md#v1-version-store) now says it: an empty pin file, or one holding only white space, is no pin, as a missing one is, and `install` pins over it. Owner 23: a store unit test (`pinned()` is `None` for an empty `pin`) and `install` pinning after it. Confirmed 2026-11-24. |
| T5 | Installing a build that is already installed downloads nothing and says so; `--force` downloads it again. | `install`; `test_tlc_install_already_installed`, `test_tlc_install_force` | kept, specified | V12's table, each row a scenario. Details change: "already there" is name plus SHA-256, the line drops "Successfully installed" (F11), and `--force` repairs in place. |
| T6 | `tools install` with no version installs the newest stable release without asking. | `install` (`next(... not v.prerelease ...)`); `test_tlc_install_selects_latest` | changed on purpose | V12, Breaking: asks stable or rolling, or reads `TLAUP_AUTO_INSTALL`, else exit 2. |
| T7 | "Stable" is never a prerelease. Today it can be: with no stable release in the list it falls back to the first entry. | `install` (`versions[0]` fallback) | kept, specified | X3, X4, V8 `stable_of`; test named ("a list with only prereleases has no stable"). One of T11's "no test today" items. |
| T8 | An unknown version name is an error naming it. | `install`, `upgrade`, `pin`, `path`: "Version X not found" | kept, specified | X3, F11 (`VersionNotFound`, code 4, with the closest tag); one `errors.feature` scenario. One of T11's items. Exit code changes (X1). |
| T9 | A failed download leaves no half-installed build behind. | `downloader.py` (removes the folder on error); `version_manager/test_download.py` | kept, specified | V5, V11; T6 rows and "after a failed download the installed builds are unchanged". |
| T10 | `--force` deletes the installed build before downloading the new one. | `download_version(force=True)`; `test_download_version_force_removes_existing` | changed on purpose | V5, V12: the installed build stays until its replacement is verified. |
| T11 | A download shows a progress bar with size and speed. | `downloader._download_jar` (Rich `Progress`, on stdout by Rich's default (inferred)) | kept, specified | X2 lists download progress on stderr. No test named. |
| T12 | Requests to GitHub carry a User-Agent and a timeout, and TLS uses the operating system's trust store. | `downloader.py`, `versioning/api.py`, `tlaup/__init__.py` (`truststore`) | kept, specified | V7 (`User-Agent: tlaup/<version>`, 10 s connect and 30 s read), roadmap "Keep"; truststore moves into the client (F9). V7's unit tests. |
| T13 | `tools install <URL>` installs a jar from an address. | `install` URL branch; `test_version_manager_url.py`, `test_urls.py` | changed on purpose | V6, D13: refused as a usage error. |
| T14 | Two different upstream builds of one tag can be installed side by side and never overwrite each other. | folder `<tag>-<sha7>`; `test_tlc_list_enhanced` | kept, specified | V1, roadmap "Keep"; unit tests named (two builds of one commit with different CalVers, two jars with one name and commit). |
| T15 | Builds live in `<cache>/tools/<tag>-<sha7>/` with `meta-tla2tools.json`; the pin is `tools-pinned-version.txt`, a plain text file. | `versioning/paths.py`, `metadata.py` | changed on purpose | V1, D14: `<cache>/tool/<id>/build.json` and `pin`, no migration. The pin stays a plain text file (Keep). |
| T16 | Install starts Java to record the TLC version string, and records an empty string without Java. | `metadata._extract_tlc_version`; `test_write_version_metadata` | changed on purpose | J3, V5: identity read from the jar's manifest with no JVM. |
| T17 | Old layouts are migrated or used: the `tlc` folder, the symlink pin, the old pin file name, a jar directly in the cache folder. | `paths._migrate_legacy_pin`, `tlc/compiler.get_tlc_jar_path`; `test_migration.py` | changed on purpose | V10. |
| T18 | `tools list` prints a table with Version, Tag/SHA, Published (date only), Status and Pinned (a check mark). | `cmd/tools/list.py`; `test_list.py` | kept, specified | V8 "`tool list` in the first wave"; `tools_list.feature` against expected files. The column becomes "Build", Published is the asset's update date, and rows follow X4. |
| T19 | `tools list` shows an installed build next to the current upstream build of the same tag, one row each, "installed" and "available". | `list_versions`; `test_tlc_list_enhanced` | kept, specified | V8, roadmap "Keep": "installed, update available"; test named. |
| T20 | `tools list` marks an installed build whose tag upstream no longer lists as "local only". | `list_versions`; `test_tlc_list_shows_local_only` | decided (D64): kept, changed | Such a build gets the status `installed, not upstream`, with no hint about not uninstalling it ([12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache)). Owner 29. Feature: with the `releases` recording and an installed build whose tag it does not list, `tool list` shows that build with `installed, not upstream`, and stdout and stderr hold no uninstall hint. |
| T21 | `tools list` shows only releases that carry a `tla2tools.jar`. | `api._process_remote_versions` | decided (D64): kept | `tool list` hides a release with no `tla2tools.jar`; the cached release list still holds it ([12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache)). Owners 25 (the cache keeps every release as it came) and 29 (the list hides them). Unit (25): the cache written from the `releases` recording holds all 17 releases. Feature (29): `tool list` on that recording shows none of the seven without a jar. |
| T22 | `tools list` works offline: within an hour it uses the cached list with no request; when GitHub fails it shows the older cached list marked as cached; with no cache it lists the installed builds and warns. | `api.fetch_remote_versions`; `tools/test_fetch_cache.py`; `list_versions` | kept, specified | V8 (the four states, roadmap "Keep"); unit tests at 59 and 61 minutes; `tools_list.feature` per state. Age now comes from `fetched_at`, not the file's time; the warning goes to stderr (F6). One of T11's items. |
| T23 | A damaged lookup cache file is ignored, not a crash. | `cache/github.load_github_cache`; `test_fetch_remote_versions_corrupt_cache` | kept, specified | V8; unit test named. |
| T24 | `install`, `upgrade` and `meta sync` use the one-hour cached list and fall back to a stale one offline. | `fetch_remote_versions` | changed on purpose | V8, V12, V4: install and upgrade always ask GitHub; with the build installed and no network, a warning and exit 0. |
| T25 | The remote list joins the first 30 tags with the first 30 releases; a build's commit is the tag's. | `api._fetch_from_api`, `_process_remote_versions` | changed on purpose | V8 (releases only, all pages), V5 (commit from the jar). |
| T26 | A release's prerelease flag and publication date are recorded. | `api`; `version_manager/test_remote.py` | kept, specified | V8 `Release`, V1 `Build.prerelease`; T6 recordings. |
| T27 | `tools pin VERSION` pins an installed build; a version not installed is an error that says to install it. | `cmd/tools/pin.py`; `test_pin.py` | kept, specified | V4; `tool_pin.feature` named. Code 4. |
| T28 | With several installed builds of one name, `pin` lists them and asks which. | `pin`; `test_tlc_pin_interactive_choice` | kept, specified | V4, X3, D23: asks on a terminal, code 2 without one; a pty scenario is named. A wrong answer now asks again. |
| T29 | `tools path [VERSION]` prints the absolute path of the pinned (or named) build's jar on one line and nothing else; it fails when nothing is pinned or the version is not installed. | `cmd/tools/path.py`; `test_path.py` | kept, specified | Roadmap "Keep", X2, C1, C2 (an outline for `path`). With several builds of one name it is now code 2 (X3, Breaking; it printed the first). |
| T30 | `tools path` fails when the pinned folder holds no jar. | `path`; `test_tlc_path_jar_missing` | kept, specified | V1: such a folder is not a build, so `PinnedBuildMissing`. Unit test named in V1. |
| T31 | `tools uninstall VERSION...` removes the named builds; removing a build that is not pinned leaves the pin alone. | `cmd/tools/uninstall.py`; `test_uninstall_non_pinned_keeps_pin`, `test_tlc_uninstall` | kept, specified | V3; `tool_uninstall.feature` named. |
| T32 | Removing the pinned build says it was pinned and moves the pin to the "latest" remaining build, or clears it when none is left. | `uninstall`; `test_uninstall_pinned_falls_back_to_latest`, `test_pin_lifecycle_install_install_uninstall`, `test_uninstall_pinned_fallback_uses_metadata_date` | changed on purpose | V3 (design-agent decision): the pin is cleared, never moved. The "was pinned" message and the cleared pin stay (`test_uninstall_pinned_last_version_clears_pin`, `test_tlc_uninstall_pinned_warns`). |
| T33 | With several builds of one name, `uninstall` asks which, with "all" as the default answer. | `_resolve_uninstall_targets`; `test_uninstall_interactive_choice` | kept, specified | V3, D43; pty scenarios named. Without a terminal all are removed; a wrong answer asks again (was skipped). |
| T34 | `uninstall --all` asks for confirmation; `-y` skips it. | `uninstall` | kept, specified | V3's table. `-y` becomes `--yes` only (C1); answering no exits 0 (was 1); no terminal and no `--yes` is code 2. |
| T35 | An argument that matches nothing is warned about and the others are still removed. | `_resolve_uninstall_targets` | changed on purpose | V3: nothing is removed, code 4. |
| T36 | A removal that fails is printed, and the command still exits 0. | `_remove_path` | changed on purpose | V3: exit 5, pin untouched. |
| T37 | `uninstall default` removes the old jar in the cache folder. | `_resolve_uninstall_targets`; `test_tlc_uninstall_default` | changed on purpose | V10. |
| T38 | `uninstall NAME --all -y` is accepted and removes everything. | `uninstall`; `test_uninstall_all_flag` | changed on purpose | C1: a version and `--all` together are a usage error. |
| T39 | `tools upgrade [VERSION]` with no argument upgrades the pinned build's name; when current it says "already up to date"; a name not installed is installed instead. | `cmd/tools/upgrade.py`; `test_upgrade.py` | kept, specified | V4; `tool_upgrade.feature` named. |
| T40 | Upgrade removes the old build of that name and moves the pin when the old one was pinned. | `upgrade`; `test_tlc_upgrade` | kept, specified | V4 step 4; test named. With several builds of the name only the newest is replaced. |
| T41 | Upgrade with no argument and nothing pinned is an error. | `_resolve_upgrade_target`; `test_resolve_upgrade_target_no_args_no_pin` | kept, specified | V4 step 1 (code 3); test named. |
| T42 | Installed builds sort by version number, then `published_at`, then folder time, then name; `rolling` sorts last; the sort picks the "latest" build. | `resolver._version_sort_key`, `resolve_latest_version`; `test_resolution.py` | changed on purpose | X4, D32, V2: `rolling` first, then numbers, then build time; nothing picks "the latest installed". |

### Modules

| # | Behaviour | Where it is today | Status | Note |
| --- | --- | --- | --- | --- |
| M1 | `modules add PATH` registers the folder under the folder's own name, replacing a module already registered under that name. | `cmd/modules/add.py` `add_module`; `test_modules_add_success` | kept, specified | M1, M2 ("Replaced module X"), F7 help. The name rule is new (M1). |
| M2 | It copies the folder's `lib/`, `modules/` and `tlc2/`. | `add_module` `copy_subfolder` | kept, specified | M2 step 2. |
| M3 | It also copies `test/` or `tests/`. | `add_module` | changed on purpose | M2: no longer copied. |
| M4 | It compiles the `.java` files under `modules/tlc2/overrides/` and `tlc2/overrides/`, searched recursively, against the tools jar and the module's own `lib/*.jar`, into `classes/`. | `add_module`; `test_modules_add_nested_overrides` | kept, specified | M2 step 3, M3; `modules.feature` asserts the logged `javac` command. `-encoding UTF-8 --release 11` and a timeout are added (M3). |
| M5 | The compile classpath also holds the other registered modules' `classes/` and `lib/*.jar`, and the jars of `module_lib_path`, so one module can compile against another. | `ClasspathResolver.resolve(ResolveMode.COMPILE)`; `test_cached_modules_resolved` (compile half); CHANGELOG 0.7.0 | decided (D61): changed on purpose | The compile classpath of `module add` is narrow: the build's `tla2tools.jar` and the module's own `lib/*.jar`, nothing from other registered modules, nothing from `module_lib_path` (a run-time setting only), nothing else on the machine, so that a module compiles the same on every machine ([13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder), with its Changed entry). Widening it later is additive. Owners 30 (a unit test: `build_module` is given the narrow classpath) and 31 (the command-level test, since only `module add` sees the settings): with a second module registered and `module_lib_path` set, the logged `javac` command's `-cp` holds exactly the build's jar and the module's own jars. |
| M6 | A module with no Java sources is added with no tools jar and no `javac`. | `add_module` (looks for the jar only when there are Java files) | kept, specified | M2 step 3; test named (neither fake is started). |
| M7 | It writes `classes/META-INF/services/tlc2.overrides.ITLCOverrides` listing every class that implements `ITLCOverrides`, with its package. | `add.find_override_classes` | kept, specified | M3 (read from the class files; a service file in the source is used as written); unit tests named. One of T11's items ("finding override classes"). |
| M8 | When no override class is found it writes the configured default class name. | `add_module` (`config.tlc.overrides_class`) | changed on purpose | M3: no service file and a note. |
| M9 | A compile error prints "Compilation failed!" with the compiler's output and removes the new copy (the previous build was already deleted). | `add_module`; `test_modules_add_compilation_failure` | kept, specified | M2: the previous build stays, `ModuleBuildError` (5) shows the output and the classpath; test named. |
| M10 | With Java sources and no tools jar, or no `javac`, it stops with the command to run next. | `add_module` | kept, specified | M2 step 3 (`NoToolsInstalled`, `NoPinnedBuild`, `JavacNotFound`, code 3); `no javac exits 3` named. |
| M11 | It writes `metadata.json` with the name and the local build time. | `add_module` | changed on purpose | M2, F8: `module.json`, UTC. |
| M12 | `add` and `remove` delete every TLC run folder. | `clear_tlc_run_cache` calls | changed on purpose | M2, R6. |
| M13 | `modules list` prints a table of module names and build times, sorted by name. | `cmd/modules/list.py`; `test_modules_list` | kept, specified | M2 (`Registry.list()`), F8 (UTC shown, test named). |
| M14 | `modules list` with nothing registered says so ("No modules currently added."). | `list_modules` | kept, not specified | Confirmed 2026-11-24: stdout stays empty for scripts, and one note on stderr is required, not optional. Owner 31. Feature: with nothing registered, `module list` exits 0, stdout is empty and stderr holds the note. |
| M15 | A module folder with no or damaged metadata is still listed, as "Unknown" or "Corrupt Metadata". | `list_modules` | changed on purpose | M2: `list()` returns only folders with a valid name and a readable `module.json`; package 31 gives such folders to `doctor` (46). |
| M16 | `modules remove NAME` deletes the module; an unknown name is an error. | `cmd/modules/remove.py`; `test_modules_remove`, `test_modules_remove_nonexistent` | kept, specified | M1 and package 31 (`ModuleNotFound`, code 4); scenarios named. The name is now checked (M1). |
| M17 | Every registered module takes part in every run: its `classes/` before the tools jar, its `lib/*.jar` on the classpath, its `modules/` in `-DTLA-Library` and on the classpath. | `ClasspathResolver._resolve_paths`, `resolve`; `test_cached_modules_resolved` | kept, specified | M2 and roadmap "Keep" (the managed-modules layer); package 30 has the test. Milestone 3 changes which modules take part. |
| M18 | Registered modules are applied in order of their names. | `sorted(managed_dir.iterdir())` in `classpath.py` | kept, specified | [13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder) now says it (`Registry.list()` by name, the order a run applies). Owner 30, whose test asserts it. Confirmed 2026-11-24. |
| M19 | A module's top folder also counts as a module folder and a jar folder (the flat form). | `_resolve_paths` "Legacy fallback" lines | changed on purpose | V10. |
| M20 | Override classes of several registered modules are passed together in one property, joined with `os.pathsep`. | `runner.get_override_classes`; CHANGELOG 0.7.0 | kept, specified | R7 part 1 (first wins, no duplicates), roadmap "Keep" (`os.pathsep`); feature named ("the logged command's property names both"). |

### Running TLC

| # | Behaviour | Where it is today | Status | Note |
| --- | --- | --- | --- | --- |
| R1 | `tlc SPEC` runs TLC on the spec with the pinned build in tool mode, formats the output, and exits with TLC's code. | `cmd/tlc.py` `tlc`; `tlc/runner.py` `run_tlc` | kept, specified | X1, G1, roadmap "Keep"; `tlc_run.feature`. |
| R2 | Java's version is checked against `java.min_version` before every run. | `run_tlc` `validate_java_version` | kept, specified | R11 step 4, J3 (now remembered); features named. |
| R3 | With no jar: "tla2tools.jar not found. Run 'tlaup tools install' first.", exit 1. | `build_tlc_command`, `tlc --version` callback | changed on purpose | V9, R11: the first-run prompt, or `NoToolsInstalled`, `NoPinnedBuild`, `PinnedBuildMissing` (code 3). |
| R4 | Any failure to start Java is reported as "'java' not found", exit 1. | `run_tlc` | changed on purpose | R1, J2, J3, X1. |
| R5 | `tlc` with no SPEC prints "Missing argument 'SPEC'." and exits 1. | `tlc`; `test_tlc_missing_spec_argument` | changed on purpose | C1: a required argument, Typer's message, code 2. |
| R6 | TLC runs in the project root, or the spec's folder, with the spec given relative to it. | `run_tlc` `cwd`, `build_tlc_command` `spec_arg`; `tlc/test_raw.py` | changed on purpose | R4, D34: the folder tlaup was started in, with an absolute spec. |
| R7 | TLC gets a `-metadir` under tlaup's cache, so TLC's state never lands in the project. | `run_cache.get_spec_run_dir`; `test_build_tlc_command_includes_metadir` | kept, specified | R6, roadmap "Keep"; tests named (R6, R9). |
| R8 | One `-metadir` per spec (name plus a hash), reused across runs, older ones of the same name deleted. | `run_cache.py`; `test_run_cache.py` | changed on purpose | R6, R12: one folder per run, no fingerprint. |
| R9 | `tlc --coverage` passes `-coverage 1` and, after the run, prints an "Action Coverage" table and the spec's source with each line's distinct-state count, marking lines never reached. | `cmd/tlc.py`, `formatter.render_coverage_table`, `render_inline_coverage`; `test_render_coverage` | kept, specified | R8 (`-coverage 1`), O2 ("kept, rewritten"), O3; tested through O6's expected files. The "never reached" mark is not named in O3; the expected files will show whether it survives. |
| R10 | `tlc --raw` prints TLC's own output unparsed, without `-tool`. | `run_tlc(raw=True)`; `test_run_tlc_raw` | kept, specified | X2, R9; `tlc_raw.feature` (real process). TLC's stderr is no longer merged into stdout (changed, X2). |
| R11 | `tlc --show-command` prints the Java command and exits 0 without running TLC; with `--cfg` and `--coverage` it includes them. | `tlc`; `test_tlc_show_command.py` | kept, specified | R9: now exact (with `-tool`, flags in place), shell-quoted, and creates nothing; tests named. |
| R12 | `--show-command` and a run check the spec and a named `--cfg` first and fail with one message. | `tlc`; `test_tlc_with_missing_cfg` | kept, specified | R11, D45; `tlc_errors.feature`. |
| R13 | `--refresh-interval` is accepted, and `tlc.refresh_interval` defaults to 1.0. | `tlc` option, `config/schema.py`; `test_tlc_rich.py` | kept, specified | O5 (it now takes effect; unit test on `Live`), F3. |
| R14 | Ctrl-C stops TLC, reads what TLC still prints, and shows the result so far as stopped ("canceled"). | `run_tlc` `except KeyboardInterrupt`; `test_run_tlc_keyboard_interrupt`; components | kept, specified | R2, G3, F8 ("interrupted"), O3 (incomplete result line); `tlc_signals.feature` (real processes) and T9. Exit code becomes 130. One of T11's items. |
| R15 | Lines TLC prints outside its messages (the spec's `Print`, anything unrecognised) are shown. | `TlcParser.process_line` `output_lines`; `cmd/tlc.py` | kept, specified | D9, O3. |
| R16 | Progress statistics are printed as they arrive, numbers with thousands separators (a fixed-width table with Diameter, Found, Distinct, Queue, Date, Time when not on a terminal). | `StatsTableFormatter`; `test_stats_table_formatter` | kept, specified | O3: one progress line per message on stderr, thousands separators. The table form is changed on purpose. |
| R17 | On a terminal a footer shows the status, the elapsed time and "Stop with Ctrl + C". | `StatusFooterRenderable` in `Live`; `test_status_footer_renderable` | changed on purpose | D40, O4: the full-screen layout. |
| R18 | A counterexample shows every state with its action and module, each variable marked as added, changed or unchanged against the state before. | `formatter.render_error_trace`, `diff_values`; `test_tla_value_diffing` | kept, specified | O2 (`diff_values` kept), O3 (`*` on a changed variable, highlight of the changed part), O6 expected files. The tree form and the alphabetical order of variables are changed on purpose (O3, Rejected). One of T11's items. |
| R19 | An error with no trace prints its message lines. | `cmd/tlc.py` | kept, specified | O3, P10 (message and trace always shown). |
| R20 | SANY errors found during a run are reported with the file and line. | `render_sany_error` | kept, specified | O3, S1 (`path:line:col: error: message`). |
| R21 | A SANY error also shows the source around it: two lines before, the line itself with `▲` marks under the columns, "Error here: line L, col A to B", and two lines after; "(Source code unavailable)" when the file cannot be read. | `render_sany_error`; `test_render_sany_error` | decided (D66): kept | The excerpt stays in terminal output, under the editor-form line, for `tlc` and for `sany` alike; it is never part of milestone 4's JSON, which carries file, line and column for machine consumers ([22 O3](22-reporters.md#o3-terminal-reporter), [21 S1](21-other-tools.md#s1-sany)). Owners 38 (the terminal reporter, for `tlc`) and 41 (`sany`). Test: the expected files of a SANY-error case, through O6 for `tlc` and through S1's feature for `sany`, show the parts of the excerpt under the editor-form line, the two lines after included; the "unavailable" note is dropped (settled 2026-11-24). |
| R22 | The run ends with "Model checking completed successfully." or "failed with N error(s)", a warning count, and "Duration: Nms". | `tlc` | changed on purpose | O3, D54: a result line from the verdict, with TLC's code and the duration. |
| R23 | The header "Starting TLC model checker (version X)." takes X from a second Java start. | `get_tlc_version`, `HeaderComponent` | changed on purpose | J3, O3: the build from the store, then TLC's own version line. |
| R24 | Override classes are taken from the service file of each classpath folder, or `tlc2.overrides.TLCOverrides` when a folder holds that class, without duplicates, and passed as `-Dtlc2.overrides.TLCOverrides`. | `runner.get_override_classes` | kept, specified | R7 part 1 (extended to jars); unit tests named. |
| R25 | Default JVM options `-XX:+IgnoreUnrecognizedVMOptions -XX:+UseParallelGC`. | `default_config.yaml`, `JavaConfig` | kept, specified | J1, F3. |
| R26 | `JAVA_OPTS` replaces the configured JVM options. | `JavaConfig.check_env_opts`; `test_settings.py` | changed on purpose | J1, D20: `TLAUP_JAVA_OPTS` and `--java-opt` add to them. |
| R27 | The main class comes from `tlc.java_class`. | `build_tlc_command` | changed on purpose | F3. |
| R28 | A trace variable's value is parsed into its structure (sets, sequences, records, functions, nesting); when it cannot be parsed, the raw text is kept. | `tlc/values.py` `parse_variable_value`; `test_values.py` | kept, specified | P7, T7 (property tests: round trip, total, never a partial tree), roadmap "Keep". Owner 11. |
| R29 | A message's severity (1 or 2 error, 3 warning) decides whether it is an error or a warning, whatever its code says. | `TlcParser.process_line` | kept, specified | P3, P4, O3 (unknown codes with error or warning severity); golden files. Owners 10, 13. |
| R30 | Start time, progress, finish time and duration, and coverage are read from TLC's messages. | `TlcParser`; `test_parser.py` | kept, specified | P3, golden facts (08, 13). The old tests used invented output (T11). |
| R31 | SANY's output is split into errors and warnings with module and range. | `tlc/sany.py`; `test_sany.py` | kept, specified | P8, golden files (12). |
| R32 | Integration: after `modules add` of `docs/examples/QueueModule`, `tlc queue` succeeds and the Java override runs. | `tests/integration/test_tlc_integration.py` | kept, specified | T9 row; owner 52 (with v1.7.4's expected warning and failure). |
| R33 | Integration: a project's own compiled `tlc2.overrides.TLCOverrides` in `classes/` is loaded in a real run, as is a class named after its module through a service file. | `tests/integration/test_naming.py` | kept, specified | [01 T9](01-testing.md#t9-integration-tests) has the row: the spec of `tests/fixtures/naming_fixed/` with its `TLCOverrides` compiled into the project's `classes/`, on both builds, asserting the override's printed marker. The second case is the QueueModule row. Owner 52. Confirmed 2026-11-24. |
| R34 | Integration: the `sequences-ext` example (CommunityModules overrides) runs with its overrides loaded. | `tests/integration/test_community_modules.py` | kept, specified | [01 T9](01-testing.md#t9-integration-tests) has its own row, on both builds, until the examples manifest exists and takes it in. Owner 52. Settled 2026-11-24. |

### Spec, cfg and project root

| # | Behaviour | Where it is today | Status | Note |
| --- | --- | --- | --- | --- |
| S1 | A SPEC that names an existing `.tla` file is used as given. | `runner.resolve_spec_file`; `test_resolution_scenarios.py` (`explicit_extension`) | kept, specified | R5 step 2; the seven old cases move into R5's unit test. Any other existing file is now refused (R5, changed). |
| S2 | A SPEC without `.tla` has it added. | `resolve_spec_file` (`with_suffix`) | kept, specified | R5 step 3: appended, so `Foo.v2` looks for `Foo.v2.tla` (a fix). |
| S3 | A SPEC is also looked for as `<parent>/spec/<name>.tla`. | `resolve_spec_file`; `inside_spec_dir`, `inside_spec_dir_path` | kept, specified | R5 step 3, F7; unit test named. |
| S4 | A spec that cannot be found is an error naming it. | `resolve_spec_file`; `not_found_*` cases | kept, specified | R5 (`SpecNotFound` with the paths tried, code 4). |
| S5 | `--cfg` takes a name or a path: an absolute path as given; otherwise beside the spec, then in the working folder, then in the project root, with `.cfg` added when missing. | `runner.resolve_cfg_file`; `test_runner.py` cfg tests | kept, specified | R4 step 5, roadmap "Keep". R4's tests cover the value passed and `foo` without `foo.cfg`, not the search order. Owner 32: unit test with the same name in all three places (spec's folder wins), then two, then one. A file named exactly as typed, without `.cfg`, is no longer taken (changed, R4). |
| S6 | The cfg reaches TLC as its bare name, or relative to the project root. | `resolve_cfg_file` `cfg_arg` | changed on purpose | R4 step 4: relative to the spec's folder (fixes TLC reading another file). |
| S7 | With no `--cfg`, tlaup checks nothing and TLC uses `Spec.cfg`. | `build_tlc_command` | kept, specified | R4 step 6. |
| S8 | The project root is the spec's folder or its parent, whichever first has `classes/`, `modules/` or `lib/`. | `project/core.find_project_root`; `spec/test_project.py` | changed on purpose | R10: the parent only when the spec's folder is `spec`, `specs`, `test` or `tests`; never the home folder. Tests named. |
| S9 | A spec in `tests/` (or `spec/`) under a folder with `modules/` gets that folder as `-DTLA-Library`, and its `lib/*.jar` on the classpath. | `spec/test_classpath.py` | kept, specified | R10 rule 2; R10 names "spec in `tests/` with `modules/` in the parent (root)". |
| S10 | The project's `classes/`, `modules/` and `lib/*.jar` take part in the run; command line, then project, then config, then registered modules. | `ClasspathResolver`; `java/test_classpath.py` (`test_hierarchy_priority`, `test_tla_library_property`, `test_get_project_path`) | kept, specified | Roadmap "Keep" and M2 ("the precedence order is unchanged"). Its test is S11's whole-list unit test: [30](../packages/30-module-build.md) writes the new test file and 33 extends it to the layers and to C6. The old `tests/unit/java/test_classpath.py`, which 33 had planned to extend, goes in 03b. |
| S11 | The runtime classpath order: project `classes/` first (ahead of the tools jar, so its classes win), then the TLA+ module folders, then each registered module's `classes/`, then the tools jar, then the jars (project, `module_lib_path`, registered modules), each folder's jars sorted, duplicates dropped. | `ClasspathResolver.resolve`, `_resolve_paths`; `test_resolve_runtime_order`, `test_deduplication` | kept, specified | The design now states the whole runtime order, with shadowing and de-duplication ([13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder)). Owner 33. Unit on the resolver with real folders and jars under `tmp_path`: the whole list equals an expected list, with one jar reachable twice. Package 30 writes the test file and 33 extends it. Confirmed 2026-11-24. |
| S12 | `-DTLA-Library` lists the module folders in the same layer order, joined with `os.pathsep`, and is left out when empty. | `get_tla_library_property` | kept, specified | G1 (joined with `os.pathsep`, left out when empty; builder unit test with an empty list), roadmap "Keep" (order). The order test is 33's, as S11. |
| S13 | A spec with no project root adds nothing of the working folder's to the run. | `test_tlc_no_project_dirs_no_extra_classpath`, `test_modules_path_empty_no_project_leaks` | kept, specified | R10 rule 4. |
| S14 | Folder names come from `workspace.modules_dir` and `workspace.classes_dir` (the integration tests point `classes_dir` at an absolute folder). | `get_project_path`, `find_project_root` | changed on purpose | F3: fixed names. |
| S15 | A `lib/` inside the project's modules folder also counts. | `get_project_path` step 3 | changed on purpose | V10. |

### Java

| # | Behaviour | Where it is today | Status | Note |
| --- | --- | --- | --- | --- |
| J1 | `java -version` answers of the forms `"1.8.0_202"` (major 8), `"11.0.2"`, `"17"`, `"21.0.1"`, and a bare `version N`, are understood. | `java/inspector.py` `get_java_version`, `parse_java_version`; `test_parse_java_version` | kept, specified | J3 ("the existing two patterns"), M3 ("1.8 meaning 8"). No unit test of the forms is named; J3's feature covers `1.8.0_202` only. Owner 20: a parametrised unit test over the five forms. |
| J2 | An answer that is not a version gives a warning and the run goes on. | `validate_java_version` | kept, specified | J3; feature named. |
| J3 | No Java, or one older than the minimum, stops the run with a message. | `validate_java_version`; `test_check_java_version_*` | kept, specified | J2, J3 (`JavaNotFound`, `JavaTooOld`, code 3); features named. One of T11's items. |
| J4 | The minimum Java version defaults to 11. | `JavaConfig.min_version` | kept, specified | J3, F3. |
| J5 | `java` and `javac` are found on `PATH` only. | `shutil.which` | changed on purpose | J2: `JAVA_HOME` first. |
| J6 | `java -version` has a 5-second timeout, and a timeout reads as "not installed". | `get_java_version` | changed on purpose | J3: 10 seconds, reported as a timeout. |
| J7 | A formatted run starts Java three times. | `validate_java_version`, `get_tlc_version`, the run | changed on purpose | J3: once, with the check remembered. |

### Configuration

| # | Behaviour | Where it is today | Status | Note |
| --- | --- | --- | --- | --- |
| C1 | Settings are in `config.yaml` in the platform's user config folder named `tlaup`; tools and modules in the platform's user cache folder named `tlaup`. | `config/loader.py` `config_dir`, `cache_dir`; `test_config_paths` | kept, specified | F2, roadmap "Keep"; unit tests named. `TLAUP_HOME` and the other variables are new. |
| C2 | The packaged defaults are read through `importlib.resources`, so they load from any install. | `loader._default_config_content` | kept, specified | F1 layer 1, roadmap "Keep"; "the default file validates" named. |
| C3 | Any command copies the defaults into `config.yaml` on first use. | `load_config`, `ensure_config`; `test_ensure_config_creates_default` | changed on purpose | F1, D10: no file until `config set` or `config edit`. |
| C4 | The config file is read with YAML's safe loader, so it cannot make tlaup run code. | `load_config` (`yaml.safe_load`) | kept, not specified | Roadmap "Keep" says it; F1 names PyYAML and not the loader. Confirmed 2026-11-24. Owner 19. Unit: a file holding a `!!python/object` tag gives `ConfigInvalid` and nothing is constructed. |
| C5 | A file missing a section fails with a traceback; unknown keys are ignored silently. | `Settings` | changed on purpose | F1. |
| C6 | `module_path` adds a folder of TLA+ modules to `-DTLA-Library` and the classpath; `module_lib_path` adds a folder's jars to the classpath; a relative value is read against the working folder. | `ClasspathResolver`; `test_tlc_modules_path.py`, `test_hierarchy_priority` | kept, specified | F3 ("stay as they are ... nothing changes for a user who set them"); no test named, and the relative-path rule is not written. Owner 33 (19 for `TLAUP_MODULE_PATH`). Feature: `module_path` set to a relative folder, the logged Java command holds its absolute path in both places. |
| C7 | The settings `workspace.*`, `tlc.java_class`, `tlc.overrides_class`, `tla.urls.*` (with `per_page`) and `tla.community_modules` exist. | `config/schema.py` | changed on purpose | F3 (one warning for an old file). |

### Other commands

| # | Behaviour | Where it is today | Status | Note |
| --- | --- | --- | --- | --- |
| O1 | `check-java` prints the Java version found and whether it meets the minimum, and fails otherwise. | `cmd/check_java.py`; `check_java/test_check_java.py` | changed on purpose | C1: `doctor`, which re-runs the check (46). |
| O2 | `tlc --version` prints the jar's path and TLC's version line. | `cmd/tlc.py` `version_callback`; `test_tlc_version.py` | changed on purpose | C1, J3: `tool current`. |
| O3 | `tools meta sync` rewrites each build's metadata from GitHub. | `cmd/tools/meta/sync.py`; `test_meta.py` | changed on purpose | C1. |
| O4 | `tools dir` prints the tools folder and the installed builds, sorted. | `cmd/tools/dir.py`; `test_dir.py` | changed on purpose | C1: the folder only; `tool list --installed` for builds. |
| O5 | `modules path` prints the paths a run with no project would use. | `cmd/modules/path.py`; two `test_modules.py` tests | changed on purpose | C1: `--show-command` and `module dir`. |
| O6 | `fetch-cache clear` removes the GitHub lookup cache. | `cmd/fetch_cache/clear.py`; `test_fetch_cache_clear` | changed on purpose | C1, V8: `cache clean` (`--remote`). |
| O7 | Clearing the lookup cache when there is none succeeds. | `test_fetch_cache_clear_idempotent` | kept, not specified | C1 says what `cache clean` removes, not what it does with nothing to remove. Confirmed 2026-11-24. Owner 45. Feature: on a fresh home, `cache clean` exits 0 and stdout and stderr hold no `error:`. |
| O8 | `tlc --cleanup` removes all run folders. | `cmd/tlc.py`; `test_tlc_cleanup_command` | changed on purpose | C1: `cache clean`. |
| O9 | `config list` prints the file as it is, and fails when there is none. | `cmd/config/list.py`; `test_config_list` | changed on purpose | C1: `config show` (settings in effect), `config path`. |
| O10 | `config edit [EDITOR]` opens the file in the given editor, else `$EDITOR`, else `vim`; an editor not on `PATH` or one that exits with an error is an error. | `cmd/config/edit.py`; `test_config_suite.py` | changed on purpose | F5: `$VISUAL`, `$EDITOR`, a platform default, no argument; a non-zero exit stays an error (code 5). F5 does not say what happens when `$EDITOR` names a program that does not exist. |

### Packaging and the command itself

| # | Behaviour | Where it is today | Status | Note |
| --- | --- | --- | --- | --- |
| P1 | The installed command is `tlaup`. | `pyproject.toml` `[project.scripts]`, `cli.main` | kept, specified | F10 (`main()`, and `python -m tlaup` added). |
| P2 | `--version` prints the name and version on one line and the package summary on the next, read from the package metadata. | `cli.version_callback`; `test_cli.py` | kept, specified | C4 (two lines), roadmap "Keep" (one source); feature named. Changed on purpose: `-v` becomes `-V`, and the line reads `tlaup 0.9.0` instead of `tlaup v0.8.2` (C4 gives the form; its changelog line mentions only the flag). |
| P3 | A development install shows `+<short commit>` after the version. | `versioning/app_version.py`; `test_app_version.py`, `test_cli_version_flag_dev_commit` | kept, specified | F9, C4; test with the fake `git` named. Only editable installs now (a source checkout found by its `.git` no longer counts), and `git` is not started otherwise. |
| P4 | `tlaup`, or a group, with nothing after it prints help. | `no_args_is_help=True` | kept, specified | X1 rule 7, F10 (exit 2, help on stdout); C1 names the scenario. |
| P5 | Help shows every command with a one-line description (the 0.8.0 fix for `tools --help`), and `tlc --help` lists its options. | Typer docstrings; `test_tools_help_shows_list_help_text`, `test_tlc_help_coverage` | kept, specified | C5, F7: the generated CLI reference with a drift test (51). |
| P6 | Messages carry symbols (`⚠ Warning:`, `✖ Error:`, `✔ Success:`, `i Info:`) on stderr. | `ui.py` | changed on purpose | F6. |
| P7 | tlaup's own errors exit 1. | everywhere | changed on purpose | X1, D29. |
| P8 | Requires Python 3.11 or newer. | `pyproject.toml` `requires-python` | kept, specified | 30 H3 (`>=3.11`). |

## The rows settled on 2026-11-24

The draft left eleven rows to the maintainer. Each row above now carries the outcome, its owner and its test; this list only says which they were.

- **Kept, not specified in the draft, confirmed with the owner it proposed:** T4 (23), M14 (31), M18 (30), R33 (52), S11 (33), C4 (19) and O7 (45). T4, M18, R33 and S11 are now stated in the design; M14, C4 and O7 need only their test.
- **Dropped in the draft, now decided:** M5 by decision D61 (the compile classpath is narrow), T20 and T21 by D64 (`installed, not upstream`; releases with no jar hidden), R21 by D66 (the SANY excerpt stays in terminal output).

## Behaviour the old tests protected, and its owners

The draft found five places where the early deletion left a behaviour without a clear owner. They were settled on 2026-11-24:

- **The classpath order and `-DTLA-Library`** (S10 to S12, C6). Package 33 had planned to keep the old `tests/unit/java/test_classpath.py` and extend it; that file goes in 03b. Package 30 writes the new whole-list test file, and 33 extends it.
- **Java version parsing** (J1). Owner 20: a parametrised unit test over the five forms.
- **The `sequences-ext` integration run** (R34). Owner 52: its own row in [01 T9](01-testing.md#t9-integration-tests) beside QueueModule, until the examples manifest exists and takes it in.
- **Live loading of a project's own override class** (R33). Owner 52: a T9 row on both builds.
- **The gap between 03b and each owner.** Every kept row has no test from 03b until its owner lands. The gap is accepted under decision D62. Nothing is released inside it, and package 59's check is where a dropped row shows ([01 T11](01-testing.md#t11-the-existing-tests)). The rows most exposed are those whose code other packages edit before the owner rewrites it: the classpath (30 and 31 edit `classpath.py` before 33), and the old `tlc` command, which runs on the new store and registry from 29 and 31 until 39.

Not user-observable, and so not rows: the tests of the never-rendered layout (`TlcDisplay`, `LogDeduplicator` and the "keep tests happy" calls; O4 rebuilds the layout), `load_config`'s per-process cache, `save_config`, and `_show_diagnostic_info`, which is never called.
