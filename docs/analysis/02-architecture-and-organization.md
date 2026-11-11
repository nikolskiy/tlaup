# 02 - Architecture and code organization

Scope: all of `src/tlaplus_cli` (about 4300 lines, read in full) at commit `bac6ba1` (0.8.1), plus the test fixtures where they show how the structure affects testability. Exploration only; nothing in the source tree was changed. Line numbers refer to that commit.

Two claims below were checked by running code rather than by reading: the ineffective `mock_download` patch (finding 3) was confirmed with a one-off interpreter check. Everything else is from reading; where a consequence is inferred rather than observed, it says so.

## Summary

The project has a sound skeleton: a pure, well-isolated TLC output parser, a clean module-level import graph with no domain-to-command imports, typed config, and a sensible on-disk idea (one directory per installed version, text-file pin). The problems are concentrated in four places:

1. The `tla tlc` path (`cmd/tlc.py`, `tlc/runner.py`, `tlc/formatter.py`, `tlc/components.py`) carries a large amount of dead or test-only display code, duplicated branches, and no object describing "one TLC invocation", so the same things are resolved three to five times per run and the `--show-command` output differs from what is executed.
2. Paths and state are reached through module-level functions spread over `config/loader.py` and `versioning/paths.py`. `versioning.paths` has become the application-wide path registry, which gives odd dependency directions and forces tests to patch the same function at five import sites.
3. An installed version's identity lives in its directory name and is parsed and re-composed by string operations in at least eight places, with two incompatible parsing rules.
4. The custom-module build pipeline lives entirely inside a command function (`cmd/modules/add.py`), while the module named `tlc/compiler.py` contains no compiler.

Adding a second tool that ships in `tla2tools.jar` (SANY, PlusCal, TLATeX) is moderately easy once a "Java tool invocation" is extracted from `build_tlc_command`. Adding a tool with its own distribution (Apalache, TLAPS) needs a real change to the version store, because "tool" currently means "a `tla2tools.jar`" everywhere.

## Actual import graph

Package-level edges, derived from every `import` in `src/`:

```
cli ──> cmd/*, config.loader, versioning
cmd/tools/*      ──> versioning (facade), config.loader, ui
cmd/modules/*    ──> versioning.paths, java.classpath, tlc.compiler, tlc.run_cache, config.loader
cmd/tlc          ──> tlc.{runner,formatter,components,models,compiler,run_cache}, java.classpath, project, config.loader, ui
cmd/check_java   ──> java, config.loader
cmd/config/*     ──> config.loader
cmd/fetch_cache  ──> versioning

tlc.runner       ──> config.loader, java, java.classpath, project, tlc.{compiler,models,parser,run_cache,sany}
tlc.compiler     ──> config.loader, versioning
tlc.run_cache    ──> versioning.paths
tlc.formatter    ──> tlc.{components,models,sany}
tlc.parser       ──> tlc.{codes,models,values}          (pure)
tlc.sany, tlc.codes, tlc.models                          (pure, leaf)

java.classpath   ──> config.schema, versioning.paths
java.inspector   ──> ui
project.core     ──> (stdlib only)

versioning.api        ──> cache.github, versioning.{paths,schema}, ui
versioning.downloader ──> versioning.{metadata,paths,resolver,schema}, rich.progress
versioning.resolver   ──> versioning.{metadata,paths,schema}
versioning.metadata   ──> versioning.schema, ui
versioning.paths      ──> config.loader, ui
cache.github          ──> versioning.schema, ui
config.loader         ──> config.schema
```

Observations:

- No domain package imports `cmd`. The command layer is the only consumer of Typer command registration. This is the main thing to preserve.
- There is no module-level cycle, but there is a package-level one: `versioning.api -> cache.github -> versioning.schema` (`versioning/api.py:7`, `cache/github.py:6`). It works only because `versioning/__init__.py` has already started importing when `cache.github` asks for the `schema` submodule.
- `java.classpath -> versioning.paths` (`java/classpath.py:6`) and `tlc.run_cache -> versioning.paths` (`tlc/run_cache.py:6`) are odd directions. Neither has anything to do with versioning; they want `get_modules_dir()` and `get_tlc_run_dir()`, which happen to live there.
- Any import of `versioning.paths` executes `versioning/__init__.py`, which eagerly imports `api` and `downloader` and therefore `requests` and `rich.progress`. So computing a classpath or a run directory pulls in the HTTP stack.
- `ui` is imported by domain modules (`versioning.api`, `versioning.metadata`, `versioning.paths`, `cache.github`, `java.inspector`), and `versioning.downloader` drives a Rich progress bar directly. See finding 6.

