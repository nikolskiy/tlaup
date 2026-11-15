# 04 - Test suite and testing strategy review

Scope: `tests/` (4 conftests, 40 unit test files, 3 integration test files, fixtures) against `src/tlaup` (about 4300 lines, 2711 statements) on branch `dev` at `fb4a5e0` (0.8.1). Exploration only; nothing in source, config, or tests was modified.

## 1. Summary

The unit suite is fast (under 3 s) and gives 86 % line coverage, but three structural problems undermine what that number means:

1. **The TLC output parser is tested only against hand-written input that does not match what TLC actually prints.** Feeding real TLC 1.7.0 and 1.8.0 `-tool` output through `TlcParser` yields **zero error-trace states** for a 4-state counterexample, and `SanyParser` returns 3 polluted errors for 2 real ones. All parser tests pass regardless. There are no golden files from any TLC version.
2. **Isolation is leaky.** On a clean machine 3 unit tests fail because they silently depend on a real `tla2tools.jar` in the user's cache; 23 of 40 unit test files write into the real config dir (`config.yaml`) and/or real cache dir (`run/tlc/*`); unit tests spawn the real `java` about 23 times and `git` once. The shared `mock_load_config` fixture patches a name nobody looks up, so it is a no-op.
3. **Integration tests never run in CI.** `testpaths = ["tests/unit"]` excludes them; CI nonetheless downloads the real jar from GitHub, only so that the three leaky unit tests pass. CI is one OS, one Python, one Java, one TLC.

## 2. How the tests were run

To honour "do not touch real config/cache", everything ran with `HOME`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME` pointed at empty scratch directories, `COVERAGE_FILE` redirected, `-p no:cacheprovider`, and `HTTP(S)_PROXY=http://127.0.0.1:9` to make any real network call fail. `.venv/bin/python -m pytest` was used directly (equivalent to `uv run pytest` / `poe test`, which CI runs). Python 3.13.5, OpenJDK 25.0.5, Linux.

### 2.1 Unit suite, clean sandbox (no jar in cache)

```
FAILED tests/unit/cmd/test_modules.py::test_modules_add_success - assert 1 == 0
FAILED tests/unit/cmd/test_modules.py::test_modules_add_compilation_failure
FAILED tests/unit/cmd/test_modules.py::test_modules_add_nested_overrides - as...
3 failed, 204 passed in 2.83s
```

The decisive failure output:

```
E   assert 'Compilation failed!' in "Copying subfolders (lib, modules, test, tlc2)...\nError: tla2tools.jar not found. Run 'tla tools install' first.\n"
```

Cause: the tests patch `tlaup.tlc.compiler.get_tlc_jar_path` (`tests/unit/cmd/test_modules.py:23`, `:95`), but `cmd/modules/add.py:13` does `from tlaup.tlc.compiler import get_tlc_jar_path`, so the patch has no effect and the real cache is consulted.

### 2.2 Unit suite, sandbox with an empty fake pinned jar

Creating `<sandbox cache>/tla/tools/v9.9.9-fffffff/tla2tools.jar` (zero bytes) plus a pin file makes everything pass: `207 passed in 1.89s` (2.80 s with branch coverage). This confirms the dependency and is the state CI is in after `tla tools install`.

Slowest tests are all under 0.2 s (`tools/test_install.py::test_install_force_does_not_move_pin` 0.18 s); the slowness there is real `java` being spawned (section 5.3).

### 2.3 Integration suite (not run by default or by CI)

Run against a sandbox `HOME` containing a copy of the locally cached TLC 1.8.0 jar (rev 4ba7d88), Java 25: `4 passed in 6.82s` (1.5 to 2.1 s each). Even here two files leaked into the sandbox "real" dirs: `.config/tla/config.yaml` and `.cache/tla/run/tlc/test_spec_d36b6596`.

### 2.4 Leak inventory (each unit file run alone in a fresh sandbox)

