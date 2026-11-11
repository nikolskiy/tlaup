# 03 - Code quality, correctness and robustness review

Scope: all of `src/tlaplus_cli` (about 4300 lines) at commit `bac6ba1` (branch `dev`, release 0.8.1).
Review date: 2026-11-09. No source, config or test file was modified.

## How claims were verified

Each finding carries a verification label:

- **Reproduced**: observed by running the code. CLI reproductions were run with `XDG_CACHE_HOME` and
  `XDG_CONFIG_HOME` pointed at a scratch directory, so the real config and cache were never touched.
  Parser reproductions fed real tool-mode output through the project's parsers. That output was produced
  by running the already-installed `~/.cache/tla/tools/v1.8.0-4ba7d88/tla2tools.jar` (TLC 2026.05.26,
  rev 4ba7d88, read-only use, `-metadir` in scratch) on two throwaway specs. Nothing was downloaded.
- **Code reading**: follows directly from the cited lines, not executed.
- **Unverified**: plausible but depends on behaviour I could not observe (Windows, GitHub API ordering,
  network conditions). Treat as a risk, not a fact.

Tooling results (all read-only):

| Tool | Result |
|---|---|
| `ruff check .` | All checks passed |
| `mypy .` (strict) | No issues in 56 source files |
| `bandit -c pyproject.toml -r src/tlaplus_cli` | No findings |
| `ruff format --check .` | **7 files would be reformatted** (`src/tlaplus_cli/cmd/tlc.py`, `src/tlaplus_cli/tlc/runner.py`, 5 test files) |

Severity counts: 7 high, 18 medium, 20 low.

---

## High severity

### H1. Error traces are never parsed from real TLC output
- **Where**: `src/tlaplus_cli/tlc/parser.py:195` (state header regex), `:223` (variable regex).
- **Problem**: the header regex is `^(\d+): <(.*)> line (\d+), col ... of module (\w+).*$`, which expects
  the source location *after* the closing `>`. Real TLC prints it *inside* the brackets, and the initial
  state has no location at all:
  ```
  1: <Initial predicate>
  /\ f = <<0, 0>>
  /\ x = 0
  2: <Next line 5, col 9 to line 8, col 39 of module T>
  ```
  The variable regex `^(\w+) = (.*)$` also does not accept the `/\ ` prefix TLC emits whenever a spec has
  more than one variable.
- **Failure scenario**: any spec with an invariant violation. Feeding the real output of a 3-state
  counterexample through `TlcParser` yields `errors=1`, `error_trace` length 0. The counterexample tree
  (`render_error_trace`, the diffing in `formatter.py:125-209`) is unreachable in practice; the user sees
  only "Invariant Inv is violated." and no states.
- **Why tests pass**: `tests/unit/tlc/test_parser.py:45` uses a fabricated header
  (`1: <Initial predicate> line 5, col 1 to line 5, col 10 of module M`) that TLC does not produce.
- **Also missing**: "Back to state" (2122) and stuttering (2218) headers have different shapes and are not
  handled either.
- **Confidence**: high. **Reproduced.**

### H2. SANY errors are shredded into many bogus messages
- **Where**: `src/tlaplus_cli/tlc/runner.py:246` together with `src/tlaplus_cli/tlc/sany.py:78-89`, `:68-76`.
- **Problem**: three interacting defects.
  1. `SanyParser.get_errors()` flushes the in-progress message as a side effect, and the runner calls it
     after *every* output line. The location line is flushed with an empty message before its text arrives.
  2. `current_block` is never reset, so once `*** Errors:` has been seen every later non-`@!@!@` line
     becomes a SANY "error" - including blank lines and the bodies of TLC tool-mode messages, because the
     runner feeds message bodies to the SANY parser too (`runner.py:238-242`).
  3. Lines keep their trailing newline.
