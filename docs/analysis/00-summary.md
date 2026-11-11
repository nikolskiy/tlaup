# Project analysis: summary

Date: 2026-11-09. Analysed at commit `bac6ba1` (release 0.8.1). Exploration only; no code was changed.

Six independent reviews were run, one per area. Each report stands alone:

1. [Merit and landscape](01-merit-and-landscape.md)
2. [Architecture and organization](02-architecture-and-organization.md)
3. [Code quality and correctness](03-code-quality-and-correctness.md)
4. [Testing](04-testing.md)
5. [Packaging, CI and release](05-packaging-ci-release.md)
6. [CLI UX and documentation](06-cli-ux-and-docs.md)

## Verdict on merit

Not a reinvented wheel, but it only half-solves the problem it was built for.

- The upstream pain is real: `tlaplus/tlaplus` force-moves the `v1.8.0` tag and re-uploads `tla2tools.jar` on every master build; the last stable release is 1.7.4.
- No other tool compiles and caches Java operator-override modules. That is the one unique feature.
- The version manager fixes the problem locally only. The pin is global, there is no project lockfile, no checksum, and an older rolling build cannot be fetched again, so a laptop and CI can still run different jars.
- Upstream is moving: a `rolling` release, immutable CalVer tags per build, and SHA-256 digests in the releases API now exist and the tool uses none of them. An open upstream PR proposes an official `tla` command.
- The TLC runner is the weakest part and currently a reason not to use the tool (see below).

## Cross-cutting findings

Findings reported by more than one review, or confirmed by reading the source afterwards.

| Finding | Evidence | Status |
| --- | --- | --- |
| Real counterexample traces parse to zero states; tests use an invented format | `tlc/parser.py:195,223` | Reproduced independently by two reviews; regex confirmed by reading |
| No way to pass TLC flags (`-workers`, `-deadlock`, `-simulate`) | `cmd/tlc.py:70-92` | Confirmed by reading |
| `tools uninstall --all` stops after the first pinned removal | `cmd/tools/uninstall.py:95` (`any()` over side effects) | Confirmed by reading |
| `modules remove` accepts `..` and can delete sibling directories | `cmd/modules/remove.py:11` | Confirmed by reading |
| Downloads have no checksum and are not atomic | `versioning/downloader.py` | Code reading by reviewer |
| Missing Java or missing jar produces a traceback on some paths | `cmd/tlc.py:123-134,287` | Reported by three reviews |
| Unit tests write to the real config and cache directories; three fail on a clean machine | `tests/conftest.py:49-52` | Observed by reviewer |
| CI does not run on `dev` and never runs integration tests | `.github/workflows/test.yml`, `pyproject.toml` | Reviewer; three tagged versions never reached PyPI |
| Nix flake is stale and does not build | `flake.nix:29` (version 0.6.0), `pyproject.toml:18` (`rich<14`) | Version and cap confirmed; build failure observed by reviewer |
| Live display code is dead and `tla tlc` callback is duplicated | `cmd/tlc.py:157-238` | Reported by two reviews |

## Suggested order of work

The detailed, itemised version is in the [roadmap](../roadmap.md).

1. **Make the runner trustworthy.** Golden-file parser tests from real TLC output for each supported version, fix trace and SANY parsing, stop dropping unknown error codes, escape Rich markup, add `--` passthrough.
2. **Close the safety gaps.** Validate module names, atomic downloads with digest checks, fix `uninstall --all`, catch the traceback paths.
3. **Fix the feedback loop.** Run CI on `dev` or move to trunk plus tags, isolate tests from the real home directory, add an integration job, harden `release.sh`, repair the flake.
4. **Finish the core idea.** Project-level lockfile with jar digest, built on upstream's new immutable tags and digests; per-project module overrides.
5. **Then structure and polish.** A single TLC invocation object, one path/config registry, a proper version identity type, JSON output, README rewrite, and a decision on the `tla` binary name given the collisions.

## Not verified

- GitHub repository settings (branch protection, environment rules); `gh` was not authenticated.
- Several alternatives in the landscape survey (nightly site, Maven snapshots, jbang, Docker images) could not be reached or searched.
- No fix was attempted, so every recommendation is untested.