| Leak | Test files |
|---|---|
| creates real `config.yaml` | `check_java/test_check_java.py`, `cmd/test_tlc_cmd.py`, `cmd/test_tlc_rich.py`, `spec/test_classpath.py`, `tlc/test_tlc_version.py`, all of `tools/test_{dir,fetch_cache,install,list,meta,path,pin,uninstall,upgrade}.py` |
| creates real `config.yaml` and real `cache/run/tlc/<Spec>_<hash>` | `spec/test_resolution_scenarios.py`, `test_tlc_modules_path.py`, `test_tlc_show_command.py`, `tlc/test_runner.py` |
| creates real `cache/run/tlc/Spec_7ab90c72` | `tlc/test_raw.py` |
| reads real cache for the jar (fails if absent) | `cmd/test_modules.py` |

Because the real config is *read* as well as created, results on a developer machine depend on whatever is in `~/.config/tla/config.yaml` (custom URLs, `java.opts`, `module_path`).

## 3. Coverage

Line coverage 86 % (2711 stmts, 348 missed with the fake jar); **branch coverage 83 %** (798 branches, 145 partial). Branch coverage is not enabled in `pyproject.toml:67` and there is no `fail_under`. Modules below 100 %, with-jar run, line+branch combined:

| Module | Stmts | Miss | Cover | Main uncovered areas |
|---|---|---|---|---|
| `cmd/tlc.py` | 174 | 91 | **45 %** | TTY/`Live` branch 151-197, whole post-run summary 223-289 (SANY errors, success/failure, trace, warnings, coverage), `--version` error path 31-33, `_show_diagnostic_info` 44-62 |
| `tlc/runner.py` | 183 | 40 | 73 % | `resolve_spec_file`, `get_override_classes` 93-108, raw Ctrl-C 209-214, `java` missing 217-219 / 265-267, `get_tlc_version` failure 283-284 |
| `java/inspector.py` | 40 | 10 | 74 % | `validate_java_version` body 77-79, fallback regex 36-43 |
| `tlc/formatter.py` | 215 | 44 | 75 % | `render_error_trace` and diff rendering 164-209 |
| `tlc/parser.py` | 168 | 25 | 76 % | nested messages, prefix/suffix on marker lines, warnings, success, SANY status, multi-variable traces |
| `cmd/modules/list.py` | 33 | 7 | 76 % | |
| `cmd/config/list.py` | 11 | 2 | 77 % | |
| `cmd/tools/list.py`, `uninstall.py` | 54 / 70 | 8 / 13 | 81 % | OSError paths |
| `tlc/values.py` | 116 | 18 | 82 % | every error/fallback path, functions, ranges, names |
| `cmd/modules/add.py` | 100 | 15 | 83 % (47 % without jar) | |
| `config/loader.py` | 40 | 5 | 84 % | `workspace_root` 83-87 |
| `versioning/app_version.py` | 45 | 5 | 84 % | |
| `cmd/tools/install.py`, `upgrade.py` | 50 / 48 | 7 / 7 | 85-86 % | |
| `versioning/metadata.py`, `cache/github.py` | 43 / 21 | 6 / 2 | 87 % | |
| `tlc/components.py` | 185 | 12 | 90 % | |
| `versioning/{paths,api,downloader,resolver}.py` | | | 91-96 % | |
| `tlc/sany.py` | 60 | 4 | 92 % | `***Parse Error***`, rangeless messages |
| `java/classpath.py` | 107 | 1 | 95 % | |
| everything else | | | 97-100 % | `tlc/codes.py` is 100 % by import only (constant table) |

### 3.1 Important behaviours with no meaningful test

**TLC output parsing (highest risk).** Verified by running real TLC 1.7.0 (rev eb3ff99, "Version 2.15") and 1.8.0 (rev 4ba7d88) on a small spec with an invariant violation, `-tool -coverage 1`, then feeding the output through `TlcParser`/`SanyParser` line by line exactly as `runner.py:234-241` does:

- Real trace headers are `1: <Initial predicate>` and `2: <Next line 5, col 9 to line 7, col 139 of module M>` (location *inside* the angle brackets). The regex at `tlc/parser.py:195` requires `<...> line N, ...` *after* the bracket. Result for both versions: `errors 1 [(1 line, 0 trace items)]`. The only test, `tests/unit/tlc/test_parser.py:45`, uses the invented line `1: <Initial predicate> line 5, col 1 to line 5, col 10 of module M`.
- Real multi-variable states print `/\ rec = ...`; `tlc/parser.py:223` matches only `^(\w+) = `. The test uses a bare `x = 1` (`test_parser.py:46`).
- Real lines carry a trailing `\n` (the runner does not strip). `Tokenizer._next_str` skips only spaces (`tlc/values.py:98`), so any value TLC wraps across lines hits a `ValueError` and silently degrades to an unparsed string: `['<< [ id |-> 0,\n', ...]` returns 0 children, the same input without `\n` returns structure. All 7 tests in `tests/unit/tlc/test_values.py` use single-line input without newlines.
- `(1 :> "a" @@ 2 :> "b")` parses to the value `1` (`values.py:139-140`); functions, ranges, model values, negative numbers, empty collections, strings containing `,` or `"` are all untested.
- SANY: for a real 2-error output `SanyParser` returns 3 errors (a spurious `('M', None, '\n')` from the blank line after `*** Errors: 2`), and the last message absorbs trailing blank lines and `SANY finished.` because the test at `tests/unit/tlc/test_sany.py:4-18` feeds no blank lines and no newlines. `Semantic errors:`, `***Parse Error***`, and 1.8.0's new `Linting of module M` line are untested.
- `process_info` is always `None`: code 2262 is registered as `Ignore` (`tlc/codes.py:305`), so the `TLC_VERSION` branch at `parser.py:142-143` is dead. No test notices.
- Version drift already visible between 1.7.0 and 1.8.0: version string format, GC-warning wording, `Parsing file ... (jar:file:...)` suffix, new coverage code 2779, coverage header suffix. Nothing pins any of it.
- Also untested: nested STARTMSG, text before/after markers on the same line (`parser.py:82, 86, 94`), severity-forced warnings, `TLC_SUCCESS`, liveness/temporal counterexamples ("Back to state", stuttering), deadlock, `Assert` failures, TLC runtime errors with Java stack traces, multiple errors, progress lines with thousands separators above 999,999.

**Downloads and GitHub.**
- Failure *mid-stream* (exception from `iter_content`), truncated body versus `content-length`, HTTP 404/403 via `raise_for_status` (every mock sets `raise_for_status = MagicMock()`, e.g. `tests/unit/tools/conftest.py:28`), disk-full `OSError`. Only "`requests.get` raises immediately" is tested (`version_manager/test_download.py:18`, `tools/test_version_manager_url.py:47`).
- `force=True` deletes the existing good version *before* downloading (`versioning/downloader.py:52-53`); a failed forced re-download therefore destroys a working install and can orphan the pin. No test.
- No integrity check exists (size or checksum) and no test would demand one.
- GitHub rate limiting (403/429), pagination beyond `per_page=30`, non-list JSON bodies (an error object), tags without a release, releases without a `tla2tools.jar` asset, tags missing `commit.sha` (`versioning/api.py:44-73`). `tests/fixtures/releases.json` has exactly two well-formed releases and `tags.json` is hand-anonymised (`owner/repo`, `aaaa...` SHAs).
- Cache TTL boundary and `save_github_cache` `OSError` (`cache/github.py:27-28`).

**Rolling release.** Covered: same tag with new SHA upgrades and re-pins (`tools/test_upgrade.py:10-22`), list shows both SHAs (`tools/test_list.py:25-49`), semver/published_at/mtime ordering (`version_manager/test_resolution.py`). Not covered: prerelease flag influencing "latest" selection; URL-installed timestamp dirs sorting against SHA dirs of the same semver; pin pointing at a deleted dir during `upgrade`; `meta sync` when the remote SHA has moved; two installs of the same tag where metadata is missing on one.

**Ctrl-C.** One test, `tests/unit/tlc/test_runner.py:8-38`, with five mocks; it asserts only `terminate` called and `callback.called`. It does not assert the final `CheckState.Stopped`, the drained output, or the exit code semantics (the mock hard-codes `returncode = 0`). Raw-mode Ctrl-C (`runner.py:209-214`) and the command-level behaviour (Rich `Live` teardown, exit code, message) are untested.

**Other error paths.** Java missing at `Popen` time; Java too old at the `tla tlc` level; `validate_java_version` itself (always mocked; lines 77-79 uncovered); unparseable version strings such as `25-ea`; `--show-command --coverage` (which appends `-coverage 1` *after* the spec argument, `cmd/tlc.py:128-129`, unlike `run_tlc` which inserts before it); the non-zero TLC exit code mapping (real TLC returned 12 and 150 above); invalid YAML or schema-invalid `config.yaml`; legacy-migration `OSError` branches (`versioning/paths.py:55-75`).

