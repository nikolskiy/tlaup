# tlaplus-cli: merit and landscape assessment

Date of assessment: 2026-11-09. Code state: branch `dev` at `fb4a5e0` (release 0.8.1).

Legend used throughout:

- **[V]** verified directly during this assessment (source URL or file path given)
- **[I]** inferred, or stated from general knowledge without a fresh check

---

## 1. Verdict in brief

The motivation is real and verifiable, and nobody else solves it well. But the project only half-solves it, and the part it solves (a local cache keyed by tag + commit SHA) is the easy half. The hard half, getting the *same* build again on another machine or in CI, is not addressed, and upstream has quietly made that tractable in the last few months (CalVer tags, a `rolling` release, SHA-256 digests on assets).

The second pillar, compiling and wiring Java operator overrides, is the most original feature and has no real equivalent elsewhere. The third pillar, the TLC runner and output formatter, is a port of the VS Code extension's parser attached to a runner that cannot pass `-workers`, `-deadlock`, `-simulate` or any other TLC flag, which makes it unusable for a large share of real specs.

Strategically, the largest risk is not a competitor but the name: upstream has an open PR for an official `tla` wrapper with `tla tlc` / `tla sany` / `tla repl`, and two Rust projects plus an asdf plugin already install a binary called `tla`. One of the Rust projects is published on crates.io under the exact name `tlaplus-cli`.

It is not wheel reinvention, but as it stands it is a personal tool with one star and a narrow niche. It becomes worth other people's attention if it commits to being the reproducible toolchain manager and override builder for TLA+ projects, and stops trying to be a TLC front end.

---

## 2. What the project actually does

All from reading the source. **[V]**

| Area | Behaviour | Where |
|---|---|---|
| Version discovery | Calls GitHub `/tags` and `/releases` (first 30 each), joins them by tag name, keeps releases that have a `tla2tools.jar` asset. Result cached for one hour, with stale-cache fallback when offline. | `src/tlaup/versioning/api.py` |
| Build identity | A build is `<tag name>-<first 7 chars of the commit the tag points to>`, for example `v1.8.0-d8fb231`. That is the install directory name. | `versioning/downloader.py`, `versioning/schema.py` |
| Metadata | `meta-tla2tools.json` stores tag, full SHA, `published_at`, `download_url`, prerelease flag, and the first line of `tlc2.TLC -version`. No checksum of the jar. | `versioning/metadata.py` |
| Pinning | One global pin: a text file in the user cache holding a directory name. No per-project pin, no lockfile. | `versioning/paths.py`, `cmd/tools/pin.py` |
| Upgrade | Compares local SHA suffix with the remote tag SHA; if different, downloads the new jar and deletes the old directory. | `cmd/tools/upgrade.py` |
| Default install | `tla tools install` with no argument picks the newest non-prerelease, which today is v1.7.4 from 2024. | `cmd/tools/install.py` |
| URL install | Installs from any HTTPS URL, identified by a version-like path segment plus a download timestamp. | `versioning/downloader.py` |
| Java overrides | `tla modules add <path>` copies `lib/`, `modules/`, `tlc2/` into a global cache, runs `javac` against the pinned jar, scans sources for `ITLCOverrides` implementers, writes a `META-INF/services` file. At run time every cached module's classes go on the classpath and `-Dtlc2.overrides.TLCOverrides=` lists all override classes. | `cmd/modules/add.py`, `java/classpath.py`, `tlc/runner.py` |
| Community modules | No dedicated support. `tla modules install-community` was removed in 0.7.0; the config schema still carries the CommunityModules URLs but nothing reads them. The integration test builds a local CommunityModules checkout from source via `modules add`. | `CHANGELOG.md`, `config/schema.py`, `tests/integration/test_community_modules.py` |
| TLC runner | Builds `java <opts> -cp ... tlc2.TLC -metadir <cache> [-config X] <spec>`, adds `-tool`. Options exposed: `--cfg`, `--coverage`, `--raw`, `--show-command`, `--cleanup`. There is no way to pass `-workers`, `-deadlock`, `-simulate`, `-depth`, `-dumpTrace`, `-continue` or anything else, short of putting them nowhere (JVM opts come from `JAVA_OPTS` only). | `cmd/tlc.py`, `tlc/runner.py` |
| Output | Parser for TLC `-tool` message framing, value tokenizer, SANY error parser, Rich rendering of progress table, error trace with state diffs, coverage. The parser file states it is ported from `ts-output-parser`, i.e. the VS Code extension. Output is human text only; no JSON or other machine format. | `tlc/parser.py`, `tlc/formatter.py`, `tlc/models.py` |
| Other tools | No SANY, PlusCal translator, TLATeX, REPL, trace explorer commands. | `cmd/` |

