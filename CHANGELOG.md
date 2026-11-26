# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Settings are read in layers: built-in defaults, then the user's config file, then environment variables, then command-line options. A config file is no longer created on first run; a file needs to hold only the settings that differ from the defaults.
- Unknown keys in the config file give a warning.
- `upgrade` compares the installed jar with the published one by SHA-256 where GitHub provides it.
- The commit shown for a build is read from the jar itself.
- Unencrypted addresses, and redirects to them, are refused.
- Installing a newer build of a name that is already installed keeps the older build and leaves the pin where it is; `tlaup tool upgrade` replaces the older build and moves the pin.
- `tool list` keeps installed builds next to their upstream release and marks one that has a newer build available.
- `tool list` marks an installed build whose release upstream no longer lists as `installed, not upstream` (was `local only`).
- `rolling` is listed first in `tlaup tool list`, then versions by number.
- `module add` says when it replaced a module of the same name; it no longer copies a `test` folder.
- `module list` shows build times in UTC.
- The output of `tlaup tlc` is reorganised: a header naming the build and Java; the spec's own output; each error with its message and full trace, changed variables marked; SANY and parse errors as `path:line:col: error: message` (was a `file://` link), still followed by the lines of the spec around the error, now with `^` under the columns; a final result line with the meaning of TLC's exit code. Results are on stdout, progress on stderr.
- The TLC output parser is now the import package `tlaup_parse`, shipped with tlaup. `tlaup.tlc.parser`, `tlaup.tlc.models`, `tlaup.tlc.values`, `tlaup.tlc.codes` and `tlaup.tlc.sany` are gone.
- When the program reading tlaup's output goes away (`tlaup tlc --raw Spec | head`), TLC is stopped instead of running on unseen; not on Windows for `--raw`.
- Each run has its own run folder, removed when the run ends, however it ends. `tlaup tlc --keep` (or the setting `tlc.keep`) keeps it when the run is interrupted or crashes and TLC has written a complete checkpoint; the size and the command to resume are printed, every `tlaup tlc` reminds you of kept folders, and `tlaup cache clean <run-id>` or `--all` removes them. tlaup never removes a kept folder on its own.
- A first Ctrl-C while TLC is writing a checkpoint waits for the checkpoint to finish, also one typed at the terminal (Linux and macOS, not with `--raw`); a second stops at once.
- On rolling builds tlaup passes `-noGenerateSpecTE`, so TLC no longer writes `_TTrace_` files next to the spec. Pass `-generateSpecTE` after `--` to get them.
- Ctrl-C exits with 130.
- `JAVA_HOME` is used to find `java` and `javac` when it is set; `PATH` is the fallback.
- A run starts Java once instead of three times; the Java version check is remembered until the Java installation changes.