## 4. Test quality

**Patches that do nothing (most serious).**
- `tests/conftest.py:49-52` `mock_load_config` patches `tlaup.config.loader.load_config`, but every consumer imports the function by name (`cli.py:13`, `cmd/tlc.py:8`, `tlc/runner.py:8`, `cmd/tools/{install,list,upgrade}.py`, `cmd/tools/meta/sync.py`, `cmd/modules/{add,path}.py`, `cmd/check_java.py`, `cmd/config/edit.py`). About 45 tests request this fixture and still run against the real, `lru_cache`d config. `cli.py:46` calls `load_config()` in the root callback on every `runner.invoke`.
- `tests/unit/cmd/test_modules.py:23`, `:95` (see 2.1).
- `tests/conftest.py:55-66` `mock_cache` works only by enumerating importing modules by hand with `create=True`, which hides typos and silently misses new importers (`tlc/run_cache` is reached only via `versioning.paths`, which is why run dirs leak when `mock_cache` is not requested).

**Over-mocking.** `test_runner.py:8-38` and `tlc/test_raw.py:7-31` mock config, Java check, spec resolution, project root, classpath resolver, jar path, and `Popen`; what remains under test is a list index. `spec/conftest.py:6-43` replaces `Popen` with a `MagicMock` whose stdout is a string (`"@!@!@type:100:0@!@!@@!@!@success@!@!@"`, line 39) that is not TLC syntax and is not parsed as success; the 20-line comment above it records the confusion. `version_manager/test_app_version.py:17-23` asserts the exact `subprocess.run` kwargs.

**Synthetic inputs instead of real ones.** Section 3.1; the parser, value and SANY tests encode the author's belief about the format rather than the format.

**Implementation-detail and Rich-output assertions.**
- `tlc/test_formatter.py:275` reads `table.columns[0]._cells[0]` (private Rich attribute); `:165-167`, `:183-184`, `:246` index `group.renderables[n].renderable.plain`; `:64-72` asserts column headers through layout internals. Rich is pinned `<14`, so the next major bump will break these wholesale.
- `cmd/test_tlc_cmd.py:11-17` is the test fixed by the last two commits: it sets `NO_COLOR`/`TERM=dumb` *and* strips ANSI by regex. The same fragility remains unfixed in `tools/test_list.py:66-71` (`tla tools --help`, exact help sentence), `cmd/test_modules.py` (table output) and every `"…" in result.stdout` check on Rich-rendered tables (`tools/test_list.py:37, 49` assert a column header and a `✓` glyph). Help text wraps by terminal width, so long strings can split.
- Many CLI tests assert only on substrings of human messages ("Auto-pinning", "selecting latest", "already up to date") rather than resulting state; `tools/test_install.py:6-16` and `tools/test_list.py:12-22` would pass with a wrong version installed.

**Time-dependent.** `tlc/test_formatter.py:176-185`, `:242-247`, `:281-288`, `:331-339` compute `datetime.now() - timedelta(seconds=N)` and assert the exact `HH:MM:SS`; these fail when a second boundary falls between the two `now()` calls. `version_manager/test_resolution.py:90-108` relies on directory mtime ordering.

**Tautological or near-empty.** `cmd/test_tlc_rich.py:19-26` tests a pydantic default; `cmd/test_tlc_rich.py:9-16` asserts an option is "not rejected" by provoking an unrelated error; `test_cli.py:7-19` asserts only that `typer.Exit` is raised (and runs real `git rev-parse` as a side effect); `version_manager/test_download.py:23` uses `pytest.raises(Exception, ...)`; `test_tlc_cmd.py:22-28` checks that a mocked function was called.

**Global-state hazards.** `test_settings.py:8-9` deletes `os.environ["JAVA_OPTS"]` directly, without `monkeypatch`, mutating the process environment for the rest of the session. `load_config` is an `lru_cache` singleton that only some tests clear (`test_config.py:29`, `test_config_suite.py:8`, `cmd/test_modules.py:11`), with no autouse reset, so results depend on execution order (no `pytest-randomly` to expose this). Module-level `runner = CliRunner()` in `cmd/test_tlc_cmd.py:7` and `cmd/test_tlc_rich.py:6` shadows the shared fixture.

