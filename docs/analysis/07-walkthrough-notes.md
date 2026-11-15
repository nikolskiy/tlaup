# Walkthrough notes and decisions

Recorded 2026-11-10 to 2026-11-14 during a spoken walkthrough of the analysis commit (`b922ab5`: summary, roadmap, reports 01-06). These are the maintainer's notes and decisions. Nothing here has been applied to the roadmap or the code yet.

Each note says where it came up. "Decided" means the maintainer agreed explicitly; "Raised, not decided" at the end lists points that came up but were not settled, for the completeness pass to clarify.

## 0. First steps

1. **Done 2026-11-14.** **Install `gh` and log in before anything else.** Several items depend on it (release script CI check, repository settings). (Roadmap, milestone 2, branch model)
2. **After `gh` works, verify everything the reports could not check**: branch and tag protection or rulesets, `pypi` environment protection rules, default `GITHUB_TOKEN` permissions, secret scanning and push protection, Dependabot alerts, which Python CI actually uses, causes of the failed release runs (v0.3.0, v0.4.0, Test on `6681e42`). (Packaging report, sections 4.7, 8, 11) Done 2026-11-14; results below.

### Verified with `gh` on 2026-11-14

Read-only checks against the old `nikolskiy/tlaplus-cli` repository; no setting was changed there.

| Item | Finding |
| --- | --- |
| Branch protection on `main` | None ("Branch not protected"). |
| Rulesets (branches and tags) | None. Version tags can be moved or deleted. |
| `pypi` environment | Exists, but no protection rules, no deployment branch or tag policy, and admins can bypass. Any ref can deploy to it. |
| Default workflow token permissions | Read-only, and workflows cannot approve pull requests. Good. |
| Allowed actions | All actions allowed; SHA pinning not required. |
| Secret scanning | Enabled, with push protection enabled. No alerts. Non-provider patterns and validity checks disabled. |
| Dependabot alerts | Disabled. |
| Dependabot security updates | Disabled. |
| Private vulnerability reporting | Disabled. Relevant to the suggested two-line `SECURITY.md`, which would point to it. |
| Code scanning | No analysis configured. |
| Which Python CI uses | Not determinable: GitHub returns HTTP 410 for all run logs, including the latest run (2026-08-13); log retention has expired. Still inferred as 3.13 via `uv` and `.python-version`. |
| Causes of failed runs | Logs expired, and step data is gone for older runs. What remains: v0.8.0 failed at "Run tests" (publish skipped). v0.2.0, v0.3.0 and v0.4.0 failed in `build-release` (publish skipped), step unknown. v0.1.3 to v0.1.6 built successfully and failed in `pypi-publish`, which confirms the orphaned GitHub Releases. Test also failed on `main` at `73b0199`, `770c0b7`, `5213351`, `6681e42`, `029faa9` and `bfaffdf`. |

Consequences for the roadmap: the Dependabot note (32) needs alerts switched on as well as security updates; the tag ruleset and the `pypi` environment policy (deploy only from `v*` tags, optional required reviewer) are not in place yet; private vulnerability reporting needs enabling if `SECURITY.md` is added. A future failure diagnosis will need logs captured before the retention window closes.

### This repository's settings, set 2026-11-14

Created as `nikolskiy/tlaup` (note 8) with these settings from the start:

| Item | Setting |
| --- | --- |
| `main` | Ruleset: no deletion, no force push. No required pull requests or checks yet. |
| `v*` tags | Ruleset: no deletion, no moving. No bypass, not even for admins. |
| `pypi` environment | Deploys only from `v*` tags. No required reviewer yet; admin bypass is on, which only matters once a reviewer is added. |
| PyPI | Trusted publisher for `tlaup`: this repository, `release.yml`, environment `pypi`. |
| Dependabot | Alerts and security updates on. |
| Private vulnerability reporting | On. |
| Secret scanning | On, with push protection. |
| Workflow token | Read-only default, cannot approve pull requests. |

History was pushed with author and committer emails, and the author email in `pyproject.toml`, rewritten to the GitHub noreply address, because GitHub blocks pushes that expose a private email. Every commit id therefore differs from the old repository.