- **Failure scenario**: a spec with 2 semantic errors. Real output run through the runner's loop produced
  **15** `SanyMessage` objects: two with a range and an empty message, the two actual texts as separate
  rangeless entries, seven containing only `"\n"`, plus `SANY finished.`, `Starting... (...)`,
  `Parsing or semantic analysis failed.` and `Finished in 200ms at (...)`. `cmd/tlc.py:253-257` renders each
  as `✖ SANY Error: ...` with a `file://...#LNone` link.
- **Note**: even without the per-line flush (defect 1), the last error swallows the trailing TLC messages.
- **Confidence**: high. **Reproduced.**

### H3. `tla tools uninstall --all` stops after removing the pinned version
- **Where**: `src/tlaplus_cli/cmd/tools/uninstall.py:95`.
- **Problem**: `any(_remove_path(p, pinned_dir) for p in targets)` uses a generator with side effects;
  `any()` short-circuits at the first `True`, which is the pinned directory.
- **Failure scenario**: three installed versions, newest pinned (the normal state, since the list is sorted
  newest first). `tla tools uninstall --all -y` removed only the pinned one, printed
  "Pin fell back to v1.7.0-bbbbbbb", exited 0 and left the other two installed. The same applies to
  `tla tools uninstall v1 v2 v3` when the pinned one is not last.
- **Confidence**: high. **Reproduced.**

### H4. No integrity or sanity check on downloaded jars, and an interrupted download looks installed
- **Where**: `src/tlaplus_cli/versioning/downloader.py:17-38`, `:48-66`; `src/tlaplus_cli/cmd/tools/install.py:64-69`.
- **Problems**:
  1. No checksum, signature, size or even ZIP-magic check. Whatever a 200 response returns is written as
     `tla2tools.jar`, reported as "Successfully installed", auto-pinned, and then *executed* immediately by
     `_extract_tlc_version` (`metadata.py:20`). A captive-portal or proxy HTML page gets installed as the jar.
  2. The jar is written in place, not to a temp file followed by a rename. Cleanup only runs for
     `requests.RequestException` and `OSError` (`downloader.py:60`, `:85`). Ctrl-C (`KeyboardInterrupt`)
     or a kill leaves `<version>-<sha>/tla2tools.jar` truncated with no metadata.
  3. "Installed" means "the directory exists" (`downloader.py:49`, `install.py:65`). After an interrupted
     download, the next `tla tools install` prints "already installed" and auto-pins the truncated jar;
     `tla tlc` then fails inside the JVM.
  4. `--force` deletes the working version first (`downloader.py:52-53`), so a failed re-download leaves
     nothing and a dangling pin.
- **Confidence**: high for the code paths (**code reading**); the Ctrl-C path was not executed because it
  needs a network download.
- **Mitigation hints**: download to `*.part` in the same directory, verify (`zipfile.is_zipfile` at
  minimum; GitHub's per-asset `digest` field where present - availability for tlaplus releases
  **unverified**), `os.replace`, and treat a directory without a jar plus metadata as not installed.

### H5. Run-cache cleanup deletes other specs' (possibly live) TLC metadirs
- **Where**: `src/tlaplus_cli/tlc/run_cache.py:29-40`, `:49`; `src/tlaplus_cli/cmd/modules/add.py:139`;
  `src/tlaplus_cli/cmd/modules/remove.py:18`.
- **Problem**: stale directories are matched by `name.startswith(f"{stem}_")` across the *global*
  `~/.cache/tla/run/tlc`. The hash includes the absolute path, so:
  - two projects that both have `Spec.tla` delete each other's run directory on every run;
  - running `Spec` deletes the directory of an unrelated spec named `Spec_v2` (prefix match);
  - editing a spec during a long run and starting a second run deletes the first run's `-metadir` while
    TLC is still writing its state queue and fingerprint files there;
  - `--show-command` has the same deleting side effect, because `build_tlc_command` calls
    `get_spec_run_dir` (`runner.py:144`);
  - `tla modules add` and `tla modules remove` wipe the whole run directory regardless of running checkers.
- **Related, reproduced**: TLC creates a new timestamped subdirectory under `-metadir` on every run and does
  not remove it. For an unchanged spec these accumulate without bound in the cache.
