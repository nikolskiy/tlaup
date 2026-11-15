# 09. nightly.tlapl.us and existing setup tools

## Question

Does `nightly.tlapl.us` respond, what does it serve, where do its downloads point, is it maintained, and when was it last updated? Does a setup GitHub Action, a jbang alias or a mise or asdf plugin for the TLA+ tools already exist? How do `tlaplus/tlaplus` and `tlaplus/Examples` set up TLC in their own CI?

## Source

Commands run on 2026-11-14 (server clock showed 2026-11-15 UTC): `curl -sI` and `curl -s` against `nightly.tlapl.us`; `gh search repos`, `gh search code`, `gh api` against GitHub; the file trees of `jdx/mise` (`registry/`), `asdf-vm/asdf-plugins` (`plugins/`) and `jbangdev/jbang-catalog`; workflow files in `tlaplus/tlaplus` and `tlaplus/Examples`. No web search tool was used.

## Short answer

- `nightly.tlapl.us` responds (HTTP 200 over http and https, Apache 2.4.71 on Debian) and is actively maintained. It is a plain directory listing, not a site. `dist/tla2tools.jar` was last modified 2026-11-15 00:22 GMT (4,510,884 bytes). The same listing holds the Toolbox zips, a p2 update site and the Toolbox docs. Nothing on it points elsewhere: the jar is served from the host itself. It is fed by an rsync from the `tlaplus/tlaplus` `main.yml` workflow.
- A setup GitHub Action for the tools exists but is tiny and does not do what milestone 4 wants: `zactionsz/tla-tools` (0 stars, created 2026-08-11). It installs and verifies a jar; it does not run TLC or produce annotations. No action that runs TLC and turns output into annotations was found.
- An asdf plugin exists: `kokjinsam/asdf-tlaplus` (0 stars, one commit, 2026-07-07). It is not in the asdf plugin list or the mise registry.
- No jbang alias and no mise registry entry for the TLA+ tools were found.

## Confidence

Partly verified. The `nightly.tlapl.us` facts, the two tools above and the CI facts are verified. The absence of other tools is only as good as GitHub code and repo search: the GitHub Marketplace could not be searched (its search page is rendered by JavaScript; `curl` returned 0 results for all queries, which means nothing), and jbang catalogues in private repos or on other hosts cannot be searched.

## Evidence

### nightly.tlapl.us

- `curl -sI https://nightly.tlapl.us/` returned `HTTP/1.1 200 OK`, `Server: Apache/2.4.71 (Debian)`. The plain `http://` URL also returns 200 (no redirect to https seen).
- Root is an Apache `Index of /` with four folders and no landing page: `dist/` (2026-11-15 01:29), `doc/` (01:05), `products/` (01:30), `toolboxUpdate/` (01:27).
- `dist/` holds `tla2tools.jar` (4.3M, modified 2026-11-15 01:22 listing time; `Last-Modified: Sun, 15 Nov 2026 00:22:04 GMT`, `Content-Length: 4510884`), `tla2tools-1a92ec7.jar` (3.3M, 2023-09-25) and a folder `1a92ec7/` with the same old jar. So there is one moving "latest" jar and one frozen 2023 build; no per-build history.
- `products/` holds `TLAToolbox-1.8.0-*` zips for linux x86_64/aarch64, macOS x86_64/aarch64 and win32. `toolboxUpdate/` is a p2 and apt repository (`Packages`, `Release.gpg`, `content.jar`, `.deb`). `doc/` is the Toolbox help HTML.
- Downloads are local to the host; no redirect to GitHub. No version number, checksum file or manifest is published next to the jar (the listing has none).
- Maintenance: `tlaplus/tlaplus/.github/workflows/main.yml` lines 265 to 268 run `rsync ... github@upload.tlapl.us:dist/` for `tla2tools.jar`, `products/`, `repository/` and `doc/` with `--delete`. The folder times above match the `v1.8.0` pre-release published 2026-11-15T00:29Z, so each CI build on the main branch replaces the files. It tracks the development branch, not a release.
- Related fact: the GitHub releases of `tlaplus/tlaplus` are `v1.8.0` (pre-release, published 2026-11-15), `rolling` (pre-release, 2026-10-23), then `v1.7.4` (2024-08-05, the latest non-pre-release). `main.yml` also uploads `tla2tools.jar` to a draft release, deleting the old asset first. So the GitHub `v1.8.0` asset is also replaced continuously (README of `zactionsz/tla-tools` says the same).
- Not checked: whether the jar on `nightly.tlapl.us` is byte-identical to the GitHub `v1.8.0` asset; whether the server publishes an HTTPS certificate with long validity; any stated support policy.