## What is good and should be kept

- **The TLC output parser stack is pure and well bounded.** `tlc/parser.py`, `tlc/codes.py`, `tlc/values.py`, `tlc/models.py`, and `tlc/sany.py` do no I/O, import nothing outside `tlc/`, and are line-driven (`TlcParser.process_line`, `parser.py:75`), which makes them trivially testable and reusable for any front end. This is the best-structured part of the project.
- **Dependency direction between layers is right.** Commands depend on domain packages, never the reverse.
- **`project/core.py` is a pure function** taking its inputs as arguments (`find_project_root`, lines 11-31). Good shape, even if the package around it is oversized (finding 8).
- **`ClasspathResolver` takes config, project root, and tool jar through its constructor** (`java/classpath.py:30-52`) and has an explicit, documented precedence (CLI > project > config > managed). The one global reach is `get_modules_dir()` (lines 107, 163).
- **`versioning/api.py` separates fetch from transform.** `_process_remote_versions` (lines 41-74) is a pure function over JSON; `FetchStatus` (`schema.py:23-27`) with a stale-cache fallback (`api.py:99-105`) is a good model for offline behaviour.
- **Typed configuration** with pydantic (`config/schema.py`), OS-standard directories via `platformdirs`, and the default config shipped as package data and read through `importlib.resources` (`config/loader.py:60-65`).
- **The pin as a plain text file** holding a directory name (`versioning/paths.py:28-43, 78-82`) rather than a symlink. Simple and portable.
- **Per-spec TLC metadir keyed by a content hash** (`tlc/run_cache.py:9-53`) keeps TLC state out of the user's project.
- **Tooling discipline**: strict mypy, a broad ruff rule set, bandit, and the Typer sub-app layout (`tla tools ...`, `tla modules ...`).

## Findings, ranked by impact

### 1. The `tla tlc` display path is half dead and duplicated (high)

Evidence:

- `cmd/tlc.py:157-195` (TTY callback) and `cmd/tlc.py:203-238` (non-TTY callback) are the same 35 lines with `live.console.print` swapped for `print`. Four `nonlocal` counters track streaming state by hand.
- Both callbacks call `formatter.update(layout, res)` under the comment "Keep tests happy by updating the formatter" (`cmd/tlc.py:160-161, 206-207`). The `layout` object is never rendered anywhere. It exists so that tests which patch `tlaplus_cli.cmd.tlc.TlcFormatter.update_logs` (four occurrences in `tests/`) keep passing.
- As a result the following production code is reachable only from tests or from that unrendered layout: `_Section`, `TlcDisplay`, `create_layout`, `update`, `_has_child`, `_ensure_layout_structure`, `update_header/stats/logs/clock`, `StatusInfoRenderable` (`tlc/formatter.py:27-67, 270-348`); `HeaderComponent`, `StatusInfoComponent`, `LogsComponent`, `StatsTableComponent` (`tlc/components.py:38-136`).
- Never referenced from `src/` at all: `StatusFooterComponent` (`components.py:139-183`, a near copy of `StatusFooterRenderable` at 245-287), `TlcDisplayComposer` (186-199), the `TlcComponent` protocol (30-35, used only by the composer), `TlcFormatter.info_dedup` (`formatter.py:82`), `_show_diagnostic_info` (`cmd/tlc.py:42-62`), and the `--refresh-interval` option, which is accepted and ignored (`cmd/tlc.py:85-89`; `TlcConfig.refresh_interval` at `config/schema.py:29` is likewise unread).
- The elapsed-time and status-text logic is written three times (`components.py:54-71`, `142-163`, `251-272`).
- `formatter.py` annotates `update_stats/logs/clock` parameters as `rich.layout.Layout` (lines 325-334) while the object is the home-made `TlcDisplay`; the rest is typed `Any`.
- `cmd/tlc.py` mixes four output mechanisms: `print`, `typer.echo`, `ui.*`, and fresh `Console()` instances created at lines 153, 254, 265, 278.