- **Confidence**: high for the matching logic (**code reading**). The effect on a live TLC whose metadir
  vanishes was not executed.

### H6. Unknown or unregistered TLC message codes are silently dropped, including errors
- **Where**: `src/tlaplus_cli/tlc/parser.py:120-122`.
- **Problem**: `if not code_obj or code_obj.type == Ignore: return` runs *before* the severity suffix
  (`STARTMSG code:severity`) is consulted, so a message with severity 1 (error) and an unregistered code
  vanishes.
- **Evidence**: comparing `tlc2.output.EC` in the installed jar (246 constants) with `codes.py` (239) shows
  these error codes are not registered: 1003 `SYSTEM_OUT_OF_MEMORY_LIVENESS`,
  2148 `TLC_STATE_NOT_COMPLETELY_SPECIFIED_LIVE`, 2254 `SYSTEM_FINGERPRINT_OVERFLOW_ERROR`,
  2256 `TLC_NO_STATES_SATISFYING_INIT_AND_CONSTRAINT`, 2404 `TLC_POSTCONDITION_FALSE`,
  2405 `TLC_POSTCONDITION_EVALUATION_ERROR`.
- **Failure scenario**: a spec whose `POSTCONDITION` is false. TLC emits 2404; the parser discards it;
  `state` never becomes `Error`; the CLI prints neither the error text nor "Model checking failed" - the only
  signal is the exit code. Every future TLC code behaves the same way.
- **Confidence**: high for the table gap and the drop logic (**reproduced** via `javap` and code reading);
  the end-to-end postcondition run was not executed.

### H7. TLC output printed through Rich markup: text is swallowed or the CLI crashes
- **Where**: `src/tlaplus_cli/cmd/tlc.py:175` (`live.console.print(log.strip())`), TTY mode only.
- **Problem**: raw TLC/user output is passed to `Console.print` with markup enabled. Anything that looks
  like `[lowercase...]` is consumed as a style tag.
- **Failure scenario**: a spec calling `PrintT([a |-> x, b |-> "s"])`. TLC prints `[a |-> 0, b |-> "s"]` as
  a plain line; Rich renders an **empty line** (reproduced with the pinned Rich 13.9.4). A line containing
  `[/]` or an unmatched closing tag raises `rich.errors.MarkupError` inside the callback. That exception is
  not caught anywhere, so the user gets a traceback mid-run. Non-TTY mode uses `print` and is unaffected,
  so piped and interactive runs differ.
- **Confidence**: high. **Reproduced** at the Rich level; the full TTY run was not executed.
- **Fix hint**: `console.print(Text(line))` or `markup=False, highlight=False`.

---

## Medium severity

### M1. Tracebacks reach the user for common failures
All **reproduced** unless noted.
- `tla tlc X --show-command` with no jar installed: `build_tlc_command` at `cmd/tlc.py:124` is outside the
  `try`, giving a full Rich traceback for `FileNotFoundError`.
- `tla tlc X --raw` with no jar: `cmd/tlc.py:133` is outside any `try`; same traceback.
- Java missing or too old: `validate_java_version` raises `RuntimeError` (`runner.py:174`,
  `inspector.py:73,86`), but `cmd/tlc.py:287` only catches `FileNotFoundError`. (**Code reading.**)
- Invalid or empty `config.yaml`: `cli.py:46` calls `load_config()` in the root callback for every
  subcommand with no handling of `yaml.YAMLError` or `pydantic.ValidationError` (`loader.py:21-22`).
  This includes `tla config edit` and `tla config list`, so the tool cannot be used to repair its own
  config.
- `_fetch_from_api`: `.json()` at `versioning/api.py:36-37` is outside the `try`; a non-JSON 200 response
  raises. A JSON object instead of a list raises `AttributeError` in `_process_remote_versions`.
  (**Code reading.**)
