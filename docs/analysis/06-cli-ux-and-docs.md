# 06 - CLI UX and Documentation Review

Scope: command-line user experience and documentation of `tla` (tlaplus-cli 0.8.1, branch `dev`, commit `fb4a5e0`).
Method: read `src/tlaup/cmd/`, `tlc/formatter.py`, `tlc/components.py`, `tlc/runner.py`, `config/`, `versioning/`; ran `--help` on every command; exercised first-run and error paths with `XDG_CONFIG_HOME` and `XDG_CACHE_HOME` pointed at a scratch directory (nothing was installed, downloaded, pinned or removed; the real `~/.config/tla` and `~/.cache/tla` were only listed and read).

What was not exercised: a real TLC run (no jar in the scratch cache), `tla tools list` against the network, the interactive prompts, and TTY-only rendering. Statements about those are from reading the code and are marked "(code reading)".

---

## 1. Summary

The command tree is small, mostly guessable, and the help text is complete (every command has a description). The version manager handles the rolling `v1.8.0` release correctly at the storage level (`<tag>-<short_sha>` directories). The main problems are at the edges that scripts, CI and new users hit first:

1. `tla tlc` cannot pass any TLC flag through (`-workers`, `-deadlock`, `-simulate`, `-depth`, ...). Only six hard-coded options exist.
2. Three first-run paths crash with a Python traceback instead of the (already well-written) error message: no Java, `--raw` with no jar, `--show-command` with no jar.
3. No machine-readable output anywhere, no documented exit codes, and stdout/stderr are interleaved inconsistently.
4. A rolling build cannot be selected non-interactively: `tools pin` and `tools uninstall` prompt, with no flag or `tag-sha` syntax to bypass.
5. No per-project configuration or tool pin; the pin lives in the cache directory.
6. The README is 40 lines and documents roughly a third of the surface. There is no install prerequisites section, configuration reference, exit-code table, or explanation of the rolling release.

Ranked recommendations are in section 10.

---

## 2. Command design

### 2.1 Command tree as shipped

```
tla [-v|--version]
  tlc [SPEC] [--version] [--show-command] [--cleanup] [--refresh-interval F] [--coverage] [--raw] [--cfg TEXT]
  check-java
  modules   add PATH | list | remove MODULE_NAME | path
  tools     dir | install [VERSION] [-f] | list | path [VERSION] | pin VERSION
            | uninstall [VERSIONS]... [--all] [-y] | upgrade [VERSION] | meta sync
  fetch-cache clear
  config    edit [EDITOR] | list
```

Root help (`tla --help`) lists commands in registration order, not by importance or alphabetically: `tlc, check-java, modules, tools, fetch-cache, config` (`src/tlaup/cli.py:51-57`).

### 2.2 Naming and grouping

| Observation | Evidence | Comment |
|---|---|---|
| `tools` verbs match version-manager conventions | `install / list / pin / upgrade / uninstall / path` | Good. `pin` is closest to `uv python pin`; rustup uses `default`, nvm `alias default`, pyenv `global`/`local`, mise `use`. `pin` is fine but only has a global scope (see 6.3). |
| `fetch-cache clear` is a top-level group with one command | `cmd/fetch_cache/__init__.py:3` | Name describes the implementation. Users think "cache". |
| A second cache is cleared by a flag on a different command | `tla tlc --cleanup` (`cmd/tlc.py:84,99-102`) | An action disguised as an option; it makes `SPEC` optional, which forced a hand-written "Missing argument" check (`cmd/tlc.py:104-106`). |
| `tools meta sync` is three levels deep for one maintenance command | `cmd/tools/meta/` | Could be `tools sync-metadata`, or folded into `tools list --refresh` / `tla doctor`. |
| `check-java` is a top-level, single-purpose, hyphenated command | `cli.py:57` | Most tools have `doctor` (mise, flutter, brew) that checks everything: Java, javac, pinned jar, config validity, cache paths. |
| `tools dir` vs `tools path` vs `modules path` | `tools dir` prints the directory plus an indented listing; `tools path` prints one jar path; `modules path` prints a three-section report | Three different meanings for `dir`/`path`. `modules path` is really "show resolved classpath". |
| `config list` prints the raw file | `cmd/config/list.py:9-16` | uv/git/npm use `list` for effective key/values; `show` or `cat` would be more honest. There is no `config path`, `get`, or `set`. |
| `config edit [EDITOR]` takes the editor positionally | `cmd/config/edit.py:13` | Unusual; `--editor` or just `$VISUAL`/`$EDITOR` is the norm. Default `vim` fails on machines without it (message is clear, though). |
| `tools` help says "TLC" everywhere although the group was renamed because it manages the whole toolset | "Manage TLC tools (tla2tools.jar)", "List available and installed TLC versions", "Uninstall ALL local versions" | CHANGELOG 0.3.1 explains the rename ("TLC, SANY, TLATeX") but help text still says TLC. |
| Two `--version` flags with different meanings | `tla --version` (app) and `tla tlc --version` (jar path + TLC version) | Acceptable, but `tla --version` could simply print both. |
| `-v` means version | `cli.py:37-38` | Convention is `-V` for version and `-v` for verbose (uv, cargo, rustup, pip). This blocks adding `-v/--verbose` later. |
| No aliases | `tla tools ls` gives "No such command 'ls'. Did you mean 'list'?" | Typer's suggestion is good enough; aliases `ls`/`rm` are cheap. |

Suggested tree (non-breaking additions first, renames behind deprecation aliases):

```
tla run|tlc SPEC [tla options] [-- TLC args...]
tla doctor                      (superset of check-java)
tla tools list|install|use(pin)|upgrade|uninstall|path|dir
tla modules add|list|remove|path
tla cache dir|clear [--api|--runs|--all]
tla config path|show|edit|get|set
tla completion bash|zsh|fish
```

### 2.3 How versions are specified and displayed

Specification:

- Exact tag string only. `install`, `pin`, `path`, `uninstall`, `upgrade` all do `v.name == version` (`install.py:62`, `pin.py:12`, `path.py:23`, `uninstall.py:31`, `upgrade.py:23`).
  - `tla tools install 1.8.0` (no `v`) fails with `Error: Version 1.8.0 not found.` and no hint.
  - No aliases such as `latest`, `stable`, `nightly`/`rolling`.
  - A specific build cannot be addressed: the directory name `v1.8.0-4ba7d88` (which the tool itself prints in "Pinned version: ...") is not accepted as input.
- `tla tools install` with no argument silently picks "latest stable release" = newest non-prerelease (`install.py:67-69`). With today's upstream data that is `v1.7.4` (2024), while the actively maintained build is the rolling prerelease `v1.8.0`. A new user gets a two-year-old TLC without being told a newer rolling build exists.
- `tla tools install <URL>` requires a `vX.Y.Z` path segment in the URL (`downloader.py:55-58`) and uses a timestamp as the build id. Not mentioned in the README.

Display (`tools list`, `cmd/tools/list.py`):

- Columns: `Version | Tag/SHA | Published | Status | Pinned`.
- A rolling build is distinguished from a tagged one only implicitly: by the 7-char SHA and the `Published` date. The `prerelease` flag is fetched and stored (`versioning/api.py:71`, `meta-tla2tools.json` has `"prerelease": true`) but never shown.
- When the local rolling build is behind the remote one, the table shows two rows with the same version name and nothing connecting them. With the data currently in the real cache (remote `v1.8.0 30cc360` published 2026-08-11, local `v1.8.0-4ba7d88` published 2026-05-26, pinned), the output would be (code reading of `list.py:55-77`):

  ```
  v1.8.0  30cc360  2026-08-11  available
  v1.7.4  5a47802  2024-08-05  available
  ...
  v1.8.0  4ba7d88  2026-05-26  installed   ✓      <- appended at the bottom, after v1.5.7
  ```

  The outdated pinned build is sorted to the bottom, and there is no "update available" or "outdated" marker. CHANGELOG 0.3.1 says the "upgrade" status was removed as confusing; the replacement loses the single most useful fact for a rolling release.
- The column header `Tag/SHA` is wrong: the tag is in the `Version` column; this column is a commit SHA (or a timestamp for URL installs).
- `tools list` always needs the network (1 h cache). There is no `--installed` / `--offline` flag; when offline it prints `⚠ remote data unavailable` to stdout (`list.py:34`, not via `ui.warn`, so it pollutes piped output) after a `ui.warn` with the raw `requests` exception.
- No `tla tools current` (what is pinned right now?). `tla tools path` gives the jar path; `tla tlc --version` gives path + TLC version string but spawns a JVM.

Recommendation: add a `Channel`/`Kind` column (`release` / `rolling`), show an `update available (30cc360, 2026-08-11)` status on the installed row, keep installed rows next to their remote counterpart, accept `v1.8.0@4ba7d88` or the directory name wherever a version is accepted, and add `latest`/`rolling` aliases.

### 2.4 Passing TLC and JVM flags

This is the largest functional gap.

- TLC flags: there is no passthrough. `tla tlc` is registered with no `allow_extra_args`/`ignore_unknown_options` (`cli.py:56`), and `build_tlc_command` builds a fixed argv (`tlc/runner.py:146-161`). Verified:

  ```
  $ tla tlc spec/queue.tla -workers 4
  Usage: tla tlc [OPTIONS] [SPEC]
  │ No such option: -w
  [exit 2]
  ```

  So `-workers`, `-deadlock`, `-simulate`, `-depth`, `-seed`, `-fp`, `-checkpoint`, `-recover`, `-dump`, `-continue`, `-difftrace`, `-lncheck`, `-generateSpecTE` are all unreachable. TLC therefore always runs single-worker. The only escape hatch is `--show-command`, copy, edit, run by hand - which also loses the formatter.
- `--coverage` is hard-coded to `-coverage 1` (`runner.py:184-187`).
- JVM flags: only via `java.opts` in the global config or the `JAVA_OPTS` environment variable, which *replaces* (not appends to) the configured list (`config/schema.py:36-43`). This is undocumented outside one CHANGELOG 0.1.0 bullet. Setting `JAVA_OPTS=-Xmx8g` silently drops the default `-XX:+UseParallelGC`. `JAVA_OPTS` is also a generic variable that other tools set; a namespaced `TLA_JAVA_OPTS` would be safer.
- No `--java` / `JAVA_HOME` handling: the `java` on `PATH` is always used (`runner.py:147`).

Recommendation: accept everything after `--` (and ideally unknown single-dash options) and append to the TLC argv; add first-class `--workers` (default `auto`), `--deadlock/--no-deadlock`, `--simulate`, `--depth`; add repeatable `--jvm-opt` / `-J`.

### 2.5 `tla tlc` option details

| Option | Issue | Evidence |
|---|---|---|
| `SPEC` help: "Name of the TLA+ specification (without .tla extension)." | Both `Spec` and `Spec.tla` and `dir/Spec` work, plus a hidden `spec/` subdirectory lookup | `runner.py:26-30` |
| `--refresh-interval` | Accepted, documented, and ignored. The parameter is `_refresh_interval` and never read; `Live(refresh_per_second=4)` is hard-coded. Config key `tlc.refresh_interval` is likewise unused | `cmd/tlc.py:85-89,155`; `default_config.yaml:22` |
| `--show-command` | README says "Inspect exact JVM command before execution"; the printed command omits `-tool` (added later in `run_tlc`, `runner.py:181-182`), is joined with spaces without shell quoting (`cmd/tlc.py:129`), and has side effects: it creates the `-metadir` directory and deletes stale run directories (`run_cache.py:43-52`) | |
| `--raw` | Described as "without structured tool mode formatting" - it drops `-tool` and streams TLC's human output unchanged. Good, but stderr is merged into stdout (`runner.py:199-200`) | |
| `--cleanup` | See 2.2 | |
| `--cfg` | Good: name or path, with or without `.cfg`, searched next to spec, cwd, project root | `runner.py:40-82` |

Dead code: `_show_diagnostic_info` (`cmd/tlc.py:42-62`) is never called.

