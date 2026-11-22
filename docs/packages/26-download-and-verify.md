# 26. Download and verify

Size: M. Suggested model: most capable. Status: ready.

## Goal

`tlaup.versioning.download.fetch_build` downloads a release's jar into a temporary folder and returns it only when its length, its digest (where GitHub gives one) and its content say it is the TLA+ tools jar that the release describes, retrying once across upstream's upload gap. Nothing it does touches an installed build. No command uses it yet.

## Covers

- Roadmap items:
  - "Download to a temporary file, check it is a valid jar, then rename. A folder without a jar and its metadata does not count as installed. `--force` keeps the old build until the new one is verified. Never report a truncated jar or a proxy's HTML page as installed." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the download to a temporary file and every check. The rename and "does not count as installed" are the store's (package [23](23-tool-store.md)); `--force` is package 27; the user sees it at the switch (29).
  - "After download, compare the commit the jar reports about itself with the expected commit ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part, and as the design departs from it: the download is verified by size and digest against the release object, and the build's commit is the jar's. The comparison with a commit the user typed (`tool install rolling@bc1b506`) is package 27.
  - "Download and GitHub failure modes are tested ..." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)), in part: nine rows of T6, listed below.
- Design sections:
  - [12 V5](../design/12-tools-and-downloads.md#v5-download-and-verify): `download.py`, that is `fetch_build` and its six steps, with V5's download tests. `jarinfo.py` was package [22](22-version-spec-and-jarinfo.md). "The commit comparison" for a typed commit, `tool_install.feature` and V5's changelog entries are packages 27 and 29.
  - [01 T6](../design/01-testing.md#t6-download-and-github-failure-tests): the nine download rows.

## Depends on

- [24](24-github-client.md): `GitHubClient.download` with `DownloadInfo` and `limit`, `get_json`, the readable `client.sleep`, the status code on the error for a 404, and `ChunkedEncodingError` already turned into `DownloadVerificationError`.
- [25](25-remote-listing.md): `Release`, `Asset`, and `parse_release` for the release object fetched again after a mismatch.
- [23](23-tool-store.md): `ToolStore` and `TmpFolder`. The download's folder is a `TmpFolder` under `<cache>/tool/.tmp/`, and the tests assert the state of a real store afterwards.
- [22](22-version-spec-and-jarinfo.md): `read_jar`, `JarInfo`, and the small-jar helper.
- [05](05-github-recordings.md): the `github` fixture, its small real jar and the `releases` recording.
- [02](02-errors-and-paths.md): `DownloadVerificationError`, `NetworkError`, `VersionNotFound`.
- [03](03-test-foundation.md): the isolation fixture and the pytest settings.

The draft named 23, 24 and 25. 22, 05, 02 and 03 are added because they are used directly; none changes the order.

## Files

Creates:

- `src/tlaup/versioning/download.py`
- `tests/unit/versioning/test_download.py`

Changes: `tests/unit/versioning/conftest.py`, if the tests need a helper to serve a body of a chosen length or digest.

Must not touch: the old `versioning/downloader.py` (a different module; the new one is `download.py`), `metadata.py`, `api.py`, `cmd/tools/install.py`, `cmd/tools/upgrade.py`, and the old tests `tests/unit/version_manager/test_download.py` and `test_metadata.py`. Package 29 deletes them with the old code. The new test file has the same base name as the old `test_download.py` and lives in the other folder, `tests/unit/versioning/`.

Deletes: nothing.

## Interfaces

Provides, from [12 V5](../design/12-tools-and-downloads.md#v5-download-and-verify):

```python
# tlaup/versioning/download.py
def fetch_build(client: GitHubClient, release: Release, dest_dir: Path, progress) -> tuple[Path, JarInfo]
```

The six steps, in the design's words shortened:

1. Stream the asset from its `download_url` to `dest_dir / "tla2tools.jar"`, hashing as it goes. Reading stops one byte past the release's `size`.
2. Check the number of bytes against `Content-Length` and against the release's `size`.
3. If the release has a `digest`, compare: the part after `sha256:` with the hash, ignoring case. A digest with another prefix is not compared.
4. On a mismatch of size or digest, or a 404: wait 2 seconds through the client's injected `sleep`, fetch the release object again, and retry once. A second mismatch is `DownloadVerificationError`.
5. `read_jar`.
6. Return the path and the info.

The return type is fixed from outside: package 27's `Fetch = Callable[[Release, Path], tuple[Path, JarInfo]]` is "`fetch_build` with the client bound", and `tests/stateful/test_tool_store.py` supplies its own function of that shape.

One helper V5 does not name. Written by stage 4; a worker may rename it:

```python
def usable_digest(asset: Asset) -> str | None
    # the 64 hexadecimal digits of a "sha256:" digest in lower case, or None when the asset has no digest
    # or one with another prefix. fetch_build compares with it; package 27 uses it for same_as_published
    # (V12) and for Source.digest_checked, so that the rule of step 3 exists once.
```

Consumes: `GitHubClient` and `DownloadInfo` (24); `Release`, `Asset`, `parse_release` (25); `read_jar`, `JarInfo` (22); `TmpFolder` (23); the errors (02). `progress` is the client's `Progress` callable or `None` (24).

Used later by: `Install.download` and `Upgrade` through the bound `Fetch` (27), and so by `ensure_tools` (28) and the commands (29).

## Tests that must pass

Plain pytest in `tests/unit/versioning/test_download.py`, against the real client and `fetch_build` with `responses`. Each test prepares a real store in `tmp_path` that already holds a build of the tag (added through `ToolStore.add`), takes a `TmpFolder` from it as `dest_dir`, and asserts the error type and the state afterwards: `store.builds()` is what it was, the earlier build's jar has its recorded SHA-256, and nothing was written outside `dest_dir`. Never the message (T12 rule 4).

The rows of [01 T6](../design/01-testing.md#t6-download-and-github-failure-tests) assigned to this package:

| T6 row | Expectation here |
| --- | --- |
| Connection drops mid-stream | `NetworkError`; the store unchanged. |
| Body shorter than `Content-Length` or than the asset's size | `DownloadVerificationError` after one retry; the store unchanged. Two tests: a body cut short under a full `Content-Length`, and a complete answer that is shorter than the release's `size`. |
| Body longer than the asset's size | At most `size + 1` bytes are in the file; `DownloadVerificationError`; the store unchanged. |
| Body is an HTML page (a proxy) | `DownloadVerificationError` from the content check ("not a zip"), with size and digest made to agree so that this check is the one that fires; the store unchanged. |
| Valid zip without `tlc2/TLC.class` | The same, from `read_jar`. |
| Digest differs from the release's `digest` | One fresh lookup of the release and one retry, then `DownloadVerificationError`: two download requests, one more request for the release, one sleep of 2 seconds. |
| Digest given in upper case; digest with a prefix other than `sha256:` | The first compares equal and the jar is returned. The second is treated as no digest: the jar is returned, the size check still applies (a second test gives it a wrong size and expects the error), and `usable_digest` is `None`. |
| Asset answers 404 once, then 200 | The jar is returned after one retry; the injected sleep was asked for 2 seconds, once. |
| Digest differs once, then matches (upstream replaced the asset) | The jar is returned, and it is the second one: `JarInfo.sha256` is the second body's hash and equals the refreshed release's digest. |

"The state afterwards" in T6 also says "no temporary file left". The temporary folder belongs to the caller: `Install.give_up` discards it and removes its lock file, and package 27 has the test that after a failed download nothing of the command is left under `.tmp/` ([V11](../design/12-tools-and-downloads.md#v11-concurrent-installs), Tests). Here the tests assert that `fetch_build` wrote only inside the folder it was given.

Also:

- The happy path against the `releases` recording: the jar is returned, `JarInfo` has the commit of the fixture jar's manifest, one download was made, and `progress` was called with a growing count.
- A release with `asset` `None` raises `VersionNotFound` and makes no request.
- A release with no digest (`v1.7.4` in the recording): size, zip and class checks pass and the jar is returned.
- The retry happens once, not once per kind of mismatch: a 404, then a wrong digest, is the error after two attempts.
- `usable_digest` for a lower-case and an upper-case `sha256:` digest, another prefix, a `sha256:` with the wrong number of digits, and `None`.

Old tests: none is deleted here. Stateful tests: none applies to this package; the stateful store test replaces `fetch_build` with its own function.

## Changelog

None in this package. V5's entries describe what a user sees through `tool install`, and package 29 writes them: Fixed "A download that was cut short, or a proxy's error page, could be recorded as an installed build. Downloads are now checked for length, for being a TLA+ tools jar, and against GitHub's SHA-256 where it provides one, before anything is installed." and "`tool install --force` deleted the installed build before the new download had succeeded."; Changed "The commit shown for a build is read from the jar itself."

## Context for the worker

Decisions:

- "A build's commit comes only from the jar's manifest; the tag's commit is not fetched" (design agent, README; a listed departure from the roadmap). Upstream moves the tag and the asset at different moments, so a comparison with the tag would fail every install made within minutes of an upstream build. What protects against a wrong or damaged download is the size and digest of the release object fetched immediately before.
- D29: a download that does not verify is "failed" (exit code 5), a release with no jar is "not found" (4).
- D15: no Windows CI; nothing here is platform-specific beyond opening the file in binary mode.
- [01 T4](../design/01-testing.md#t4-fakes-at-the-edges), "Time": the 2-second wait goes through the client's injected `sleep`; nothing sleeps or reads the clock directly.

Facts from research that the design restates:

- The release object holds the asset's `size`, and for uploads since mid-2025 a SHA-256 `digest` written `sha256:<64 hexadecimal digits>`; `v1.7.4` and older have none (research 18). The digest comes from the same account as the file: it detects corruption and a replaced asset, not a compromised release.
- Upstream replaces an asset by delete-then-upload, so the download address can answer 404 for one to three seconds, and a download can straddle the replacement and get bytes that do not match the release object read before it (research 7). That is the one case the single retry is for.
- `responses` keeps a `Content-Length` longer than the body; `requests` then raises `ChunkedEncodingError` from `iter_content`, which the client (package 24) turns into `DownloadVerificationError`. Code that reads `response.raw` gets the short body with no error and must compare the count itself; step 2 does that in any case (research 30).
- `testzip` on the real 4.4 MB jar took 0.09 seconds, measured once.

Points that are easy to miss:

- **The two rows about a body that stops.** A connection that is reset or times out while the body is read comes out of the client as `NetworkError` and is not retried here: step 4's retry is for a mismatch or a 404. A body that simply ends early is a size mismatch, `DownloadVerificationError`, and is retried once. If the finished client cannot tell the two apart for some way of serving the body, T6's Risks apply: the row that cannot be reached is removed with a line in the pull request, not bent to fit.
- **Step 4 fetches the release again**, because the likely cause is a replaced asset: the second attempt compares with the new `size` and `digest`. Fetch it with `client.get_json` on the tag's path, percent-encoded, and `parse_release` (package 25). The retry is once in total.
- **Before the second attempt the file is started again from nothing**, and so is the hash.
- **`fetch_build` returns the jar and the info, not the release.** After a retry the caller still holds the release it looked up first, whose `asset.id` and `asset.updated_at` may be one upload old. What the caller writes into `Source` is package 27's business; the index carries a note on it. Do not change the return type to hand the release back: the stateful test fixes it.
- **`limit`.** Pass the asset's `size + 1` to `client.download`, so that a body longer than the asset is seen and a server cannot fill the disk.
- **A digest with another prefix is not an error.** It is treated as a release with no digest. For such a release the checks are size, zip validity and `tlc2/TLC.class`.
- **`read_jar` hashes the file again.** Its `sha256` must equal the hash made while downloading; if they differ, something wrote to the file in between, and that is `DownloadVerificationError`.
- **The download address is `asset.download_url` as the release gave it.** No address is built here, and no token is added here; both are the client's rules.
- **A release without a jar** should not reach `fetch_build` (`Remote.resolve` refuses it, package 25). If one does, raise `VersionNotFound` before any request. What to do when the release fetched again in step 4 has no asset (the upload gap seen from the API) is not designed; treat it as the mismatch it is and fail after the one retry, and say so in the pull request.
- **No printing, and no Rich.** `progress` is a callable the command supplies.
- **Nothing here takes the store lock or looks at installed builds.** Downloads happen outside the lock ([V11](../design/12-tools-and-downloads.md#v11-concurrent-installs)); "already installed" and `--force` are decided by the caller under the lock ([V12](../design/12-tools-and-downloads.md#v12-install)).

About the fixture. Package 05's `github` fixture answers jar downloads with a small real jar it builds, not the 4.5 MB original, while the recorded release objects carry the real jar's `size` (4,510,884) and `digest`. For any download to verify, the release objects the fixture serves must carry the small jar's size and digest. If the fixture on `main` does not do that, do not weaken a check to get a green test: register the release objects in the test with the right values, and report it in the pull request so that 05's fixture is put right.

Platform (D15): `pathlib`; the file is opened in binary mode; nothing else is platform-specific.

State of `main` when this starts: the 0.8.x code with packages 01 to 03, 05 and 22 to 25 on top. The old `versioning/downloader.py` still streams straight into the final folder for the old commands; it is not touched and not imported.

## Done when

- The tests above pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- No file listed under "Must not touch" is in the diff.
- The pull request says: which T6 row, if any, was removed as unreachable and why; what happens when the refreshed release has no asset; and what was found about the fixture's sizes and digests.

## Out of scope

- The client's own behaviour (retry on 5xx, redirects, the token, the timeout): package [24](24-github-client.md).
- The release list and its cache: package [25](25-remote-listing.md).
- Moving the verified jar into the store, "already there", `repair`: package [23](23-tool-store.md) built `add`; package 27 calls it.
- `Install`, `Upgrade`, `install()`, `same_as_published`, `--force`, the comparison with a typed commit, the two T6 rows "`--force` reinstall fails" and "two installs of one build at once", and "nothing left under `.tmp/`" (V12, V4, V11): package 27.
- The first-run prompt (V9): package 28. `tool install`, `tool_install.feature`, the progress bar, the changelog entries, deleting `versioning/downloader.py`: package 29.
- Trusting a jar without a digest on first download and pinning its SHA-256 afterwards: milestone 3.

## Risks

- From V5: GitHub's digest detects corruption and a replaced asset, not a compromised release. A jar with no `X-Git-Revision` is accepted with no commit; no published release has one. A check against a tag's commit is not designed; should one ever be added it must peel annotated tags and be a warning.
- From T6: the table follows the design, not finished code; an unreachable row is removed with a line in the pull request.
- From the cut: the verification is built two packages before a command exercises it, and the feature file that shows a user "after a failed download the installed builds are unchanged" is package 29's. Until then the store-state assertions of these unit tests are the only proof.
- A mistake here installs a jar that is not what GitHub published. The review should walk the six steps against the nine rows.