- `get_pinned_version_dir`: `pin_file.read_text()` (`paths.py:39`) is unguarded. (**Code reading.**)
- Non-UTF-8 bytes in TLC output: `text=True` with the locale encoding and strict errors
  (`runner.py:196-203`, `:225-232`) raises `UnicodeDecodeError`, which is not caught. (**Code reading.**)

### M2. Every `OSError` during a run is reported as "'java' not found"
- **Where**: `src/tlaplus_cli/tlc/runner.py:217-219`, `:265-267`.
- **Problem**: the `except (SubprocessError, OSError)` wraps the whole streaming loop *and the callback*.
- **Failure scenario**: `tla tlc Spec --raw | head -5` raises `BrokenPipeError` on stdout, which is reported
  as "'java' not found. Please install Java." with exit 1. Any `OSError` raised while rendering does the
  same. The original exception is discarded with `from None`.
- **Confidence**: high. **Code reading.**

### M3. No SIGTERM handling; the JVM is orphaned
- **Where**: `src/tlaplus_cli/tlc/runner.py:196-216`, `:225-264`.
- **Problem**: no signal handling exists anywhere in `src/`. Only `KeyboardInterrupt` is handled.
- **Failure scenario**: a CI step timeout or `kill <pid>` sends SIGTERM to `tla`. Python exits; the `java`
  child is not terminated and, since Java's `PrintStream` swallows write errors, it keeps model checking
  with a closed pipe.
- **Related**: a second Ctrl-C during the post-interrupt drain loop (`runner.py:252-256`) escapes
  unhandled. After Ctrl-C the exit code is whatever `returncode` is (130 from the JVM, or -15 mapped to
  241 by `sys.exit`), which is inconsistent.
- **Confidence**: medium-high. **Code reading**, not executed.

### M4. Version directory naming is parsed inconsistently
- **Where**: `src/tlaplus_cli/versioning/resolver.py:87` (split on first `-`),
  `src/tlaplus_cli/cmd/tools/upgrade.py:30` (split on last `-`),
  `src/tlaplus_cli/versioning/downloader.py:47`, `:79`.
- **Failure scenarios**:
  - URL-installed and pinned build `v1.8.0-2026-04-06T12:51:28Z`: `tla tools upgrade` printed
    "Error: Version v1.8.0-2026-04 not found on remote." (**Reproduced.**)
  - A tag containing a hyphen (for example `v2.0.0-rc1`) installs to `v2.0.0-rc1-abc1234` but is listed as
    name `v2.0.0`, sha `rc1-abc1234`. `tla tools pin v2.0.0-rc1` then says "not found locally", and
    `tools list` shows it twice (available plus local only). No current tlaplus tag is known to have a
    hyphen, so this is latent. (**Code reading.**)
  - A tag containing `/` creates nested directories that `list_local_versions` never finds.
    (**Code reading.**)
- **Fix hint**: stop encoding identity in the directory name; read name and sha from
  `meta-tla2tools.json`.

### M5. `tla tools meta sync` writes the wrong metadata
- **Where**: `src/tlaplus_cli/cmd/tools/meta/sync.py:24-29`.
- **Problem**: metadata is matched by tag name only.
- **Failure scenario**: an older rolling build `v1.8.0-aaaaaaa` gets the `sha`, `published_at` and
  `download_url` of the current remote build `bbbbbbb`. URL-installed builds have their `download_url`
  and `tag` overwritten with GitHub data. This also corrupts the `published_at` ordering used by
  `resolve_latest_version`.
- **Confidence**: high. **Code reading.**

### M6. Rolling-release identity is only loosely tied to the downloaded bytes
- **Where**: `src/tlaplus_cli/versioning/api.py:44-73`, `:87-96`.
- **Problem**: the sha comes from the *tags* endpoint, the jar from the release asset URL (identical for
  every rolling build), fetched in separate requests and cached for an hour.
- **Failure scenario**: the tag moves or the asset is re-uploaded between the tag fetch (or cache write)
  and the download. The directory and metadata then claim sha X while the jar is build Y. `tla tools
  upgrade` can also report "already up to date" for up to an hour after a new build; the only override is
  `tla fetch-cache clear`.