Roughly 150 of 287 lines in `components.py` and 110 of 348 in `formatter.py` are not on any production path. What `formatter.py` really provides is four static renderers (`render_sany_error`, `render_error_trace` with `diff_values`, `render_coverage_table`, `render_inline_coverage`).

Direction: decide which display is the product (the streaming one is) and delete the layout machinery together with the tests that pin it. Introduce one small "reporter" object with an output sink, so TTY and non-TTY differ only in the sink and the footer, and move the streaming state and the final summary (`cmd/tlc.py:250-286`) into it under `tlc/`. `cmd/tlc.py` should shrink to option parsing, error mapping, and exit code.

### 2. No "TLC invocation" object; work is repeated and the shown command is not the run command (high)

`run_tlc` and `build_tlc_command` take the raw `spec: str` and each re-derive everything from globals.

Evidence, for one `tla tlc Spec --cfg x` run:

- `resolve_spec_file` is called at `cmd/tlc.py:110`, `runner.py:176`, `runner.py:121`, and again at `cmd/tlc.py:255` and `282` when there are SANY errors or coverage.
- `find_project_root` is called at `cmd/tlc.py:113`, `runner.py:122`, `runner.py:189`.
- `resolve_cfg_file` at `cmd/tlc.py:118` (result discarded, used as an existence check) and `runner.py:158`.
- `load_config()` at `cmd/tlc.py:112`, `runner.py:173`, `114`, `272`.
- `get_tlc_jar_path()` at `runner.py:116` and `273`, each of which calls `get_pinned_version_dir()`, each of which runs the legacy migration probes (finding 4).
- `get_tlc_version()` (`cmd/tlc.py:137`) spawns a JVM just to print a version header before the real JVM starts.

Consequences beyond wasted work:

- **`--show-command` does not show the executed command.** `cmd/tlc.py:124-126` appends `-coverage 1` after the spec argument and never adds `-tool`, while `run_tlc` inserts `-tool` and `-coverage 1` before the spec by positional `cmd.insert(-1, ...)` (`runner.py:181-187`). Flag assembly exists in two places with different results.
- **`build_tlc_command` has side effects.** It calls `get_spec_run_dir` (`runner.py:144`), which creates a directory and deletes stale sibling directories (`run_cache.py:49-52`), so `--show-command` mutates the cache.
- **Error mapping is by exception type coincidence.** `run_tlc` converts any `SubprocessError` or `OSError` from `Popen` into `FileNotFoundError("'java' not found")` (`runner.py:217-219, 265-267`), and the command only catches `FileNotFoundError` (`cmd/tlc.py:119, 287`). `validate_java_version` raises `RuntimeError` (`java/inspector.py:73, 86`), which nothing on the `tla tlc` path catches, so a missing or old Java should surface as a traceback (inferred from reading, not run). The `--raw` branch (`cmd/tlc.py:132-134`) and the `--show-command` branch (`cmd/tlc.py:123-130`) are outside any `try`, so a missing jar there is also unhandled.
- The raw and parsed `Popen` loops are two copies of the same block (`runner.py:194-219` and `224-267`).
- `ModelCheckResult.sany_errors` is typed `list[Any]` (`models.py:131`) and assigned from outside the parser (`runner.py:246`); it is not populated on the Ctrl-C path (`runner.py:252-261`).
- `if not cmd:` at `cmd/tlc.py:127` can never be true.

Direction: introduce a small immutable value (spec path, cfg path, project root, cwd, jar, run dir, flags) built once by a resolver function that takes `Settings` and paths as arguments. `build_command(invocation)` becomes pure and is the single place flags are assembled; `run(invocation, on_event)` only spawns and feeds parsers. Define a small domain exception family (spec not found, tool not installed, Java missing or too old) and map it to exit codes in one place in `cmd/`.

### 3. Paths and config are global functions scattered over two packages (high, mainly for testability)

Evidence:

- `cache_dir()` and `config_dir()` live in `config/loader.py:45-57`. Every derived location lives in `versioning/paths.py:8-25`: tools, custom modules, run dir, TLC run dir, GitHub cache. The same file also holds pin state (28-43, 78-89), the migration (46-75), and fetch-cache clearing (92-97). It is the application's path registry under a misleading name, which is why `java.classpath`, `tlc.run_cache`, and `cmd/modules/*` import "versioning".
- Because every consumer does `from ... import cache_dir`, tests must patch each import site. `tests/conftest.py:56-65` patches `cache_dir` in five modules, four of them with `create=True`, including `cmd.tools.install`, which does not import `cache_dir` at all, so that patch creates an attribute nothing reads. Across `tests/` there are 161 patch calls; the most common targets are `config.loader.config_dir` (15), `tlc.runner.load_config` (12), `tlc.runner.validate_java_version` (11).
- The patch-by-import-site pattern has already produced silently ineffective fixtures. `tests/unit/tools/conftest.py:57` patches `tlaplus_cli.versioning.download_version`, but `cmd/tools/install.py:8-16` bound the name at import time. Verified in an interpreter: after the patch, `tlaplus_cli.cmd.tools.install.download_version` is still the real function. Those tests pass because `mock_github_api` patches `requests.get` on the shared module object, so the real downloader runs against a `MagicMock` response. `mock_load_config` (`tests/conftest.py:50`, patching `config.loader.load_config`) has the same shape and by the same mechanism cannot affect `cmd` modules that imported the name.
- `load_config()` is an `lru_cache` singleton (`config/loader.py:13`) that also creates the file on first call (`ensure_config`, 68-75). The root callback calls it for every command (`cli.py:46`). Two consequences: state leaks between tests unless the cache is cleared, and an invalid config file makes every command fail in the callback, including `tla config edit`, the command a user would use to fix it (inferred from reading).
- Config evolution is not handled. `Settings` requires `tla`, `workspace`, and `tlc` (`config/schema.py:47-49`), the user file is a one-time full copy of the default, and there is no merge with packaged defaults or schema version. Any new required key in a later release invalidates existing user configs. Defaults are also stated twice (`TlcConfig` and `JavaConfig` defaults versus `resources/default_config.yaml:19-28`).
- `JAVA_OPTS` is applied inside a pydantic `before` validator (`config/schema.py:36-43`), so environment reading is hidden in the schema, only fires when a `java` key is present in the file (inferred), and would be written back to disk by `save_config`.
- Configured but unused: `workspace.root` and `workspace.spec_dir` (only `workspace_root()` at `loader.py:78-87` reads `root`, and nothing calls it; `runner.py:29` hardcodes `"spec"`), `tla.community_modules` (`schema.py:16`, yaml 6-9), `tlc.refresh_interval`. `save_config` (`loader.py:25-42`) has no production caller and still carries "as per plan" comments. `module_path` and `module_lib_path` sit at the top level of `Settings` (51-52), absent from the default YAML.

Direction: one top-level `paths` module (or a small `AppPaths` dataclass) that owns every directory, with an environment override for the cache and config roots so tests and users can redirect without patching. Build `Settings` and `AppPaths` once in the root callback, store them on the Typer context, and pass them down as arguments; domain functions stop calling `load_config()` themselves. Move pin and migration into a version-store module. Make config loading tolerant (defaults for every section, merge over packaged defaults) and let `config` subcommands run without a valid config.

### 4. Installed-version identity is a parsed directory name (high for correctness, medium for effort)

Layout today:

```
<cache>/tools/<tag>-<short_sha>/tla2tools.jar            GitHub install
<cache>/tools/<tag>-<ISO timestamp>/tla2tools.jar        URL install
<cache>/tools/<dir>/meta-tla2tools.json
<cache>/tools/tools-pinned-version.txt                   contains <dir>
<cache>/github_cache_<asset>.json
<cache>/modules/<name>/{lib,modules,tlc2,classes,metadata.json}
<cache>/run/tlc/<spec stem>_<hash8>/
<cache>/tla2tools.jar                                    legacy fallback
```

Evidence:

- The `<tag>-<suffix>` name is composed at `downloader.py:47, 79`, `install.py:64`, `list.py:50, 59, 72`, and parsed at `resolver.py:87` (split on the first hyphen) and `upgrade.py:30` (split on the last hyphen), plus a suffix test at `upgrade.py:53`.
- The two parsing rules disagree. A URL install is named like `v1.8.0-2026-04-06T12:51:28Z` (`downloader.py:76-79`, `metadata.py:11-14`). `upgrade.py:30` turns that into `v1.8.0-2026-04` when it is the pinned version, so `tla tools upgrade` would report it as not found on the remote (inferred). A tag that itself contains a hyphen would break `resolver.py:87` the other way.
- The timestamp contains colons, which are not valid in Windows directory names, while the project is classified "OS Independent" and the changelog cites cross-platform support as the reason for dropping the symlink pin.
- `LocalVersion.short_sha` (`schema.py:19`) holds a timestamp for URL installs. The metadata file, which does contain `tag_name`, `sha`, and `download_url`, is an untyped dict written by two functions with different key sets (`metadata.py:47-54` and `83-91`) and is never used to establish identity, only for `published_at`.
- `_version_sort_key` reads the metadata file and stats the directory for every element on every sort (`resolver.py:53, 58`), and `list_local_versions` sorts on every call.
- Installation is not atomic. The jar is streamed straight into the final directory (`downloader.py:55-59`); cleanup only happens for `RequestException` and `OSError` (60-62), so Ctrl-C leaves a directory that `install.py:65` and `list.py:63` then treat as installed.
- Writing metadata spawns `java ... tlc2.TLC -version` (`metadata.py:17-31`) with the class name hardcoded, duplicating `runner.get_tlc_version` (`runner.py:270-285`), which reads the class from config. So `versioning` knows about TLC and needs Java at install time; `tools meta sync` re-runs it per version.
- Migration: `_migrate_legacy_pin` runs on every `get_pinned_version_dir()` call (`paths.py:35`), three filesystem probes each, several times per command, indefinitely, because there is no layout-version marker. It only runs via the pin lookup, so `tools list` calls `list_local_versions()` (`list.py:22`) before the migration has renamed `tlc/` to `tools/` (`list.py:23`). A third legacy form, `<cache>/tla2tools.jar`, is handled separately in `tlc/compiler.py:11-12` and `uninstall.py:23-29`. With nothing pinned, `get_tlc_jar_path` returns that legacy path, so the "not found at ..." message (`cmd/tlc.py:31`) points at a location the current design never writes.
- The remote cache: `cache/github.py` is 28 lines of (de)serialization for a `versioning` type, while the TTL, file naming, and stale fallback are in `versioning/api.py:81-105`. `get_github_cache_file()` names `github_cache.json`, a file nothing writes; only its `.parent` is used (`api.py:84`, `paths.py:94`). The cache key is the asset name, not the URLs, so changing `tla.urls` in config keeps serving the old list for up to an hour.

Direction: make the metadata file the source of truth and give it a typed model (one writer, one reader, a `source` field distinguishing release from URL installs, a schema version). Hide the directory naming behind a single `VersionStore` (list, get, add, remove, pin, unpin) so no command composes or parses names. Use a filesystem-safe suffix for URL installs. Download to a temporary directory and rename into place. Run migrations once, from the root callback, gated by a layout-version file, and delete the legacy branches after a stated number of releases. Fold `cache/github.py` into `versioning` and key the cache on the request.

### 5. Domain logic in commands, most of all the module build (medium to high)

Evidence:

- `cmd/modules/add.py:47-140` is the whole custom-module pipeline: copy subfolders, find Java sources, build a classpath, run `javac`, write the `META-INF/services` file, write `metadata.json`, clear the run cache, all interleaved with `typer.echo` and `typer.Exit`. It cannot be called as a library. `tests/integration/conftest.py:36-60` consequently re-implements the compile and service-file steps by hand and imports `find_override_classes` from the command module.
- `tlc/compiler.py` (12 lines) contains only `get_tlc_jar_path`. The name is a leftover; the compiler is in `cmd/`.
- Knowledge of the managed-module layout (`lib/`, `modules/`, `classes/`, `metadata.json`, legacy flat form) is spread over `cmd/modules/add.py`, `cmd/modules/list.py:19-31`, `cmd/modules/path.py:34-40`, `java/classpath.py:107-121, 163-169`, and `tlc/runner.py:85-109`. `cmd/modules/path.py:53-61` reconstructs "library jars" by filtering the resolved classpath on a directory being named `classes`.
- `cmd/tools/*`: the same three-argument call `fetch_remote_versions(config.tla.urls.tags, config.tla.urls.releases, config.tla.urls.per_page)` and its error block appear in `install.py:46-50`, `list.py:20`, `upgrade.py:42-46`, `meta/sync.py:17-21`. Version selection and the "already installed" rule are in `install.py:52-69`; the upgrade algorithm is `upgrade.py:18-76`; pin fallback after uninstall is `uninstall.py:94-104`; the disambiguation prompt is written twice (`pin.py:18-28`, `uninstall.py:36-49`).