### 2.6 First-run experience

Observed with empty config and cache directories:

1. Any command (including `tla tools --help`) silently writes `~/.config/tla/config.yaml` (root callback, `cli.py:45-46`). No message. See 6.1 for why copying the whole default file is a problem.

2. `tla tlc spec/queue.tla`, nothing installed, piped:

   ```
   ✖ Error: tla2tools.jar not found. Run 'tla tools install' first.
   Starting TLC model checker (version unknown).
   [exit 1]
   ```

   The message is actionable. But the "Starting ..." line is printed before validation (`cmd/tlc.py:201`) and, being buffered stdout, appears after the error. Also `get_tlc_version()` is called before the jar check.

3. `tla tlc spec/queue.tla --raw`, nothing installed: Rich traceback ending in

   ```
   FileNotFoundError: tla2tools.jar not found. Run 'tla tools install' first.
   ```

   Cause: the `--raw` branch (`cmd/tlc.py:132-134`) is outside the `try` block.

4. `tla tlc spec/queue.tla --show-command`, nothing installed: same traceback (`cmd/tlc.py:123-130` outside the `try`).

5. `tla tlc spec/queue.tla` with no `java` on `PATH`: traceback ending in

   ```
   RuntimeError: Java is not installed or not found in PATH. Please install Java 11 or higher.
   ```

   Cause: `validate_java_version` raises `RuntimeError` (`java/inspector.py:71-73`) but `cmd/tlc.py:287` only catches `FileNotFoundError`. `tla check-java` handles the same error cleanly (exit 1, one line).

6. `tla tlc --version` with nothing installed prints the legacy fallback path `~/.cache/tla/tla2tools.jar` as if it were the expected location, then the error. `tla modules path` lists the same non-existent jar under "Library Paths (JARs)" (`cmd/modules/path.py:51` only filters it out when it exists).

7. `tla tools path`: `Error: No pinned version found.` - no "run `tla tools install`" hint.

Recommendation: one `ensure_ready()` preflight used by every `tlc` branch that checks jar, Java, spec, cfg in that order and emits a one-line error with the next command. Consider offering auto-install on first `tla tlc` (prompt on TTY, `--yes`/env to auto-accept, error in non-TTY), as rustup/mise/uv do. Disable Typer pretty exceptions for end users (`pretty_exceptions_enable=False`) and add a top-level handler that prints `✖ Error: ...` plus "re-run with `--debug` for a traceback".

---

## 3. Output modes

### 3.1 What exists

| Mode | How | Notes |
|---|---|---|
| Live TTY | default when `sys.stdout.isatty()` (`cmd/tlc.py:141`) | Streams log lines and a progress table; Rich `Live` footer with status, elapsed, diameter/generated/distinct/queue (`components.py:136-183`) |
| Plain streaming | default when stdout is not a TTY (`cmd/tlc.py:198-240`) | Same content via `print`, no footer. The 40 lines of callback are duplicated between the two branches |
| Raw | `--raw` | TLC's own output, no `-tool`, no parsing |
| Machine-readable | none | No `--json`, `--format`, `--output` anywhere. No JUnit/SARIF/GitHub annotations |
| Quiet / verbose | none | No `-q`, `-v` (taken by version), `--debug` |

The parser already builds a rich structured model (`ModelCheckResult`: state, status, errors with traces, coverage, SANY errors with ranges, stats, durations - `tlc/models.py`). Serialising it is mostly `dataclasses.asdict`. This is the cheapest high-value feature in the project for CI and agent use.

### 3.2 stdout / stderr discipline

Inconsistent, which makes piping unreliable:

- `ui.success/error/warn/info` go to stderr (`ui.py`). So the final verdict "✔ Success: Model checking completed successfully." and "✖ Error: Model checking failed with N error(s)." go to stderr, as does `Duration`.
- Error traces, SANY errors and coverage tables go to stdout via fresh `Console()` objects (`cmd/tlc.py:254-283`); non-trace error lines go to stderr (`:268-269`).
- Result: `tla tlc Spec > out.txt` captures the trace but not the verdict; `2>/dev/null` hides the verdict. In CI logs (both merged, stdout block-buffered) the order can be scrambled, as seen in 2.6 item 2.
- Informational chatter in other commands goes to stdout: `tools install` prints "No version specified...", "Download complete.", "Auto-pinning ..." on stdout; `tools dir` prints path plus listing.
- `Duration: 1234ms` is raw milliseconds (`cmd/tlc.py:286`).

Rule to adopt: results on stdout, diagnostics/progress on stderr; one `Console` each, created once.

### 3.3 Colour control

- Rich output (tables, traces, help) honours `NO_COLOR` and non-TTY detection automatically, because every `Console()` is default-constructed.
- `ui.py` uses `typer.style`/`typer.echo`. Click strips ANSI when the stream is not a TTY, but Click 8.3 does not read `NO_COLOR` (no reference to it in the installed `click` or `typer` packages). So on a TTY with `NO_COLOR=1` the ✔/✖/⚠ glyphs are still coloured (code reading).
- No `--color auto|always|never` or `--no-color` flag, no `FORCE_COLOR` documentation. CHANGELOG 0.8.1 shows the project already tripped over forced colour in CI.
- Unicode glyphs (✔ ✖ ⚠ │ └──) are emitted unconditionally, including to non-TTY and legacy Windows code pages.
- Fixed-width decorations (`formatter.py:233`) do not adapt to narrow terminals.

### 3.4 Exit codes

Current behaviour (`cmd/tlc.py:291`, `runner.py:216,264`):