- **Evidence available**: TLC prints its own revision (`TLC2 Version ... (rev: 4ba7d88)`), which is already
  captured as `tlc2_version_string` and could be compared against the expected sha.
- **Confidence**: medium. **Unverified** as to how often it happens.

### M7. No pagination; "latest stable" depends on API ordering
- **Where**: `src/tlaplus_cli/versioning/api.py:25-31`; `src/tlaplus_cli/cmd/tools/install.py:61`.
- **Problem**: only the first page (30 items) of tags and releases is read. `install` without a version
  picks the first non-prerelease in whatever order the tags endpoint returns; nothing sorts by semver or
  date, even though `_parse_semver` exists in `resolver.py`. If all listed versions are prereleases it
  silently installs `versions[0]`, a prerelease, while printing "selecting latest stable release".
- **Confidence**: medium. Ordering behaviour **unverified**.

### M8. GitHub API: unauthenticated only, no retries, opaque rate-limit failure
- **Where**: `src/tlaplus_cli/versioning/api.py:27-34`.
- **Problem**: no `GITHUB_TOKEN` support, no `Accept` or `User-Agent` header on API calls (the download
  sets one), no retry or backoff. A 403/429 rate-limit response becomes a generic "Failed to fetch remote
  versions" warning.
- **Failure scenario**: on a shared CI IP with no cache, `tla tools install` fails with
  "Could not fetch remote versions (status: unavailable)". `.github/workflows/test.yml` itself runs
  `uv run tla tools install` unauthenticated.
- **Positive side**: no token is handled, so there is nothing to leak.
- **Confidence**: high for behaviour (**code reading**); frequency unverified.

### M9. Plain-HTTP jar URLs accepted
- **Where**: `src/tlaplus_cli/versioning/resolver.py:14`; `src/tlaplus_cli/versioning/downloader.py:19-24`.
- **Problem**: `tla tools install http://...` downloads and then executes a jar over cleartext. Redirects
  are followed without restriction, including https to http. Combined with H4 (no verification) this is
  code execution for a network attacker.
- **Confidence**: high. **Code reading.**

### M10. `tla modules remove` and `tla modules add` can delete outside the module they name
- **Where**: `src/tlaplus_cli/cmd/modules/remove.py:11-17`; `src/tlaplus_cli/cmd/modules/add.py:57-62`.
- **Failure scenarios**:
  - `tla modules remove ../tools` deleted the entire tools directory and printed
    "Module '../tools' successfully deleted from cache." (**Reproduced** in the scratch cache.)
  - An absolute path argument makes `get_modules_dir() / name` equal that path, which is then `rmtree`d.
    `tla modules remove .` removes all modules. (**Code reading.**)
  - `tla modules add /`: `Path("/").name == ""`, so `target_dir` is the modules directory itself and
    `add.py:62` removes every managed module. (**Code reading.**)
  - `add` deletes the existing module before compiling. A javac error (`add.py:114-119`) therefore
    destroys the previously working build.
- **Confidence**: high.

### M11. Function-valued variables are parsed incorrectly
- **Where**: `src/tlaplus_cli/tlc/values.py:139-140`.
- **Problem**: `(` is handled by parsing a single following token.
- **Failure scenario**: `parse_variable_value("f", ["(n1 :> 0 @@ n2 :> 1)"])` returns
  `TlaValue(key="f", value="n1")` with no children (**reproduced**). Nested inside a set or sequence, the
  `:>` and `)` tokens become garbage items.
- **Related**: multi-line values always fall back to the raw joined string, because the tokenizer does not
  skip `\n` (`values.py:98`) and the runner passes lines with newlines. That fallback is graceful.
- **Currently masked by H1**; it becomes user-visible once traces parse.
- **Confidence**: high.

### M12. Error text is hidden when a trace exists (latent)
- **Where**: `src/tlaplus_cli/cmd/tlc.py:263-269`.
- **Problem**: when `err.error_trace` is non-empty only the trace is printed; `err.lines`
  ("Invariant Inv is violated.") is skipped and is not printed anywhere else.