Scale and traction **[V]**: about 4300 lines, 103 commits since 2026-02-15, 14 PyPI releases, 1 GitHub star, 0 forks, last push 2026-08-13 (GitHub API `repos/nikolskiy/tlaplus-cli`, `pypi.org/pypi/tlaplus-cli/json`).

---

## 3. Is the motivation real?

Yes, and it is slightly worse than the author describes. It is also changing.

### 3.1 How upstream publishes today

All checked on 2026-11-09 against the GitHub API and the upstream workflow file. **[V]**

- **Last stable release is v1.7.4, published August 2024.** Everything since lives in "v1.8.0, The Clarke release", which is flagged prerelease. Source: `https://api.github.com/repos/tlaplus/tlaplus/releases`.
- **The `v1.8.0` git tag is force-moved on every master build**, and the release's `tla2tools.jar` asset is deleted and re-uploaded. The workflow literally runs `git tag -f v1.8.0`, pushes with `--force`, and does a DELETE then POST on the asset. It also re-publishes the release to refresh `published_at`. Source: `https://github.com/tlaplus/tlaplus/blob/master/.github/workflows/main.yml` (steps "Upload release assets" and "Update tags").
- Today `v1.8.0` points at commit `d8fb231` (2026-11-06) and the asset was last replaced 2026-11-06T22:28Z. The same file name under the same version number has been a different binary hundreds of times.
- **There is now a second moving target, a `rolling` tag and release** ("Most recent build of the master branch"), first published 2026-10-23. The workflow comment says it exists because "Unlike v1.8.0, the rolling tag survives version bumps". It currently holds a byte-identical jar to `v1.8.0` (same SHA-256 digest in the API).
- **Upstream now also creates an immutable CalVer tag per build**, for example `2026.11.06.222357`, derived from `TLCGet("revision").calver` inside the jar. There are about 80 of these going back to 2026-04-27. They are git tags only: `releases/tags/2026.11.06.222357` returns 404, so there is no downloadable jar per CalVer tag.
- **GitHub now exposes a SHA-256 `digest` for each recent asset** in the releases API (present for `v1.8.0` and `rolling`, null for older releases).
- **Maven**: the workflow deploys to `central.sonatype.com/repository/maven-snapshots/` as `org.lamport:tla2tools:1.8.0-SNAPSHOT`. `maven-metadata.xml` there confirms a single `1.8.0-SNAPSHOT`, last updated 2026-11-06. Nothing under `repo1.maven.org/maven2/org/lamport/tla2tools` (404), so there is no immutable Maven Central release. The snapshot jar is also stripped of some bundled dependencies, so it is not the same artifact as the GitHub jar.
- **CommunityModules does it properly**: every release has an immutable timestamp tag (`202611060952`) with versioned jars plus unversioned aliases. Source: `https://api.github.com/repos/tlaplus/CommunityModules/releases`.
- `nightly.tlapl.us` is mentioned in mailing list posts as another channel; my request to it timed out, so its current state is **not verified**.

### 3.2 Independent evidence that this hurts people

- **nixpkgs is visibly broken by it.** `pkgs/by-name/tl/tlaplus18/package.nix` fetches `releases/download/v1.8.0/tla2tools.jar` with a fixed hash `sha256-OXgpd1xu...` (hex `39782977...`). The asset's current digest is `e1f11b75...`. The fixed-output hash cannot match the live file, so a from-source build fails unless a binary cache still holds the old jar. **[V]** (`https://raw.githubusercontent.com/NixOS/nixpkgs/master/pkgs/by-name/tl/tlaplus18/package.nix` versus the releases API.)
- **A Guix bug thread** complained that upstream moved the v1.8.0 tag by 87 commits and that 1.8.0 "is not a proper release" (`https://lists.nongnu.org/archive/html/bug-guix/2021-09/msg00414.html`, seen via search summary, not read in full). **[I]**
- **A TLA+ maintainer asked for the same thing.** In January 2024 Andrew Helwer asked on the mailing list whether rolling builds are archived by commit; Markus Kuppe answered that they are not, and suggested `git bisect`. Helwer's stated motive was reproducible tool versions for research papers. **[V]** (`https://groups.google.com/g/tlaplus/c/ohE2v4BEs8M`)