## 1. How the work is done

3. **Ship everything as one release instead of staged milestone versions.** Few users, so a big change from 0.8 to 0.9 is fine. Still land the CI and test fixes from milestone 2 early, even without publishing. Milestone 3 needs its design note first and is the most likely to hold the batch up. (Roadmap, milestone 1b)
4. **Agent pipeline** (four stages decided during the walkthrough; revised 2026-11-14 to five stages with review gates, design in waves and one source of truth):
   1. **Completeness pass.** One agent reads all six reports, the roadmap and these notes, and makes sure everything is on the roadmap. Obvious decisions go straight in; uncertain ones are clarified by the maintainer. This pass also picks up small items not settled one by one (error message wording, help text, smaller defects) and the "Raised, not decided" list at the end of these notes. Any factual question it finds that needs checking before a decision or a design (upstream behaviour, real tool output, what an API returns) is added to the stage 2 list below instead of being guessed. When it is done, the roadmap is the single authoritative document and these notes are frozen as history: later stages read the roadmap, not the notes.
   2. **Investigation.** Small spikes that answer the factual questions the design depends on, before anything is designed on assumptions. No product code is written. Each answer records its evidence (links, commands run, captured output) in the roadmap item it serves, and says plainly when a question could not be answered. Contacting upstream (an issue, a discussion post) is the maintainer's call; the spike only searches what already exists. Questions collected from these notes, the roadmap and the reports; the completeness pass adds any new ones it finds:
      - Real TLC output for each supported version (success, violation, deadlock, liveness, SANY and parse errors, assertion failure, coverage), captured as golden-file fixtures. First item of milestone 1.
      - Whether TLC can write traces as JSON itself (`-dumpTrace json`), which would avoid value parsing for traces. (Note 13)
      - How to tell which jar build is running, and the state of upstream's official command (open PR 1371) and its entry point, for the hand-off. (Notes 15 and 20)
      - Whether upstream TLC builds fire the CommunityModules `repository_dispatch` trigger, which would tighten matching module releases to TLC builds by date. (Note 16, raised list)
      - Whether upstream attaches, or plans to attach, a jar to each CalVer tag; search existing issues and discussions. (Note 21, roadmap risks)
      - Building `tla2tools.jar` from source at a CalVer tag: build tool, required Java version, time taken, network access needed, and whether the result matches the published jar byte for byte. (Note 21)
      - The tag and asset race on rolling builds: whether the jar can change while a download or a version lookup is in progress. (Merit 3.3, reasoned from code, not reproduced)
      - GitHub tags and releases API ordering and pagination, which "latest stable" currently depends on. (Quality M7)
      - Current state of `nightly.tlapl.us`, and whether a setup GitHub Action, a jbang alias or a mise plugin for TLA+ tools already exists, before building the GitHub Action in milestone 4. (Merit, not verified)
      - The tlaplus/Examples manifest format: outcome vocabulary and state counts, as input to the JSON schema. (Note 41; milestone 4, so it can wait for the second design wave)
      - Sources for download numbers: pypistats or the BigQuery dataset, GitHub release asset counts, repository traffic. Input for the usage statistics session. (Note 6)

      Behaviour on macOS and Windows (quality M15 and M16, packaging "OS Independent") is not a spike: the CI matrix in milestone 2 answers it.
   3. **Design, in waves.** An agent designs or confirms solutions for each roadmap item, in light of all decisions and the investigation results. This replaces the earlier "planning review" note and covers every fix proposed during the walkthrough that goes beyond the reports. The testing approach (note 5) is designed first, since every work package writes tests. The first wave designs milestones 1, 1b and 2 in full and only sketches milestones 3 to 5; those are designed in a later wave, after the first wave is built, because building it will change what the lockfile and structure work needs. Milestone 3 still needs its design note (note 3).
   4. **Work packages.** An agent cuts the designed work into packages without implementing: each states its goal, the files it touches, its dependencies on other packages, the tests that must pass, and all the context a worker needs, so a worker never has to read the analysis.
   5. **Workers.** Separate agents build one package each, in its own worktree, ending in a pull request. If a worker finds the design wrong or incomplete, it stops and reports instead of improvising; the fix goes into the design and the package before work continues.

   Review gates: after stages 1, 3 and 4, a fresh agent that did not produce the output reviews it against its inputs (for stage 1, the reports against the roadmap; for stage 3, the decisions against the design), and the maintainer signs off before the next stage starts. Each stage 5 pull request needs green CI and a review by a separate agent before it merges.

   Models (suggested): the most capable model at high effort for stages 1, 3 and 4, since their output steers everything after them and their token volume is small. Stage 2 does not need the most capable model: its questions are narrow and factual (fetch, read, run, record), and the recorded evidence lets stage 3 check any answer that looks doubtful, so a mid-tier model, with several spikes in parallel, gives the same result for less. Workers can use a mid-tier model for clearly specified packages and the most capable model for the hard ones, such as the TLC output parser and the lockfile. Mechanical lookups inside a stage, such as checking that a line reference still points at the right code, can go to a cheaper subagent.
   (UX report, error messages)