- **Currently masked by H1.** **Code reading.**
- **Related**: `ErrorInfo` lines keep their trailing newline, so the fallback path prints double-spaced.

### M13. `-config` argument can point TLC at a different file than the one validated
- **Where**: `src/tlaplus_cli/tlc/runner.py:77-80`.
- **Problem**: when the resolved cfg is not under the project root (or there is no project root), only
  `cfg_file.name` is passed, dropping its directory.
- **Failure scenario**: spec in `./specs/A.tla`, `--cfg alt.cfg` found in the current directory
  (`runner.py:60`). TLC runs with `cwd=./specs` and `-config alt.cfg`, so it either fails or picks up
  `./specs/alt.cfg`. An absolute cfg path outside the project behaves the same way.
- **Confidence**: medium. **Code reading**; TLC's relative-path resolution not executed.

### M14. Quadratic, discarded rendering work on every output line
- **Where**: `src/tlaplus_cli/cmd/tlc.py:160-161`, `:206-207`; `src/tlaplus_cli/tlc/formatter.py:276-336`;
  `src/tlaplus_cli/tlc/components.py:89-107`, `:116-136`.
- **Problem**: `formatter.update(layout, res)` runs for every line ("Keep tests happy") but `layout` is
  never displayed. Each call re-deduplicates all `output_lines` and rebuilds a Rich `Table` of all progress
  rows.
- **Failure scenario**: a spec that prints heavily (`PrintT` in `Next`) or a multi-hour run. Cost is
  O(n squared) in output lines, and `output_lines` is retained in memory without bound
  (`parser.py:111`).
- **Confidence**: high for the code path; impact not measured.

### M15. Unicode output assumptions on Windows (unverified)
- **Where**: `src/tlaplus_cli/ui.py:6-21`; `src/tlaplus_cli/cmd/tlc.py:226-237` (`print` of `─`);
  `src/tlaplus_cli/cmd/tools/list.py:34`.
- **Risk**: with stdout or stderr redirected under a legacy code page (cp1252, cp437), `print("─...")` can
  raise `UnicodeEncodeError`. **Unverified**, no Windows host available.

### M16. URL installs cannot work on Windows (unverified)
- **Where**: `src/tlaplus_cli/versioning/metadata.py:14`; `src/tlaplus_cli/versioning/downloader.py:79-80`.
- **Risk**: the directory name embeds an ISO timestamp with colons (`v1.8.0-2026-04-06T12:51:28Z`), which
  are illegal in Windows file names. `mkdir` should fail with `OSError`, reported as "Failed to download".
  **Code reading**; not run on Windows.

### M17. Project-root heuristic can pull unrelated jars onto the classpath
- **Where**: `src/tlaplus_cli/project/core.py:6-8`, `:27-29`; `src/tlaplus_cli/java/classpath.py:129-134`.
- **Problem**: a directory counts as project root if it, *or its parent*, has `classes/`, `modules/` or
  `lib/`.
- **Failure scenario**: a spec at `~/work/Spec.tla` where `~/lib` exists. The root becomes `~`, TLC's cwd
  becomes `~`, and every `~/lib/*.jar` is put on the classpath.
- **Confidence**: medium. **Code reading.**

### M18. `tla config edit` rejects `$EDITOR` values with arguments
- **Where**: `src/tlaplus_cli/cmd/config/edit.py:22-27`.
- **Failure scenario**: `EDITOR="code --wait"` (or `"true --wait"`, **reproduced**) gives
  "Editor '...' not found in PATH". No Windows default (`vim`). The config is not re-validated after
  editing, which feeds M1.

---

## Low severity