So the pain is confirmed by packagers, by a maintainer, and by the release machinery itself.

### 3.3 How well does tlaplus-cli address it?

Partly.

What it gets right:

- It refuses to treat `v1.8.0` as one thing. Keying the install directory on the tag's commit SHA means two different rolling builds never overwrite each other silently, and `tla tools list` shows which SHA you have versus what is current. That is the correct basic model.
- `tla tools upgrade` gives an explicit, visible moment when the jar changes, instead of a silent re-download.
- It records the TLC version string and download URL next to the jar.

What it does not solve:

1. **It cannot reproduce a build anywhere else.** The only thing it can download for `v1.8.0` is whatever is there right now. A colleague or a CI runner that installs "v1.8.0" tomorrow gets a different jar from the one pinned on your laptop, and there is no command to say "give me `d8fb231`". The pin is a local cache pointer, not a portable lock. This is the actual reproducibility problem, and it is untouched.
2. **The pin is global and per-user.** No project file, so a repository cannot declare which toolchain it was checked with.
3. **No integrity check.** The jar's SHA-256 is neither recorded nor compared, although GitHub now publishes a digest. The identity rests on an indirect link: "the tag pointed at commit X when I asked the tags API".
4. **That link is racy.** The upstream workflow uploads the asset first and moves the tag afterwards (and the tags API and releases API are fetched in two separate requests). During a build window the tool can label a new jar with the old commit SHA or the reverse. **[I]** from reading both the workflow order and `versioning/api.py`; I did not reproduce it.
5. **It ignores the better identifiers upstream now provides.** The CalVer string and git revision are embedded in the jar (`TLCGet("revision")`), and matching immutable CalVer git tags exist. The tool stores the `-version` banner but does not use the CalVer as identity.
6. **`rolling` and `v1.8.0` appear as two unrelated versions** and will be downloaded twice despite being the same bytes. Version ordering puts `rolling` below any semver because it has no parseable version.
7. **Default install gives v1.7.4**, a 2024 build. Defensible as "latest stable", but most active users and the VS Code extension are on 1.8.0 builds, so the out-of-box default is the one channel that does not have the problem the tool exists to solve.

Net: the tool diagnoses the problem correctly and makes it visible locally. It does not yet deliver reproducibility, which is what the motivation promises.

---

## 4. Alternatives and what they already cover

### 4.1 Name and binary collisions (important)

| Thing | Collision | Status |
|---|---|---|
| crates.io `tlaplus-cli` | Exact package name. It is drbh/tlaplus-rs, a Rust TLA+ model checker, published 2026-10-29, and it "puts the `tla` binary on your path". | **[V]** `https://crates.io/api/v1/crates/tlaplus-cli`, `https://github.com/drbh/tlaplus-rs` |
| crates.io `tla-cli` | younes-io/tla: lint, format and `tla check` wrapper around TLC. Binary is `tla`. | **[V]** `https://github.com/younes-io/tla` |
| asdf-tlaplus | Installs shims `sany`, `tlc`, `tla`, `pcal`, `tla2tex`. | **[V]** `https://github.com/kokjinsam/asdf-tlaplus` |
| Upstream PR #1371 | "Add optional CLI wrapper for tla2tools.jar": a `tla` script with `tla tlc`, `tla sany`, `tla repl`. Open since 2026-04-04, not merged, last activity September 2026. Maintainers want a thin wrapper over a new entry point in the jar and a `tla <verb>` design. | **[V]** `https://github.com/tlaplus/tlaplus/pull/1371`, `https://groups.google.com/g/tlaplus/c/RhOG4eyHxLs` |
| PyPI `tla` | johnyf's TLA+ parser library. Import-name neighbour, not a binary clash. | **[V]** `https://pypi.org/pypi/tla/json` |
| npm `tla-cli` | Unrelated "AI powered CLI for the TLA ecosystem". | **[V]** npm registry |
| GNU arch | The historical GNU arch client binary is `tla`. Largely extinct. | **[I]** |
| GitHub `Nugine/tlaplus-cli`, `owickstrom/tlaplus-cli-template` | Same repo name, dormant. | **[V]** GitHub search |