Direction: add a `modules` domain package (store layout plus build) that raises exceptions and returns results, with `ClasspathResolver` asking it for class and lib directories instead of walking the cache itself. Give `versioning` a few use-case functions (install, upgrade, uninstall with pin fallback, remote listing from `Settings`) so the `tools` commands become argument parsing plus printing.

### 6. UI in domain code and inconsistent output conventions (medium)

- `ui.warn` is called from `versioning/api.py:33, 91`, `versioning/metadata.py:30, 41`, `versioning/paths.py:56, 66, 75`, `cache/github.py:17, 28`, `java/inspector.py:78`; `versioning/downloader.py:28-38` owns a Rich progress bar.
- Commands print errors two ways: 21 hand-written `typer.echo("Error: ...", err=True)` calls against the `ui.error` helper that exists for this purpose. `ui.success` and `ui.info` write to stderr (`ui.py:14-21`), which is surprising for success output.

Direction: domain code reports through return values, exceptions, the `logging` module, or a progress callback; only `cmd/` and a reporter print. Route all command errors through `ui`.

### 7. Extensibility to other TLA+ tools (medium now, high later)

What is tied to TLC or to the jar today:

- `"tla2tools.jar"` appears as a literal 31 times in `src/`. "Tool" in `tools/`, `get_tools_dir`, and `tla tools` means "a version of that jar"; the metadata file is `meta-tla2tools.json`; the jar locator is `tlc.compiler.get_tlc_jar_path`.
- The pin is one global file; config has a single `tla.urls` source.
- JVM launching (Java check, opts, classpath, `-DTLA-Library`, cwd, main class) is embedded in `build_tlc_command` and `run_tlc`.
- `tlc/sany.py` is a parser for another tool's output filed under `tlc/`.

Two different cases:

- **Tools inside `tla2tools.jar`** (SANY `tla2sany.SANY`, PlusCal `pcal.trans`, TLATeX `tla2tex.TLA`, the REPL, trace explorer). The version store needs no change. What is missing is a reusable "Java tool invocation": jar, classpath, JVM options, main class, arguments, cwd, plus a streaming runner. With finding 2 done, `tla sany` or `tla pcal` is a main-class name, an argument list, and optionally a parser. Without it, each new command would copy `build_tlc_command`.
- **Tools with their own distribution** (Apalache: tarball with launcher script and platform independence via JVM; TLAPS: platform-specific native installers; Community Modules: a second jar). These need a distribution dimension the store does not have: `tools/<distribution>/<version>/`, a pin per distribution, an asset selector, archive extraction, possibly platform selection.

Missing abstractions: a distribution descriptor (repository URLs, asset pattern, how to derive a version string), the Java tool invocation, the invocation value object and error family from finding 2, and a reporter.

Premature or half-built generality that currently only adds surface: `asset_name` (`api.py:42, 78`), `jar_name` and `base_dir` (`downloader.py:42, 69`) have no caller that passes them; `tla.community_modules` config is unread; `TlcComponent` and `TlcDisplayComposer` are a plug-in mechanism with no plug-ins. Either finish these as part of a distribution descriptor or remove them until needed.

Suggestion on sequencing: do not build a generic plug-in framework. Extract the Java invocation and add one jar-internal tool (SANY is the natural first, since its parser already exists) to validate the seam; introduce the distribution dimension only when the first non-jar tool is actually scheduled, but reserve the directory level now as part of the layout migration in finding 4, since on-disk layout is the expensive thing to change later.

### 8. Fragmentation, naming, and leftovers (low to medium)

