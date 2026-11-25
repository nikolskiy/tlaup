# 22. Version spec and jar information

Size: M. Suggested model: mid-tier. Status: built.

## Goal

Two new modules exist under `src/tlaup/versioning/` with their unit tests: `spec.py` turns what a user types as a version into a `VersionSpec` or a usage error, and `jarinfo.py` reads a jar's identity and capabilities from its manifest and entries, with no network and no JVM. No command uses them yet.

## Covers

- Roadmap items:
  - "Typing versions (note 45): accept a version without the `v`; the shortcuts `latest`, `stable` and `rolling` ..." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)), in part: the grammar and its refusals. Lookup and the printed form are package [23](23-tool-store.md); the commands, `tool current` and the column label are package 29.
  - "Non-interactive version selection: accept `tag@sha` and the folder name wherever a version is accepted ..." ([milestone 4](../roadmap.md#milestone-4-automation-surface)), in part: the `tag@commit` syntax, which the item says is decided in the first wave. Folder names are not accepted (a listed departure). The item stays open for milestone 4.
  - "After download, compare the commit the jar reports about itself with the expected commit ... How to read it, ideally without starting a JVM ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: reading the commit and the build time from the jar. The comparison is packages [26](26-download-and-verify.md) and 27.
  - "Download to a temporary file, check it is a valid jar, then rename ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the check that a file is a TLA+ tools jar. The rest is packages [23](23-tool-store.md), [26](26-download-and-verify.md), 27 and 29.
- Design sections:
  - [02 X3](../design/02-cross-cutting.md#x3-version-syntax): the syntax, the table "Typed / Means" as far as parsing goes, the refusals, `VersionSpec` and `parse_version_spec`, and the parametrised unit test. `format_build`, the round-trip property test, lookup and "when a spec matches several builds" are package 23 and the commands.
  - [12 V5](../design/12-tools-and-downloads.md#v5-download-and-verify): `jarinfo.py` only (`JarInfo`, `read_jar`, the paragraph "`read_jar` requires", and the unit tests of `read_jar`). `fetch_build` is package 26.
  - [00, "What a build can do"](../design/00-overview.md#what-a-build-can-do): the four capabilities, decided in `read_jar`.

## Depends on

- [02](02-errors-and-paths.md): `UsageError` and `DownloadVerificationError` from `tlaup.errors`.
- [03](03-test-foundation.md): the isolation fixture, the pytest settings, and the rules the tests follow.
- [05](05-github-recordings.md): the recorded manifests at `tests/unit/data/manifests/`. [01 T3](../design/01-testing.md#t3-golden-files) moves them there from `tests/fixtures/research/03-jar-identity/manifest-*.txt` and `tests/fixtures/research/14-jar-manifest/*.MF`; stage 4 gave that one row of the move to 05, which needs the manifests first, for the small jar its `github` fixture builds (reconciled by stage 4; this file first named 07).

## Files

Creates:

- `src/tlaup/versioning/spec.py`
- `src/tlaup/versioning/jarinfo.py`
- `tests/unit/versioning/test_spec.py`
- `tests/unit/versioning/test_jarinfo.py`
- `tests/unit/versioning/__init__.py`, if the test folders under `tests/unit/` are packages as [03](03-test-foundation.md) leaves them; later packages add `test_remote.py`, `test_download.py` and others to this folder, and two test modules of one base name in two folders need package files.
- A helper that packs a manifest into a small jar for tests (a zip with `META-INF/MANIFEST.MF`, `tlc2/TLC.class` and optionally `tlc2/REPL.class`), in `tests/unit/versioning/conftest.py`. Packages 23, 26 and 27 use it too. If package [05](05-github-recordings.md) is already merged and its `github` fixture has such a builder in a shared place, use that one and add nothing (T12 rule 9).

The manifests are moved by [05](05-github-recordings.md), on which this package depends; this package moves nothing.

Changes: nothing in `src/` outside the two new files. In particular not `src/tlaup/versioning/__init__.py`: the new modules are imported by their full names and are not re-exported.

Must not touch: the old modules `versioning/api.py`, `downloader.py`, `metadata.py`, `paths.py`, `resolver.py`, `schema.py`, `cache/github.py`, `cmd/tools/`. They stay until package 29 switches the `tool` commands and deletes them (their old tests went in 03b). No new module name collides with an old one (`spec.py` and `jarinfo.py` are new names; the old `schema.py` holds the old dataclasses and is a different thing from `spec.py`).

Deletes: nothing.

## Interfaces

Provides, from [02 X3](../design/02-cross-cutting.md#x3-version-syntax):

```python
# tlaup/versioning/spec.py
@dataclass(frozen=True)
class VersionSpec:
    name: str | None      # "stable", "rolling" or a tag as typed; None when only a CalVer was given
    commit: str | None    # lower-case hex prefix
    calver: str | None
    sha256: str | None    # lower-case hex prefix, from "@sha256:..."

def parse_version_spec(text: str) -> VersionSpec      # raises UsageError
def latest_refused(stable_tag: str | None = None) -> UsageError
    # written by stage 4: X3's refusal of `latest`; with a tag, "Use `stable` (<tag>) or `rolling` (the newest build).",
    # without one the brackets after `stable` are left out. The parser raises latest_refused(); 29 passes the tag.
```

The grammar, copied so that the worker and the reviewer read the same text:

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

From [12 V5](../design/12-tools-and-downloads.md#v5-download-and-verify):

```python
# tlaup/versioning/jarinfo.py        no network, no JVM
@dataclass(frozen=True)
class JarInfo:
    sha256: str; size: int
    commit: str | None           # X-Git-Revision, None if absent
    built_at: str | None         # Build-TimeStamp
    calver: str | None           # built_at as %Y.%m.%d.%H%M%S in UTC
    capabilities: frozenset[str]

def read_jar(path: Path) -> JarInfo        # raises DownloadVerificationError if not a TLA+ tools jar
```

Capabilities ([00](../design/00-overview.md#what-a-build-can-do)): `repl` when the jar has the entry `tlc2/REPL.class`; `calver`, `overrides_property` and `no_generate_spec_te` when the manifest has `Build-TimeStamp`.

Consumes: `UsageError`, `DownloadVerificationError` (package 02).

Used later by: `ToolStore.find` and `add` (23), `Remote.resolve` (25), `fetch_build` (26), the step classes (27), every `tool` command (29), and `tests/stateful/test_tool_store.py`, whose `tlaup_impl` calls `tlaup.versioning.jarinfo.read_jar`.

## Tests that must pass

Plain pytest; these are pure functions on real files in a temporary folder ([01 T1](../design/01-testing.md#t1-the-approach), T12 rule 1).

`tests/unit/versioning/test_spec.py`, the parametrised test X3 asks for:

- The accepted forms of the table: `v1.7.4` and `1.7.4` (the name is kept as typed; trying it with a `v` is the lookup's job, package 23), `stable`, `rolling`, `rolling@bc1b506`, `v1.8.0@bc1b506` with a prefix of 7 and of 40 digits, `rolling@2026.11.15.002146`, `rolling@sha256:7e53aa636dac`, the bare CalVer `2026.11.15.002146` (name is `None`), and `2026.11.15.002146@bc1b506` (before `@` the CalVer shape is an ordinary tag). Upper-case hexadecimal input gives lower-case fields.
- Tags the grammar lets through: with a hyphen, an underscore, a slash and a plus.
- Refused with `UsageError`: `latest`; `https://example.org/tla2tools.jar` and `http://...`; `@abc`; `v1.7.4@`; `rolling@xyz`; a 6-digit commit prefix; an empty string; a tag starting with `-`; a tag containing `@` twice; white space inside; `@sha256:` with seven digits, with a non-hexadecimal digit, and with nothing after the colon.
- The refusal of `latest` and of an address are told apart from the others by what the error offers: the first names `stable` and `rolling`, the second carries the hint that installing from an address is not supported. Assert the type and that fact, not the sentence (T12 rule 4).
- `latest_refused("v1.7.4")` names `v1.7.4` after `stable`; `latest_refused()` names no tag and has no empty brackets.

`tests/unit/versioning/test_jarinfo.py`, the unit tests V5 lists for `read_jar`, on the recorded manifests packed into small jars:

- v1.7.4's manifest gives the commit `5a47802b5c391f59ecdd44117981f4ff8c0656ba`, no `built_at`, no CalVer, and none of the four capabilities when the jar has no `tlc2/REPL.class`.
- The rolling manifest gives the CalVer `2026.11.15.002146` (from `Build-TimeStamp: 2026-11-15T00:21:46.50Z`), the commit `bc1b506b...`, and `calver`, `overrides_property`, `no_generate_spec_te`; with `tlc2/REPL.class` in the jar also `repl`.
- A manifest with a wrapped `X-Git-Revision` line (a continuation line starts with one space) and one with CRLF line ends give the same commit.
- A manifest without `X-Git-Revision` gives `commit` `None`.
- A zip without a manifest, a zip without `tlc2/TLC.class`, a text file, and a zip cut to half its length each raise `DownloadVerificationError`.
- `sha256` and `size` are those of the file.

Old tests: none is left (03b, decision D62); no row of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) names this package as its owner. Stateful tests: none applies yet; `tests/stateful/test_tool_store.py` needs the store and `install.py` as well, and its `pending` markers are removed by package 27.

## Changelog

None. Nothing a user can see changes until the commands are switched. X3's entries (Added: "Versions can be typed without the `v`, as `stable` or `rolling`, and as `tag@commit` to name one build."; Breaking: "With several builds of one tag installed, `tlaup tool path TAG` now fails and lists them ...") and V5's "The commit shown for a build is read from the jar itself." are written by package 29.

## Context for the worker

Decisions:

- D31: the version syntax. `latest` is not offered, because it is ambiguous here: GitHub's "latest" is the 2024 stable release and most users mean the newest build.
- D13: no installs from an address; the grammar refuses one without looking anything up, since no tag contains a colon.
- D37: the store is built now, so folder names are internal and are never accepted as input.
- "A build's commit comes only from the jar's manifest" (decision of the design agent, README): the tag and the jar move at different moments upstream, so the jar is the stronger identity.
- D19: the two supported builds are v1.7.4 and the current rolling build; the capability rules are exact for them and a guess for builds in between.

The parser, points that are easy to miss:

- It only parses. It never touches the store, the network or the release list. "Tried as typed, then with `v`", `stable` among installed builds, and what happens when several builds match belong to `ToolStore.find` and the commands.
- A bare CalVer is always a build time, never a tag: `name` is `None` and `calver` is set. The same shape before `@` is a tag.
- After `@`, the three forms cannot be confused: hexadecimal digits never contain a dot, a CalVer always does, and the third starts with `sha256:`.
- `stable` and `rolling` are names like any other for the parser (`stable@bc1b506` parses). `latest` is refused as a whole spec and as a name before `@`.
- The message for `latest` in X3 names the stable tag in brackets (`stable (v1.7.4)`). The parser cannot know it and does not try; it raises `latest_refused()`, without it. X3 now says where the command takes the tag from (the stable release of the cached release list, else the highest installed build that is not a prerelease, else none; never a request, finding B16); that is [29](29-tool-commands.md)'s, which calls `latest_refused(tag)`.
- An address is recognised by its colon or by `://`; anything else outside the grammar is the plain usage error. Both are `UsageError` (exit code 2), never "not found" (4).
- The message follows [20 G2](../design/20-groundwork.md#g2-domain-errors): one line, no trailing full stop, no "Error:" prefix; `hint` is one line.

`read_jar`, points that are easy to miss:

- What it requires, and nothing more: a valid zip for which `ZipFile.testzip()` returns nothing; an entry `tlc2/TLC.class`; a readable `META-INF/MANIFEST.MF`. It does not check that `TLC.class` is a real class file: the fixture jars and the stateful test's jars hold a few bytes of text there, and they must be accepted.
- The manifest reader handles CRLF and continuation lines (a line that starts with one space continues the previous one). None of the three recorded manifests has a wrapped line (research 14), which is why the wrapped case is a hand-made test input.
- Not read, on purpose: `Build-Tag`, `Build-Rev`, `X-Git-Tag`, `Implementation-Version`. In the recorded manifests the first two are unfilled placeholders (`${env.BUILD_TAG}`) and the others are not unique.
- `calver` is `built_at` in UTC written `%Y.%m.%d.%H%M%S`; the fraction of a second is dropped, not rounded. The recorded value, `2026-11-15T00:21:46.50Z`, has two fractional digits and a `Z`; `datetime.fromisoformat` of Python 3.11.15, the lowest supported line, reads it and gives `2026.11.15.002146` (tried once while this package was written, on Linux). A value it cannot read is not designed for; treat the jar as having no build time rather than refusing it, and say so in the pull request.
- `commit` is the manifest's value in lower case. The design does not say what a value that is not 40 hexadecimal digits does; no published jar has one. Say in the pull request what you did with it.
- Every published jar back to v1.5.6 has `X-Git-Revision` (research 26, restated in V5). A jar without one is still accepted, with `commit` `None`: that is the path for a jar tlaup builds itself or a future upstream publishes.
- `read_jar` raises `DownloadVerificationError` for everything it refuses, also when it is called on a file that was never downloaded. The name is the design's.
- Cost, from V5's Risks: `testzip` reads every entry; 0.09 seconds for the real 4.4 MB jar, measured once on one Linux machine. Hash the file in chunks, not by reading it whole.
- `zipfile` raises several exception types for a damaged file (`BadZipFile`, `OSError`, `KeyError` for a missing entry, and others for odd input). All of them must come out as `DownloadVerificationError`; a traceback from here would reach a user through `tool install`.

Platform (D15): `pathlib` only; nothing here is platform-specific.

Test rules that bite ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests)): no patching of tlaup's own code, no mocks; real jars in `tmp_path`. A manifest is not TLC output, so rule 3 does not forbid the two hand-made manifests; build them in the test from a recorded one.

State of `main` when this starts: the 0.8.x code with packages 01 to 03 on top (and possibly 04). `src/tlaup/versioning/` holds the old modules; importing `tlaup.versioning.spec` runs the old `versioning/__init__.py` first, which imports `requests` and the old code. That is expected until package 29 empties it; the new modules import nothing from the old ones.

## Done when

- The tests above pass; `uv run poe lint` (mypy strict covers the two new modules) and `uv run poe test` pass; CI is green.
- No file listed under "Must not touch" is in the diff.
- The pull request says how a malformed `X-Git-Revision` is treated.

## Out of scope

- `format_build`, `ToolStore.find`, the order of builds, the round-trip property test: package [23](23-tool-store.md).
- `fetch_build` and the size and digest checks: package [26](26-download-and-verify.md).
- The commit comparison for `tool install rolling@bc1b506`, `install`, `upgrade`, `uninstall`, `pin` as functions (V12, V3, V4, V11): package 27. The first-run prompt (V9): package 28. The `tool` commands, the feature files and the changelog entries of X3: package 29.
- Completion of version names (23 C3): package 47.

## Risks

- From V5: a jar with no `X-Git-Revision` is installed with no commit and can be named only by its tag; no published release has such a jar.
- From X3: a release tagged literally `stable` or `latest`, or with a CalVer-shaped tag, cannot be named by its tag. None exists with a jar (research 5 and 8).
- From the cut: the manifests are 05's; this package waits for 05, which is early (it needs only 03).