If upstream ever merges an official `tla` command, this project's entry point and its `tla tlc` subcommand collide head-on with the canonical tool. That alone is a reason to plan a rename of the binary now, while there is one star's worth of users to migrate.

### 4.2 Tool by tool

**Official VS Code / Cursor extension (tlaplus/vscode-tlaplus)**. **[V]** from its README and `package.json` (v1.7.0).
Bundles tla2tools and CommunityModules, runs TLC, SANY, PlusCal, TLATeX, renders progress, error traces with diffs, coverage profiler, sequence diagrams. It has a built-in MCP server (`tlaplus.mcp.port`, filesystem and knowledge-base tools), so AI agents inside the editor are already served by the official tool. The upstream build triggers a "VSCode nightly build" on every tla2tools commit. What it does not have: any setting to choose or pin a tla2tools build (none in the settings list; you can only override Java options and module search paths), and no headless or CI use. It is the origin of this project's output parser, so in the terminal-pretty-printing area tlaplus-cli is a port of it, not an alternative to it.

**TLA+ Toolbox**. GUI IDE, bundles a matching tools build, model editor, trace explorer. No CLI role. The Homebrew cask `tla+-toolbox` is at 1.7.4. **[V]** (`formulae.brew.sh/api/cask/tla+-toolbox.json`). There is no Homebrew formula for the command-line tools (no formula with a TLA+ description in `formula.json`). **[V]**

**tla-bin (pmer/tla-bin)**, 173 stars, last push April 2023. **[V]** Shell scripts: download latest release or `--nightly`, install `tlc`, `pcal`, `sany`, `tlatex`, REPL wrappers under `/usr/local`. One version at a time, no pinning, no identity. Covers "get the tools on PATH" better than tlaplus-cli (it exposes all tools and passes all flags through), and covers versioning not at all.

**tlacli (hwayne/tlacli)**, 83 stars, last push 2021, PyPI 0.0.1. **[V]** Different goal: friendlier flags and generating the `.cfg` from command-line arguments. No version management. Cited by maintainers as the reference point for a CLI. Unmaintained, so the "nice TLC flags" niche is actually open, but tlaplus-cli does not fill it either.

**tlc-cmd (tangruize/tlc-cmd)**. **[V]** Python scripts driven by an INI file: config generation, batch runs, result tables, trace to JSON, distributed mode, optional jar download. Covers batch/CI and JSON traces, which tlaplus-cli lacks.

**asdf-tlaplus**, 0 stars, July 2026. **[V]** Lists versions with `git ls-remote --tags refs/tags/v*`, so it sees `1.8.0` as one immutable version and inherits the rolling problem unsolved. It does give per-project `.tool-versions`, which tlaplus-cli lacks. I found no mise-specific plugin; mise can consume asdf plugins. **[I]**

**nixpkgs**. **[V]** `tlaplus` (1.7.4) and `tlaplus18` (1.8.0), both with `tlc`, `tlasany`, `pcal`, `tlatex` wrappers. 1.7.4 is properly reproducible. 1.8.0 is pinned by hash against a mutable URL and is currently mismatched (section 3.2). For stable releases Nix is strictly better than tlaplus-cli at pinning; for rolling builds it is broken in exactly the way this project could fix.

**AUR**. **[V]** `tla-tools` 1.7.4, `tla-toolbox` 1.7.4, `tla-toolbox-nightly`. No conda-forge `tlaplus` package (404). Repology lists only Nix for the `tlaplus` project name; a FreeBSD port and a Snap exist per search results. **[I]** for the last two.

**Apalache**. **[I]** A different checker (symbolic, SMT-based) with its own versioned GitHub releases and container images. Not affected by the rolling problem and not a substitute for managing TLC. Relevant only because mailing list participants asked whether an official CLI should also front Apalache and TLAPM.

**CommunityModules releases**. **[V]** Immutable timestamped releases with `CommunityModules.jar` and `CommunityModules-deps.jar` that include the compiled Java overrides. The normal way to use them is to put the jar on the classpath. tlaplus-cli's current route, cloning the repo and compiling it with `modules add`, is strictly more work and less reproducible than downloading the release jar, and the dedicated command for it was removed.