- **Too many tiny files and packages.** `cache/` is one 28-line module; `project/` is 31 lines plus a re-exporting `__init__`; `cmd/tools/meta/` is a package for a single `sync` command; `cmd/fetch_cache/clear.py` is 11 lines; `cmd/tools/dir.py` and `cmd/config/list.py` are 16. One file per group (`cmd/tools.py`, `cmd/modules.py`, `cmd/config.py`) would be around 300, 250, and 50 lines and remove the import-order workarounds below.
- **Two command registration styles.** `tools`, `config`, `fetch_cache`, and `meta` create `app` in `__init__` and import submodules afterwards for their decorator side effects, each needing `# noqa: F401, E402` (`cmd/tools/__init__.py:8`, shadowing the builtins `dir` and `list`). `modules` and `cli.py` register plain functions explicitly (`cmd/modules/__init__.py:13-16`, `cli.py:56-57`). The explicit style has no circular import between a package and its submodules; pick it everywhere.
- **Misplaced or misnamed.** `tlc/compiler.py` (no compiler); `versioning/app_version.py` (the CLI's own version, unrelated to TLA+ tool versions, re-exported through the `versioning` facade and used only by `cli.py:14`); `versioning/paths.py` (finding 3); `tlc/sany.py` (finding 7); top-level `fetch-cache` command for what is one file of release metadata; `InitialStateStatItem` and `initial_states_stat` for what are progress samples (name inherited from the TypeScript port).
- **`versioning/__init__.py` exports private names** `_migrate_legacy_pin` and `_utc_now_iso` in `__all__` (lines 39-40) so tests can import them.
- **Hardcoded values that config pretends to control.** `"spec"` (`runner.py:29`), `"modules"`, `"classes"`, `"lib"` (`classpath.py:70-74`, `project/core.py:16`), `"tlc2.TLC"` (`metadata.py:21`), `"tlc2.overrides.TLCOverrides"` (`runner.py:100-101`) alongside `config.tlc.overrides_class`.
- **Unpopulated model fields**: `workers_count`, `collision_probability`, `trace_file_path` (`models.py:128-132`); `CoverageItem.file_path` and `ErrorTraceItem.file_path` are always `None`.
- **Scaffolding comments**: "as per plan" (`loader.py:31-35`), "New command modules" (`tests/conftest.py:63`), "Import functions for new commands" (`cmd/modules/__init__.py:6`), "Correctly handle subprocess outputs as per docs/development.md" (`inspector.py:29`; that document is not in the repository). `_load_from_cache` (`api.py:18-19`) is a one-line pass-through.
- **Test tree does not mirror the source tree**: `tests/unit/version_manager/`, `tests/unit/spec/` (holds classpath and project tests), `tests/unit/tools/test_fetch_cache.py`, and several test files at the top of `tests/unit/`. These look like names from an earlier module layout.
- Stray double blank lines inside functions (`cmd/tlc.py:135-136`, `runner.py:178-179`) suggest these two files were last edited without the formatter.

## Size assessment of the three large files

| File | Lines | Assessment |
| --- | --- | --- |
| `cmd/tlc.py` | 291 | Too large for a command module. About 35 lines are dead, about 40 are a duplicate branch, about 40 are result reporting that belongs in `tlc/`. Target is under 100. |
| `tlc/formatter.py` | 348 | Not too large in principle, but a third of it is the unrendered layout. After removal it is four renderers and a diff helper, a reasonable single module. |
| `tlc/runner.py` | 285 | Mixes four responsibilities: spec and cfg resolution (19-82), override discovery (85-109), command construction (112-162), process execution (165-267). Splitting resolution and command construction from execution follows naturally from finding 2. |
| `tlc/codes.py` | 314 | A data table. Fine as is. |

## Suggested target shape

A direction, not a prescription; the names are illustrative.

```
tlaplus_cli/
  cli.py                 root callback builds Settings + AppPaths, runs migrations once
  ui.py                  the only place that prints, plus a progress adapter
  errors.py              small domain exception family mapped to exit codes
  paths.py               every directory, env-overridable
  config/                schema, loader (tolerant, merges packaged defaults)
  cmd/                   tools.py, modules.py, tlc.py, config.py, check_java.py (thin)
  store/ (or versioning/) VersionStore, typed metadata, pin, migrations, remote listing + cache, download
  modules/               managed-module layout + build (javac, service file)
  java/                  inspector, classpath, JavaInvocation + streaming runner
  tlc/                   invocation (resolve spec/cfg/project), command, parser stack, report renderers
  sany/                  parser (and later a command)
```

Suggested order of work, each step independently shippable:

1. Delete the dead display code and its tests; collapse the duplicate callbacks (finding 1). Pure reduction, no behaviour change.
2. Centralize paths with an environment override and pass `Settings` and paths down from the root callback (finding 3). This removes most patching and makes the remaining steps testable.
3. Introduce the invocation object and single command builder; fix `--show-command` and error mapping (finding 2).
4. Introduce the version store with typed metadata, atomic install, a layout version, and one-shot migration (finding 4).
5. Extract the module build into a domain package (finding 5).
6. Extract the Java invocation and add the first jar-internal tool (finding 7).