**Duplication.**
- `test_config.py` (loader), `test_config_suite.py` (`tla config` commands), `test_settings.py` (`JavaConfig` schema) are not duplicates of each other, but the names say nothing about that split, and all three repeat the same three-line `config_dir` patch.
- `java/test_classpath.py` (resolver unit tests, good) versus `spec/test_classpath.py` (same behaviour again through the CLI with `Popen` mocked); same basename, distinguishable only because of `__init__.py` files.
- `fetch_remote_versions` is tested in both `tools/test_fetch_cache.py:31-98` and `version_manager/test_remote.py`; downloader functions in both `tools/test_version_manager_url.py` and `version_manager/test_download.py`.
- GitHub mock payloads exist three times: `tests/fixtures/*.json`, `tools/conftest.py:6-20`, and inline dicts in `test_fetch_cache.py`.
- `find_real_tla2tools_jar` and the 12-line `captured_result`/`mock_update_logs` block are copy-pasted across all integration tests (`test_tlc_integration.py:12-18`, `test_community_modules.py:12-18`, `test_naming.py:40-48`, `:84-92`).

**What is good.** `java/test_classpath.py`, `version_manager/test_resolution.py`, `version_manager/test_urls.py`, `spec/test_project.py`, `tools/test_install.py:39-115` (pin-state assertions on the filesystem), `tools/test_uninstall.py` and `version_manager/test_migration.py` test real behaviour on `tmp_path` with few or no mocks.

## 5. Isolation and determinism

### 5.1 Filesystem
No autouse fixture redirects `platformdirs`. Isolation is opt-in per test and, as shown in 2.4 and section 4, the opt-in fixtures are partly ineffective. Nothing destructive to user data was observed (writes are `config.yaml` creation-if-missing and `run/tlc/<name>_<hash>` dirs), but `get_spec_run_dir` deletes stale sibling run dirs with the same spec stem, so a user's real `MySpec_*`, `Spec_*`, `Test_*` or `my_model_*` TLC run state in `~/.cache/tla/run/tlc` can be removed by running the unit tests.

### 5.2 Network
With the proxy blackholed, no unit test attempted a connection: `requests.get` is patched everywhere it is reached. There is no guard (`pytest-socket` or similar) to keep it that way. CI itself depends on the network and on unauthenticated GitHub API quota at `.github/workflows/test.yml:39-40`.

### 5.3 Subprocesses and installed Java
With shim `java`/`javac`/`git` on `PATH` recording invocations, the unit suite spawned `java -version` 4 times, `java -cp tla2tools.jar tlc2.TLC -version` 18 times (against the fake jar, from metadata writing during install/upgrade/pin tests), and `git rev-parse --short HEAD` once. The suite still passed with the shims exiting 3, so nothing asserts on these results; they are pure side effects and the reason the install tests are the slowest. `tests/conftest.py:87-93` `java_available`/`javac_available` patch global `shutil.which` with mutually exclusive lambdas (requesting both makes `which("java")` return `None`).

### 5.4 Determinism
Wall-clock assertions and mtime ordering (section 4); order dependence via `lru_cache`; integration tests pick "the first jar `glob` returns" (`test_tlc_integration.py:15-17`), so the TLC version under test is arbitrary when several are installed.

## 6. Organization

- **Tree does not mirror source.** Source packages: `cache`, `cmd/{config,fetch_cache,modules,tools,tools/meta}`, `config`, `java`, `project`, `tlc`, `versioning`. Tests: `version_manager/` (source is `versioning/`), `spec/` (no such package; holds tests for `project/core.py`, `tlc/runner.py` and `cmd/tlc.py`), `check_java/` (source is `java/inspector.py` + `cmd/check_java.py`), `tools/` (source is `cmd/tools/`, but also holds `versioning` tests), `cmd/` (only modules and tlc). `test_tlc_modules_path.py` and `test_tlc_show_command.py` sit at top level although `cmd/` exists. A stale traceback path `tests/cmd/test_modules.py` (from cached bytecode) shows the tree was recently moved.
- **Naming.** Test functions for `tla tools ...` are still called `test_tlc_install`, `test_tlc_list`, `test_tlc_pin`; `test_config_suite.py` and `test_tlc_rich.py` do not describe their content.
- **Conftest layering.** Root conftest mixes unit-only mocks with shared fixtures; `tools/conftest.py` is fine; `spec/conftest.py` holds a fixture really about `cmd/tlc`; `tests/integration/conftest.py` has fixtures that take `tmp_path` and `mocker` as *call arguments* (`conftest.py:15`) instead of depending on them.
- **Markers.** None. No `markers` or `--strict-markers` in `pyproject.toml:66-68`; unit versus integration is expressed only by `testpaths`. `addopts` forces coverage on every run, including single-test debugging.