**MCP servers for agents**. **[V]** for existence and stated features: `richashworth/tlaplus-mcp` (parse, check, simulate, coverage, trace spec generation as structured JSON tools; auto-downloads tla2tools.jar; companion Claude Code plugin), `sonoisa/tlaplus-mcp` (npm, SANY, PlusCal, TLC), `r33drichards/mcp-tlaplus`, plus the official one inside the VS Code extension. None of these does version identity; they all grab "the" jar. For agent use they are ahead of tlaplus-cli today because they return structured data.

**New checkers written in Rust or TypeScript**. **[V]** for existence: `tla-checker` (fabracht/tla-rs, with MCP server and a Claude plugin), `tlaplus-rs`, `aidenybai/tla-ts`. Not alternatives to a TLC manager, but they compete for the "simple `tla` command in a terminal" mindshare and avoid Java entirely.

**Generic approaches**.

- *Shell script or Makefile with `curl`*: what most projects do. Has the same reproducibility hole unless the script checks a SHA-256, and then it breaks at the next upstream build. **[I]**
- *Vendoring the jar in the repo (or Git LFS)*: 4.5 MB. Crude, but it is the only approach available today that truly reproduces a rolling build for every collaborator and CI, and it needs no tool. This is the real baseline tlaplus-cli has to beat. **[I]**
- *Docker image with a baked jar*: same effect as vendoring, heavier. I did not find an official, maintained TLC image. **[I]**, not searched exhaustively.
- *Nix flake pinning a jar by hash*: reproducible only if someone keeps the bytes (own cache or mirror), for the reason shown in 3.2. **[I]**
- *Maven, coursier, jbang against the snapshot repository*: Maven snapshot repositories keep timestamped snapshot files for a while, so `1.8.0-SNAPSHOT` could in principle be resolved to a specific timestamped build. I verified the snapshot coordinate exists; I did not verify retention, timestamped resolution, or whether a jbang alias exists. The Maven artifact is also a stripped jar. **[I]**
- *Build from source at a CalVer tag*: now possible and fully deterministic in identity, since each build has an immutable git tag. Costs a JDK, Ant/Maven and minutes of build time. **[I]** that the build is straightforward.

---

## 5. Feature comparison

Scale: yes / partial / no. Rows are capabilities, columns are the realistic choices.

| Capability | tlaplus-cli 0.8.1 | VS Code ext. | tla-bin | asdf-tlaplus | nixpkgs | curl + vendored jar | MCP servers |
|---|---|---|---|---|---|---|---|
| Distinguishes two rolling builds of "1.8.0" | yes (tag + commit SHA) | no (ships one) | no | no | no (hash mismatch instead) | yes (it is the file) | no |
| Several builds installed side by side | yes | no | no | yes (by tag only) | yes (stable only) | manual | no |
| Re-obtain an older rolling build | no | no | no | no | no | yes | no |
| Per-project pin / lockfile | no (global pin) | no | no | yes (`.tool-versions`) | yes | yes | no |
| Checksum verification | no | n/a | no | no | yes | manual | no |
| Same toolchain on laptop and CI | no | n/a | no | partial | yes for 1.7.4 | yes | no |
| Compile Java operator overrides | yes | no | no | no | no | no | no |
| Wire multiple override classes at run time | yes | no | no | no | no | no | no |
| Community modules ready to use | no (build from source) | yes (bundled) | no | no | no | manual | partial |
| All TLC flags available | no (`--cfg`, `--coverage` only) | yes | yes | yes | yes | yes | partial |
| SANY, PlusCal, TLATeX, REPL | no | yes | yes | yes | yes | yes | partial |
| Readable terminal output, trace diffs | yes | yes (GUI) | no | no | no | no | n/a |
| Machine-readable results (JSON) | no | no (MCP gives some) | no | no | no | TLC's own `-dumpTrace json` **[I]** | yes |
| Works headless in CI | partial (no JSON, no flags; exit code passes through) | no | yes | yes | yes | yes | n/a |
| AI agent friendly | partial (`--show-command`, non-TTY plain output) | yes (MCP) | no | no | no | no | yes |
| Install friction | `uv tool install`, needs Python 3.11 + Java | marketplace | git clone + sudo | asdf | nix | none | npx |

Comments on the rows where tlaplus-cli looks good:

- **Rolling-build identity**: genuinely unique among the tools surveyed. Nobody else even tries.
- **Java overrides**: genuinely unique. The alternative is hand-written `javac -cp tla2tools.jar ...` plus a hand-written `META-INF/services` file or a `-Dtlc2.overrides.TLCOverrides` flag. The audience for this is small (people writing custom Java overrides are a minority of a minority), but for them it removes real friction. Design caveat: every cached module is global and is put on the classpath of every run, so two projects with conflicting overrides interfere, and results depend on invisible machine state. That works against the reproducibility story.
- **Terminal output**: good work, but it is a second implementation of the VS Code parser that must track TLC message codes forever, and it is only reachable through a runner that cannot pass flags.

One packaging detail **[I]**, from reading `flake.nix` and not tested: the Nix wrapper puts `jre_headless` on PATH, which has no `javac`, so `tla modules add` would likely fail for a user who has only the flake install.

---

## 6. Conclusions

### 6.1 Where it is genuinely useful

1. **Making the rolling build visible.** `tla tools list` showing tag, SHA, publish date and what you have installed is something no other tool offers, and it answers "which TLC am I actually running" correctly.
2. **Java override modules.** Compile, register and activate custom `ITLCOverrides` classes with one command. No equivalent exists.
3. **`--show-command`.** Printing the exact JVM invocation is valuable for bug reports and for agents.

### 6.2 Where it duplicates something better

1. **TLC front end and output rendering.** The VS Code extension does more, is official, and is the source of the parser. In the terminal, raw TLC output is acceptable to most users and supports every flag. A wrapper that cannot set `-workers` or `-deadlock` is a regression against `java -jar tla2tools.jar`.
2. **"Get TLC on my PATH."** tla-bin, nixpkgs, AUR, asdf all do that for stable releases, with every tool exposed.
3. **Community modules.** Upstream ships immutable prebuilt jars; compiling from a checkout is the worse path.
4. **A `tla <verb>` umbrella command.** Upstream is designing one. A third-party Python tool will not win that position, and maintainers have already voiced hesitation about Python-based system tools in that thread.

### 6.3 Realistic audience

- People who run TLC from a terminal or CI, track 1.8.0 rolling builds, and care which build produced a result: spec authors in industry teams, researchers who must cite tool versions, and maintainers of repositories like tlaplus/Examples-style collections.
- The subset of those who write Java overrides.
- AI coding agents driving TLC in a terminal, if and only if the tool grows structured output.

That is a small audience, on the order of hundreds of people, not thousands. Beginners use the VS Code extension and will not look for this. One star after nine months and 14 releases is consistent with that: either the niche is small, or the README does not state the one thing the tool does that nothing else does (it currently lists generic goals and never mentions rolling builds).

### 6.4 Strategic directions, in order of value

1. **Make reproducibility real: a project lockfile with content identity.**
   A `tla.lock` (or a section in a project file) recording tag, commit SHA, CalVer from `TLCGet("revision")`, the jar's SHA-256 and source URL, plus the same for CommunityModules. `tla tools install --locked` verifies the digest and fails loudly on mismatch. Use the `digest` field the GitHub API now returns to verify downloads. This turns the tool from "cache with labels" into the thing the motivation promises.

2. **Solve "get that exact build again", which is the actual gap in the ecosystem.**
   Options, cheapest first: (a) resolve timestamped Maven snapshots if retention allows, (b) a small community mirror, for instance a GitHub repository with a scheduled workflow that re-publishes each rolling jar as an immutable release named by CalVer and SHA, (c) build from source at the CalVer tag as a fallback. Option (b) would be useful to nixpkgs, Guix, asdf and CI users regardless of this CLI, and is probably the highest-leverage single thing the author could ship. Also worth raising upstream: attaching the jar to each CalVer tag would fix it at the source, and a maintainer has already asked for exactly that archive.

3. **Stop being a partial TLC wrapper: pass everything through.**
   Accept `tla tlc Spec -- <any TLC args>` (or unknown-option passthrough), and add `tla exec <java class> ...` / `tla jar-path` so scripts, Makefiles and editors can use the managed jar without the formatter. Add thin `sany`, `pcal`, `repl` passthroughs or drop the pretense of being the single interface. Without this, the version manager is held hostage by its own runner.

4. **Add structured output and a CI story; that is the agent story too.**
   `--json` or `--format ndjson` emitting the already-parsed `ModelCheckResult` (status, state counts, violated property, trace as data, coverage), documented exit codes, a GitHub Action or a three-line CI recipe that restores the locked toolchain. The parser already exists; the only missing piece is serialization. This is where the ported parser stops being a duplicate of the VS Code extension and becomes something agents and CI can consume. An MCP mode is a possible later step but there are already four MCP servers; a clean JSON CLI is the less crowded position.