### Existing tools

| Tool | URL | Owner | What it does | Last activity | Stars | Licence |
|---|---|---|---|---|---|---|
| GitHub Action `zactionsz/tla-tools` | https://github.com/zactionsz/tla-tools | `zactionsz` (organisation) | Node 24 action (TypeScript). Inputs `version` and `sha256`. Downloads a jar from the repo's own immutable releases (mirror of `tla2tools.jar`), checks SHA-256, checks the jar has TLC classes (`jar tf`), checks `java -cp jar tlc2.TLC -h` prints `Version <version>`. Exports `TLA2TOOLS_JAR` and outputs `version`, `jar-path`, `sha256`, `java-command`. Needs Java 11+ and `jar` already on PATH. Does not run TLC, does not cache (not seen in `src/`), no annotations. | Last commit 2026-08-24; one release `tla2tools-2026.08.11.125311` (2026-08-24, immutable); repo created 2026-08-11 | 0 | MIT |
| asdf plugin `kokjinsam/asdf-tlaplus` | https://github.com/kokjinsam/asdf-tlaplus | `kokjinsam` (personal) | `asdf plugin add tlaplus <url>`; `asdf install tlaplus 1.8.0`. Downloads from `github.com/tlaplus/tlaplus/releases/download`, keeps `lib/tla2tools.jar`, writes shims `sany`, `tlc`, `tla`, `pcal`, `tla2tex` that run `java -cp ... <class>`. Needs Java 11+. No TLC run, no annotations. | One commit, 2026-07-07 | 0 | none stated (GitHub reports no licence) |
| `pmer/tla-bin` | https://github.com/pmer/tla-bin | `pmer` | Older command line wrapper binaries for the tools (README not read in this spike) | 2023-04-27 | 173 | not checked |

Other hits for `tla2tools` in `action.yml` code search are composite actions private to the owner's own CI, not reusable tools: `lukacf/meerkat` (`setup-tlc-ci`), `NSTA1/Orleans.Lattice` (`tla-toolchain`), `strawgate/fastforward` (`run-tlc`), `AlexanderMattTurner/agent-glovebox` (`cache-tla2tools`, keyed on a version and digest pin, caches the jar), `Parcha-ai/agentrun`, and a few unrelated repos. They show the same need (pinned jar, cache, run TLC) is rebuilt by hand in several projects. Their contents were not read beyond the descriptions and `cache-tla2tools`'s header.

Searches that returned nothing relevant: `gh search repos` for `setup-tlaplus`, `tlaplus action tlc`, `setup-tlc`, `tla2tools github action`, `jbang tlaplus`, `mise tlaplus`, `tla+ model checker github action`, `tlc annotations github`; topic search `tlaplus` plus `github-actions` returned `zactionsz/tla-tools`, `AlexEreh/tla-test` (a Go demo project with a Makefile, not an action) and one unrelated repo.

### jbang, mise, asdf registries