## 7. Integration strategy

- Four tests in three files; each compiles Java overrides with real `javac` and runs real TLC on a small spec, asserting on a line printed by the override. They exercise the classpath/override mechanism well. They assert nothing about parsed results beyond `state == Success` in two of them; no failing spec, no trace, no SANY error, no coverage run, no Ctrl-C.
- **CI does not run them.** `pyproject.toml:68` restricts collection to `tests/unit`; `.github/workflows/test.yml:43` and `release.yml` run `poe test` = `pytest`. The comment at `test.yml:38` ("Running tests requires a TLC") and the download step exist only to satisfy the leaky unit tests.
- **Environment in CI:** ubuntu-latest only; Java temurin 17 only (`test.yml:30`; minimum supported is 11, developer machine runs 25); Python resolved from `python-version-file: pyproject.toml` (`requires-python >=3.11`, so a single unpinned version) while classifiers advertise 3.11-3.13 and "OS Independent"; TLC = whatever `tla tools install` resolves as latest that day (unpinned, currently the rolling 1.8.0 prerelease).
- **Skip logic is broken.** `if not java_available: pytest.skip(...)` (`test_naming.py:33-36`, `test_tlc_integration.py:38-41`, `test_community_modules.py:39-42`) tests a `MagicMock`, which is always truthy; without Java these tests fail rather than skip.
- **Jar discovery is Linux-only and bypasses isolation:** `Path.home() / ".cache" / "tla" / "tools"` (`test_tlc_integration.py:13`); `tests/integration/conftest.py:42` and `test_naming.py` use the real cache directly without `mock_cache`.
- **No golden files.** There is no recorded TLC output from any version anywhere in `tests/fixtures`. Given section 3.1, this is the single most valuable missing asset.

## 8. Gaps in approach

| Technique | Present | Value here |
|---|---|---|
| Golden/recorded TLC output per TLC version | No | Very high; would have caught the trace-parsing mismatch |
| Property-based tests (Hypothesis) for `tlc/values.py` | No | High; generate TLA+ values, render them TLC-style (including wrapping), assert round-trip and "never raises, never loses text" |
| Snapshot tests for formatter/CLI output (e.g. syrupy, fixed-width `Console(record=True, width=100, color_system=None)`) | No | High; replaces `_cells`/`renderables[n]` poking and substring checks |
| Contract tests against recorded GitHub responses (`responses`/`requests-mock`, real captures incl. 403 rate-limit, paginated, asset-less release) | Partial (2 edited releases) | Medium-high |
| Python x OS matrix | No | Medium; code uses `os.pathsep`, symlinks, `platformdirs`, `:` in directory names (`v1.9.0-2026-04-06T12:51:28Z`, illegal on Windows) |
| Java x TLC matrix for integration | No | High for a tool whose job is to run TLC |
| Network guard (`pytest-socket`), random ordering (`pytest-randomly`), `filterwarnings = error` | No | Cheap hardening |
| Branch coverage and a threshold | No | Cheap |

## 9. Ranked recommendations