5. **Rename the binary, and decide the package name's future.**
   `tla` collides with an open upstream proposal, two crates and an asdf shim, and `tlaplus-cli` is taken on crates.io by a different kind of tool. A distinct name that says what it is (toolchain or version manager for TLA+) avoids confusion and avoids being displaced the day upstream merges its wrapper. Do it before there are users to break. Position the tool explicitly as complementary to an official CLI: it supplies the jar, the classpath and the lock; the official `tla` can run it.

6. **Scope overrides per project and restore community modules as a download.**
   Let a project declare its override modules and community-modules version in the same lockfile, build into a project-keyed cache, and only put declared modules on the classpath. Reinstate a community modules command that fetches the immutable release jar by timestamp tag. Global, implicit classpath contents contradict everything in direction 1.

### 6.5 What to drop or freeze

- **The Rich live UI** (ticking footer, 4 Hz refresh, scrolling stats table). It consumed several releases, is the area most duplicated by the VS Code extension, and adds parser maintenance burden. Keep the plain streamed output and the error-trace rendering; freeze the rest.
- **Config surface that nobody needs** (`workspace.spec_dir`, `config edit`, legacy pin migrations) can stay but should not grow.
- **"Latest stable = v1.7.4" as the silent default.** Either ask, or default to the rolling build with a clear label, since stable is two years old and is the one case every other packager already handles.

---

## 7. What was verified and what was not

Verified with a direct request on 2026-11-09:

- Upstream releases, tags, asset digests and dates: `https://api.github.com/repos/tlaplus/tlaplus/releases`, `.../tags`, `.../git/matching-refs/tags/rolling`
- Upstream release mechanics: `https://raw.githubusercontent.com/tlaplus/tlaplus/master/.github/workflows/main.yml`
- No release behind CalVer tags: `https://api.github.com/repos/tlaplus/tlaplus/releases/tags/2026.11.06.222357` (404)
- Maven snapshot coordinate: `https://central.sonatype.com/repository/maven-snapshots/org/lamport/tla2tools/maven-metadata.xml`; absence on Maven Central release repo
- CommunityModules releases: `https://api.github.com/repos/tlaplus/CommunityModules/releases`
- nixpkgs packages and hash mismatch: `https://raw.githubusercontent.com/NixOS/nixpkgs/master/pkgs/by-name/tl/tlaplus18/package.nix`
- Registry name checks: PyPI, npm and crates.io JSON APIs for the names listed in 4.1
- READMEs of younes-io/tla, drbh/tlaplus-rs, pmer/tla-bin, hwayne/tlacli, kokjinsam/asdf-tlaplus, sonoisa/tlaplus-mcp, richashworth/tlaplus-mcp, tangruize/tlc-cmd, tlaplus/vscode-tlaplus (README and `package.json`)
- Mailing list threads and PR: `https://groups.google.com/g/tlaplus/c/ohE2v4BEs8M`, `https://groups.google.com/g/tlaplus/c/RhOG4eyHxLs`, `https://github.com/tlaplus/tlaplus/pull/1371` (read through an automated page summary, and the first thread was truncated, so later replies may be missing)
- AUR and Homebrew: `aur.archlinux.org/rpc`, `formulae.brew.sh/api`
- Project facts: source files under `src/tlaup/`, GitHub and PyPI APIs

Not verified:

- `nightly.tlapl.us` current content (request timed out)
- Whether Maven snapshot timestamped builds are retained long enough to serve as an archive, and whether the stripped Maven jar behaves identically
- Existence of jbang aliases, coursier recipes, a maintained official Docker image, a dedicated mise plugin, or a setup GitHub Action (GitHub search was rate-limited before I could run those queries; absence here means "not found", not "does not exist")
- The tag/asset race described in 3.3 point 4 (reasoned from code, not reproduced)
- That `tla modules add` fails under the Nix flake install (read from `flake.nix`, not run)
- Apalache distribution details, GNU arch `tla` presence in current distros, the Guix bug thread content, FreeBSD port and Snap status (general knowledge or search snippets only)
- Actual user numbers: PyPI download statistics were not checked, so the audience estimate is a judgement
- I did not run the tool or its test suite; all behaviour claims come from reading the code