5. **Redesign the testing approach from scratch.** Decide where tests give most value, whether the existing unit tests are worth keeping and in what form, and how tests are written from now on. (Testing report, summary)
   - Check whether one approach can cover the whole program (preferred); if not, choose an approach per part. The report's per-part techniques are input: golden TLC output for the parser, property-based tests for the value parser, snapshots for rendering, recorded GitHub responses for downloads, a fake `java` replaying recordings for end-to-end runs, a Java and TLC matrix for integration.
   - Lean on documentation tests and example tests rather than many small unit tests.
   - Consider human-readable scenarios (behave or pytest-bdd, Gherkin "given / when / then") for CLI behaviour. Cost: step definitions to maintain; less suited to parser internals.
   - Anti-patterns to avoid, all from the testing report: patches that never take effect (import-by-name, the no-op `mock_load_config`, wrong patch targets in module tests); over-mocking until only a list index is under test; invented TLC output; assertions on Rich internals and help-text wording; checking messages instead of resulting state; wall-clock and mtime dependence; tautological tests; shared state leaking between tests (direct `os.environ` edits, `lru_cache` config, mutually exclusive `shutil.which` fixtures, module-level runners); real `java` and `git` launched by unit tests with unchecked results; tests writing to and deleting from the real config and cache; duplicated tests and three copies of GitHub fixtures; integration tests with broken skip guards, Linux-only jar discovery and no assertions on parsed results; no markers, no branch coverage, no threshold.
   - Coverage policy from the report: branch coverage on, a `fail_under` near the current 83 percent, coverage only in the full-suite task, randomised order, warnings as errors.