| Situation | Exit code |
|---|---|
| TLC ran | TLC's own code passed through unchanged (0 ok; 10 assumption, 11 deadlock, 12 safety, 13 liveness; 75-77 failures; 150+ errors, per TLC's `EC` class) |
| Spec/cfg/jar not found, bad module path, etc. | 1 |
| No Java (in `tlc`) | 1, with traceback |
| Usage error raised by Click | 2 |
| Missing SPEC / missing VERSIONS | 1 (hand-rolled, inconsistent with Click's 2: `cmd/tlc.py:104-106`, `uninstall.py:85-87`) |
| Ctrl+C during TLC | `process.terminate()` then `returncode` = -15, i.e. 241 in the shell (code reading); not 130 |
| `tools uninstall X` where X is not installed | 0 with a warning ("No versions to uninstall.") |
| `tools uninstall`: `rmtree` fails | 0, error printed (`uninstall.py:68-69`) |
| `tools install` of an already-installed version | 0, prints "already installed" then "Successfully installed" |

Passing TLC's code through is the right call and is script-friendly, but:

- It is not documented anywhere (README, help, CHANGELOG).
- `tla`'s own exit 1 collides conceptually with "TLC failed": a script cannot tell "tool not set up" from "TLC returned 1".
- `tlc/codes.py` (314 lines of TLC message codes) has no exit-code mapping, so the tool cannot print "exit 12: safety violation".

Recommendation: document the table; reserve a distinct code for tlaplus-cli setup errors (e.g. 64-78 sysexits range is taken by TLC's 75-77, so pick e.g. 3 = environment not ready, 2 = usage); return 130 on SIGINT; include `exit_code` and its meaning in the JSON output.

---

## 4. Error messages

Good:

- `tla2tools.jar not found. Run 'tla tools install' first.` (`runner.py:118`, `modules/add.py:96`, `cmd/tlc.py:31-32`)
- `Version v9 not found locally. Install it first.` (`pin.py:15`)
- `Java version 11 or higher is required. Found version X (major version N).`
- `'javac' not found. Ensure JDK is installed.`
- Typer's "Did you mean 'tools'?" on typos.

Need work:

| Message | Where | Problem / suggested text |
|---|---|---|
| `Could not find a TLA+ spec file for 'nope'` | `runner.py:34` | CHANGELOG 0.3.2 promises "a detailed error message listing all checked locations"; it does not. List the three candidates. |
| `Error: Version 1.8.0 not found.` | `install.py:64` | Add "Did you mean v1.8.0? Run `tla tools list` to see available versions." |
| `Error: Could not fetch remote versions (status: unavailable)` | `install.py:57`, `upgrade.py:45`, `meta/sync.py:20` | Preceded by a raw `requests` exception in a warning. No mention of GitHub rate limiting (60 unauthenticated requests/hour, common on shared CI runners) or how to supply a token (there is no token support at all). |
| `Error: No pinned version found.` | `path.py:19` | Add "Run `tla tools install` or `tla tools pin <version>`." |
| `Error: No version specified and no version is pinned.` | `upgrade.py:26` | Same. |
| `Version v1.7.4 is already installed.` + `Successfully installed v1.7.4 to ...` | `install.py:74-75` | Contradictory pair; drop the second, mention `--force`. |
| `could not extract a version name from the URL...` | `downloader.py:57` | Offer `--name vX.Y.Z` instead of requiring it in the URL. |
| `Compilation failed!` + raw javac output | `modules/add.py:115-117` | Fine, but exit code is always 1 and the classpath used is not shown; add `--show-command` (existed for `modules build` in 0.5.0, lost in 0.7.0). |
| Invalid `config.yaml` | `config/loader.py:22` | No handling: a YAML or pydantic validation error surfaces as a traceback on every command, including `tla config edit` (which calls `load_config()` first, `edit.py:19`) - the user cannot use the tool to fix the file. |

Style is inconsistent: `tlc` uses `ui.error` ("✖ Error: ..."), `tools`/`modules`/`config` use bare `typer.echo("Error: ...", err=True)`, `tools list` uses a bare "⚠ ..." on stdout. Route everything through `ui.py`.

---

## 5. Suitability for CI, editors and AI agents

| Requirement | Status | Detail |
|---|---|---|
| Non-interactive by default | Partial | `tools pin` prompts with `typer.prompt` when several builds share a tag (`pin.py:21-28`) - exactly the rolling-release case (e.g. after `tools install v1.8.0` when an older v1.8.0 build exists, since `install` does not replace the old directory, or after URL installs). No flag or syntax bypasses it; with stdin closed it aborts. `tools uninstall` has the same prompt (`uninstall.py:36-49`); `--yes` only covers `--all`. |
| Destructive actions confirmed | Inconsistent | `uninstall --all` confirms; `uninstall v1.8.0` does not; `modules add` silently deletes and replaces an existing module of the same directory name (`modules/add.py:60-62`); `tlc --cleanup` and `fetch-cache clear` do not confirm (fine, caches). |
| Stable, parseable output | No | No JSON; Rich tables wrap/truncate by terminal width; `tools list` mixes a warning into stdout; `tools dir` mixes a path with a listing. Only `tools path` is clean (deliberately, CHANGELOG 0.3.2). |
| Deterministic exit codes | Partial | See 3.4. |
| Reproducible toolchain | No | No project pin file; `tools install` with no args resolves "latest stable" at run time; the rolling tag cannot be pinned by SHA from the CLI; a jar checksum is not recorded or verified (`meta-tla2tools.json` has the commit SHA but no file hash). |
| Offline / cached operation | Partial | `tlc` works offline. `tools list/install/upgrade` need the GitHub API; no `GITHUB_TOKEN` support, no retry/backoff. |
| Hermetic state location | Partial | Honours XDG via platformdirs (verified with `XDG_*`), but there is no `TLA_HOME` / `TLA_CONFIG` / `TLA_CACHE_DIR` override, which matters on Windows/macOS runners where XDG is not used. |
| Global mutable state affecting runs | Risk | Every module in `~/.cache/tla/modules` is put on the classpath and into `-DTLA-Library` for every TLC run (`java/classpath.py:106-121`). A leftover module from another project changes results silently. There is no per-run opt-out (`--no-global-modules`) or per-project selection. |
| Concurrency | Risk | `get_spec_run_dir` deletes "stale" run dirs for the same spec stem (`run_cache.py:29-40`); two CI jobs or two editor tabs checking same-named specs with different content can delete each other's `-metadir`. |
| Editor integration | Weak | SANY errors print `file://path#Lnn` (`formatter.py:93`) which is clickable in some terminals but is not the `path:line:col: message` shape editors and problem matchers parse. |

The project's own CI does `uv run tla tools install` (`.github/workflows/test.yml:39`) with no version, so the test suite runs against whatever "latest stable" is that day - the tool has no way to express a pinned toolchain for its own repo.

For AI coding agents specifically: an agent needs (a) one command that never prompts, (b) a compact structured verdict (status, violated property, counterexample trace, file/line of parse errors), (c) no ANSI or box-drawing noise, (d) exit codes it can branch on. Today it gets none of (b) and has to scrape Rich trees. A `tla tlc Spec --json` (final document) and optionally `--json-stream` (NDJSON progress events) would cover CI, editors and agents with one feature.

---

## 6. Configuration

### 6.1 The file

`src/tlaup/resources/default_config.yaml` (28 lines) is copied verbatim to `<user_config_dir>/tla/config.yaml` on first run (`config/loader.py:68-75`); on Linux `~/.config/tla/config.yaml`.

| Key | Used? | Notes |
|---|---|---|
| `tla.urls.tags/releases/per_page` | Yes | GitHub API endpoints as user config. Because the file is copied once, a future change to defaults never reaches existing users. |
| `tla.community_modules.*` | No | Leftover from the removed `modules install-community` (CHANGELOG 0.7.0). |
| `workspace.root` | No | Only read by `workspace_root()` (`loader.py:78`), which nothing calls. |
| `workspace.spec_dir` | No | `resolve_spec_file` hard-codes `"spec"` (`runner.py:29`). |
| `workspace.modules_dir`, `workspace.classes_dir` | Yes | Project root detection and classpath. |
| `tlc.java_class` | Yes | |
| `tlc.overrides_class` | Yes (fallback) | `modules/add.py:128` |
| `tlc.refresh_interval` | No | See 2.5. |
| `java.min_version`, `java.opts` | Yes | `opts` overridden wholesale by `JAVA_OPTS`. |
| `module_path`, `module_lib_path` | Yes, but not in the default file | Read by `classpath.py:159,176`; the commands that set them were removed in 0.7.0, so they are only settable by hand-editing and are documented nowhere. |

Four of the keys in the shipped file do nothing. The comment in the file ("Path to the TLA+ workspace (specs, custom modules, compiled classes). Relative paths are resolved from the current working directory.") describes behaviour that no longer exists.

Other issues:

- `save_config` exists (`loader.py:25`) but is unused; it would rewrite the file and drop comments.
- No schema version, no migration, no validation message (see section 4).
- `config list` shows the file, not the effective configuration (does not reflect `JAVA_OPTS`).

Recommendation: stop copying the default file. Load packaged defaults, deep-merge an optional user file, then an optional project file, then environment variables, then flags. Ship the user file empty/commented. Remove dead keys.

### 6.2 Environment variables

Only two are read in the whole codebase: `JAVA_OPTS` (`config/schema.py:40`) and `EDITOR` (`cmd/config/edit.py:22`). Neither is documented in the README or help. Missing and expected: `TLA_TOOLS_VERSION` (override the pin for one shell/CI job, cf. `RUSTUP_TOOLCHAIN`, `UV_PYTHON`, `MISE_<TOOL>_VERSION`), `TLA_CONFIG`, `TLA_HOME`/`TLA_CACHE_DIR`, `GITHUB_TOKEN`/`GH_TOKEN`, `TLA_JAVA_OPTS`, `JAVA_HOME`.

### 6.3 Per-project configuration and pinning

There is none.

- The pin is a single global text file inside the *cache* directory: `~/.cache/tla/tools/tools-pinned-version.txt` containing e.g. `v1.8.0-4ba7d88` (`versioning/paths.py:28-30`). Installed jars and compiled modules live there too. `~/.cache` is routinely wiped (and is not persisted on CI runners unless cached explicitly), taking the pin and user-registered modules with it. Jars are re-downloadable (though a rolling build is not: the old SHA's jar is gone upstream once the release is re-published), but the pin and the modules registry are state/data and belong in `user_data_dir` / `user_state_dir`.
- A repository cannot declare "this spec is checked with tla2tools v1.8.0 at commit 4ba7d88". Compare `rust-toolchain.toml`, `.nvmrc`, `.python-version`, `.tool-versions`/`mise.toml`.
- "Project" is inferred heuristically from the presence of `modules/`, `classes/` or `lib/` next to the spec or one level up (`project/core.py`). There is no marker file and the search does not walk further up.

Recommendation: a project file discovered by walking up from the spec/cwd, e.g. `tla.toml` (or `.tla-version` for the minimal case):

```toml
[tools]
version = "v1.8.0"
sha = "4ba7d88"          # required for rolling tags; verified after download
# sha256 = "..."         # optional jar checksum

[tlc]
workers = "auto"
args = ["-deadlock"]

[java]
opts = ["-Xmx8g"]

[modules]
paths = ["modules"]
use_global = false
```

Resolution order for the tools version: `--tools-version` flag > `TLA_TOOLS_VERSION` > project file > global pin. `tla tools pin --local` writes the file; `tla tools install` with no args installs what the project file asks for (like `rustup show`/`mise install`). Because upstream does not retain old rolling jars, also document that reproducing an old rolling SHA requires a cache or a mirror URL - and consider `tools install --from <path>` to import a jar from CI cache.

---

## 7. Shell completion, help text, typos

Completion: explicitly disabled - `add_completion=False` (`cli.py:20`). Typer provides bash/zsh/fish/PowerShell completion for free; the usual objection is that `--install-completion`/`--show-completion` clutter root help. Options: enable it, or add a `tla completion <shell>` command that prints the script. Dynamic completers for installed versions (`pin`, `uninstall`, `path`, `upgrade`) and module names (`modules remove`) are a few lines each.

Help text quality: every command has a one-line description; no command has examples, a long description, or an epilog. Specific defects:

| Location | Text | Issue |
|---|---|---|
| `tla --help` | "TLA+ tools: download TLA+ toolset distribution, compile custom modules, run model checker." | Differs from the package summary printed by `tla --version` ("TLA+ tools: download TLC, compile custom modules, run model checker"). Pick one. |
| `tla tlc --help` SPEC | "Name of the TLA+ specification (without .tla extension)." | Inaccurate (2.5). |
| `tla tlc --help` | `--refresh-interval FLOAT  Refresh interval for the output (seconds).` | No-op (2.5). |
| `tla tlc --help` | `--raw  Run TLC in raw mode without structured tool mode formatting.` | Jargon. Suggest "Print TLC's own output unmodified (no parsing or formatting)." |
| `tla tlc --help` | `--cleanup  Purge all cached TLC run artifacts from cache.` | "cached ... from cache"; and it is an action, not an option. |
| `tla tools path --help` | `version  [VERSION]` with empty description | `path.py:10` has no `help=`. |
| `tla tools install --help` | "Download and install a specific TLC version." | Does not say what happens with no VERSION (latest non-prerelease) or that the first install is auto-pinned. |
| `tla tools upgrade --help` | "Upgrade an installed version (or the pinned version) to its latest remote build." | The only place the rolling-build concept surfaces, and it is unexplained. Users will read "upgrade" as "move to a newer version", which it does not do. |
| `tla tools uninstall --help` | `--yes  Skip confirmation prompt.` | Only skips the `--all` prompt, not the multi-build prompt. |
| `tla modules --help` | "Manage TLA+ Java modules." | They are TLA+ modules with optional Java overrides. |
| `tla modules add --help` | "Path to the module directory to add." | Does not describe the expected layout (`modules/`, `modules/tlc2/overrides/*.java`, `lib/*.jar`), that the directory name becomes the module name, or that an existing module is replaced. |
| `tla modules list` | column "Last Built/Modified" | Value is local time without zone (`modules/add.py:135`). |
| `tla modules remove` | "successfully deleted from cache" vs `add` "successfully added to cache" | "cache" undersells it: this is the registry of user modules. |
| Root help | Command order | Put `tlc` first, then `tools`, `modules`, `config`, then maintenance; or use Typer `rich_help_panel` to group "Run", "Manage", "Maintenance". |

Typos and wording found:

- `java/inspector.py:35` comment: "distributions that might minimal output" (missing verb). Line 29 references a non-existent `docs/development.md`.
- CHANGELOG 0.7.0: "compiles Java overrides and copy subfolders" (copies).
- CHANGELOG 0.5.0: "The TLC output now parsed" (is now parsed).
- Status text "canceled" (`components.py:57,145,254`) while the enum is `Stopped` and the footer says "Stop with Ctrl + C"; pick one word.
- `list.py` column `Tag/SHA` (see 2.3).
- No user-facing spelling errors were found in help output.

---

## 8. Documentation

### 8.1 README accuracy against actual commands

`README.md` is 40 lines. Line-by-line:

| README line | Claim | Actual | Verdict |
|---|---|---|---|
| 13 | Heading "Toolset Management (`tla tools`)" | First bullet under it is `tla check-java`, which is not in `tla tools` | Mismatch |
| 15 | `tla tools list` | Exists | OK |
| 16 | `tla tools install [vX.Y.Z]` | Exists; also accepts a URL and `--force`; default = latest non-prerelease; auto-pins on first install | Incomplete |
| 17 | `tla tools pin <version>`: "Set default toolset version for TLC runs" | Exists; requires the version to be installed; may prompt | Incomplete |
| 20 | `tla tlc <spec>` | Exists | OK |
| 21 | `--show-command`: "Inspect exact JVM command before execution" | Prints *instead of* executing (help says so); command lacks `-tool`; not shell-quoted | Mismatch |
| 24 | `tla modules add <path>`: "register module in CLI cache" | OK; expected directory layout not described | Incomplete |
| 25-26 | `modules list`, `modules remove <name>` | OK | OK |
| 28 | Link `docs/examples/` | Relative link; README is the PyPI long description (`pyproject.toml:9`), where relative links do not resolve | Broken on PyPI |
| 34 | `uv tool install tlaplus-cli` | Plausible; no `pipx`/`pip` alternative; no mention that the command is `tla`, not `tlaplus-cli` | Incomplete |
| 39 | `nix profile install github:nikolskiy/tlaplus-cli` | `flake.nix` exists; not verified | Unverified |

Present in the CLI but absent from the README:

- `tla tools upgrade`, `uninstall` (`--all`, `-y`), `path`, `dir`, `meta sync`
- `tla tools install <URL>`, `--force`
- `tla tlc --raw`, `--coverage`, `--cfg`, `--cleanup`, `--version`, `--refresh-interval`
- `tla modules path`
- `tla config list`, `tla config edit`
- `tla fetch-cache clear`
- `tla --version`
- Prerequisites: Java 11+ (`java.min_version`), a JDK with `javac` for `modules add`, Python 3.11+
- Config file location, keys, `JAVA_OPTS`
- Where things are stored (`~/.cache/tla/{tools,modules,run}`)
- Spec resolution rules (`Spec`, `Spec.tla`, `spec/Spec.tla`), cfg resolution, project-root detection (`modules/`, `classes/`, `lib/`)
- Exit codes
- What the output looks like (no sample, no screenshot)

Structure: "Quick Start & Usage" is a command list, not a quick start (no install -> check-java -> tools install -> tlc sequence with expected output), and "Quick Installation" comes *after* usage.

### 8.2 CHANGELOG

Readable and follows Keep a Changelog; entries are specific and user-facing, which makes it the best documentation in the repo today. Issues:

| Entry | Problem |
|---|---|
| 0.3.1 "Internal cache directory moved from `~/.cache/tlaplus-cli/tlc` to `~/.cache/tlaplus-cli/tools`" | Actual directory is `~/.cache/tla/...` (`_APP_NAME = "tla"`, `config/loader.py:10`; confirmed on disk). |
| 0.3.1 "`uninstall`: Added `--all` flag to remove all tags for a specific version name" | Current `--all` removes *every* installed version (`uninstall.py:76,80-83`). Behaviour changed without a changelog entry, or the entry was wrong. |
| 0.3.2 "Provides a detailed error message listing all checked locations" | Not the case today (section 4). |
| 0.7.0 "Comprehensive documentation updates." | README is 40 lines; older, longer docs appear to have been removed without an entry. |
| 0.5.0 `--show-command` on `modules build`, `--resolved` on `modules path`; 0.4.0/0.3.5 `modules path <PATH>`, `modules lib` | Removed in 0.7.0; "Removed" lists the commands but not the lost flags or that `module_path`/`module_lib_path` are now hand-edit only. |
| 0.3.1 | Two "Breaking Change" items are filed under "Added". |
| 0.8.1, 0.2.1 "Fixed" | Test-suite-only changes; not user-facing. |
| Whole file | No compare links at the bottom, no "Unreleased" section, no migration notes for breaking renames (`tla tlc` -> `tla run` -> `tla tlc` across 0.2.1 and 0.3.1). |

Five command renames/removals in six months at 0.x is acceptable, but each should carry a one-line "before -> after".

### 8.3 docs/examples

Contents: four module sets (`QueueModule`, `module-set-a`, `module-set-b`, `sequences-ext`) and `spec/` with three specs. Problems:

- No top-level `docs/examples/README.md`. Nothing says which module set goes with which spec, or the commands to run. The intended flow (inferred) is `tla modules add docs/examples/QueueModule && tla tlc docs/examples/spec/queue`, and `test_both` needs both `module-set-a` and `module-set-b`. A reader has to reverse-engineer this from `EXTENDS` lines.
- Only `sequences-ext/README.md` exists, and it says what the example is *not* for ("use the actual CommunityModules instead") without saying how to do that with this CLI - `modules install-community` was removed in 0.7.0 and there is no replacement workflow documented.
- No pure-TLA+ example (no Java) - the most common user case. No example of an invariant violation showing the formatted error trace, no `--coverage` example, no `--cfg` example.
- Naming is inconsistent: `QueueModule` (PascalCase) vs `module-set-a`, `sequences-ext` (kebab). Since the directory name becomes the registered module name, examples teach a naming convention implicitly.
- `docs/examples/sequences-ext/lib/commons-lang3-3.12.0.jar` is a committed binary; fine for tests, but it should be stated.
- The examples double as integration-test fixtures (`tests/integration/`), which is good, but they read as fixtures (`module-set-a`, `test_both`) rather than as teaching material.
- A git-ignored `docs/examples/spec/states/` directory is present in the working tree from a pre-`-metadir` run; harmless.

### 8.4 Missing documentation topics

| Topic | Why it matters | Suggested location |
|---|---|---|
| Concepts: the rolling release | The tool's main reason to exist. Explain: upstream re-publishes the `v1.8.0` prerelease with a new commit; the same tag therefore means different jars over time; tlaplus-cli stores `tag-shortsha`; `upgrade` = move to the newest build of the same tag; `install` with no args skips prereleases; how to tell which build you have (`tla tlc --version`); what is and is not reproducible | `docs/concepts/versions.md` |
| Installation and prerequisites | Java 11+, JDK for overrides, uv/pipx/Nix, verifying with `tla check-java`, first `tools install` | `docs/install.md` + README quick start |
| Command reference | Auto-generate from Typer (`typer tlaup.cli utils docs`) so it cannot drift again | `docs/reference/cli.md` |
| Configuration reference | Every key, default, env var, file location per OS | `docs/reference/configuration.md` |
| Exit codes and output modes | CI authors need this | `docs/reference/exit-codes.md` |
| Custom modules guide | Directory layout, how overrides are discovered (`implements ITLCOverrides`, service file), global vs project-local `modules/`/`classes/`/`lib/`, precedence order from `ClasspathResolver` | `docs/guides/modules.md` |
| CI recipe | GitHub Actions snippet: setup-java, `uv tool install`, cache `~/.cache/tla`, `tla tools install vX`, `tla tlc` | `docs/guides/ci.md` |
| Troubleshooting | GitHub rate limit, corporate proxy/CA (truststore is already integrated - CHANGELOG 0.3.1 - but undocumented), "tla2tools.jar not found", stale fetch cache, javac missing, Java too old | `docs/troubleshooting.md` |
| Contributing | `uv sync`, `poe lint`, `poe test`, unit vs integration tests, release script, commit conventions. There is no `CONTRIBUTING.md`; `inspector.py:29` cites a `docs/development.md` that does not exist | `CONTRIBUTING.md` |
| Architecture notes | Package map (`cmd/`, `versioning/`, `tlc/parser`+`formatter`, `java/classpath`), the `-tool` mode parsing pipeline, cache layout | `docs/architecture.md` |

### 8.5 Is a docs site warranted?

Not yet as a first step. Priority order:

1. Fix the README (accurate quick start, prerequisites, full command table, link to docs with absolute URLs for PyPI).
2. Add the Markdown pages above under `docs/`, readable on GitHub.
3. Generate the CLI reference from code in CI and fail on drift.

Once there are roughly 8-10 pages, publishing them with MkDocs Material on GitHub Pages is about an hour of work (one `mkdocs.yml`, one workflow) and gives search, versioning and a stable URL for error messages to point at. A site becomes worth it when error messages start linking to docs ("see https://.../troubleshooting#rate-limit") and when a JSON schema needs a canonical home.

---

## 9. Smaller defects found along the way

| # | Defect | Evidence |
|---|---|---|
| 1 | `tools upgrade v1.8.0` when two v1.8.0 builds are installed compares only `matching[0]` (sort order dependent) | `upgrade.py:21-23` |
| 2 | `tools install v1.8.0` when an older v1.8.0 build exists installs a second build beside it and does not move the pin; `tla tlc` keeps using the old one with no notice | `install.py:72-87`, `_auto_pin_if_needed` |
| 3 | `tools pin` validates choice range; `tools uninstall` accepts negative indexes (`matching[-1]`) | `uninstall.py:45-47` |
| 4 | Local version directory names are split on the first hyphen, so a tag containing a hyphen (e.g. `v1.8.0-rc1`) would be mis-parsed | `resolver.py:87-89` |
| 5 | A stale legacy `github_cache.json` sits beside `github_cache_tla2tools_jar.json` in the real cache | `~/.cache/tla/` listing; cleared only by `fetch-cache clear` |
| 6 | `tools dir` and `modules list` scan directories without the legacy migration that `get_pinned_version_dir` triggers | `paths.py:33-35` |
| 7 | `modules add` copies the tree and compiles in place; names collide on directory basename across projects | `modules/add.py:57-62` |
| 8 | Downloads have no integrity check and write straight into the final directory (partial file removed on exception, but not on SIGKILL) | `downloader.py:17-38` |
| 9 | 40 duplicated lines between TTY and non-TTY callbacks; comment "Keep tests happy by updating the formatter" | `cmd/tlc.py:157-195` vs `203-238` |

---

## 10. Recommendations ranked by user impact versus effort

Effort: S = under half a day, M = 1-3 days, L = a week or more. Impact is for end users, CI and agents.

### Tier 1 - high impact, low effort (do first)

| # | Recommendation | Impact | Effort |
|---|---|---|---|
| 1 | Fix the three traceback paths in `tla tlc` (no Java; `--raw` and `--show-command` with no jar): one preflight, catch `RuntimeError`, disable pretty exceptions, add `--debug` | High | S |
| 2 | TLC argument passthrough: everything after `--` appended to the TLC argv; add `--workers` (default `auto`) | High | S |
| 3 | Rewrite the README: prerequisites, 5-line quick start with expected output, complete command table, flags, config location, exit codes, absolute links | High | S |
| 4 | Make version selection non-interactive: accept `tag@sha` / directory name in `pin`, `uninstall`, `path`, `upgrade`; error (not prompt) when ambiguous and stdin is not a TTY; make `--yes` apply to all prompts | High | S |
| 5 | Document exit codes; return 130 on Ctrl+C; use exit 2 for hand-rolled usage errors | Medium | S |
| 6 | Show rolling/prerelease and "update available" in `tools list`; fix the `Tag/SHA` header; keep installed rows adjacent; add `--installed` (no network) | High | S-M |
| 7 | Remove or implement `--refresh-interval`; fix SPEC help; add help to `tools path VERSION`; make `--show-command` print the real, shell-quoted command including `-tool` | Medium | S |
| 8 | Add next-step hints to the six error messages in section 4; route all messages through `ui.py`; honour `NO_COLOR` there | Medium | S |
| 9 | `docs/examples/README.md` with exact commands per example; add one pure-TLA+ example with a violated invariant | Medium | S |
| 10 | Enable shell completion (`tla completion <shell>` or `add_completion=True`) | Medium | S |

### Tier 2 - high impact, medium effort

| # | Recommendation | Impact | Effort |
|---|---|---|---|
| 11 | `--json` for `tla tlc` (serialise `ModelCheckResult`: status, exit code + meaning, errors, traces, SANY diagnostics with file/line/col, stats, coverage) and for `tools list`, `modules list`, `tools path`; publish a schema | High (CI, editors, agents) | M |
| 12 | Project-level pin and config file (`tla.toml` / `.tla-version`) discovered by walking up; `TLA_TOOLS_VERSION` and `--tools-version` overrides; `tools pin --local`; `tools install` with no args honours it | High (reproducibility) | M |
| 13 | Config layering: packaged defaults + optional user file + project file + env + flags; stop copying the default file; drop dead keys (`workspace.root`, `workspace.spec_dir`, `tlc.refresh_interval`, `tla.community_modules`); friendly validation errors; `config path`, `config show --effective` | Medium-High | M |
| 14 | stdout/stderr discipline: results to stdout, diagnostics to stderr; single shared consoles; `--quiet` and `-v/--verbose` (move version to `-V`); `--color auto/always/never` | Medium | M |
| 15 | `tla doctor` (Java, javac, pinned jar and its build age vs remote, config validity, cache paths, registered modules), keeping `check-java` as an alias | Medium | S-M |
| 16 | Concepts page on the rolling release + configuration reference + troubleshooting + CONTRIBUTING | Medium | M |
| 17 | `GITHUB_TOKEN`/`GH_TOKEN` support and a rate-limit-specific error message | Medium (CI) | S |
| 18 | Move pin and registered modules out of the cache directory to data/state dirs (with migration); add `TLA_HOME` override | Medium | M |

### Tier 3 - worthwhile, larger or lower urgency

| # | Recommendation | Impact | Effort |
|---|---|---|---|
| 19 | Consolidate caches under `tla cache dir|clear [--api|--runs|--all]`; deprecate `fetch-cache clear` and `tlc --cleanup` with aliases; flatten `tools meta sync` | Low-Medium | S-M |
| 20 | Scope global modules: per-project enable list, `--no-global-modules`, show active modules in the run header | Medium (correctness) | M |
| 21 | First-run auto-install offer in `tla tlc` (TTY prompt; `--yes`/env for CI) | Medium | S-M |
| 22 | Auto-generated CLI reference checked in CI; MkDocs site once docs exceed about 8 pages | Medium | M |
| 23 | Jar integrity: record sha256 in metadata, verify on pin from project file, atomic download via temp file + rename | Medium | M |
| 24 | Editor-friendly diagnostics (`path:line:col: severity: message`), GitHub Actions annotations mode, JUnit output | Medium | M |
| 25 | Version aliases `latest`, `stable`, `rolling`; accept versions without the `v` prefix | Low-Medium | S |
| 26 | CHANGELOG hygiene: correct the 0.3.1 cache path and `--all` entries, add an Unreleased section and compare links, mark breaking changes consistently | Low | S |

### Suggested sequencing

- Release A (hardening, no breaking changes): items 1, 2, 4, 5, 7, 8, 3, 9, 10.
- Release B (automation): items 11, 14, 6, 17, 15.
- Release C (reproducibility; needs a design note first): items 12, 13, 18, 20, 23.
- Docs track in parallel: 16, 22, 26.