| # | Location | Issue | Verification |
|---|---|---|---|
| L1 | `cmd/tlc.py:129` | `--show-command` joins with `" ".join`, so paths with spaces are not copy-pasteable (use `shlex.join`). It also differs from the real command: no `-tool`, and `-coverage 1` is appended *after* the spec (`:126`) while the real run inserts it before (`runner.py:186`). `if not cmd` at `:127` is dead. | Code reading |
| L2 | `cmd/tlc.py:85-89`, `config/schema.py:29` | `--refresh-interval` and `tlc.refresh_interval` are accepted but unused. `_show_diagnostic_info` (`cmd/tlc.py:42`), `save_config`, `workspace_root`, `workspace.root`/`spec_dir`, `tla.community_modules`, `TlcDisplayComposer`, `StatusFooterComponent` and `SanyParser.get_warnings` are dead. | grep |
| L3 | `cmd/tlc.py:61`, `cmd/modules/list.py:28` | `except Exception: pass` (one silenced with `# nosec`). | Code reading |
| L4 | `cmd/tlc.py:157-240` | TTY and non-TTY callbacks are 40-line near-duplicates; three near-identical elapsed-time renderers in `components.py:54`, `:142`, `:251`. | Code reading |
| L5 | `cmd/tlc.py:137`, `runner.py:174`, `:270-285` | Each `tla tlc` starts three JVMs (`java -cp ... -version`, `java -version`, TLC). The first two add fixed latency and have no timeout except `java -version` (5 s). | Code reading |
| L6 | `java/inspector.py:22,40` | A `java -version` timeout is reported as "Java is not installed". No `JAVA_HOME` support; `java`/`javac` come from `PATH` only. | Code reading |
| L7 | `config/schema.py:40-42` | `JAVA_OPTS` replaces (does not extend) configured opts and is split with `str.split`, breaking quoted values. | Code reading |
| L8 | `config/schema.py` | Models do not forbid extra keys, so typos are silently ignored. `workspace` and `tlc` are required with no defaults, so an older or hand-trimmed config fails validation (traceback, M1). | Code reading |
| L9 | `versioning/api.py:83-84` | Cache file is keyed by asset name only; changing `tla.urls` serves the old repository's list for up to an hour. Cache write is not atomic (`cache/github.py:25`). | Code reading |
| L10 | `versioning/paths.py:82`, `metadata.py:38` | Pin and metadata writes are not atomic; no locking anywhere. Two concurrent `tla tools install` of one version write the same jar path, or the second reports "already installed" mid-download. | Code reading |
| L11 | `tlc/compiler.py:7-12` | A dangling pin silently falls back to the legacy `cache/tla2tools.jar`, not the newest installed version. | Code reading |
| L12 | `cmd/tools/uninstall.py:63-70`, `:47` | Removal failures print an error but exit 0, and the pin is still moved. A negative index is accepted in the prompt. | Code reading |
| L13 | `cmd/tools/path.py:22-26` | Prints a jar path without checking that it exists; with several builds of one version it silently picks the first. | Code reading |
| L14 | `tlc/runner.py:26-30` | `with_suffix(".tla")` turns `Foo.v2` into `Foo.tla` (wrong file) and raises `ValueError` for `.`; an existing non-`.tla` file such as `queue.cfg` is accepted as the spec. | Code reading |
| L15 | `tlc/run_cache.py:21` | The hash covers the default `.cfg` only, not a `--cfg` file or extended modules. | Code reading |
| L16 | `tlc/parser.py:46-48` | `STARTMSG -1` raises an uncaught `ValueError`. Regexes are recompiled per line. | Code reading |
| L17 | `cmd/modules/add.py:33-34`, `:106` | Comment stripping (`//.*`) corrupts string literals containing `//`. javac runs with no `-encoding` and no timeout. | Code reading |
| L18 | `__init__.py:6` | `truststore.inject_into_ssl()` is a process-global side effect of importing the package (the package ships `py.typed`, inviting library use). | Code reading |
| L19 | `config/loader.py:57`, `versioning/paths.py:12-17` | Installed jars, the pin and compiled modules live in the OS *cache* directory, which cleaners may purge. | Design |
| L20 | `cli.py:7-14` | Startup cost: `tla --help` took about 0.33 s wall; importing `tlaplus_cli.cli` about 240 ms, of which truststore/urllib3 about 113 ms, pydantic schema about 57 ms, requests about 32 ms. All command modules are imported eagerly; network and Rich imports could be deferred into the commands that need them. | Measured |

