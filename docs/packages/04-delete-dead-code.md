# 04. Delete dead code

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

The display code that nothing references, installs from a URL and every old-layout code path are gone from `src/`. No new code is added and nothing else a user sees changes. The old tests that covered this code are already gone, with the rest of the old suite, in 03b (decision D62).

## Covers

- Roadmap items:
  - "Remove installs from a URL (decision D13). Do this first ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)). The removal is complete here. The refusal of an address with exit code 2 and a hint comes with the version grammar: package [22](22-version-spec-and-jarinfo.md) writes the parser and package 29 puts it behind `tool install`.
  - "Remove the legacy fallback jar path, so it is never shown as the expected location, and all other legacy-layout code (pin migration, flat module form) ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part. The removal is here. The item's last sentence, "A pin that points at a missing build is a clear error with a hint", is `PinnedBuildMissing`: package [23](23-tool-store.md) raises it and packages 29 and 33 show it.
  - "Delete display code that nothing in `src/` references (`StatusFooterComponent`, `TlcDisplayComposer`, the `TlcComponent` protocol, `info_dedup`, `_show_diagnostic_info`) and the tests that pin it ..." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)), in part. The five names go here; the tests that pinned them went with the old suite in 03b. The item's second sentence (the duplicated callback in `cmd/tlc.py` and the three copies of the elapsed-time logic) is not this package's: they disappear with the reporter interface and the terminal reporter (packages 36 and 38).
