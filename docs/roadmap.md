# Roadmap

Drafted 2026-11-09 from the [project analysis](analysis/00-summary.md), against release 0.8.1. The project has since moved from `tlaplus-cli` to this repository and was renamed to `tlaup` in 0.8.2 (2026-11-14); items finished since then are ticked with the date. This is a proposal, not a commitment: nothing here has been implemented or tested, and effort sizes are rough estimates carried over from the reviews (S = hours, M = one to three days, L = a week or more).

## Guiding principle

The tool's reason to exist is **a reproducible TLA+ toolchain**: the same jar, the same modules, on every machine. Today it delivers a labelled local cache and a TLC runner that mis-parses real output. The order below is therefore:

1. Stop being wrong (runner correctness, data safety).
2. Stop shipping blind (tests and CI that would have caught the above).
3. Deliver the promise (lockfile, digests, re-fetchable builds).
4. Then restructure and widen.

Each milestone is releasable on its own. Items link to the report section that holds the evidence.

## Decisions

Made on 2026-11-10. They shape several milestones below.

| # | Question | Decision | Consequence |
| --- | --- | --- | --- |
| D1 | Keep the `tla` binary name? | **Rename package, command and repository to `tlaup`; retire `tlaplus-cli`.** Revised 2026-11-14 (walkthrough notes 8). | `tla` collides with a crates.io project, `tla-cli`, an asdf shim, and open upstream PR 1371. Done in 0.8.2 with no `tla` alias; the final `tlaplus-cli` release forwards to `tlaup` with a notice. See [merit 6.4](analysis/01-merit-and-landscape.md). |
| D2 | Branch model? | **Trunk plus tags.** | Retire the `dev` branch and worktree; CI runs on every push to `main` and on pull requests; releases are tags on green commits. See [packaging 6](analysis/05-packaging-ci-release.md). |
| D3 | Rich live display: finish, freeze, or remove? | **Finish it.** The analysis recommended freezing. | The unrendered layout gets wired up rather than deleted, which adds work to milestone 1b and keeps the display coupled to parser correctness. See [architecture 1](analysis/02-architecture-and-organization.md). |
| D4 | Default version when none is pinned? | **Ask on first run** between stable and rolling. | Needs a flag and an environment variable so CI and scripts never hit the prompt. |
| D5 | Scope beyond TLC? | **Dedicated `sany`, `pcal` and `repl` commands now.** The analysis recommended passthrough plus a generic exec first. | The generic Java tool invocation moves up from the structure milestone to milestone 1b, since every new command depends on it. |

## Milestone 1: a runner you can trust (0.9.0)

Goal: `tlaup tlc` shows correct results for real TLC output, and no command destroys data it was not asked to.

Runner correctness

- [ ] Capture real `-tool` output from TLC 1.7.4 and the current rolling build into `tests/fixtures/tlc_output/<version>/` for: success, invariant violation with wrapped values, deadlock, liveness with back-to-state, SANY semantic error, parse error, assertion failure, coverage. Add expected parsed results. These tests should fail first. (M) [testing 9.1](analysis/04-testing.md)
- [ ] Fix error-trace parsing so real counterexamples yield states (`tlc/parser.py:195,223`). (S-M) [quality H1](analysis/03-code-quality-and-correctness.md)
- [ ] Fix SANY error grouping (`tlc/runner.py:246`, `tlc/sany.py`). (S) [quality H2](analysis/03-code-quality-and-correctness.md)
- [ ] Surface unregistered message codes instead of dropping them; add the six missing error codes including 2404. (S) [quality H6](analysis/03-code-quality-and-correctness.md)
- [ ] Print TLC text without Rich markup interpretation (`cmd/tlc.py:175`). (S) [quality H7](analysis/03-code-quality-and-correctness.md)
- [ ] Fix function-valued variable parsing. (S-M) [quality M11](analysis/03-code-quality-and-correctness.md)

Reaching TLC

- [ ] Pass everything after `--` to TLC; add `--workers` defaulting to `auto`. (S) [ux 10.2](analysis/06-cli-ux-and-docs.md)
- [ ] Make `--show-command` print the exact, shell-quoted command that would run, without touching the run cache. (S) [architecture 2](analysis/02-architecture-and-organization.md)