---

## Typing, lint and CI configuration

- **Formatting is not enforced.** `ruff format --check` fails on 7 files, including
  `src/tlaplus_cli/cmd/tlc.py` and `src/tlaplus_cli/tlc/runner.py`. Neither `.pre-commit-config.yaml` nor
  `poe lint` (used by CI) runs it.
- **Typing escape hatches despite `strict = true`**: `layout: Any` throughout `formatter.py:270-323`;
  `update_stats/logs/clock` are annotated `Layout` but receive `TlcDisplay` (`formatter.py:325-336`);
  `sany_errors: list[Any]` (`models.py:131`); `_Section.renderable: Any`. Tests are excluded from mypy.
- **Ruff rule gaps relevant to defects found here**: `BLE` (blind except, L3), `DTZ` (naive
  `datetime.now()` in `components.py:64`, `add.py:135`), `T20` (`print` in `cmd/tlc.py`), `S` (bandit runs
  separately), `PERF`, `FBT`. `PLW1510` is globally ignored. Several `noqa: PLR0912/PLR0915` mark the
  functions where most defects cluster (`cmd/tlc.py:69`, `runner.py:165`, `add.py:47`).
- **Bandit** skips B404/B603/B607 globally, which hides partial-path execution of `java`, `javac`, `git`.
- **CI** (`.github/workflows/test.yml`): Ubuntu only, a single Python version, although classifiers claim
  3.11-3.13 and "OS Independent". Integration tests are excluded by `testpaths = ["tests/unit"]`, and the
  unit tests for the parser use synthetic TLC output (root cause of H1 and H2 going unnoticed).
- **Dependency pins**: `rich<14` and `pre-commit<4` are behind current majors.

---

## What is done well

- Lint, strict mypy and bandit are all clean; the code is consistently typed and readable.
- Every `subprocess` call uses argument lists; there is no `shell=True`, so no shell injection.
- All `requests` calls set timeouts; TLS verification is on and uses the OS trust store via `truststore`.
- `yaml.safe_load`/`safe_dump` are used; the default config is loaded via `importlib.resources`.
- GitHub fetches have a sensible online, cached (1 h TTL), stale, unavailable fallback with an explicit
  `FetchStatus`, so most commands still work offline.
- Truncated downloads with a `Content-Length` are detected by urllib3 2.x and trigger directory cleanup.
- `os.pathsep` is used for classpath, `-DTLA-Library` and the overrides property; `platformdirs` is used
  for config and cache locations.
- TLC's exit code is propagated to the shell (verified: 12 for an invariant violation, 150 for a parse
  failure).
- Legacy layout migration (`tlc/` to `tools/`, symlink pin to pin file) is handled and non-fatal.
- Value-parse failures fall back to the raw string instead of crashing.
- Destructive `uninstall --all` asks for confirmation; `--force` and `--yes` are explicit.
- Each spec gets an isolated `-metadir`, keeping TLC state out of the user's project.
- Good unit-test breadth by file count and a maintained changelog.

---

## Suggested order of work

1. Capture real tool-mode transcripts (success, invariant violation, deadlock, liveness with "Back to
   state", SANY parse and semantic errors, coverage) as fixtures, then fix H1, H2, H6, M11, M12 against
   them.
2. One-line fixes: H3 (materialise the list before `any`), H7 (disable markup), M1 (wrap `load_config`
   and widen the `except` in `cmd/tlc.py`), M2 (narrow the `except` to the `Popen` call).
3. Download path: temp file plus rename, validity check, jar-exists-based "installed" test (H4, M9).
4. Run-cache scoping and cleanup policy (H5); input validation for module names (M10).
5. Replace directory-name parsing with metadata (M4, M5, M6).
6. Add `ruff format --check` to CI and a macOS/Windows matrix job.