- Design sections:
  - [22 O2](../design/22-reporters.md#o2-delete-dead-display-code), the list under "Deleted outright" only. Everything in O2's table "Not deleted here" stays, and the table says which later section takes each row.
  - [12 V6](../design/12-tools-and-downloads.md#v6-remove-installs-from-a-url), all of the removal. The usage error for `tool install https://...` is [02 X3](../design/02-cross-cutting.md#x3-version-syntax) (packages 22 and 29).
  - [12 V10](../design/12-tools-and-downloads.md#v10-remove-old-layouts), with one difference forced by the order of work, described under Context: `get_tlc_jar_path` loses its fallback here but the function and `tlc/compiler.py` stay until their callers are replaced (39 deletes them).

This is step 3 of the [order of work](../design/00-overview.md#order-of-work): pure removal, done early so that everything after it is smaller.

## Depends on

- [03](03-test-foundation.md): it has deleted the old suite (D62), so no test reaches the code removed here, and it has set the pytest settings this package's run is judged by.

Nothing else. The package uses no new type or function.

## Files

Line numbers are those of the tree at the time this file was written (before the format commit of package 01); find the code by name.

Changes:

| File | What goes | What stays |
| --- | --- | --- |
| `src/tlaup/tlc/components.py` | The classes `TlcComponent`, `StatusFooterComponent`, `TlcDisplayComposer`. The imports that only they used (`Protocol`, `RenderableType`). | `LogDeduplicator`, `HeaderComponent`, `StatusInfoComponent`, `LogsComponent`, `StatsTableComponent` (finished or replaced by O4), `StatsTableFormatter`, `StatusFooterRenderable` (shown today; replaced by O3). |
| `src/tlaup/tlc/formatter.py` | The attribute `info_dedup` in `TlcFormatter.__init__`, and `LogDeduplicator` from the import list, which nothing else in the file uses. | Everything else: `TlcDisplay`, `_Section`, the layout functions, the `render_*` and diff functions, `StatusInfoRenderable`. |
| `src/tlaup/cmd/tlc.py` | The function `_show_diagnostic_info`. | Everything else, including `version_callback` (`tlc --version` is a user-visible option and goes with its replacement, O2's table) and the two "keep tests happy" layout calls (O4). All of its imports are still used by the rest of the file; let ruff confirm. |
| `src/tlaup/versioning/resolver.py` | `is_url`, `extract_version_from_url`, the `urlparse` import. | `_SEMVER_RE`, `_parse_semver`, `_version_sort_key`, `resolve_latest_version`, `list_local_versions`. V2 deletes `resolve_latest_version` later, with the old commands (package 29). |
| `src/tlaup/versioning/downloader.py` | `download_version_from_url` and the imports only it used (`_utc_now_iso`, `write_version_metadata_from_url`, `extract_version_from_url`). | `_download_jar`, `download_version`. |
| `src/tlaup/versioning/metadata.py` | `write_version_metadata_from_url`. `_utc_now_iso` too if nothing uses it once the URL install is gone (today only `download_version_from_url` and the deleted URL tests do). | `_extract_tlc_version`, `_write_metadata`, `write_version_metadata`, `read_version_metadata`. |
| `src/tlaup/versioning/paths.py` | `_migrate_legacy_pin` and its call in `get_pinned_version_dir`; `get_github_cache_file` (it names `github_cache.json`, a file nothing writes). | The other path functions, `set_pin`, `clear_pin`, `clear_cache`. `clear_cache` used `get_github_cache_file().parent`; it now takes the cache folder directly. |
| `src/tlaup/versioning/api.py` | The import and use of `get_github_cache_file`; the cache file's folder is the cache folder itself. | Everything else. The real cache file name, `github_cache_<asset>.json`, does not change. |
| `src/tlaup/versioning/__init__.py` | The re-exports of every name deleted above. | The rest. |
| `src/tlaup/cmd/tools/install.py` | The URL branch at the top of `install`, the imports `download_version_from_url` and `is_url`, and "or a direct URL to tla2tools.jar" in the argument's help text. | The rest of the command, unchanged. |
| `src/tlaup/cmd/tools/uninstall.py` | The `default` branch in `_resolve_uninstall_targets` and the `cache_dir` import it needed; in `_remove_path`, the `else: path.unlink()` branch, which only the single legacy jar file could reach. | The rest, bugs included: the short circuit at `any(...)` and the pin fallback are V3's, fixed by packages 27 and 29. |
| `src/tlaup/tlc/compiler.py` | The legacy fallback `cache_dir() / "tla2tools.jar"`. `get_tlc_jar_path` returns the pinned build's jar when the pin names a folder that holds one, and `None` otherwise (the signature is under Interfaces). | The file and the function, until packages 29, 31 and 39 replace the callers (see Context). |
| `src/tlaup/cmd/tlc.py`, `src/tlaup/tlc/runner.py`, `src/tlaup/cmd/modules/add.py`, `src/tlaup/cmd/modules/path.py` | Each call of `get_tlc_jar_path` handles `None`, which mypy in strict mode requires. The smallest handling is the branch each already has for a jar that does not exist, with the message it already prints, minus the path; `tlc --version` then no longer prints `tla2tools.jar path: <cache>/tla2tools.jar` when nothing is pinned. | Their behaviour with a pinned build. Exit codes stay as they are (1); the new codes arrive with the switch packages. |
| `src/tlaup/java/classpath.py` | In `ClasspathResolver._resolve_paths`, the two lines marked "Legacy fallback" that add a registered module's top folder (the flat module form). In `get_project_path`, step 3, the lookup of `lib` inside the project's modules folder. | Everything else. The class is kept ([00](../design/00-overview.md#packages-after-the-first-wave)); G1 and M2 change it later. |
| `CHANGELOG.md` | | Two entries under `## [Unreleased]`, see Changelog. |

Creates: nothing. Deletes: no whole file. No test file is touched: none of the old ones is left, and no new test reaches this code.

Files another package of the same period also touches: `CHANGELOG.md` (every package with an entry; one block of lines each). The parallel tracks that start after package 03 do not edit the files above: the parser track works under `src/tlaup_parse/` and `tests/parse/`, the store track adds new modules beside `versioning/`'s old ones, and the groundwork track adds new modules. `src/tlaup/cmd/tlc.py` and `src/tlaup/tlc/runner.py` are next edited by the switch packages.

## Interfaces

Provides: nothing new. One signature changes:

```python
# src/tlaup/tlc/compiler.py
def get_tlc_jar_path() -> Path | None      # was -> Path; None when nothing usable is pinned
```

Consumes: nothing from other packages.

## Tests that must pass

No new test: the three sections only remove ([22 O2](../design/22-reporters.md#o2-delete-dead-display-code), "Tests"). What proves the package is mypy in strict mode on `src`, ruff, and the suite that is left after 03b (the new tests of 02 and 03, the stateful tests, whatever parser and groundwork packages have merged): a name on a list that is referenced after all fails one of them.

The old tests of this code (V6's and V10's lists, O2's two formatter tests) went with the old suite in 03b ([12 V6](../design/12-tools-and-downloads.md#v6-remove-installs-from-a-url), [V10](../design/12-tools-and-downloads.md#v10-remove-old-layouts): "not deleted one by one"). Preserved-behaviour rows: none is this package's; what it removes is changed on purpose (V6, V10, O2).

## Changelog

Under `## [Unreleased]`, heading Removed, word for word from the design:

- "`tlaup tool install <URL>`. Install by version name; installing from an address may return later." ([V6](../design/12-tools-and-downloads.md#v6-remove-installs-from-a-url))
- "Support for old storage layouts (a jar directly in the cache folder, the symlink pin, the `tlc` folder, modules without a `modules/` subfolder). The `tlaup` folders never contained them." ([V10](../design/12-tools-and-downloads.md#v10-remove-old-layouts))

O2 has no entry: nothing a user can see changes.

The first entry says `tlaup tool install` although the command on `main` is still `tlaup tools install` until package 29 renames the group (D47). The changelog describes release 0.9.0 as a whole (D6: nothing is released in between), so the entry is written in its final form now.

## Context for the worker

Decisions this rests on:

- D13: installs from a URL are dropped for now. No released version could put a URL-installed build into the `tlaup` folders, so nothing handles one left on disk.
- D14: clean breaks, no aliases, shims or migrations. The `tlaup` folders exist only since the rename of 2026-11-14 and have never held the old layouts, so the migration code can go without a replacement.
- D40: the full-screen layout is finished, not deleted. That is why O2's list is short. `TlcDisplay`, the layout functions, the log panel and `LogDeduplicator` look dead (the layout is built on every line and never printed) and must stay: O4 (package 40) owns them. Their old tests are gone (03b); that is no reason to delete the code.
- D6 and D62: one release, and between packages `main` need only be green. An old command may behave differently after this package (below); no CI job runs real TLC through one (03b removed the one step that did).

Where this package differs from V10's text, and why. V10 says: delete `get_tlc_jar_path` and `tlc/compiler.py`, "callers use `store.pinned().jar`". The store is package 23 and no command uses it before package 29, while this package is step 3. So here the function loses only its fallback: it returns the pinned jar or `None`, and the legacy path is never returned or printed again, which is what the roadmap item asks for. The function and the file are deleted when their callers are: `cmd/tlc.py` and `tlc/runner.py` by package 39, `cmd/modules/add.py` and `cmd/modules/path.py` by package 31; package 29 re-points the function at the new store in between. This is a reading of V10 (finding A8 of the first review), which reviewer F of the [second review](review-2026-11-24.md) confirmed (finding F4): the order of work forces it, and nothing a user relies on depends on which package deletes the function.

Points that are easy to miss:

- "Pure removal" includes the lines that become unreachable or unused because of a removal (an import, an `else` branch, a re-export). It does not include fixing what is left. `uninstall` still stops at the pinned build, `install` still prints "Successfully installed" after "already installed", `upgrade` still splits folder names: each has its own section and package.
- After this package `tlaup tools install https://...` is no longer an install: the old command takes the address for a version name, asks GitHub for the version list and answers that the version was not found, with exit code 1. That is the accepted in-between state. Do not add a refusal here; the grammar that refuses an address without any request is X3's.
- `tools uninstall default` becomes "Version default not found locally", through the code path every unknown name takes.
- `tools meta sync` and its module `cmd/tools/meta/` are not on any of the three lists and stay, although package 03 deleted `tools/test_meta.py`. The command goes with the command tree (23 C1, package 29).
- `get_pinned_version_dir` keeps returning `None` for a pin that names a missing folder. Turning that into an error is the store's `pinned()` (package 23), not a change to the old function.
- The flat module form cannot be produced by today's `modules add` (it copies only `lib`, `modules`, `tlc2` and the test folder), so removing the two fallback lines changes nothing for a module registered by a released version.
- Coverage: no threshold is set until package 59 ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)); removing untested code can only raise the figure.

State of `main` when this starts: release 0.8.x code, formatted by package 01, with `tlaup/errors.py`, `tlaup/paths.py` and the context skeleton of package 02 beside it and the test foundation of package 03. All old command and domain modules exist; none of their old tests does.

## Done when

- Every name under "What goes" is gone, and a search of `src/` for `is_url`, `extract_version_from_url`, `download_version_from_url`, `write_version_metadata_from_url`, `_migrate_legacy_pin`, `get_github_cache_file`, `TlcComponent`, `StatusFooterComponent`, `TlcDisplayComposer`, `info_dedup`, `_show_diagnostic_info` and the string `Legacy fallback` finds nothing.
- `uv run poe lint` (ruff, bandit, mypy strict) and `uv run poe test` pass; CI is green.
- The two changelog entries are written.
- The pull request lists, per file, what was removed, and names anything it had to remove beyond the table above with the reason.

## Out of scope

- The usage error for an address or `latest` given as a version: packages [22](22-version-spec-and-jarinfo.md) and 29.
- `PinnedBuildMissing` and the new store: package [23](23-tool-store.md).
- Deleting `tlc/compiler.py`, `resolve_latest_version`, `tools meta sync`, `fetch-cache`: the switch packages (29, 31, 39).
- Everything in O2's table "Not deleted here": packages 38 (O3) and 40 (O4).
- The duplicated callback in `cmd/tlc.py` and the elapsed-time copies: packages 36 and 38.
- The settings `workspace.*` that `ClasspathResolver.get_project_path` still reads: 14 F3, package 19 and the switch packages.

## Risks

- A name on a list is referenced after all (O2's risk). mypy and the suite fail in that case; that is the check.
- Deleting a little too much of the layout code because it looks dead. D40 and O2's table are the guard; with the old layout tests gone, mypy and the reviewer are what catch it, and package 40 rebuilds the layout from O4 in any case.
- The cut adds one: `get_tlc_jar_path` now returns `None`, and a caller that is missed would fail with an `AttributeError` at run time. mypy in strict mode catches it on `src`; there are five call sites.