1. **Add golden-file parser tests from real TLC output, for at least 1.7.x and 1.8.0.** Create `tests/fixtures/tlc_output/<tlc-version>/<scenario>.out` (success, invariant violation with multi-variable wrapped values, deadlock, liveness with back-to-state, SANY semantic error, parse error, assertion failure, coverage) plus an expected JSON of the parsed `ModelCheckResult`. Drive `TlcParser`/`SanyParser` exactly as `runner.py:234-241` does (lines with `\n`). Expect these to fail immediately at `parser.py:195`, `parser.py:223`, `values.py:98`, `sany.py:68-76`; fix the parser against them. Replace `test_parser.py:36-58` and `test_sany.py`.
2. **Make isolation automatic and total.** Add an autouse fixture in `tests/conftest.py` that sets `XDG_CONFIG_HOME`/`XDG_CACHE_HOME`/`HOME` (and patches `platformdirs.user_config_dir`/`user_cache_dir` for macOS/Windows) to `tmp_path`, and calls `load_config.cache_clear()` before and after each test. Then delete `mock_cache`'s per-module patch list (`conftest.py:55-66`) and the no-op `mock_load_config` (`conftest.py:49-52`), and fix the wrong patch targets at `cmd/test_modules.py:23, 95`. Remove the `tla tools install` step from `test.yml:39-40` for the unit job once the suite passes on a clean machine.
3. **Run integration tests in CI as a separate, marked job.** Register `integration` and `network` markers with `--strict-markers`; mark `tests/integration`; add a job with a matrix over Java (11, 17, 21, 25) and pinned TLC versions (v1.7.4, v1.8.0), jar provided through a session fixture (env var `TLA2TOOLS_JAR` or a cached download) instead of `Path.home()`. Fix the skip logic with `shutil.which` evaluated at collection time (`pytest.mark.skipif`).
4. **Add end-to-end tests of `tla tlc` output handling using a fake `java`.** A tiny script on `PATH` that replays a golden file and exits with a chosen code lets you cover `cmd/tlc.py:151-289` (45 % today), exit-code propagation, Ctrl-C (send `SIGINT`, assert `Stopped` and exit code), raw mode, and Java-missing, with no mocks of `Popen`.
5. **Block accidental subprocess and network use in unit tests.** `pytest-socket --disable-socket`; an autouse fixture that fails on un-mocked `subprocess.run/Popen`. Mock `get_tlc_version`/metadata version probing in `tools/conftest.py` so 18 real JVM launches disappear.
6. **Harden download and GitHub tests.** Use `responses` with real recorded payloads; add cases for mid-stream failure, HTTP 403/404, short body, non-list JSON, missing asset, missing SHA, pagination; add a test (and fix) for `force=True` destroying the existing install on failure (`downloader.py:52-62`).
7. **Property-based tests for `parse_variable_value`** with Hypothesis: totality (never raises), text preservation, round-trip for records/sets/sequences/functions/ranges/strings with escapes, invariance under TLC-style line wrapping.
8. **Replace Rich-internals assertions with snapshots** rendered through a fixed-width, colourless recording console; inject a clock into `StatusInfoComponent`/`StatusFooterRenderable` instead of `datetime.now()` (`test_formatter.py:176, 242, 281, 331`). Force `NO_COLOR=1`, `TERM=dumb`, `COLUMNS=200` once in an autouse fixture instead of per-test regex stripping (`test_tlc_cmd.py:13`).
9. **Reorganize to mirror the source:** `tests/unit/{cache,cmd/{config,modules,tools,tlc},config,java,project,tlc,versioning}`; rename `version_manager` to `versioning`, dissolve `spec/` and `check_java/`, move the two top-level `test_tlc_*.py` under `cmd/`, rename `test_config_suite.py` to `cmd/config/test_commands.py`, `test_settings.py` to `config/test_schema.py`, and `test_tlc_*` functions in `tools/` to `test_tools_*`. Merge the duplicated `fetch_remote_versions` and downloader tests.
10. **CI matrix and coverage policy.** Python 3.11/3.12/3.13 (and 3.14 if intended) on Linux, plus at least one macOS and one Windows job for the unit suite; enable `--cov-branch` and a `fail_under` near the current 83 %; move `--cov` out of default `addopts` into the `poe test` task; fix `test_settings.py:8-9` to use `monkeypatch.delenv`; add `pytest-randomly`.

## 10. Notes on method and limits

- Real TLC was executed only against jars already in the local cache (read-only), with spec, metadir and Java temp dir in a scratch directory; no downloads were made and no project or user files were changed (`git status` clean before the report was written).
- The parser findings come from one spec per version; the golden corpus in recommendation 1 should be broader before conclusions are drawn about which other message types mis-parse.
- macOS/Windows behaviour was assessed by reading code, not by running.