### Added
- Each setting can be given as an environment variable `TLAUP_<SECTION>_<KEY>`.
- `TLAUP_HOME` moves all of tlaup's folders; `TLAUP_CONFIG_DIR`, `TLAUP_CACHE_DIR` and `TLAUP_DATA_DIR` move one each.
- `--debug`, and `python -m tlaup`.
- `GITHUB_TOKEN` or `GH_TOKEN` is used for GitHub API requests, which raises the rate limit. The token is sent only to `api.github.com`, and to hosts you list in `tool.token_hosts`; it is never printed. Credentials in `.netrc` are not used.
- Versions can be typed without the `v`, as `stable` or `rolling`, and as `tag@commit` to name one build.
- `tlaup tool current` shows the pinned build and its jar without starting Java.
- `tlaup tool list --installed` lists the installed builds only, with no network.
- `tool.token_hosts` lists extra hosts that may receive the GitHub token.
- tlaup warns before a run when a registered Java override class will not be loaded by the pinned TLC build. On v1.7.4 only a class named `tlc2.overrides.TLCOverrides` is loaded.
- Arguments after `--` are passed to TLC: `tlaup tlc Spec -- -deadlock -simulate num=10`.
- `--workers N|auto`.
- `--java-opt`.
- tlaup passes `-fp` and `-seed` to TLC when you do not, and repeats them when you resume, so a resumed run warns less and counts correctly.
- A hint when a spec or cfg name has non-ASCII characters and the locale is not UTF-8, which TLC cannot open.
- With no tools installed, `tlaup tlc` (and `sany`, `pcal`, `repl`) asks whether to install the stable release or the rolling build, installs it and carries on. `--auto-install stable|rolling` or `TLAUP_AUTO_INSTALL` answers the question for scripts. The spec is checked first, and `--show-command` never asks or installs.
- On a terminal `tlaup tlc` shows a full-screen live view while TLC runs: the build and spec, the current phase and elapsed time, the state-space progress table and the newest output. When the run ends the view closes and the complete result is printed, so it stays in the scrollback. When output is redirected or piped, output is plain as before; `--plain`, or the setting `tlc.plain`, gives plain output on a terminal too.
- `tlaup sany SPEC` runs the SANY parser and prints its findings as `path:line:col: severity: message`, each followed by the lines of the spec around it with `^` under the columns. It exits 150 when the spec has errors.
- `tlaup pcal SPEC` runs the PlusCal translator. It rewrites the spec in place and keeps the previous version as `SPEC.old`, as the translator does. It also writes `SPEC.cfg`, replacing an existing one without a backup; pass `-- -nocfg` to keep yours. With `-- -label -reportLabels` it prints each label the translator added as `Spec.tla:7:3: label Lbl_1 added`.
- `tlaup repl` starts the TLA+ REPL of the pinned build (rolling builds only).