- jbang: `gh search code tla --filename jbang-catalog.json` returned only `JabRef/jbang-catalog` (no TLA entry in the file as listed by `grep`, not read in full); `jbangdev/jbang-catalog` has no TLA entry (`grep -i tla` found nothing); the `tlaplus` organisation has no repo with "catalog" in its name; `raw.githubusercontent.com/tlaplus/jbang-catalog/main/jbang-catalog.json` is 404. Conclusion: no TLA+ jbang alias found.
- mise: `jdx/mise` git tree (1024 files in `registry/`, tree not truncated) has no TLA+ entry. The only matches for `tla` are `atlas.toml` and `atlas-community.toml`, which are the Atlas database tool (false positives). mise can still use `asdf:` plugins by URL, so `kokjinsam/asdf-tlaplus` would work there too (not tested).
- asdf: `asdf-vm/asdf-plugins` (843 plugin files) has no TLA+ entry (matches only `atlas`). The only plugin found is the unlisted `kokjinsam/asdf-tlaplus`.
- GitHub Marketplace: not searchable from the command line; see Confidence.

### How the upstream repositories set up TLC in CI

- `tlaplus/tlaplus` builds the jar itself (`ant -f tlatools/org.lamport.tlatools/customBuild.xml ... test`, Maven for the Toolbox) in `main.yml`, uses `actions/setup-java` pinned by commit SHA, and publishes the results (see above). It does not use any setup action.
- `tlaplus/Examples` `.github/workflows/CI.yml`: `actions/setup-java@v4` (Temurin 17 for TLC, 21 for Apalache), then `.github/scripts/linux-setup.sh` / `windows-setup.sh` which run `wget https://github.com/tlaplus/tlaplus/releases/download/rolling/tla2tools.jar` (line 43), plus Apalache, CommunityModules, tlapm and tlauc downloads. TLC is then run by Python scripts (`check_small_models.py`, `parse_modules.py`) with `--tools_jar_path deps/tools/tla2tools.jar`. It uses neither `nightly.tlapl.us` nor a pinned jar: it takes the `rolling` GitHub pre-release asset, which is a moving target and not reproducible. No annotations were seen in the part of the workflow read (lines 1 to 140 of 1 file; the remaining jobs and `ewd998.yml`, `TLAi.yml`, `manual.yml` were only seen by name and by the `uses: tlaplus` code search hit).
- `tlaplus/vscode-tlaplus` workflows (`ci.yml`, `release.yml`) were listed only, not read.

## Implications for the roadmap

- Milestone 4: no existing action runs TLC and produces annotations, so the "check first" gate is passed in the sense that nothing to reuse or replace was found. The closest, `zactionsz/tla-tools`, covers only the install step and pins by SHA-256 against its own mirror; it is a single-maintainer project 3 months old with no users. It is a sign the problem (rolling release assets that disappear) is real and others hit it, and that tlaup's lock file plus checksum approach is addressing a known gap. Re-check just before starting milestone 4; the field is new and moving.
- `nightly.tlapl.us` is a plausible, but unversioned, download source: one moving jar, no checksum, no history, tied to the development branch. tlaup should not treat it as a stable pin source. If tlaup supports it at all, it needs to record the SHA-256 at install time (the lock approach) because the URL never changes while the bytes do.
- A jbang alias or mise registry entry does not exist; a "mise plugin" would be a new project, and tlaup's own install command makes it largely redundant. Whether to submit one is a decision for the maintainer, not needed for the milestones.
- The upstream Examples CI downloads the `rolling` asset each run; a tlaup-based action that restores a locked jar and caches it would be a real improvement for repositories like that.

## Open follow-ups

- Search the GitHub Marketplace in a browser (or via the Chrome or browser tools) for `tla`, `tlaplus`, `tlc` to close the one gap in the search.
- Read the `src/` of `zactionsz/tla-tools` for caching and `action.ts` details if the milestone 4 design wants to build on or interoperate with it; contact is out of scope for this spike.
- Compare the `nightly.tlapl.us/dist/tla2tools.jar` bytes with the GitHub `v1.8.0` asset (requires a download, which was not done).
- Read `tlaplus/vscode-tlaplus` CI and the rest of `tlaplus/Examples` workflows for any annotation or problem-matcher use.
- Check whether TLC output has a GitHub problem matcher in any of the composite actions found (not read).

## Date checked

2026-11-14 (GitHub and server data read on that date; the server's own clock was already on 2026-11-15 UTC).
