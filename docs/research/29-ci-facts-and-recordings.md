# 29: CI facts from the network, and real GitHub recordings

## Question

Roadmap question 29: does `actions/setup-java` offer Temurin 11 on the macOS runner (arm64 today) and on `macos-13`; what is the newest CPython that `actions/setup-python` offers and does `uv python install` offer it; what is the current release of every action the workflows and the design use, with the commit SHA its tag points to; and real GitHub recordings for the tests: two pages of a paginated listing with their `Link` headers, and a rate-limit 403 with its headers.
Serves [30 I1, I2, L2](../design/30-ci-and-release.md), [12 V7, V8](../design/12-tools-and-downloads.md) and [01 T4, T6](../design/01-testing.md).

## Source

- Adoptium API (`api.adoptium.net/v3`), queried with the same URL `actions/setup-java` builds. setup-java source read at commit `d1374f8ac74474200d16ef8ecee22c7ae7a51880` (v6.3.0): [temurin/installer.ts](https://github.com/actions/setup-java/blob/d1374f8ac74474200d16ef8ecee22c7ae7a51880/src/distributions/temurin/installer.ts), [base-installer.ts](https://github.com/actions/setup-java/blob/d1374f8ac74474200d16ef8ecee22c7ae7a51880/src/distributions/base-installer.ts), [action.yml](https://github.com/actions/setup-java/blob/d1374f8ac74474200d16ef8ecee22c7ae7a51880/action.yml), [README](https://github.com/actions/setup-java/blob/d1374f8ac74474200d16ef8ecee22c7ae7a51880/README.md).
- Runner images: [README](https://github.com/actions/runner-images/blob/fbb26cb01c3651ea3a0347e54bfa2ef83d740d49/README.md) and the [macOS 26 arm64 image list](https://github.com/actions/runner-images/blob/fbb26cb01c3651ea3a0347e54bfa2ef83d740d49/images/macos/macos-26-arm64-Readme.md), at `main` = `fbb26cb0`.
- [`actions/python-versions` `versions-manifest.json`](https://github.com/actions/python-versions/blob/9bc1fe8f6b4befbb1edd3955a1adc8fc086b3e08/versions-manifest.json) at `9bc1fe8f`; `astral-sh/python-build-standalone` release `20261110`; uv 0.13.9 (latest release) run with `uv tool run --from uv==0.13.9 uv python list --only-downloads`. The local uv is 0.10.10 and knows only 3.15.0a7, so a stale uv says "no 3.15.2".
- GitHub REST API through `gh api` (releases, refs, tags) for the actions; `curl` without a token for the recordings.
- Files: `<repo>/tests/fixtures/research/29-ci-facts-and-recordings/` (`README.md` describes each; `record.sh`, `action_tags.sh`, `adoptium_pages.py`, `actions.txt` produced the data).
- Checked 2026-11-19 UTC, Linux x86-64, 12 cores. Nothing was run on a macOS machine by this agent; the CI run below did.

## Short answer

1. **Temurin 11 on macOS arm64: yes.** Adoptium publishes `OpenJDK11U-jdk_aarch64_mac_hotspot_11.0.33_10.tar.gz` (11.0.33+10), and the x64 build too. setup-java passes the runner's own architecture (`os.arch()`, with `arm64` turned into `aarch64`) to the Adoptium query and has **no fallback to x64**: if a version were missing for that architecture the step would fail, not substitute. Here nothing is missing: the exact query setup-java builds (5 pages of 20 for aarch64) returns 23 Java 11 builds, newest 11.0.33+10. `macos-latest` is macOS 26 on arm64 today. That image also has Temurin 11.0.32 preinstalled (`JAVA_HOME_11_arm64`), and with `check-latest: false` (the default) setup-java takes a matching cached version before downloading, so the cell may run 11.0.32 and not 11.0.33; either is fine.
2. **`macos-13` is gone.** It is not in the runner-images list. The Intel labels now are `macos-15-intel` and `macos-26-intel` (`macos-latest-large` = macOS 26 Intel); macOS 14 images were retired on 2026-11-02. If the design wants an Intel macOS cell it names `macos-15-intel`, and Temurin 11 x64 exists. The design names only `macos-latest`, so nothing to change unless Intel is wanted.
3. **Newest CPython.** `actions/setup-python` offers **3.15.2** (stable; also 3.16.0-alpha.2, not stable) for every OS and arch the matrix uses (darwin arm64 and x64, linux x64 on 22.04, 24.04 and 26.04, win32 x64). uv offers **3.15.2** too, from python-build-standalone 20261110, with uv 0.13.9 (what `astral-sh/setup-uv` installs by default); an older uv offers an older newest (0.10.10: 3.15.0a7 only). The runner images carry 3.14.x preinstalled as their newest, so "newest" via setup-python is a download, via uv also a download.
4. **Action releases** (latest release, tag, commit it points to; all tags here are lightweight commits except where marked):

| Action | Used now | Latest release | Commit SHA | Published |
| --- | --- | --- | --- | --- |
| `actions/checkout` | `@v4` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | 2026-07-20 |
| `actions/setup-python` | `@v5` | `v7.1.0` | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` | 2026-10-22 |
| `actions/setup-java` | `@v4` | `v6.3.0` | `d1374f8ac74474200d16ef8ecee22c7ae7a51880` | 2026-11-14 |
| `astral-sh/setup-uv` | `@v5` | `v10.3.3` | `68559e99cc807c1eb7e9238fd43a15bba460eec2` | 2026-10-28 |
| `actions/upload-artifact` | `@v4` | `v7.0.2` | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` | 2026-10-07 |
| `actions/download-artifact` | `@v4` | `v8.0.2` | `9000827ccba6bdab643e8b6fd33ac0654aef8333` | 2026-10-07 |
| `actions/cache` (named in I1) | none yet | `v6.1.0` | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` | 2026-06-26 |
| `pypa/gh-action-pypi-publish` | `@release/v1` | `v1.14.3` (annotated tag, dereferenced) | `7245906fb61fa33a13554f9d5fb856fe61758086` (same as the `release/v1` branch head) | 2026-10-20 |
| `softprops/action-gh-release` | `@v2` | `v3.0.4` (annotated tag, dereferenced) | `8a0cd651e5b2365bd640854a3fa5dfc70e4875f3` | 2026-11-05 |

   The design drops `softprops/action-gh-release` for `gh release create` (L2), so it needs no pin. Every action is several majors ahead of the workflows. `setup-uv` has no floating `v10` tag (`git/ref/tags/v10` is a 404; only full tags such as `v10.3.3` exist), so a Dependabot or hand pin of that action must use the full tag; the `actions/*` ones have `v7`, `v6`, `v8` major tags. Dependabot is not an action.
5. **Recordings** made (details below): two pages of the tags listing at `per_page=30`; two pages of the releases listing at `per_page=10` (the `releases-paged` of T4); and a real 403 from the exhausted unauthenticated allowance. A 429 was not seen.
6. **Cache immutability** (I1 step 3 risk): confirmed from the action's own documentation at `55cc8345`: "A cache today is immutable and cannot be updated" (`tips-and-workarounds.md`); the fix it gives is a unique key plus `restore-keys`. Caches idle for a week are evicted, and the repository limit is 10 GB (README).

## Confidence

Verified for (1), (3), (4), (5) and (6): each was read from the live source on 2026-11-19. (1) is now also confirmed by a real run on a macOS runner (see "Confirmed by a CI run" under Evidence). (2) rests on the runner-images README listing; the absence of `macos-13` is read from that list, not from a failed job.

## Evidence

**Confirmed by a CI run (setup-java on macOS arm64).** [GitHub Actions run 44489200898](https://github.com/nikolskiy/tlaup/actions/runs/44489200898) (branch `research/top-up-experiments`, commit `0d43a75`, 2026-11-19 08:37 to 08:48 UTC, conclusion success). Runner images: `macos-latest` = macos26 image 20261112.0504.1, arm64 (`uname -m` = arm64); `ubuntu-latest` = ubuntu26 20261111.82.6 x86_64; `windows-latest` = win25-vs2026 20261103.298.1 x86_64. `actions/setup-java` v6.3.0 with `distribution: temurin`, `java-version: 11` and `check-latest: true` installed **Temurin 11.0.33+10** on all three: on macOS under `hostedtoolcache/Java_Temurin-Hotspot_jdk/11.0.33-10/aarch64/Contents/Home` (the aarch64 build, no x64 fallback), on Linux and Windows x64. The macOS output: `openjdk version "11.0.33"`, `Temurin-11.0.33+10`, 64-Bit Server VM. Temurin 21 (21.0.13+9, Windows 21.0.13.1+2) was on `PATH`. `actions/setup-python` gave Python 3.13.17 (3.13.18 on Linux) and uv was 0.13.9. Note: one check line on Windows failed only because of a backslash in the workflow's own `echo`; the Java 11 home itself was set correctly. The macOS result with `check-latest: true` shows 11.0.33 is reachable; without it the preinstalled 11.0.32 may be used, as noted above.

**Adoptium, aarch64 and x64** (`adoptium_pages.py`, same query string as the setup-java source: `project=jdk&vendor=adoptium&heap_size=normal&sort_method=DEFAULT&sort_order=DESC&os=mac&architecture=<a>&image_type=jdk&release_type=ga&jvm_impl=hotspot&page_size=20&page=0`, versions `[1.0,100.0]`, following `Link rel="next"`):

```
aarch64 pages read: 5 java 11 builds: 23 newest: [('11.0.33+10', 'OpenJDK11U-jdk_aarch64_mac_hotspot_11.0.33_10.tar.gz')]
x64 pages read: 7 java 11 builds: 26 newest: [('11.0.33+10', 'OpenJDK11U-jdk_x64_mac_hotspot_11.0.33_10.tar.gz')]
```

The first page alone shows only Java 22 to 27 (sorted by version, newest first), which is why a one-page look gives a false "none"; setup-java reads every page up to a safeguard limit. The first request without a `User-Agent` got a 403 from the Adoptium host; setup-java sends `actions/setup-java`. Also `GET /v3/assets/latest/11/hotspot?architecture=aarch64&image_type=jdk&os=mac&vendor=eclipse` returns `jdk-11.0.33+10`, and `/v3/info/available_releases` lists LTS 8, 11, 17, 21, 25.

**setup-java architecture handling.** `action.yml`: input `architecture`, "Defaults to the action runner's architecture"; `base-installer.ts` line 62-64: `normalizeArchitecture(installerOptions.architecture || os.arch())`; the Temurin installer sends that value as `architecture=` and has no retry with another one. README line 244: with `check-latest: false` the runner tool cache is tried first, then a download.

**macOS runner.** `macos-latest` row of the runner-images README: macOS 26 Arm64, labels `macos-latest`, `macos-26`, `macos-26-xlarge`. macOS 26 Intel: `macos-latest-large`, `macos-26-intel`, `macos-26-large`. macOS 15: `macos-15`, `macos-15-intel`. No row for macOS 13. macOS 26 arm64 image: Java 11.0.32+101 (`JAVA_HOME_11_arm64`), 17.0.21+9, 21.0.13+9.0 (default), 25.0.5+8.0.

**Python.** `versions-manifest.json` first entries: 3.16.0-alpha.2 (not stable), 3.16.0-alpha.1, then **3.15.2 stable**, 3.15.1, 3.15.0. Platforms of 3.15.2: darwin arm64 and x64, linux x64 and arm64 (22.04, 24.04, 26.04), win32 x64, arm64, x86, plus free-threaded builds. uv: `cpython-3.15.2-linux-x86_64-gnu <download available>` with uv 0.13.9; python-build-standalone 20261110 has `cpython-3.15.2+20261110-aarch64-apple-darwin`, `-x86_64-pc-windows-msvc` and `-x86_64-unknown-linux-gnu` `install_only` archives. The project's `pyproject.toml` lists classifiers 3.11 to 3.13 and `requires-python >=3.11`; per the design the unit matrix would run 3.11 and "the newest", which today is **3.15** (not 3.13 or 3.14). Whether `tlaup` and its locked dependencies work on 3.15 was not tried here.

**Action tags** (`actions.txt`, from `action_tags.sh`: `releases/latest`, then `git/ref/tags/<tag>`, and `git/tags/<sha>` when the ref's type is `tag`). Major tags checked: `checkout v7`, `setup-python v7`, `setup-java v6`, `upload-artifact v7`, `download-artifact v8`, `cache v6` point at the same commits as the full tags; `softprops v3` points at `40c2ca6d`, a different commit from `v3.0.4` (it moved on or is not the same release, so a major tag is not a substitute for a pin).

**Recordings** (`<repo>/tests/fixtures/research/29-ci-facts-and-recordings/`, full headers):

- `tags-paged/page1`: 200, 30 tags, 12,296 bytes, `link: <https://api.github.com/repositories/50906927/tags?per_page=30&page=2>; rel="next", <...&page=4>; rel="last"`. `page2`: 200, 13,621 bytes, `link` with `rel="prev"`, `"next"` (page 3), `"last"` (page 4), `"first"`. The addresses use `/repositories/50906927/`, not `/repos/tlaplus/tlaplus/` (as research 8 found), and keep `per_page`. Headers also carry `x-ratelimit-limit: 60`, `-remaining`, `-used`, `-resource: core`, `-reset`, `cache-control: public, max-age=60`, `etag`, `server: github.com`.
- `releases-paged/page1`, `page2`: `per_page=10` gives 10 and 7 releases; `page1` `link` has `rel="next"` and `rel="last"` both pointing at page 2; `page2` has `rel="prev"` and `rel="first"` and **no** `rel="next"` (the loop's end). Bodies are cut to the fields tlaup reads (README of the folder).
- `rate-limited/response`: the request that came after 60 unauthenticated requests within the hour (this machine's quota was 60/hour; the earlier 4 recordings and 56 loop requests used it; the 57th loop request was refused). Result: `HTTP/2 403`, `server: Varnish` (not `github.com`: an edge answer), `x-ratelimit-limit: 60`, `x-ratelimit-remaining: 0`, `x-ratelimit-used: 60`, `x-ratelimit-resource: core`, `x-ratelimit-reset: 1795078778` (the top of the hour after the first request: 2026-11-19 08:59:38 UTC), `content-length: 279`, **no `retry-after`**, no `link`. Body: `{"message":"API rate limit exceeded for <ip>. (But here's the good news: Authenticated requests get a higher rate limit. Check out the documentation for more details.)","documentation_url":"https://docs.github.com/rest/overview/resources-in-the-rest-api#rate-limiting"}`; the real address was replaced by `<ip>`. No header carried personal or machine data; no token was sent. The fixture files contain no home path, user name or email.

## Implications for the roadmap

- **30 I1:** the `java: 11` cell on `macos-latest` is supported: Temurin 11 exists for aarch64 macOS; no distribution change needed, and the "if it does not, name the distribution" branch is not taken. Drop the mention of `macos-13`; if Intel is wanted use `macos-15-intel`. Say in a comment that `macos-latest` is arm64 and that the runner's preinstalled 11.0.32 may be used before the download.
- **30 I2 and the Python table (section on versions):** "newest" is 3.15 (setup-python 3.15.2, uv 3.15.2 with a current uv). The classifier list therefore says 3.11 and 3.15, unless the maintainer decides otherwise; whether the code and locked dependencies pass on 3.15 is untried (the CI run will show). `uv sync --python 3.15` needs a uv that knows 3.15.2: leave `setup-uv` on its default (latest uv) and do not pin an old uv version.
- **30 L2, B1 and the pinning rule:** pin `pypa/gh-action-pypi-publish` to `7245906fb61fa33a13554f9d5fb856fe61758086` (# v1.14.3) and `actions/download-artifact` to `9000827ccba6bdab643e8b6fd33ac0654aef8333` (# v8.0.2); `upload-artifact` `cf430e030ddbb5b0abf93d22962f4752f3646cd9` (# v7.0.2), `checkout` `3d3c42e5...` (# v7.0.1), `setup-java` `d1374f8a...` (# v6.3.0), `setup-python` `6d4fd22b...` (# v7.1.0), `setup-uv` `68559e99...` (# v10.3.3), `cache` `55cc8345...` (# v6.1.0). Today's workflows are two to five majors behind; the Dependabot job (B1) will propose them. `softprops/action-gh-release` can go. `release/v1` of the PyPA action is a branch, which is mutable, so the pin is a real gain over the current `@release/v1`.
- **12 V7 and 01 T4, T6:** the recordings exist now. V7's rate-limit rule (403 or 429 with `x-ratelimit-remaining: 0` or `Retry-After`) matches the real 403, which has `x-ratelimit-remaining: 0` and **no `Retry-After`**, so the `remaining == 0` test is the one that fires, and the reset time comes from `x-ratelimit-reset` (seconds since the epoch). The message "resets at HH:MM" works from that. A real 429 was not obtained; the design keeps it as documented. `get_paged` follows `rel="next"` and stops when it is absent, as `releases-paged/page2` shows; the next addresses are `https://api.github.com/repositories/50906927/...?...&page=N`.
- **01 T4:** the recording layout can use `tags-paged`, `releases-paged` and `rate-limited` from this folder (T4 lists `releases-paged`, `rate-limited`; and says no tags recording is made, so `tags-paged` is extra and holds the full-size bodies, a useful check that tlaup handles headers like `link` with four relations). T4's sentence "the real list is one page today" is true of releases only (17), and `per_page=10` gives the real two pages as planned.
- **30 I1 step 5, risks:** cache immutability confirmed from the action's documentation (unique key, or the `1` in the key raised by hand).

## Open follow-ups

- Done by the CI run (above): the check below for `macos-latest`. Still open: `macos-15-intel`, and 3.15 through `setup-python` (the run used 3.13). Original list: on `macos-latest` run `actions/setup-java` (`distribution: temurin`, `java-version: '11'`) and print `uname -m`, `java -version` and `$JAVA_HOME`: expect `arm64`, an `OpenJDK 64-Bit Server VM Temurin-11.0.33+10` (or 11.0.32 if the preinstalled copy was used; setting `check-latest: true` forces 11.0.33), and `os.arch aarch64` (`java -XshowSettings:properties -version 2>&1 | grep os.arch`). Also run the same on `macos-15-intel` if an Intel check is wanted. Also print `uv python list --only-downloads | grep 3.15` (after `setup-uv`) and `python --version` after `setup-python` with `3.15`.
- Not done: running either build of TLC on Java 11 on arm64 macOS (question 28 covers Java 11 generally; arm64 macOS is a separate cell for the CI run).
- Not found: a real 429, and a secondary-limit 403 with no rate-limit headers (V7's risk note); both stay documented only.
- The unauthenticated quota is per address and per hour; the recorder script can be rerun only after the reset, and recorded `date` and `reset` values will differ.

## Date checked

2026-11-19 (UTC).