### Breaking
- Config settings removed: `workspace.root`, `workspace.spec_dir`, `workspace.modules_dir`, `workspace.classes_dir` (the folder names `spec`, `modules`, `classes` and `lib` are fixed), `tlc.java_class`, `tlc.overrides_class`, `tla.community_modules`. `tla.urls.tags`, `tla.urls.releases` and `tla.urls.per_page` are replaced by `tool.repository`. A config file that still has them loads with one warning on every command; earlier versions wrote all of them into the file, so delete the file or remove those lines with `tlaup config edit`.
- Toolsets, custom modules, the run cache and the config file now live in folders named `tlaup` instead of `tla` (on Linux `~/.config/tlaup` and `~/.cache/tlaup`, was `~/.config/tla` and `~/.cache/tla`). Nothing is moved over: run `tlaup tool install` and `tlaup module add` again. The old `tla` folders are not touched and can be deleted.
- Installed tools are stored in a new layout with a `build.json` beside each jar. They live in the cache's `tool` folder (was `tools`). Builds installed by earlier versions are not recognised: run `tlaup tool install` again. The old `tools` folder can be deleted.
- Uninstalling the pinned build clears the pin; it no longer switches to another installed build. Pin one with `tlaup tool pin`.
- With several installed builds of one name, `tlaup tool uninstall NAME` without a terminal, or with `--yes`, removes all of them; name one build as `NAME@COMMIT`.
- `tlaup tool install` with no version asks which build to install (stable or rolling), or takes the answer from `TLAUP_AUTO_INSTALL`, and fails without either; it used to install the latest stable release.
- With several builds of one tag installed, `tlaup tool path TAG` now fails and lists them (it printed the first).
- `tlaup tools dir` is now `tlaup tool dir` and prints only the folder; use `tlaup tool list --installed` for the builds.
- `tlaup tools install -f` and `tlaup tools uninstall -y` are now `tlaup tool install --force` and `tlaup tool uninstall --yes`.
- `tlaup tools` and `tlaup modules` are now `tlaup tool` and `tlaup module`; every subcommand keeps its name.
- A module name must start with a letter or digit and hold only letters, digits, `.`, `_` and `-`, at most 64 characters. `module add` refuses a folder whose name does not fit (for example one with a space); rename the folder.
- Modules are stored in the cache's `module` folder (was `modules`), each with a `module.json`. Modules added by earlier versions are not found: run `tlaup module add` again. The old `modules` folder can be deleted.
- `module add` compiles a module's Java sources against the TLA+ tools jar and the module's own `lib/*.jar` only. Other registered modules and the jars of `module_lib_path` are no longer on the compile classpath (they still take part in runs); a module that needs a jar to compile puts a copy in its own `lib/`.
- Override classes are compiled with `-encoding UTF-8 --release 11`. A module whose sources use language features or library classes newer than Java 11 no longer compiles; set `java.min_version` higher to raise the release. `javac` must be version 11 or newer.
- A folder is treated as the project root of a spec only if it is the spec's own folder, or its parent when the spec is in a folder named `spec`, `specs`, `test` or `tests`. The home folder is never a project root. A project that keeps specs in a differently named subfolder must move `modules/`, `classes/` or `lib/` beside the specs or rename the subfolder.
- Output streams are now consistent: results go to stdout; progress, the live display and tlaup's own messages go to stderr. The verdict line moved from stderr to stdout. `--raw` no longer merges TLC's stderr into stdout.
- TLC now runs in the folder where `tlaup` was started (was the project root, or the spec's folder). TLA+ modules in the project root but outside `modules/` are no longer found; move them beside the spec or into `modules/`. A relative `-config` given after `--` is read relative to the spec's folder, as TLC does with an absolute spec path; use `--cfg` instead. Every other relative path after `--` (`-dump`, `-userFile`, `-dumpTrace` and the rest) is read from the folder you run tlaup in. `--cfg NAME` looks only for a file ending in `.cfg`.
- TLC now runs with `-workers auto` by default (was TLC's default of one worker). Set `tlc.workers: 1` or pass `--workers 1` for the old behaviour.
- `JAVA_OPTS` is no longer read. Use `TLAUP_JAVA_OPTS` or `--java-opt`; both add to the configured options instead of replacing them.

### Removed
- `tlaup tool install <URL>`. Install by version name; installing from an address may return later.
- Support for old storage layouts (a jar directly in the cache folder, the symlink pin, the `tlc` folder, modules without a `modules/` subfolder). The `tlaup` folders never contained them.
- `tlaup tools meta sync` is removed; metadata is read from the jar at install.
- `tlaup modules path` is removed; `tlaup tlc SPEC --show-command` shows the classpath in use and `tlaup module dir` the folder.
- `tlaup tlc --version`; use `tlaup tool current`.

### Fixed
- A config file written by an older version, or missing a section, caused a traceback.
- Several failures printed a Python traceback. tlaup now prints one `error:` line; `tlaup --debug ...` or `TLAUP_DEBUG=1` shows the traceback.
- `tlaup tool uninstall --all` stopped after removing the pinned version.
- A failed uninstall now exits 5 and leaves the pin alone.
- `tlaup tool upgrade` could report 'already up to date' for up to an hour after upstream published a new build.
- A download that was cut short, or a proxy's error page, could be recorded as an installed build. Downloads are now checked for length, for being a TLA+ tools jar, and against GitHub's SHA-256 where it provides one, before anything is installed.
- `tool install --force` deleted the installed build before the new download had succeeded.
- A GitHub rate limit was reported as a generic failure.
- A non-JSON answer from GitHub (for example from a proxy) caused a traceback.
- Two `tlaup tool install` commands running at once could leave a damaged install.
- `tlaup tool install` printed 'Successfully installed' after 'already installed'.
- `tlaup tool install` could treat a moving tag such as `rolling` as up to date for an hour after upstream published a new build; it now asks GitHub every time and compares the installed jar with the published one.
- Installing tools without Java present recorded an empty version.
- Only the first 30 tags were read from GitHub, so `rolling` would have disappeared at the next upstream release.
- The 'Tag/SHA' column of `tool list` is now 'Build'.
- `tlaup tool install` could offer a prerelease as the stable version when no stable release was in the first page of results.
- A warning from `tool list` went to stdout.
- `tlaup modules remove ../tools` deleted the tools folder. Module names are now checked.
- A compile error in `tlaup module add` deleted the module's previous, working build.
- `module add` could misread which classes provide overrides when a source file had `//` inside a string.
- Errors while running TLC were all reported as "'java' not found". Each is now reported as what it is.
- `--cfg` pointing at a file outside the project could make TLC read a different file with the same name.
- A spec name containing a dot (`Foo.v2`) was looked up as `Foo.tla`; `tlaup tlc .` failed with a traceback; an existing file that is not a spec (such as `Spec.cfg`) was passed to TLC.
- Running a spec could delete the run data of another spec whose name starts the same way, or of a run in progress; `tlaup module add` and `remove` deleted all run data.
- On rolling builds an override class named `tlc2.overrides.TLCOverrides` inside a jar on the classpath stopped loading when another override module was registered.
- `--show-command` printed a command without `-tool` and with `-coverage 1` in the wrong place, and created (and could delete) run data. It now prints exactly what would run and creates nothing in the run cache.
- Missing Java, a missing jar, or a missing spec could print 'Starting TLC' and then a traceback. Every `tlaup tlc` path now checks the spec, the cfg, the tools and Java first and reports the first problem in one line with the command to run next.
- Stopping `tlaup tlc` with SIGTERM (for example a CI timeout) now stops TLC too; it used to keep running.
- A second Ctrl-C no longer loses the summary.
- Output that is not valid UTF-8 no longer crashes tlaup.
- If tlaup is killed, the Java tool it started stops within about two seconds.
- TLC, SANY, PlusCal and the REPL now always write UTF-8; under a C locale non-ASCII characters were printed as `?`, and with Java 11 and v1.7.4 the PlusCal translator wrote them as `?` into the spec.
- A Java that did not answer was reported as 'not installed'.
- Errors with a TLC message code tlaup did not know (for example a false POSTCONDITION, code 2404) were not shown at all. Every message TLC marks as an error is now shown, and output tlaup does not recognise is printed as TLC wrote it.
- Counterexample traces were not shown: real TLC output parsed to zero states. Traces now show every state, the action and its location, the loop-back state of a liveness counterexample, and stuttering.
- Function values such as `(a :> 1 @@ b :> 2)` were shown as their first key; values TLC wraps over several lines were shown as one raw string.
- A SANY error was reported twice, and TLC messages printed after it were shown as part of it.
- The message of a violated invariant or property was hidden when a trace was shown.
- On a terminal, TLC output containing square brackets (every TLA+ record) was printed as an empty line or made tlaup fail.
- Runs with a lot of printed output became slower and slower and used more and more memory.
- `--refresh-interval` and `tlc.refresh_interval` had no effect. They now set how often the live view is redrawn.

## [0.8.2] - 2026-11-14

The project is renamed from `tlaplus-cli` to `tlaup` and moves to a new repository, github.com/nikolskiy/tlaup. Apart from the name, the code is the same as 0.8.1.

### Breaking
- The PyPI package is now `tlaup` (was `tlaplus-cli`). Install with `uv tool install tlaup`; uninstall the old package first with `uv tool uninstall tlaplus-cli`.
- The command is now `tlaup` (was `tla`). There is no `tla` alias: `tla tools install` becomes `tlaup tools install`, `tla tlc spec` becomes `tlaup tlc spec`.
- The Python import package is now `tlaup` (was `tlaplus_cli`).

### Removed
- The Nix flake. It was never kept up to date.

### Unchanged
- Installed toolsets, custom modules, the run cache and the config file stay in the same folders, so nothing needs to be reinstalled.

## [0.8.1] - 2026-08-13

### Fixed
- Fixed CLI help coverage test assertion failures on CI environments with forced color output by stripping ANSI escape sequences from rendered help output.

## [0.8.0] - 2026-08-13

### Added
- `--cfg <name>` option to `tla tlc` command to allow running TLC with custom `.cfg` specification configuration files (e.g. `tla tlc spec --cfg spec-v1`).
- Isolated TLC run artifacts and state caching (`run/tlc`) using TLC's `-metadir` option, avoiding working directory pollution with `./states` folders and supporting explicit purging via `tla tlc --cleanup`.
- `tla --version` — appended short git commit hash for development and editable installations (`v<version>+<short_sha>`) to prevent version ambiguity in bug reports.

### Fixed
- `tla tools list` — added missing docstring to `list_versions` command so `tla tools --help` output displays subcommand description text.

## [0.7.0] - 2026-06-17

### Added
- `tla modules add <PATH>` — compiles Java overrides and copy subfolders (`lib/`, `modules/`, `test/` or `tests/`) into a global user cache directory per module.
- `tla modules list` — displays a formatted table of all added modules and their built/modified times.
- `tla modules remove <NAME>` — deletes a module and its compiled assets from the cache.
- Automatic cleanup of the cached module directory if the Java compilation fails.
- Automatic scanning of Java source files for classes implementing `ITLCOverrides` during `tla modules add` to register all custom overrides.
- Support for multiple active custom module sets by dynamically resolving all registered override classes and configuring them via the `-Dtlc2.overrides.TLCOverrides` system property at runtime.
- Standardized examples in `docs/examples/`:
  - `sequences-ext` example featuring comprehensive override implementations for TLA+ sequences (`SequencesExt`), functions (`Functions`), and finite sets (`FiniteSetsExt`).
  - `QueueModule` example featuring TLA+ queue utilities and custom Java override implementation.
- Comprehensive documentation updates.

### Changed
- `tla modules path` — simplified to a read-only command showing the active resolved paths (Source, Classes, and Library JARs) from all cached modules.
- Dynamic classpath resolution: TLC automatically appends/prepends compiled classes, libraries (`lib/*.jar`), and TLA sources (`modules/`) from all globally added modules.
- Cached module classes are now available as dependencies in compile mode (`ResolveMode.COMPILE`) letting custom modules compile against other cached modules.
- Refactored `tla tlc` output formatting to stream logs and progress statistics line-by-line. In interactive TTY mode, a dynamic, smoothly updating status footer overlay is rendered at the bottom of the screen.
- Separated `tests/` directory into `tests/unit` and `tests/integration` subdirectories, and updated pytest configuration (`testpaths` in `pyproject.toml`) to only run unit tests by default.

### Removed
- `tla modules lib` command.
- `tla modules install-community` command.
- `tla modules build` command (superseded by `tla modules add`).

## [0.6.0] - 2026-05-29

### Added
- Dynamic, borderless terminal UI for `tla tlc` using `rich.console.Group`.
- Smoothly updating "Elapsed time" display that ticks independently of TLC output (4Hz refresh rate).
- Graceful `KeyboardInterrupt` (Ctrl+C) handling for `tla tlc` that stops the process, parses remaining output, and marks the status as "canceled".
- Infinite scrolling support for the "State Space Progress" table in the `tla tlc` output.

### Changed
- Relocated TLC version information to the primary header of the `tla tlc` output.
- Reorganized `tla tlc` output layout order: Header, Status Info, Logs, and State Space Progress.
- `tla tlc` logs section title is now centered and no longer underlined.


## [0.5.0] - 2026-05-03

### Added
- `--show-command` flag to `tla tlc` and `tla modules build` to inspect the exact Java command before execution.
- `--resolved` flag to `tla modules path` to display fully resolved Source, Classes, and Library paths for the current context.
- Centralized `ClasspathResolver` component for unified path management across compilation and execution.

#### Experimental
- The TLC output now parsed for errors and warnings.
- Model checking progress statistics are now displayed.

### Changed
- `tla tlc` now includes `module_lib_path` in the runtime classpath, ensuring consistency between build and runtime environments.
- Refactored `cmd/` layer to use standardized `warn()` helper and adhere to strict public API boundaries.

### Fixed
- Improved `try` block scoping and error handling in CLI commands.
- Standardized fake-file creation in tests using `touch()`.

## [0.4.2] - 2026-04-24

### Fixed
- `tla modules build` now uses both local and custom module paths.

## [0.4.1] - 2026-04-24

### Fixed
- List local versions order. If there is a version that doesn't follow any standards it is sorted by name.

## [0.4.0] - 2026-04-20

### Added
- `tla modules lib <PATH>` — configure a persistent custom Java modules dependencies directory (jars).
- `tla config list` — display the current configuration file content.
- `tla config edit [EDITOR]` — open the configuration file in an editor ($EDITOR or vim).

### Changed
- `tla modules path` — now supports viewing the current path (no arguments) and resetting it (`tla modules path none`).
- `tla modules build` — now uses the configured `module_lib_path` if set, otherwise defaults to the `lib/` subdirectory within the resolved modules directory.

## [0.3.5] - 2026-04-19

### Added
- `tla modules path <PATH>` — configure a persistent custom Java modules path. This decouples module compilation and execution from the current working directory.

### Changed
- `tla modules build` now prioritizes the configured `module_path` for source discovery.
- `tla tlc` now automatically includes the configured `module_path` in the Java classpath and sets `-DTLA-Library` if it exists, enabling global or persistent custom module overrides.
- Reorganized and improved tests.

## [0.3.4] - 2026-04-06

### Added
- `tla tools install <URL>` — install `tla2tools.jar` from a custom HTTPS URL.
  The version name is extracted from the URL path (e.g. `/v1.8.0/`); the
  download timestamp (ISO 8601) is used as the tag.  Duplicate installs of the
  same version are allowed and distinguished by their tag.  The install appears
  identically in `tla tools list`.

## [0.3.3] - 2026-04-06

### Fixed
- Resolved `FileNotFoundError` when loading the default configuration in certain installation environments (e.g., `uv tool install`) by switching to `importlib.resources` for robust package data access.

## [0.3.2] - 2026-04-03

### Added
- `tla tlc` now intelligently resolves `<spec>` files:
  - Supports running without the `.tla` extension.
  - Automatically checks for files inside a `spec/` subdirectory relative to the specification path.
  - Provides a detailed error message listing all checked locations when a specification cannot be found.
- `tla tlc --version`: Added a flag to display the absolute path to the currently pinned `tla2tools.jar` and its internal TLC version string.
- Project-aware TLA+ support:
  - `tla tlc` now automatically discovers project roots by looking for `modules/`, `classes/`, or `lib/` directories adjacent to the spec or its parent.
  - TLC's classpath now includes the project's `classes/` directory and any `*.jar` files found in the project's `lib/` directory.
  - `-DTLA-Library` is automatically set to the project's `modules/` directory if it exists.
- `tla modules build`:
  - Added an optional `[PATH]` argument to specify the project root (defaults to workspace root).
  - Automatically includes `lib/*.jar` files from the project root in the `javac` classpath.

### Changed
- `tla build` renamed to `tla modules build` for better command organization.
- `tla tools path`: Output now strictly emits the absolute path to `tla2tools.jar` only, removing the TLC version string to better support scripting and piping.


## [0.3.1] - 2026-04-03

### Added
- **System CA Support**: Integrated `truststore` to automatically utilize the native OS certificate store for network requests. This resolves SSL verification failures in environments with custom CAs (e.g., corporate proxies).
- **Breaking Change**: Renamed the `run` command to `tlc` to better reflect its function, since the previous `tlc` command group was renamed to `tools`.

  - To run the model checker, use `tla tlc <spec>` instead of `tla run <spec>`.
- **Breaking Change**: Renamed the `tlc` subcommand group to `tools` to better reflect that it manages the entire TLA+ toolset distribution (TLC, SANY, TLATeX).
  - `tla tlc <action>` is now `tla tools <action>`.
  - Internal cache directory moved from `~/.cache/tlaplus-cli/tlc` to `~/.cache/tlaplus-cli/tools`.
  - Pin file renamed to `tools-pinned-version.txt`.
  - Automatic migration of existing cache and pins is performed on first run.
- Intelligent pin state management:
  - **Auto-pinning**: The first toolset version installed is now automatically pinned.
  - **Pin stability**: Subsequent installations of other versions will no longer "hijack" the current pin.
  - **Smart Fallback**: Uninstalling the pinned version now automatically re-pins the "latest" remaining version based on semantic versioning, release date, or directory age.
- `uninstall`: Added `--all` flag to remove all tags for a specific version name.
- `uninstall`: Added interactive selection when multiple tags exist for the same version name.
- `upgrade`: Now seamlessly installs the target version if it is not already present locally.

### Changed
- `list`: Enhanced table display with a "Published" column and a green checkmark `✓` for the pinned version.
- `list`: Improved version resolution to show separate entries for different SHAs of the same version name, removing the confusing "upgrade" status.
- `upgrade`: Now defaults to upgrading the currently pinned version if no version argument is provided.
- `upgrade`: Automatically updates the pin to the new directory if the version being upgraded was currently pinned.
- `pin` & `uninstall`: Matching versions are now sorted by directory name for consistent interactive selection.

## [0.2.1] - 2026-03-30

### Added
- Comprehensive TLC version management under the `tla tlc` command group.
  - `list`: Show available remote versions and locally installed versions.
  - `install`: Download specific or latest TLC versions directly from GitHub.
  - `pin`: Set a default version to use across the workspace.
  - `upgrade`: Update the pinned version to a newer commit.
  - `path`: Get the absolute path to the local `tla2tools.jar` for the pinned or a specific version. Displays the TLC2 version string from cached metadata above the path when available.
  - `dir`: Show the TLC versions directory and list all installed version directories.
  - `uninstall`: Remove local versions to free up space.
  - `meta sync`: Backfill or rebuild `meta-tla2tools.json` metadata profiles for existing local installations.
- Robust local TLC version profile generator saving metadata like parsed dates and `java -cp` output headers via `meta-tla2tools.json`.
- Added GitHub API caching with a 1-hour TTL to avoid rate limits (manageable via `tla fetch-cache clear`).
- Added `--force` flag for re-downloading versions.
- Added a visual progress bar for TLC jar downloads.

### Changed
- **Breaking Change**: The main execution command has been renamed from `tla tlc <spec>` to `tla run <spec>` to support the new `tlc` subcommand group.
- Migrated legacy `tla2tools.jar` handling. The old `tla download` command has been removed.
- Refactored `tlaUrls` in `config.yaml` to point to GitHub tags and releases endpoints directly.
- Use a plain text marker (`tlc-pinned-version.txt`) for tracking the pinned TLC version to ensure cross-platform compatibility (avoiding Windows symlink requirements).

### Fixed
- Significantly expanded the test suite to use robust mock fixtures for GitHub API and filesystem side-effects.


## [0.1.8] - 2026-03-18

### Changed

- Refactored `tla` source directory to use the standard Python `src/tlaplus_cli` layout.
- Renamed the internal Python package to `tlaplus_cli` to avoid global namespace collisions on PyPI while keeping the external `tla` CLI command name.
- Improved tests.

## [0.1.6] - 2026-02-16

### Added

- Automated release workflow (`.github/workflows/release.yml`) for GitHub Releases and PyPI publishing.
- `scripts/release.sh` helper script to simplify version bumping and tagging.

### Fixed

- Corrected invalid PyPI classifier (`Topic :: Utilities`) that caused upload failures.
- Added comprehensive test suite execution (Java check, linting, tests) to the release workflow.

## [0.1.3] - 2026-02-16

### Added

- Metadata for PyPI release.

## [0.1.1] - 2026-02-16

### Fixed

- Fixed `--version` flag to correctly read package metadata after `uv tool install`.

## [0.1.0] - 2026-02-13

### Added

- `tla download` — download stable or nightly `tla2tools.jar`.
- `tla check-java` — verify Java version meets the minimum requirement.
- `tla build` — compile custom Java modules for TLC.
- `tla tlc <spec>` — run the TLC model checker on a specification.
- Automatic config creation on first run (`~/.config/tla/config.yaml`).
- Pydantic-based configuration with `JAVA_OPTS` environment variable support.