6. **Thinking session on usage statistics**, carefully and without sending data from users' machines without consent. (UX report, command layout; docs site)
   - A script that collects download numbers: PyPI (pypistats or the public BigQuery dataset; PyPI's own API no longer gives counts), GitHub release asset download counts, and GitHub repository traffic (views and clones, kept only 14 days, so save regularly).
   - Later, a docs site as an indirect signal: visits and returning visitors to specific pages, compared with installs, using a cookie-less counter (GoatCounter, Plausible).

## 2. Roadmap rewording

7. **Guiding principle**: broaden it. The tool brings the TLA+ tools together and helps them work together: version management including rolling builds, managing your own modules (add, list, remove), running TLC and the other tools. Reproducibility and rolling builds are important but not the only thing. (Roadmap, documentation track)
8. **Decision D1**: package and binary are both `tlaup`, so it is clear what is where. Status 2026-11-14: steps 1 to 5 below are done and `tlaup` 0.8.2 is on PyPI. `tlaplus-cli` 0.8.3, the forwarding release, is on PyPI and the old repository is archived; marking the PyPI project as archived is left to the maintainer. (Roadmap, milestone 1b, new name)
   - Claim `tlaup` on PyPI now, before someone else takes it. A pending publisher does not reserve the name; only the first upload does, and PyPI discourages empty placeholders, so the claim is a small real release. (Name still free on PyPI and TestPyPI on 2026-11-14.)
   - Move to a new GitHub repository, `tlaup`, instead of renaming the old one (decided 2026-11-14; replaces the earlier thin-wrapper idea). Order:
     1. Done. Create the new repository and set its minimal settings first: rules on `main`, a ruleset protecting `v*` tags, the `pypi` environment limited to `v*` tags, Dependabot alerts and security updates, private vulnerability reporting, secret scanning with push protection.
     2. Done. Add a pending trusted publisher for `tlaup` on PyPI pointing at the new repository, workflow `release.yml`, environment `pypi` (maintainer, in the PyPI web interface).
     3. Done, with emails rewritten (see the settings table under note 2). Push the existing history into the new repository (not a fresh copy), so commits, tags and the changelog carry over. Stars, open issues and GitHub's rename redirect are lost; acceptable with few users.
     4. Done: 0.8.2 released 2026-11-14, after refreshing the lock file (note 32). First `tlaup` release: today's code with only the name changed, continuing the numbering (0.8.2), so 0.9 stays the big release.
     5. All roadmap work then happens in the new repository. The analysis and these notes moved here too; the old repository's `dev` branch was not pushed.
   - Own folders (decided 2026-11-14, after 0.8.2): `tlaup` stores toolsets, modules, run cache and config under `tlaup` folders instead of the old `tla` ones, a clean break with no migration and no fallback, so no legacy name is carried and nothing collides with other tools using `tla`. Few users are affected; the changelog and README tell them to reinstall and delete the old folders. 0.8.2 still uses the `tla` folders.
   - Done 2026-11-14 except the PyPI archive flag. Retire `tlaplus-cli` with one final maintenance release from the old repository, then archive that repository:
     - the package depends on `tlaup`, so upgrading moves users over without action;
     - the old command prints a one-line notice (now called `tlaup`, install that instead) and then runs the same command through `tlaup`, so existing scripts keep working (decided 2026-11-14; a `uv tool` install does not expose a dependency's own command);
     - the PyPI description says the same in its first line, and the status classifier becomes `Development Status :: 7 - Inactive`;
     - after publishing, mark the project as archived on PyPI. Do not yank old versions (it breaks pinned installs and helps no one).
   - Done in 0.8.2. Drop the `tla` command right away, with no deprecated alias. Document the change in the changelog and on the GitHub release page.
9. **Decision D3**: the live display is a reporter built on the separate parser package (see note 12). It is one of several reporters: a live terminal one, one for AI, maybe others later such as writing to a file. Its consequence column should stop describing the display as coupled to parser correctness. (Merit report, what to drop)
10. **The VS Code extension is an inspiration, not a parity target.** It was the example of nicer TLC output; the tool can go beyond it, and missing some of its features is fine. (Roadmap, milestone 1)
11. **Risks section**:
    - Risk 1, upstream ships an official `tla`: add how the tool would hand off to it (see note 20).
    - Risk 2, 1b delaying reproducibility: matters less with a single release.
    - Risk 4: reword around building from source; if upstream attaches jars to its CalVer tags, building from source can be skipped.
    - Risk 6, Maven snapshot retention: remove (Maven is dropped, note 21).

## 3. Architecture and design

12. **Parser as its own package.** An ordinary dependency, not something fetched per TLC version at runtime. One parser release handles several TLC versions by reading the version TLC prints at startup. Golden files live in the parser package, filed by TLC version. Start as a separate package in the same repository; move it to its own repository later if editors or other tools use it. (Roadmap, risk 5)
13. **Parser rule: never lose output.** Anything it does not recognise is shown exactly as TLC printed it. Also check whether TLC can write traces as JSON itself (`-dumpTrace json`, unverified), which would avoid value parsing for traces. (Roadmap, risk 5)
14. **Reporters.** TLC output goes through reporters that read the parsed result and run events. Terminal and JSON first; an AI-facing reporter later as a plug-in; possibly file or others. Reporters never parse; the result carries everything any reporter needs, such as file and line for errors. (Merit report, AI tools)
15. **Thin tool commands (milestone 1b design guideline).** Keep `sany`, `pcal` and `repl` thin, with no logic beyond reading their output. Launch everything through the shared Java launcher. Check which jar build is running, so the tool can switch to upstream's own entry point when it exists and fall back for older jars. (Roadmap, risk 1)
16. **Community modules as pinned release downloads.** Download the published release jars, not compiled from a checkout. The tool picks the release built against the user's TLC build by date (published after that TLC build and before the next one), and writes that choice into the project file; after that everyone reads the file. On a TLC upgrade the tool picks again and updates the file. `modules add` stays for the user's own modules. Background checked during the walkthrough: CommunityModules releases have empty notes, their build compiles against whatever the `rolling` jar is at that moment, releases happen on every push to their main branch, and the workflow has a `repository_dispatch` trigger (possibly fired by upstream TLC builds; not confirmed). (Merit report, conclusions)
17. **Config layering** goes on the roadmap: packaged defaults, then the user file, then the project file, then environment variables, then flags. Config commands keep working when the file is broken. No config file is written until the user actually changes a setting. (Architecture report, config)
18. **Apalache and TLAPS** move from "not planned" to "after this roadmap". Leave room for other distributions in the storage layout during milestone 3, since the on-disk layout is the expensive part to change. The examples runner skips models that need unsupported tools and reports them as skipped, not failed. (Roadmap, not planned)
19. **After this roadmap**: Homebrew tap, aimed at macOS users who have Java but do not use Python. (Packaging report, channels)
20. **Hand-off to an official upstream command**: the tool supplies jar, classpath, lock and modules; upstream's entry point can run on top of it (see note 15). (Roadmap, risk 1)
21. **Milestone 3, fetching old rolling builds**: drop the mirror option (it was never the plan) and drop Maven (unclear retention, and the Maven jar is stripped of bundled dependencies, so not the same bytes). Single fallback: build from source at the CalVer tag when an old build cannot be downloaded, with the needed Java build tools fetched automatically. Remove that logic if upstream starts publishing a jar per tag. Use the official sources and the local cache only. (Roadmap, risks 4 and 6)
22. **Drop installs from a file address (URL installs)** for now; maybe reintroduce later. Removes the colon timestamps, the upgrade mis-split, `meta sync` overwriting URL installs and the plain-HTTP path. Existing URL-installed builds on disk are left alone but not listed or pinned, with a message saying why. (UX report, versions)

## 4. Additions to milestones

### Milestone 1

23. Problems to fix, not previously on the roadmap (code quality report):
    - Every `OSError` during a run is reported as "'java' not found" (for example `BrokenPipeError` when piping `--raw` into `head`). (M2)
    - The violated-invariant text is hidden when a trace exists; currently masked by the trace parsing bug. (M12)
    - A `--cfg` file outside the project root is passed to TLC by name only, so TLC can read a different file. (M13)
    - Only the first page of tags and releases is read; "latest stable" depends on API order; with only prereleases it silently installs one while saying "stable". (M7)
    - The project-root heuristic counts a parent with `lib/`, `modules/` or `classes/`, so a spec under `~/work` with `~/lib` pulls unrelated jars onto the classpath. (M17)
    - `config edit` rejects `$EDITOR` values with arguments (such as `code --wait`), has no Windows default, and does not re-validate after editing. (M18)
24. Safety section additions (code quality report, low findings):
    - Concurrent installs collide: pin and metadata writes are not atomic and there is no locking. (L10)
    - A failed uninstall exits 0 and still moves the pin; the disambiguation prompt accepts negative indexes. (L12)
    - Spec names with dots are mangled by `with_suffix`; any existing file, such as a `.cfg`, is accepted as the spec. (L14)
25. Problem descriptions only, solutions to come from the design stage (pipeline stage 3, note 4):
    - The run-cache fingerprint covers the default `.cfg` only, not a `--cfg` file or extended modules. (L15)
    - The module build strips `//` comments with a regex that corrupts string literals; `javac` runs with no `-encoding` and no timeout. (L17)
    - Unknown config keys are silently ignored, so typos have no effect and no warning. (L8)
26. Downloads: refuse unencrypted addresses and any redirect to an unencrypted address. After download, compare the commit the jar reports about itself (`-version` banner revision) with the expected commit. (M9, M6)
27. First-run section:
    - Print nothing (no "Starting TLC") until the checks pass.
    - Remove the legacy fallback jar path so it is never shown as the expected location.
    - Disable Typer's decorated crash reports for users; add a `--debug` option that shows the full traceback.
    - One first-run prompt that asks stable or rolling and then installs it (merges D4 with the auto-install offer).
28. Java handling (code quality L5, L6, L7; UX report):
    - A Java options variable named for the tool (`TLAUP_` prefix) and a repeatable flag, both adding to the configured options instead of replacing them.
    - Use the standard `JAVA_HOME` when set, falling back to `PATH`.
    - One Java start per run: read the TLC version from saved metadata instead of launching Java, remember the Java version check. Report a timeout as a timeout, not "not installed".
29. Startup cost item: skip the `git rev-parse` call on normal installs, load heavy libraries only in the commands that need them, one Java start per run. (Packaging 2.1, quality L20)

### Milestone 2

30. **Done 2026-11-14 in 0.8.2.** Remove the Nix flake: it was a one-off and never kept up to date. Replace the roadmap's Nix item and remove the Nix install line from the README. (Summary; milestone 2)
31. Branch model and CI:
    - CI runs on every push to `main` and on pull requests; the integration job runs on every push too.
    - Integration matrix trimmed to Java 11 and 25 (oldest and newest), against both pinned TLC builds; widen later if other versions need support. GitHub-hosted runners, macOS included (free for public repositories).
32. Dependencies:
    - Dependabot security alerts and security updates on. Done 2026-11-14 in this repository.
    - A monthly Dependabot run that groups all version updates into one pull request, instead of one per release.
    - Refresh the lock file before each release and let CI run before tagging. Done for 0.8.2; it cleared all 44 alerts and needed two small fixes (Typer 0.29's test runner has no `isolated_filesystem`; ruff 0.17's new PLR0917 rule).
    - Keep `uv sync --locked` and read-only workflow permissions (confirmed).
33. Build fixes as their own items: `setuptools>=77.0.3`, a real Pydantic minimum, remove the `rich<14` cap (kept even though the flake goes), delete the redundant `MANIFEST.in`, and one CI check that installs the newest allowed dependency versions. (Packaging 1.1, 1.2, 1.3)
34. Release workflow security: the full three-job split (read-only build, PyPI publish with id-token only, release page with write access and no project code), `persist-credentials: false` on checkout, pin by SHA or replace the actions with write access (`gh release create` instead of the third-party release action), `timeout-minutes` on every job. (Packaging 4.5) The 0.8.2 release page also shows why: it carries a stray `default.gitignore` asset because the release action uploads everything in `dist/`, including the `.gitignore` that `uv build` writes there.
35. Release pages:
    - Each GitHub release page gets that version's changelog section as its text.
    - Backfill existing release pages from the changelog.
    - PyPI's changelog link points at the GitHub releases page. No "what's new" section in the README.
36. Changelog and versioning process: use `uv version --bump` behind a task so `pyproject.toml` and `uv.lock` move together; the release script checks for a proper `## [X.Y.Z] - date` heading. Leave history alone except marking 0.4.0 and 0.8.0 as never published and correcting the two wrong 0.3.1 entries (cache path, `--all`). Do not move old tags. The rename is a natural fresh start. (Packaging 2.2, 2.3)
37. PyPI and GitHub metadata: keywords, missing classifiers (Console, Developers, Science/Research, a QA or scientific topic, Typing :: Typed), fix the questionable "Build Tools" topic, GitHub topics, absolute README links, pipx and uvx install options. (Packaging 1.1)
38. Windows: not officially supported and no Windows CI, but write code that should work there, and say exactly that in the README. Change the "OS Independent" classifier to Linux and macOS. (Code quality M15, M16)

### Milestone 3

39. Fix the `tools meta sync` bug explicitly (matches by tag name only, so an older rolling build gets the current build's metadata). (Code quality M5)
40. Folder names without colons for any remaining non-tag installs (largely moot once URL installs are dropped). (Code quality M16)

### Milestone 4

41. JSON output: research the tlaplus/Examples repository's manifest format before designing the schema, and aim for compatible results (outcome vocabulary, state counts). (Roadmap, milestone 4)
42. Exit codes: a separate exit code for the tool's own setup errors; move the version flag to `-V` so `-v` can mean verbose. (UX 3.4, 2.2)
43. Later idea: run the examples straight from the Examples repository's manifest. (Roadmap, milestone 4)

### Commands and rename

44. During the rename, review the layout of every command so it follows the most common CLI patterns and users can guess commands from other tools. No aliases for old command names. Starting point: the UX report's suggested tree (doctor, one cache command, config path/show/get/set, completion). (UX 2.2)
45. Fold the version-typing items into that review: accept versions without the `v`, shortcuts `latest`, `stable`, `rolling`, fix the "Tag/SHA" column label, a command that shows what is pinned. (UX 2.3)
46. Shell completion goes on the roadmap. (Packaging 7, UX 7)

### Documentation

47. README quick start shown as an animated terminal recording (asciinema or VHS, which renders a GIF that plays on GitHub and PyPI). (Roadmap, documentation track)
48. README and concepts page present the broader purpose (note 7), with rolling builds as one important part.
49. Mechanisms so docs and changelog stay right:
    - Changelog: an Unreleased section; the entry written in the same commit as the change; fixed headings including Breaking and Removed; a before and after line for every rename or removal; the release script checks the heading; CI warns when code changes without a changelog change.
    - Generate the CLI reference from the code and fail CI when the checked-in copy drifts.
    - Run the README quick start commands in CI.
    - Each example gets a short README and runs in CI with its expected result.
    - A project instructions file for AI agents (such as `CLAUDE.md`) and a contributing guide for people, holding these conventions.
50. No docs site (MkDocs) yet; reconsider later, partly as a usage signal (note 6).

### Dropped

51. Docker image: dropped; reconsider only if users of non-GitHub CI systems ask. The GitHub Action covers the main CI case.

## Raised, not decided

For the completeness pass to include or clarify:

- Error message wording fixes from the UX report section 4 (spec-not-found locations, "did you mean v1.8.0", rate-limit hint, next-step hints, contradictory install messages, javac classpath).
- Help text defects from UX section 7 (upgrade meaning, modules wording and expected layout, install defaults, jargon, `--yes` scope, inconsistent summaries).
- Missing docs pages not on the roadmap: install page, custom modules guide, CI recipe, architecture notes; troubleshooting should mention proxy and custom CA support via truststore.
- Environment overrides for the tool's home, config and cache folders.
- Editor-friendly diagnostics (`path:line:col: severity: message`), GitHub Actions annotations, JUnit output; candidates for reporters.
- Destructive confirmations: single-version uninstall does not confirm; `modules add` silently replaces a module with the same name.
- UX smaller defects: upgrade by name compares only the first of several builds; installing a newer rolling build beside an older one does not move the pin; stale legacy cache file.
- UI printing from domain code and the 21 hand-written error prints (architecture finding 6).
- Small organisation items from architecture finding 8 (tiny files, two registration styles, misnamed modules, hard-coded values that config pretends to control).
- Pre-commit: move pytest to pre-push, add a format hook, whole-project mypy; widen `poe clean`; `.gitignore` gaps; align Python versions; a two-line `SECURITY.md` (private vulnerability reporting is now on, note 2).
- Annotated or signed tags, and a required reviewer on the `pypi` environment. The environment tag policy and the tag ruleset are in place in this repository since 2026-11-14 (note 2).
- Whether CommunityModules builds are triggered by upstream TLC builds (would tighten date matching).
- An override that fails to load should be reported clearly.