Safety

- [ ] Reject module names containing path separators or `..` in `modules remove` and `modules add`. (S) [quality M10](analysis/03-code-quality-and-correctness.md)
- [ ] Fix `tools uninstall --all` (`cmd/tools/uninstall.py:95`). (S) [quality H3](analysis/03-code-quality-and-correctness.md)
- [ ] Download to a temporary file, check it is a valid jar, then rename; never report a truncated jar as installed. (S-M) [quality H4](analysis/03-code-quality-and-correctness.md)
- [ ] Stop run-cache cleanup from deleting other specs' directories (`tlc/run_cache.py:29-40`). (S) [quality H5](analysis/03-code-quality-and-correctness.md)

First-run failures

- [ ] One preflight for Java and jar; no tracebacks for missing Java, missing jar with `--raw` or `--show-command`, or a broken config. (S) [ux 10.1](analysis/06-cli-ux-and-docs.md)
- [ ] Forward SIGTERM to the JVM; exit 130 on Ctrl-C. (S) [quality M3](analysis/03-code-quality-and-correctness.md)
- [ ] When nothing is pinned, ask once between stable and rolling (decision D4); a flag and an environment variable answer it without a prompt; error with a hint when stdin is not a terminal. (S-M)

Exit criteria: golden-file tests pass for both TLC versions; a spec with a violated invariant shows its full trace; `tlaup tlc Spec -- -workers 4 -deadlock` runs; no listed failure path prints a traceback.

## Milestone 1b: other tools, live display, new name (0.10.0)

Goal: carry out decisions D1, D3 and D5 on top of a correct runner. Do not start the display work before the golden-file tests from milestone 1 pass, since the display renders what the parser produces.

Shared groundwork

- [ ] A single TLC invocation object built once per run and shared by show-command, raw and formatted paths. (M) [architecture 2](analysis/02-architecture-and-organization.md)
- [ ] Extract a generic Java tool invocation (jar, classpath, JVM options, main class, arguments) that TLC and every other tool use. (M) [architecture 7](analysis/02-architecture-and-organization.md)

Other tools (decision D5)

- [ ] `sany` command: parse a spec and report diagnostics with file, line and column. Reuses the fixed SANY parser. (S-M)
- [ ] `pcal` command: run the PlusCal translator; passthrough for its flags. (S-M)
- [ ] `repl` command: interactive, so no output parsing; terminal passed straight through. (S)
- [ ] Golden-file tests for SANY and PlusCal output per TLC version; passthrough after `--` for each. (M)

Live display (decision D3)

- [ ] Remove the duplicated `tlaup tlc` callback and decide on one render path (`cmd/tlc.py:157-238`). (S-M) [architecture 1](analysis/02-architecture-and-organization.md)
- [ ] Render the existing layout on a terminal; fall back to plain streamed output when stdout is not a terminal or `--raw` is given. (M)
- [ ] Make `--refresh-interval` and the matching config key take effect. (S) [ux 10.7](analysis/06-cli-ux-and-docs.md)
- [ ] Fix the per-line re-rendering cost. (S-M) [quality M14](analysis/03-code-quality-and-correctness.md)
- [ ] Snapshot tests through a fixed-width, colourless console with an injected clock, replacing assertions on Rich internals. (M) [testing 9.8](analysis/04-testing.md)

New name (decision D1)

- [x] Choose the command name: `tlaup`. On 2026-11-10 the name was unused on PyPI, crates.io, npm and Homebrew.
- [x] Ship the `tlaup` entry point; update README, help text and examples. Done 2026-11-14 in 0.8.2: package, command and import package renamed, new repository, no `tla` alias, flake removed rather than updated (walkthrough notes 8 and 30).

Exit criteria: `sany`, `pcal` and `repl` run against the pinned jar; a long TLC run shows a live status on a terminal and clean line output when piped; `tlaup` works (done in 0.8.2).

## Milestone 2: a feedback loop that catches this (0.9.x, alongside milestone 1)

Goal: a broken parser or a broken release is caught before a tag exists.

Tests

