# Working in the stage 4 review, 2026-11-24

Written 2026-11-24. It records how the [stage 4 review](../packages/review-2026-11-21.md) of the work packages, the maintainer's walk-through of the faults it found in the design (2026-11-22 to 2026-11-24), and the [inventory](preserved-behaviour-2026-11-22.md) of the behaviour of 0.8.x were worked into the design documents and the roadmap. Later stages read the sections and the roadmap, not this file: everything here is also said, with its reason, where it applies. Each changed section carries a note "(Stage 4 review, 2026-11-24: ...)". The working-in was then reviewed, and that review's findings were worked in the same day (below, "After the review of the working-in").

The faults the review found in the design were gaps (the design did not say what happens), a few errors (one wrong claim about Typer's completion modules) and clerical drift, mostly plural names left from before D47. The maintainer settled every question; the ones that change what a user sees, or how the work is tested, became decisions D61 to D67 in the roadmap's decision table. The rest are readings the maintainer confirmed, or low-impact choices made by the design agents and the coordinator, under the roadmap's rule for weighing a decision ("How a decision is weighed", added the same day).

## New decisions

- **D61**, the narrow compile classpath of `module add`: [13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder), [M3](13-modules-and-java.md#m3-module-build-details), [14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay), [40](40-later-milestones.md#milestone-3-reproducibility).
- **D62**, the old tests deleted in 03b, the inventory as the list of requirements, and no in-between promise: [01 T11](01-testing.md#t11-the-existing-tests) (rewritten), T2, T10, T12, [00](00-overview.md) ("What every package must respect", order of work), [30 I2](30-ci-and-release.md#i2-unit-job), the inventory. The exception the decision allows, a CI job that runs real TLC through an old command, arises once: today's `tools install` step, which fetches a jar for the old tests and goes in 03b.
- **D63**, the exit status words: the table is in [02 X1](02-cross-cutting.md#x1-exit-codes), and [10 P2](10-parser.md#p2-the-tlaup_parse-package) holds the test over every code. A code TLC does not document has the word `error` (settled with the maintainer while this was worked in: nobody can say it was checked and found wrong).
- **D64**, `tool list` hides releases with no jar and marks `installed, not upstream`: [12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache), [40](40-later-milestones.md#milestone-4-automation-surface).
- **D65**, what tlaup promises to reproduce: [40](40-later-milestones.md#milestone-3-reproducibility) (Direction, open questions 4 and 11), and the roadmap's milestone 3 design-note item and documentation-track concepts page.
- **D66**, the SANY source excerpt in terminal output, never in JSON: [21 S1](21-other-tools.md#s1-sany) (with `source_excerpt`), [22 O2, O3, O6](22-reporters.md#o3-terminal-reporter), [40](40-later-milestones.md#milestone-4-automation-surface). Settled while this was worked in: the two lines after the location are kept, as 0.8 printed them, and 0.8's "(Source code unavailable)" note is dropped.
- **D67**, `pcal`'s added labels on stdout: [21 S2](21-other-tools.md#s2-pcal).

## Per document

**[00](00-overview.md).** The package tree gains the modules stage 4 added (`tlaup/stdio.py`, `tlaup/doctor.py`, `project/core.py`, `project/spec.py`, `java/opts.py`, `reporters/text.py`, `versioning/first_run.py`, `cmd/common.py`). The order of work deletes the old tests at once (D62), and "What every package must respect" says that `main` between packages need only be green.

**[01](01-testing.md).** T2: the integration fixture keeps `JAVA_HOME` and `PATH`; the old fixtures go in 03b. T3: research 22's captures are adopted (the older captures stay golden, a non-empty `.err` sits beside its `.out`, `tool-live` is not adopted, per-build inputs go under `golden/specs/<build>/`, research 28's two `override-class-too-new-*` captures are added); the facts file holds TLC cases only, and the SANY and PlusCal cases are checked by their parsers' own assertions and `to_dict()` (Q18); three synthetic cases are named. T4: the fake `java`'s `checkpoint` field begins and commits around given lines, logs a `checkpoint` line and commits before message 2196 (Q10); SIGQUIT is noted and the fake carries on (Q5); `version` has an object form for an answer that is not a version; the fake `javac` answers `-version`. T5: steps for a checkpoint in progress, a `javac` version and a non-version answer, and the `{kept-id}` placeholder; `completion.feature` (and `version.feature`, dropped again after the review, finding H7); a named race in the checkpoint step, with a remedy if it flakes. T8: golden `<case>.json` files are the one exception to `expected/`. T9: rows for a project's own compiled `TLCOverrides` (R33) and for `sequences-ext` until the examples manifest exists. T10: the `lifeline` marker; no `fail_under` until the last package, which sets it from the measured figure (at least 80, else to the maintainer). T11: rewritten for D62, with corrected counts. T12 rule 2 follows.

**[02](02-cross-cutting.md).** X1: the full table of codes, words and meanings (D63); the meaning is printed beside the verdict and the word goes to milestone 4's JSON; the postcondition wording agrees with O3. X3: the `latest` refusal fills in the versions from the cached release list, else the installed builds, with no request (finding B16). X4: singular names.

**[03](03-run-stages-and-specs.md).** The waiting line during a checkpoint is the reporter's (Q12). "Specs and their tests" records the Q5 change to the signals machine's fake child and Q17's resource fixes in 03b; no rule of the specs changed.

**[10](10-parser.md).** P1: facts for TLC only (Q18). P2: `ExitStatus` follows X1, with the test over every code; `tlaup.tlc.models` stays until O4 replaces the old layout. P3: a stated pattern for message 2186; corrected counts; the verdict test names the real cfg cases. P4 rule 2 and P5: the typed and information codes agree with P3's table; code 2285's upstream name. P8: corrected counts and dependencies; `SanyResult.to_dict()`.

**[11](11-runner.md).** R2: the waiting line goes from the launcher through the runner to `Reporter.notice` (Q12). R6: `-recover` takes the folder's lock whenever the path lies under an existing run folder (Q9); the deferral scenario uses the new checkpoint step (Q10); duplicate changelog entries dropped. R7: its Changed entry was dropped on 2026-11-22 (finding C1). R11: the Java check timeout has no scenario; J3's unit test stands in (finding C4).

**[12](12-tools-and-downloads.md).** V1: an empty pin file means no pin (inventory T4); singular names. V3: the race under the lock is written out with tests (Q8, finding B7: follow the design). V4: the `upgrade` sketch gains the remote. V7: the debug filter is a stand-alone `redact` function in its own module, in before the tool commands (Q6, finding B9). V8: the release list is cached as it came back and an error answer never is (Q7); D64; the Removed entry for `fetch-cache clear` points to C1.

**[13](13-modules-and-java.md).** M1: singular names. M2: D61 with its Rejected entry, a Breaking changelog line and an exact `-cp` scenario; modules in name order (inventory M18); `module list` with nothing registered prints a note on stderr (M14); a new paragraph, "The classpath of a run", gives the whole runtime order with a whole-list test (S11). J3: a unit test of the `java -version` forms.

**[14](14-config-and-cli.md).** F1: the YAML safe loader, with a test (inventory C4); ranges are the command's (Q16, kept as built). F3: names, `tlc.keep`, and D61's effect on `module_lib_path`. F6: the waiting line goes through the reporter. F7: singular names. F9: the one exception to lazy imports, `tlaup.cmd.completion`; the `PLC0415` per-file ignores; the test of Typer's shell registry. F10: debug output through `redact`.

**[20](20-groundwork.md).** G1: the sketch uses F6's names. G3: `on_held` for the waiting line; the fake child's SIGQUIT; the checkpoint marker in the pseudo-terminal scenario; a duplicate changelog entry dropped.

**[21](21-other-tools.md).** S1: D66, with `source_excerpt` and its tests; the test argument matches its capture; the hint names no later command. S2: D67, with `PcalResult.to_dict()`. S5: the parsers' own assertions.

**[22](22-reporters.md).** O1: `Reporter.notice`. O2 and O3: the excerpt (D66); the four checkpoint, recovery and finish events print nothing; the header leaves out what is not known; the "not checked" wording; the hint line (Q11). O4: the waiting line in the Status panel, copied to stderr on close; the interrupted wording agrees with O3. O6: tests for both.

**[23](23-command-layout.md).** C1: `cache clean --all` with a kind (Q14), the doctor levels (Q15), nothing to clean (inventory O7), and a duplicate changelog entry dropped. C3: the claim that an ordinary start does not load Typer's completion modules was wrong on the locked Typer (finding D1) and is corrected; the registry test is F9's.

**[30](30-ci-and-release.md).** I2: the lifeline tests and marker; D62's consequence for CI. I5: Markdown in the format commit (Q1); the lifeline job is required. I8: a second allowed blind `except`; `shutil.which` for `git` and the editor; one rule group per pull request (finding D15). H1: `ruff-format` covers Markdown. H2: a `.gitattributes` rule for the golden files.

**[40](40-later-milestones.md).** Milestone 3: D65 and a rebuild from the recorded commit; D61 noted. Milestone 4: D64 and D66.

**[The inventory](preserved-behaviour-2026-11-22.md).** Reviewed with the maintainer; now D62's list of requirements. The rows that needed a decision are decided (M5 by D61, T20 and T21 by D64, R21 by D66); the seven kept-but-unspecified rows have their owners and tests, and all seven are now specified; the closing sections name the owners of what had none.

**[The roadmap](../roadmap.md).** Decisions D61 to D67; "How a decision is weighed" under "How the work is done"; the stage 4 entry; D65 under the milestone 3 design note and the concepts page.

## Choices made while working in, low impact

- The lifeline jar of [20 G3](20-groundwork.md#g3-java-launcher), which the design left to the package, is checked in, with the CI test that compiles its source and compares the class files: the same bytes in every test run and every wheel.
- No coverage threshold until the last package of the wave (01 T10).
- A release upstream still lists whose jar is missing for a moment keeps its installed builds at the status `installed` (12 V8).
- Each meaning in X1's table is one sentence, shown by the terminal reporter with a lower-case first letter, unless the first word is an acronym such as `TLC`, and no full stop (02 X1; the acronym rule after the review, finding G5).
- A relative `module_path` is read against the working folder, as in 0.8.x (14 F3, inventory row C6).
- `source_excerpt` lives in `tlaup/reporters/text.py` (21 S1).
- `doctor` warns about folders in the module folder that are not modules (23 C1, inventory row M15).
- The lifeline job installs the current rolling build for its REPL case, since v1.7.4 has no REPL (30 I2).
- `T20` is on for the whole tree, with `scripts/` and `tests/fakes/` exempt per file (30 I8).
- An editor that is not on `PATH` is `NotSetUp`, code 3 (14 F5, inventory row O10); the broken-config scenario of `tlaup tlc Spec` belongs to the new `tlc` command's feature (14 F4).
- The Java check that timed out has no `tlc_errors.feature` scenario; J3's unit test stands in for it (11 R11, finding C4).
- Each rule group of I8 is switched on in its own pull request, with the fixes it needs (30 I8, finding D15).

## Left open

Readings the review raised that nobody settled stay as the packages wrote them, listed for the next review to confirm in the [packages index](../packages/README.md), under "Readings the packages build on": among them findings A3, A6, A7 and C16 on the parser and `pcal`, and the readings of 14 and 12 that the index lists (for example `ToolStore.leftovers()` and the age of a `.tmp` entry). A relative `module_path` is not among them: it was a low-impact choice (above), not something left open. (Stage 4 sign-off, 2026-11-24: none is left open; the maintainer settled the user-visible ones and confirmed the rest, as the index's "Settled since" lists.)

## After the review of the working-in

Four fresh agents reviewed this working-in and the packages on 2026-11-24 ([review](../packages/review-2026-11-24.md)): ready after small fixes, with one blocker. Its findings on the design and the roadmap were worked in the same day, each section's note naming the finding:

- **The checkpoint fake** (E1, with G2; settled with the maintainer): in the one-signal deferral the fake never got a signal to end its hang, since under D60 the signal reaches tlaup alone and tlaup holds it until 2196. The fake now waits for a release file, which T5's checkpoint steps create once tlaup has shown the waiting line; only then does it commit and print 2196, and any hang comes after 2196 ([01 T4, T5](01-testing.md#t4-fakes-at-the-edges), [11 R6](11-runner.md#r6-run-folders), [20 G3](20-groundwork.md#g3-java-launcher)).
- **Settled with the maintainer, as the packages wrote them:** `config show` prints YAML with each leaf key's source as a trailing comment, and `config get KEY` prints one value as `config set` reads it, a section name being code 4 ([14 F1](14-config-and-cli.md#f1-layered-configuration), [23 C1](23-command-layout.md#c1-command-tree)); the two top-level settings' variables are `TLAUP_MODULE_PATH` and `TLAUP_MODULE_LIB_PATH` (14 F1); `tool uninstall --all` on a terminal asks `y` or `n`, default `n` ([12 V3](12-tools-and-downloads.md#v3-uninstall)); the live display's phase word before TLC reports a phase is `Starting` ([22 O4](22-reporters.md#o4-live-display)). The names of the parser's events and result fields, which milestone 4's JSON exposes, stay internal until that milestone publishes its schema, and are reviewed then ([40](40-later-milestones.md#milestone-4-automation-surface)).
- **D63's undocumented code** is in the decision tables (E3), and P2's test expects `error` (E2). D12 is marked as narrowed by D65, and 40 follows D65's wording (E6).
- **Smaller fixes:** R5 and R10 take the old cases over as inputs, not files (E5); I2's threshold and the wheel check's `tools dir` until 29a (E8, H9); F3's relative-path rule covers `module_lib_path` (E9); one wording for D62's CI exception (E12); notes moved out of text a worker copies (E13); the inventory's statuses in the design index (E14); 00's tree gains `versioning/redact.py`, `config/editor.py`, `tools/__init__.py` and `tools/invocation.py` (E11, H14); the lifeline jar is recorded as checked in, in G3, I4 and L2 (F7); X1's lower-case rule keeps an initial acronym (G5); S1 names the line after the marks, gives `format_diagnostic` the whole order, and runs the excerpt's integration test through the command (G13, H4, H3); C4's test is plain pytest and T5 has no `version.feature` (H7); `doctor`'s module-folder check skips `.tmp/` and `.lock` (H1).
- **The inventory** (E7, F1, G1, H13): the notes follow the design's new text, C4, M14 and O7 are "kept, specified", J4, R25 and S7 name their owners, and M5 is a changed row whose new behaviour has its tests.

These fixes were not reviewed again.