- [ ] Autouse fixture that points home, config and cache directories at a temporary path; remove the no-op `mock_load_config`; unit suite passes on a machine with nothing installed. (S-M) [testing 9.2](analysis/04-testing.md)
- [ ] Block real network and unmocked subprocess calls in unit tests. (S) [testing 9.5](analysis/04-testing.md)
- [ ] End-to-end tests of `tlaup tlc` using a fake `java` that replays golden files, covering exit codes, raw mode and Ctrl-C. Target: `cmd/tlc.py` above 80 percent from 45. (M) [testing 9.4](analysis/04-testing.md)
- [ ] Mark integration tests and fix their dead skip guards. (S) [testing 9.3](analysis/04-testing.md)

CI and release

- [ ] Move to trunk plus tags (decision D2): merge or confirm `dev` equals `main`, remove the `dev` branch and worktree, run the test workflow on every push and pull request, protect `v*` tags (tag ruleset in place since 2026-11-14). (S) [packaging 10.1](analysis/05-packaging-ci-release.md)
- [ ] Integration job with a matrix over Java 11, 17, 21, 25 and pinned TLC builds; cache the jar. (M) [packaging 10.10](analysis/05-packaging-ci-release.md)
- [ ] Python 3.11 and newest, plus one macOS job. (M) [packaging 10.11](analysis/05-packaging-ci-release.md)
- [ ] Harden `scripts/release.sh`: require `main`, clean tree, green CI, annotated tag, atomic push. (S-M) [packaging 10.2](analysis/05-packaging-ci-release.md)
- [ ] Restructure `release.yml`: build and test, then publish to PyPI, then create the GitHub Release; fail if the tag does not match `pyproject.toml`; attach only wheel and sdist. (M) [packaging 10.9](analysis/05-packaging-ci-release.md)
- [ ] Enforce `ruff format --check`; add Dependabot; `uv sync --locked`; read-only workflow permissions. Since 2026-11-14: Dependabot alerts and security updates on, read-only workflow permissions confirmed. (S) [packaging 10.6](analysis/05-packaging-ci-release.md)

Nix

- [x] Nix flake removed in 0.8.2 (2026-11-14) instead of fixed (walkthrough note 30). The `rich<14` cap stays a separate item. [packaging 10.4](analysis/05-packaging-ci-release.md)

Exit criteria: a clean checkout passes unit tests with no jar installed and no writes outside temporary directories; a pull request that breaks trace parsing fails CI; a release cannot be tagged from a red commit.

## Milestone 3: reproducibility, the actual promise (1.0 candidate)

Goal: a repository can declare its TLA+ toolchain and get the same bytes everywhere. Write a short design note before starting; this milestone has the most open questions.

- [ ] Version identity as a type, not a parsed directory name; one place composes and parses it. Prerequisite for the rest. (M) [architecture 4](analysis/02-architecture-and-organization.md)
- [ ] Record SHA-256 for every installed jar; verify against the `digest` field the GitHub releases API now returns. (M) [merit 6.4.1](analysis/01-merit-and-landscape.md)
- [ ] Project file discovered by walking up from the spec, holding the pinned build and its digest; `tlaup tools install --locked` fails loudly on mismatch; `tools pin --local`; environment and flag overrides. (M-L) [ux 10.12](analysis/06-cli-ux-and-docs.md)
- [ ] Adopt upstream's `rolling` release and immutable CalVer tags for naming builds. (M) [merit](analysis/01-merit-and-landscape.md)
- [ ] Decide how to re-fetch an older rolling build. Options, cheapest first: timestamped Maven snapshots if retention allows (unverified), a small mirror repository that republishes each rolling jar as an immutable release, or build from source at the CalVer tag. (L, needs investigation) [merit 6.4.2](analysis/01-merit-and-landscape.md)
- [ ] Per-project override modules and community-modules version in the same file; only declared modules go on the classpath. (M) [merit 6.4.6](analysis/01-merit-and-landscape.md)
- [ ] Move the pin and registered modules out of the cache directory, with migration. (M) [ux 10.18](analysis/06-cli-ux-and-docs.md)
- [ ] GitHub token support and a clear rate-limit message. (S) [quality M8](analysis/03-code-quality-and-correctness.md)

Exit criteria: clone a repository with a lock file on a fresh machine, run one install command, and get a jar whose digest matches; a mismatched jar is refused.

## Milestone 4: automation surface

Goal: CI pipelines, editors and coding agents can consume results without scraping.

- [ ] `--json` for `tlaup tlc` serialising the parsed result (status, exit code meaning, errors, traces, SANY diagnostics, statistics, coverage), plus `tools list`, `modules list`, `tools path`. Publish a schema. (M) [ux 10.11](analysis/06-cli-ux-and-docs.md)
- [ ] Results on stdout, diagnostics on stderr; `--quiet`, `--verbose`, `--color`; honour `NO_COLOR`. (M) [ux 10.14](analysis/06-cli-ux-and-docs.md)
- [ ] Non-interactive version selection: accept `tag@sha` everywhere, error instead of prompting when stdin is not a terminal, `--yes` covers every prompt. (S) [ux 10.4](analysis/06-cli-ux-and-docs.md)
- [ ] Documented exit codes. (S) [ux 10.5](analysis/06-cli-ux-and-docs.md)
- [ ] `tools list` shows rolling versus tagged and "update available"; `--installed` works offline. (S-M) [ux 10.6](analysis/06-cli-ux-and-docs.md)
- [ ] A generic exec command and jar-path output so scripts can use the managed jar without the formatter. (S) [merit 6.4.3](analysis/01-merit-and-landscape.md)
- [ ] A GitHub Action that restores the locked toolchain and runs TLC. (L) [packaging 10.23](analysis/05-packaging-ci-release.md)

## Milestone 5: structure

Do these when the behaviour above is pinned down by tests, not before. Some will fall out of earlier milestones naturally.

- [ ] One application-level registry for paths and config, passed in rather than imported per site. (M) [architecture 3](analysis/02-architecture-and-organization.md)
- [ ] Move the module build pipeline out of `cmd/modules/add.py` into domain code. (S-M) [architecture 5](analysis/02-architecture-and-organization.md)
- [ ] TLATeX and any further jar tools as thin additions on the generic invocation from milestone 1b. (S)
- [ ] Reorganise tests to mirror the source tree. (S-M) [testing 9.9](analysis/04-testing.md)

## Documentation track (parallel, start with milestone 1)

- [ ] README rewrite: prerequisites, five-line quick start with expected output, full command table, config location, exit codes. Currently covers about a third of the commands. (S) [ux 10.3](analysis/06-cli-ux-and-docs.md)
- [ ] Concepts page explaining the rolling-release problem and what this tool does about it. (S-M)
- [ ] Run guide for `docs/examples`, plus one pure TLA+ example with a violated invariant. (S)
- [ ] Changelog: add an Unreleased section, mark 0.4.0 and 0.8.0 as not published, correct the 0.3.1 entries. (S)
- [ ] Configuration reference, troubleshooting, contributing guide. (M)

## Deliberately not planned

- Standalone binaries: Java is required anyway.
- SBOM generation and heavier release tooling: disproportionate for one maintainer.
- An MCP server: four already exist; a clean JSON interface is the less crowded position.
- Apalache and TLAPS: they are separate distributions, not classes in the jar, and need a distribution dimension in the version store first.
- Homebrew, Docker, nixpkgs and conda-forge channels until milestone 3 ships.

## Risks to the plan

- **Upstream ships an official `tla` command.** Mitigated by D1 and by focusing on what an upstream wrapper will not do: locking, digests, override modules. The dedicated `sany`, `pcal` and `repl` commands from D5 are the part most likely to be duplicated by it.
- **Milestone 1b delays reproducibility.** Finishing the display and adding three commands sits between the runner fixes and the lockfile. If time is short, milestone 3 can run before 1b; only the two groundwork items are shared.
- **The live display raises parser maintenance.** Every TLC output change now affects a second surface; the golden files and snapshot tests are what keep that affordable.
- **Upstream attaches jars to CalVer tags.** That would remove the need for a mirror and simplify milestone 3; worth asking upstream before building one.
- **Golden files reveal more parser breakage than the two known cases.** The reviews tested one spec per TLC version, so milestone 1 may grow.
- **Maven snapshot retention is unverified.** The cheapest re-fetch option may not exist.
