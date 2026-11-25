# 01. Testing approach

Decision D16 asks for the testing approach to be designed from scratch, before anything else, because every work package writes tests. This document is that design and also covers the testing items of milestone 2. Decision D33 (2026-11-15) fixes the form of the command-line tests.

Inputs: [roadmap, milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this); research [1](../research/01-tlc-output.md), [8](../research/08-github-api-ordering.md), [12](../research/12-sany-pcal-repl.md), [13](../research/13-override-loading.md), [15](../research/15-exit-codes-and-signals.md). A fresh agent read every existing test on 2026-11-15 and ran the unit suite in a scratch home folder with `java`, `javac` and `git` replaced by logging stand-ins; its findings are in T11.

Revised 2026-11-15 after the review of the first design wave: how scenarios are run (T5), the fake `java` (T4), which captures really exist (T3), how a live build finds its golden folder (T9) and the rules of T12. Nothing in this document was run except where it says so; the Typer facts in T5 were probed on the locked Typer 0.29.1.

Revised again on 2026-11-15 and 2026-11-16 after the second check of the revision: the step vocabulary is rebuilt so that the scenarios the other documents cite can be written, or are named as plain pytest (T5); the fake `java` gets the fields those scenarios need (T4); the terminal steps run at the size they say (T5); prompts have one mechanism (T5); and the facts about test libraries that nobody has tried are collected under question 30 (T4, T5, T10) instead of being scattered as "not tried".

Revised 2026-11-24 after the review of the work packages and the maintainer's decisions on it: the old tests go at once and the preserved-behaviour inventory takes the place of T11's tables (decision D62); the fakes and a step for the checkpoint deferral (T4, T5); research 22's placements and the scope of the facts (T3); two integration rows (T9); no coverage threshold until the end of milestone 2 (T10). Each change is marked in its section.

## T1 The approach

**Problem.** The current suite passes while the program is wrong. The parser tests use output typed by hand, so real traces parse to zero states and the tests stay green. Twelve tests ask for a download fixture that patches the wrong name, so the real downloader runs and starts `java`. A full unit run starts `java` 20 times and `git` once (the triage's count on 0.8.2; the roadmap item says 23 subprocess starts, counted by the analysis on 0.8.1; the difference was not looked into), and writes to the real `~/.cache/tlaup`.

**Design.** One idea covers the whole program: **test at a boundary, with real recordings at the edges.**

There are two boundaries worth testing at, and three edges where the outside world is replaced.

| Boundary | What is tested | Form |
| --- | --- | --- |
| The command line | Everything `tlaup` does: exit code, stdout, stderr, and the files it leaves. | pytest-bdd feature files (T5), in-process where that can see the result and as a real process where it cannot. |
| The `tlaup_parse` package | Text in, parsed result out. | Golden files in plain pytest (T3), property tests for values (T7). |

| Edge | Replaced by | Never |
| --- | --- | --- |
| Processes (`java`, `javac`, `git`, an editor) | Small fake executables on a `PATH` that holds nothing else. The fake `java` replays captured output. (T4) | A patched `Popen` or `subprocess.run`. |
| The network (GitHub) | Recorded responses served by the `responses` library. (T4, T6) | A patched function of ours. |
| Time | A clock and a sleep function passed in as arguments. | The wall clock, `sleep`, file modification times. |

The captured TLC output is the link between the two boundaries: the same `.out` files are parsed directly by the golden tests and replayed by the fake `java` in the feature files. A parser bug therefore fails in two places, and a feature file never contains invented TLC output.

Below the two boundaries, a **small** set of plain pytest tests stays where a scenario would be a poor fit. They are of three kinds, and T12 rule 1 names them: pure functions (sorting versions, parsing a version spec, reading a jar manifest, reading a class file, resolving a spec name, composing the classpath, building the Java command); a reporter driven directly with events and writing to in-memory consoles ([22 O6](22-reporters.md#o6-snapshot-tests)); and the pieces that sit directly on an edge, driven with the edge's fake (the launcher and `run_tlc` with the fake `java`, the GitHub client with `responses`, the run-folder locks with a second real process). They take real files in a temporary folder and use no mocks.

Above them, **integration tests** (T9) run real Java and real jars. They are the only tests allowed to do so.

**Does one approach cover the whole program?** Nearly. The command-line boundary reaches every line of `tlaup`. It does not suit two things, which is why they have their own form:

- The parser. It ships as its own package (decision D7), its input space is large, and a failing scenario would say "output differs" rather than "state 2 has the wrong value". Golden files and property tests say exactly what broke.
- Download failures. They need a body that stops half way, a redirect to an unencrypted address, a rate-limit header. These are set up in Python more naturally than in a feature file, so they are plain pytest against the real HTTP code (T6). Feature files cover the user-visible outcome of one or two of them.

**Rejected.**

- *Plain pytest scenarios plus runnable documentation* (the design agent's recommendation): fewer moving parts and no step definitions. The maintainer chose feature files for readability (D33). The cost named in the roadmap, step definitions to maintain, is contained by a fixed step vocabulary (T5).
- *Many small unit tests with mocks*, the current form: this is what failed.
- *Feature files for the parser too*: the roadmap already notes they suit parser internals less.
- *A snapshot library (syrupy)*: one more dependency and its own file format. A 40-line helper that compares against plain text files does the same and the files read well in a pull request (T8).

**Risks.** Feature files can drift into testing wording. T12 rule 4 and the step vocabulary guard against it. The fake `java` can drift from real Java; the integration job is the check.

## T2 Isolation

Roadmap: "Isolation is automatic and total." Relies on decision D25 and [14 F2](14-config-and-cli.md#f2-folder-overrides).

**Problem.** `mock_cache` patches five names by hand and misses the config folder; `mock_load_config` patches a name nobody looks up and is requested by 50 tests. The suite is isolated from the user's config only by test order: with an unreadable user config, `tests/unit/tools` run alone fails 48 of 61.

**Design.** One autouse fixture, `isolated`, in `tests/conftest.py`. `tests/integration/conftest.py` defines a fixture of the same name, which replaces it for that folder (pytest's ordinary override): it does the same except that it keeps the real `PATH` and `JAVA_HOME`, so the tests run the Java of the CI cell ([30 I1](30-ci-and-release.md#i1-integration-job)), and sets the JVM's own folders (T9). (Stage 4 review, 2026-11-24: `JAVA_HOME` is kept as well, a reading of packages 52 to 58 that I1 already answered.)

```python
@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch) -> Isolated:
    home = tmp_path / "home"
    for name in list(os.environ):
        if name.startswith("TLAUP_"):
            monkeypatch.delenv(name)
    for name in (
        "JAVA_HOME",
        "JAVA_OPTS",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "EDITOR",
        "VISUAL",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "FORCE_COLOR",
        "CLICOLOR_FORCE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TLAUP_HOME", str(home / "tlaup"))  # moves config, cache and data (D25)
    monkeypatch.setenv("HOME", str(home))  # anything that still asks for the home folder
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("COLUMNS", "100")
    monkeypatch.setenv("LINES", "40")
    monkeypatch.setenv("PATH", str(fake_bin_dir(tmp_path)))  # only the fakes (T4)
    monkeypatch.setenv(
        "TLAUP_TOOL_REPOSITORY",  # a closed local port: a request that is not
        "https://127.0.0.1:9/repos/tlaplus/tlaplus",
    )  # recorded fails at once (T4, Network)
    monkeypatch.chdir(tmp_path / "work")
    tlaup.context.reset()  # the one process-wide cache
    return Isolated(home=home, work=tmp_path / "work", paths=AppPaths.from_env(os.environ))
```

`tlaup.context.reset()` clears the single cached application context ([00](00-overview.md#application-context)). There is no other module-level cache; a second one is a design error.

Forced colour broke the 0.8.0 release, so `FORCE_COLOR` and `CLICOLOR_FORCE` are removed and `NO_COLOR` is set. Width is fixed because all six `tools list` tests fail today at 40 columns. `TERM=dumb` switches the live layout off ([22 O4](22-reporters.md#o4-live-display)), which is right for every test except the ones about the layout. The in-process layout tests set `TERM=xterm-256color` with `monkeypatch.setenv` and build their `Ui` with `terminal=True, size=(100, 30)` ([22 O6](22-reporters.md#o6-snapshot-tests), [14 F6](14-config-and-cli.md#f6-messages)); the second alone is not enough, because under `TERM=dumb` Rich's live display writes nothing even on a console forced to terminal mode (tried on the locked Rich 13.9.4: 0 frames against 4); the terminal steps of T5 set `TERM` and the window size themselves and remove `COLUMNS` and `LINES` from the child's environment, because Rich takes those two over the terminal's real size (tried on the locked Rich 13.9.4, [22 O4](22-reporters.md#o4-live-display)) and every terminal scenario would otherwise run at 100 by 40 whatever it says.

The environment the fixture builds is also the environment of every real process a step starts (T5): the step passes `os.environ` as it is at that moment, so a child tlaup has the same `TLAUP_HOME`, the same `PATH` of fakes and the same repository address.

**Proof that it holds.** CI runs the unit job on a runner with no jar installed and ends with a step that fails if `~/.config/tlaup`, `~/.cache/tlaup` or `~/.local/share/tlaup` exists (`~/Library/...` on macOS). Locally the same check is `uv run poe test-clean`, which runs the suite with `HOME` set to an empty temporary folder and lists it afterwards.

**Removed.** `mock_load_config`, `mock_cache`, `java_available`, `javac_available`, `base_settings`, the three sub-folder conftests' patch lists. They go in the first testing package, together with the old tests that use them (T11, decision D62), so no old fixture lives on beside the isolation fixture. (Stage 4 review, 2026-11-24: when they go, D62; resolves question Q2 of the packages index.)

**Tests.** The fixture has two tests of its own. One writes a file through every folder of `AppPaths` and asserts each path is under `tmp_path`. The other is a pair: each test of the pair asserts that a marker variable `TLAUP_LEAK_CHECK` is absent and then sets it with `os.environ` directly, so whichever runs second fails if the fixture did not clean up.

**Depends on.** F2 (folder overrides), which lands first.

## T3 Golden files

Roadmap: milestone 1, first parser item; milestone 1b, "Golden-file tests for SANY and PlusCal output". Relies on D7, D19, research 1, 12, 13.

**Where they live.** With the parser's tests, filed by tool and by build (D7):

```
tests/parse/
  golden/
    specs/                         the TLA+ specs and cfg files, shared by all builds
    specs/overrides/<case>/        the spec, cfg and Java source of each override case (research 13)
    specs/<build>/                 inputs that differ per build, named like the build folders (research 22)
    tlc/v1.7.4/                    <case>.out   <case>.err   <case>.json   cases.toml   build.toml
    tlc/2026.11.15.002146/         the rolling build captured on 2026-11-14
    sany/v1.7.4/  sany/2026.11.15.002146/
    pcal/v1.7.4/  pcal/2026.11.15.002146/
    synthetic/                     hand-made framing cases, each with a note beside it saying why it exists
  facts.py                         hand-written expectations per case (see below)
  test_golden.py  test_facts.py  test_framing.py  test_framing_props.py  test_values.py  test_values_props.py
  test_sany.py  test_pcal.py
```

A build's folder is named by its own identity: the tag for a numbered release, the CalVer for a rolling build. This answers the open follow-up of research 1 (how to name a rolling fixture once rolling moves): a new capture goes in a new CalVer folder. Decision D19 supports the latest stable release and the current rolling build, so when a newer rolling capture is added and passes, the older rolling folder is deleted in the same pull request. There is therefore at most one rolling folder at a time.

`build.toml` in each folder says what the capture is: `line = "stable"` or `"rolling"`, the tag, the commit and, for rolling, the CalVer. It is how a live jar finds its expectations (T9): a jar with a build time is checked against the one folder whose `line` is `rolling`, whatever its CalVer; a jar without one against the folder whose tag equals the jar's. `facts.py` is keyed by case, and where the two lines differ for a case (`postcondition-false`, `stack-overflow`, `coverage`) by case and line, never by an exact build.

**What moves.** The research captures become the golden files; they are moved with `git mv`, not copied:

| From `tests/fixtures/research/` | To |
| --- | --- |
| `01-tlc-output/{1.7.4,1.8.0}/*.out`, `specs/` | `tests/parse/golden/tlc/{v1.7.4,2026.11.15.002146}/`, `golden/specs/`. The `plain/` captures (no `-tool`) move to `tlc/<build>/plain/`; they are not parsed, only replayed for `--raw` scenarios. |
| `02-json-traces/Live.tool.1.8.0.out` | `tlc/2026.11.15.002146/dump-trace-live.out`: the one `-tool` capture made with `-dumpTrace` (it has the unwrapped `CounterExample written` line). |
| `02-json-traces/Live.tool.1.7.4.out`, `Stut.tool.1.7.4.out` | `tlc/v1.7.4/json-live.out`, `json-stut.out`: two more liveness traces. They are not dump-trace cases; v1.7.4 has no such flag. The specs `Live` and `Stut` move to `golden/specs/`. |
| `12-sany-pcal-repl/<v>/outputs/sany-*`, `pcal-*`, each file that is one command | `sany/<build>/`, `pcal/<build>/`. The first line (the command), the `[exit=N]` line and, in the pcal files, the `-- files before:` and `-- files after:` lines that follow it are not tool output; they move into `cases.toml`. `pcal-retranslate-and-lint.txt` is several commands with hand-written notes and stays as evidence. |
| `13-override-loading/<v>/out/<case>.txt` for the cases `ok_warn_true`, `legacy_ok`, `annot_op_missing`, `annot_module_missing`, `arity_java_fewer`, `static_init_throws`, `ctor_throws`, `ctor_private`, `eval_throws_runtime`, `method_not_public` | `tlc/<build>/override-<case>.out`; the `.cmd` and `.exit` files beside each go into `cases.toml`; each case's spec and source into `golden/specs/overrides/<case>/`. Ten cases: `method_not_public` has text after an end marker and `ctor_private` a message nested in one of the same code ([10 P4](10-parser.md#p4-framing-and-never-losing-output)). |
| `28-java-11-and-macos-java/out/`: the two `-tool` captures on Java 11 of a too-new index class (message 2173) and a too-new listed class (1000 with `UnsupportedClassVersionError`), on each build | `tlc/<build>/override-class-too-new-index.out`, `override-class-too-new-listed.out`; the `.exit` content into `cases.toml`. [11 R7](11-runner.md#r7-override-modules-that-do-not-load) calls them golden and P5 takes the kind of 2173 from them. Research 28 kept their specs inside its script, so the cases have no `spec` and the capture script skips them with a note. |
| `03-jar-identity/manifest-*.txt`, `14-jar-manifest/*.MF` | `tests/unit/data/manifests/` |

`08-github-api/` and `18-digest/` are **not** moved: they are trimmed, concatenated lists with no headers (their README says so), which is evidence and not something `responses` can serve. The GitHub recordings of T4 are new.

**Captures this design named before they existed** (top-up). Research 22 made them on 2026-11-19, on both builds, with stdout and stderr apart ([result](../research/22-more-tool-captures.md), `tests/fixtures/research/22-more-tool-captures/`), and they are adopted as golden files like research 1's, moving to `tests/parse/golden/` by the same rule:

- The PlusCal "changed since last translation" warning from SANY, as single-command captures for each of its three texts and for two files (`sany-stale-*`), and inside TLC (`stale-*-tool`); they replace the composite file above as golden input.
- SANY `-help` (`sany-help`, `sany-h`) on both builds.
- Separate stdout and stderr for every TLC, SANY and pcal case; TLC writes nothing to stderr in `-tool` mode except v1.7.4's `File does not exist` line for a missing module.
- `-tool` captures of a false `ASSUME`, an evaluation error (in `Next` and in an invariant), an action-property violation and three cfg errors; a `-dfid` run and a `-generate` run; simulation and `-generate` violations; `-difftrace` on a violation and a liveness counterexample, with its plain twin; an `ALIAS`; a parameterised action and a sub-action of `Next`; `-deadlock` and `-deadlock -continue`; a checkpoint and `-recover`; 4802 and the stuttering lints inside TLC.
- SANY's level errors on v1.7.4.

Their time-dependent values (the 2185 time, progress, the seeds of 2285, the checkpoint folder's name) get the same normalisation as research 1's. Where a flag does not exist on v1.7.4 (`-generate`, `ALIAS`, `-noGenerateSpecTE`) the v1.7.4 file is the refusal, and is a golden case of its own.

Five placements follow from how research 22 was run:

- *Re-runs of older cases.* Research 22 re-ran research 1's and 12's cases under the same names (`q01-*`, `q12-*`) with the streams apart. The older captures stay the golden files: the design's counts and examples were made on them, research 22 found TLC's stderr empty in every `q01` run, and [21 S1](21-other-tools.md#s1-sany) wants SANY's two streams joined, which only research 12's files hold. The re-runs stay with research 22 as evidence.
- *Stderr.* A TLC case's `.err` file moves beside its `.out` when it is not empty, and `cases.toml` names it; that is v1.7.4's `tool-missing-module` alone. Empty `.err` files stay as evidence, and so do research 22's two SANY cases with a non-empty `.err`, whose joined twins are research 12's.
- *One spec name, two specs.* Research 22's `tool-live` ran a different `Live.tla` from research 2's, which moves to `golden/specs/`; a module's name must equal its file's, so `tool-live` is not adopted. Liveness is covered by research 1's two liveness cases, `json-live` and `difftrace-liveness`.
- *Inputs that differ per build.* The PlusCal-stale specs were made by each build's own translator, so they go to `golden/specs/<build>/`, and the cases name them by that path; `golden/specs/` itself stays shared by all builds.
- *Research 28.* Its two class-version captures move in as golden cases (the table above), since R7's tests and P5 need them.

(Stage 4 review, 2026-11-24: the five placements, question Q3 of the packages index, as the maintainer settled them.)

Everything else under `tests/fixtures/research/` stays where it is as evidence, and its `README.md` gets a line per moved folder saying where it went and when. The old fixtures `tests/fixtures/releases.json`, `tags.json` (superseded by the recordings) and `naming_dynamic` (covered by T9's QueueModule row) are deleted with the old tests in the first testing package (T11, D62). `naming_fixed`, a spec with a project's own `TLCOverrides` source, stays until the integration tests take it for their project-override row and move it beside them (T9). (Stage 4 review, 2026-11-24: when the old fixtures go, D62; `naming_fixed` kept for preserved-behaviour row R33.)

**`cases.toml`** holds what the README tables hold today, in a form tests can read:

```toml
[violation]
spec = "Violation"
args = []
exit = 12
java = "25.0.5"
captured = "2026-11-14"

[pcal-err]                      # pcal cases also record the files around the run
spec = "PcalErr"
exit = 0
files_before = ["PcalErr.tla"]
files_after = ["PcalErr.cfg", "PcalErr.old", "PcalErr.tla"]
```

**Two kinds of expectation**, because the roadmap wants tests that fail first and a full JSON written by hand for forty traces is not realistic:

1. **Facts** (`facts.py`): a few hand-written assertions per case, written from reading the raw capture, before the parser is fixed. For example, for `violation`: one error of kind `invariant` named `Small`; a trace of 4 states; state 1 has no location; state 2's action is `Next` at line 10, column 59; state 2's `n` is the integer 1; `log` in state 4 is a sequence of 3 records. These are the tests that fail first.
2. **Full expected result** (`<case>.json`): the whole parsed result as `RunResult.to_dict()` ([10 P3](10-parser.md#p3-result-model)), or for SANY and PlusCal as `SanyResult.to_dict()` and `PcalResult.to_dict()`. Generated by the fixed parser with `--update-expected` (T8), then reviewed line by line against the `.out` file by a separate agent. It guards against regressions the facts do not mention.

`facts.py` is also used by the integration tests (T9): the same assertions run against the result of a live TLC run of the same spec. One set of expectations, two sources, so a stale golden file shows up as "facts pass on the capture and fail on the live run". It holds TLC facts only, since a fact takes a `RunResult`; the work on the SANY and PlusCal parsers writes its own hand-written checks first, failing, in `test_sany.py` and `test_pcal.py`, and gives both results the dictionary form above ([10 P8](10-parser.md#p8-sany-output), [21 S5](21-other-tools.md#s5-golden-files-for-sany-and-pluscal)). (Stage 4 review, 2026-11-24: facts are TLC's only and the two other results get `to_dict()`, question Q18 of the packages index.)

**How the parser is driven.** Exactly as the runner drives it: the file is read in binary, split into lines that keep their newline, decoded as the launcher decodes ([20 G3](20-groundwork.md#g3-java-launcher)) and fed one line at a time to `TlcParser.feed`, which takes one line per call. Each golden test also checks the properties of [10 P4](10-parser.md#p4-framing-and-never-losing-output), which hold for every file:

- **Nothing is lost at the framing level** (D9): the file is fed to the public `Framer`, everything it returns is written back with `render_framed`, and the result equals the file's lines exactly: nothing lost, nothing moved, nothing added. A message keeps its lines and its nested messages in one ordered body for this reason.
- **Nothing is lost at the event level**: the number of `OutputLine` events equals `RunResult.unframed_lines` minus `RunResult.sany_lines_used`, where the first counts every piece of text the framer found outside a message (each `Unframed` item, and each non-empty `before` or `after` text of a top-level message) and the second counts the lines the SANY parser took for itself; and every top-level message is carried by at least one event. The test gets the first number a second way, by running the public `Framer` over the file and counting, and asserts the two agree. In the captures the top-level `before` and `after` texts are always empty; the synthetic case "end marker with text after it at top level" is the one where they are not, and there the count is one higher than the number of `Unframed` items.
- **Line endings do not matter**: feeding each line with its `\n`, without it, and with `\r\n` gives equal results.

**Re-capturing.** `scripts/capture_golden.py --jar PATH --build NAME` runs every case in `cases.toml` with the given jar in a temporary folder and writes the `.out` files with the repository and temporary paths replaced by `<repo>` and `<tmp>`, as the pre-commit hooks require. It is a developer tool, not run in CI, and needs Java. Volatile parts (time, pid, seed, rates) are left as captured: parser tests read a fixed file, so they need no normalising.

**Synthetic cases.** `STARTMSG -1`, a marker with a leading zero, a start with no end at end of input, an end whose code does not match, crossed ends, an end marker with text after it at the top level, an error nested in an informational message, a marker inside quoted `Print` output with text after it. Real TLC did not produce these (research 1 tried), so they are written by hand and kept in `synthetic/`. Four more are made from real captures with the smallest edit that gives the shape: `invalid-utf8.out`, a copy of the `violation` capture with the bytes `FF FE` put into one unframed line (it falls inside the SANY window, so it is a SANY line, not an output line; reworded while building 13a) and a Latin-1 `é` into one value, for [11 R3](11-runner.md#r3-non-utf-8-output); `crlf.out`, a capture with every line ending `\r\n` ([10 P4](10-parser.md#p4-framing-and-never-losing-output), Tests); `cut-off.out`, a capture cut inside a message and before the finish message 2186 ([10 P3](10-parser.md#p3-result-model), Tests); and `unknown-code.out`, a capture with the codes of three messages, at severity 1, 3 and 0, changed to codes no TLC table has (P4's rule 4, which no capture exercises). Each has a file beside it, `<case>.why`, saying why it exists and how it was made; the note is not put inside the `.out` file, where it would be one more line of tool output for the parser. These are the only hand-made tool output in the repository. (Stage 4 review, 2026-11-24: the last three cases, named elsewhere in the design and missing here; a reading of packages 07, 10 and 13, and a clerical item.)

**Rejected.** Keeping the files under `tests/fixtures/research/` and pointing the tests there: D7 says with the parser's tests, and the folder would then be both frozen evidence and live test data. Copying instead of moving: about 200 duplicated files.

**Depends on.** T2; P2 for the test files. **Risks.** A live rolling build newer than the rolling folder is checked against that folder's facts; a fact that fails then means upstream changed its output, and the answer is a new capture, not a weaker fact. Moving breaks the paths quoted in the research result files. They are historical; the research README records the move. `detect-secrets` has two `exclude_lines` patterns for the manifest and tag-list hashes; they are line shapes, not paths, so they keep working after the move (check when moving).

## T4 Fakes at the edges

Roadmap: "Unit tests cannot reach the network or start an unmocked subprocess."

### Processes

`tests/fakes/` holds four small Python scripts. The isolation fixture writes a launcher for each into a temporary `bin` folder (a shebang line naming the running interpreter; on Windows a `.cmd` file), and `PATH` holds only that folder. So a test cannot start the real `java`, `javac` or `git` by accident: the name resolves to the fake or to nothing. `JAVA_HOME` is unset; a test that wants it points it at a fake JDK folder with the same launchers.

- **`java`**: reads the file named by `TLAUP_FAKE_JAVA` (JSON). It appends a line to a log file when it starts, then takes the first entry of `runs` for its main class that no earlier start has taken, and acts on it; each declared run answers one start, which is what T5's scenarios with two runs need, and the `start` line records which entry it took:

  ```json
  {"version": "25.0.5",
   "version_delay_ms": 0,
   "log": "<tmp>/java-calls.jsonl",
   "runs": [{"main": "tlc2.TLC", "stdout": "tlc/v1.7.4/violation.out", "stderr": null,
             "generate_lines": null,
             "exit": 12, "line_delay_ms": 0, "hang_after_line": null,
             "on_sigint": 130, "on_sigterm": 143,
             "write_into_metadir": [], "checkpoint": null, "echo_stdin": false, "replace": {}}]}
  ```

  | Field | What the fake does |
  | --- | --- |
  | `version`, `version_delay_ms` | `-version` prints a banner in the real format to stderr, after the delay. A long delay is how the version-check timeout is tested ([13 J3](13-modules-and-java.md#j3-one-java-start)). `version` may instead be `{"stdout": ..., "stderr": ..., "exit": n}`, printed as given: J3's answer that is not a version, and the macOS stub's `Unable to locate a Java Runtime.` with exit 1. |
  | `stdout`, `stderr` | A golden file to replay on that stream, or literal text for the few raw-mode scenarios that only need to tell the streams apart. Bytes are written as they are in the file, so a file with invalid UTF-8 replays as such. |
  | `generate_lines` | Instead of a replay, write that many lines `line 1`, `line 2`, ... to stdout. With 100,000 it is the output that is larger than a pipe's buffer and ten times the launcher's queue bound, for the closed-pipe scenario of [11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are) and the queue tests of [20 G3](20-groundwork.md#g3-java-launcher). The lines are unframed, so the parser treats them as the spec's output; they are not invented TLC messages (T12, rule 3). |
  | `exit` | The exit code after the output. |
  | `line_delay_ms`, `hang_after_line` | Pace the output; stop after a line and wait for a signal. With `hang_after_line` equal to the number of lines the fake writes everything and then waits, which is "prints 100,000 lines and then waits". |
  | `on_sigint`, `on_sigterm` | The exit code when that signal arrives, or `"ignore"` to stay alive, which is how the second-signal and kill paths of [11 R2](11-runner.md#r2-signals) are reached. SIGQUIT needs no field: the fake logs it and carries on, as the JVM does after its thread dump, which is what G3's Ctrl-\ scenario asserts ([20 G3](20-groundwork.md#g3-java-launcher)). A signal already ignored when the fake starts stays ignored (G3's `nohup` rule). |
  | `write_into_metadir` | File names to create, before the output, in a timestamped folder the fake makes under the folder given after `-metadir`, as TLC does (for example `["queue.chkpt", "vars.chkpt"]`, a complete checkpoint under D52, or `["queue.chkpt", "queue.tmp"]`, an incomplete one), for the checkpoint rules of [11 R6](11-runner.md#r6-run-folders). Revised 2026-11-20 (review finding TU5): the first wording wrote into the `-metadir` folder itself, where D52's completeness test and `Kept.checkpoint_dir` do not look. |
  | `checkpoint` | `{"begin_after_line": n, "commit_before_line": m, "release_file": null}`: after replaying line `n` the fake writes `queue.tmp` and `vars.tmp` into its timestamped folder and logs a `checkpoint` line (below); before it writes line `m` it renames them to `queue.chkpt` and `vars.chkpt`. With `release_file` set to a path, the fake waits after the `checkpoint` line until that file exists, and only then renames the two and writes line `m`; with `null` it goes straight on. With the 2195 line at `n` and the 2196 line at `m` in the replayed text, a release file, and `hang_after_line` at `m` or later (never between `n` and `m`), this is the checkpoint the real-process deferral scenarios of R6 and G3 need: T5's checkpoint steps give the release once tlaup has shown the waiting line. A hang cannot stand between `n` and `m`, because a hang waits for a signal and in the one-signal deferral none comes: under D60 the signal reaches tlaup alone, and tlaup holds it until it reads 2196. The rename comes before line `m` because TLC commits its checkpoint before it prints 2196: a fake that printed first would let tlaup's SIGTERM, sent on at 2196, arrive before the rename, and the "kept" assertion of the one-signal deferral would race. A signal that ends the fake between `n` and `m`, while it waits for the release, leaves the `.tmp` files, as TLC does; a release that never comes ends the fake as a hang that gets no signal does. A plain pytest test that signals from a reporter's callback (R2's exact-moment tests) leaves `release_file` at `null`. |
  | `echo_stdin` | Copy stdin to stdout line by line until it closes, for `repl` ([21 S3](21-other-tools.md#s3-repl)). |
  | `replace` | Text to substitute in the replayed output, for example `{"<tmp>/q1/specs": "{work}"}`. The captures hold `<tmp>` and `<repo>` placeholders where real paths were; with this a scenario can check rules that depend on real paths, such as diagnostics relative to the working folder. Without it such a rule can only be checked by the integration tests. |

  **The log** is what the Then steps about Java and the waits of the signal steps read. One JSON line per event, written and flushed at once:

  | Line | Fields | Written |
  | --- | --- | --- |
  | `start` | The process id, its process group id (D60: a parsed run's JVM has a group of its own), the fake's own path, the argument list, the working folder, the main class (or `-version`), and whether its stdout is a pipe. | First thing, before any output. |
  | `signal` | The signal's name. | When a signal arrives, also one the fake ignores. |
  | `checkpoint` | The timestamped folder. | Once it has flushed line `n` of `checkpoint` and written the `.tmp` files. It is the marker T5's `once java has begun its checkpoint` waits for. |
  | `exit` | The exit code. | Last thing, on every way out the fake controls. |

  The working folder is there for [21 S1](21-other-tools.md#s1-sany) (SANY is started in the spec's folder), the fake's own path for [13 J2](13-modules-and-java.md#j2-finding-java) (which of two `java`s ran), and the pipe flag for T12 rule 10 (a parsed run gives the child a pipe; `run_passthrough` gives it tlaup's own stdout, which in-process is not one). With no file set, the fake exits 127 with "fake java: no script", so an unplanned Java start fails loudly.
- **`javac`**: answers `-version` with `javac <version>` on stdout and exit 0, as JDK 25 does, with the version from its script (default `25.0.5`), for the `javac` version check of [13 M3](13-modules-and-java.md#m3-module-build-details); copies prepared class files for the sources it is given into the `-d` folder, or prints a recorded compiler error and exits 1. The class files are real: compiled once from the override sources in `tests/fakes/java-src/` with `javac --release 11`, committed, with the compiler version noted in a README beside them.
- **`git`**: prints a fixed short hash. Used only by the version test for editable installs.
- **`editor`**: reads the file named by `TLAUP_FAKE_EDITOR` (JSON: the text to put in the file it is given, or nothing to leave it alone, and an exit code), logs its argument list, and acts on it.

`javac`, `git` and `editor` log their starts to the same kind of log as `java`, so one Then step, `<tool> was started with "<argument>"`, serves all four.

(Stage 4 review, 2026-11-24, on the fake `java` and `javac` above: each declared run answers one start, a reading of package 03 that T5 already implied; the `version` object form, for J3's two answers that are not a version; SIGQUIT logged and survived, for G3's Ctrl-\ scenario; the `checkpoint` log line and the commit before line `m`, question Q10 of the packages index; `javac -version`, a clerical item.; the `checkpoint` field's `release_file`, so that the fake reaches line `m` in the one-signal deferral, finding E1, settled with the maintainer on 2026-11-24.)

Some states of Java are files, not script fields, and have a Given step each (T5):

- A `java` that is on `PATH` and not executable (the launcher is written without the execute bit). tlaup never finds such a file, so the result is `JavaNotFound`, code 3, the same as no `java` at all ([13 J2](13-modules-and-java.md#j2-finding-java)); the scenario asserts exactly that. The first revision expected a start failure with code 5 here, which cannot happen through the command line. A file that is found and then cannot be started (`ToolStartError`, code 5) is reachable only by handing the launcher a path, and is a unit test of the launcher ([20 G3](20-groundwork.md#g3-java-launcher)).
- A `java` replaced by another version (the launcher file is rewritten, which changes its size and time, the things the remembered version check keys on).
- A JDK folder for `JAVA_HOME`: a folder with `bin/java` and `bin/javac` launchers of its own, or an empty folder for the stale-variable case.

### Network

`pytest-socket` runs with `--disable-socket` for every test, the integration tests included (they copy their jars into the store and need no network, T9), so an unrecorded connection is an error, not a slow test. GitHub is served by `responses`, which answers at the `requests` adapter, below tlaup's own retry, header, redirect and pagination code; that code is therefore exercised for real.

`tests/recordings/github/` holds real API responses, trimmed, one folder per situation:

```
releases/                the full release list (17 releases, one page), per-tag release objects for rolling, v1.8.0, v1.7.4
releases-paged/          the same list asked for ten at a time: two pages with their real Link headers
rate-limited/            a 403 with x-ratelimit-remaining: 0 and its reset header
```

**The recordings exist** (top-up, [research 29](../research/29-ci-facts-and-recordings.md), made 2026-11-19 in `tests/fixtures/research/29-ci-facts-and-recordings/`): `releases-paged`, two pages at `per_page=10` with their real `Link` headers, the second without `rel="next"`; and `rate-limited`, a real 403 from the exhausted unauthenticated allowance, which has `x-ratelimit-remaining: 0` and `x-ratelimit-reset` and **no `Retry-After`**, so the `remaining == 0` rule of [12 V7](12-tools-and-downloads.md#v7-github-client) is the one that fires. They move to `tests/recordings/github/` by T3's rule. The research also recorded `tags-paged`; the client never calls the tags endpoint ([12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache)), so it stays with the research as evidence. A 429 was not obtained; that row stays a synthetic case, and its first line says so. The research fixtures `08-github-api` and `18-digest` are trimmed lists without headers and stay where they are (T3).

A fixture `github(recording="releases")` removes the closed-port repository address the isolation fixture set (so the client uses its default, the real API host, which matters for the token tests), registers a recording with `responses` and returns an object that lists the requests made, so a test can assert "no request", "three requests", or "this request carried no Authorization header". Jar downloads are answered with a small real jar built in the fixture (a zip with `META-INF/MANIFEST.MF` copied from the recorded manifests and an empty `tlc2/TLC.class`), not the 4 MB original.

Recordings are captured with `scripts/record_github.py`, a developer tool that needs the network and trims each response to the fields tlaup reads, keeping the status and the headers.

**Real processes and the network.** `responses` and `pytest-socket` work inside the pytest process only. A scenario that runs tlaup as a real process (T5) is kept off the network in two ways. By rule: such a scenario starts from a store that already holds what it needs and exercises nothing that asks GitHub; anything that downloads is tested in-process. By construction: the isolation fixture points `TLAUP_TOOL_REPOSITORY` at a closed port on the local machine and removes the proxy variables, so a request made by mistake is refused at once and the scenario fails on the resulting error instead of reaching GitHub. Not tried.

### Time

Nothing reads the clock directly. The reporter takes `clock: Callable[[], float]`; the GitHub client takes `sleep: Callable[[float], None]`; the store takes `now: Callable[[], datetime]`. Production code passes the real ones at the top; tests pass a counter. The lookup cache stores its fetch time inside the file rather than relying on the file's modification time, which removes the two `os.utime` tests.

**Rejected.** A fixture that makes `subprocess.Popen` raise unless marked: it guards by patching and says nothing about what was started. A local HTTP server for GitHub: needs sockets and plain HTTP, which [12 V7](12-tools-and-downloads.md#v7-github-client) refuses. An interface of our own in front of `requests`: the code worth testing (retry, token scoping, redirect checks) would sit behind the fake.

**Depends on.** T2, F2. **Risks.** The fake `java` grows a field whenever a document wants a new behaviour; a field needs the same kind of reason in the pull request as a new step (T5). Two library facts this section rests on were tried by research 30 (top-up, [result](../research/30-library-behaviours.md)): `responses` 0.23.3 to 0.26.3 and `pytest-socket` work together (mocked requests work under `--disable-socket`, and an unregistered address gets `responses`' own `ConnectionError`); and `responses` keeps a `Content-Length` longer than the body, after which `requests` raises `requests.exceptions.ChunkedEncodingError` from `.content` and from `iter_content`, while `raw.read()` returns the short body with no error. So the downloader maps `ChunkedEncodingError` to `DownloadVerificationError`, and code that reads `response.raw` compares the byte count itself. Under `pytest-socket` 0.8 with `filterwarnings = error`, a blocked socket surfaces as its `UserWarning` raised as an exception, not as `SocketBlockedError`, so no test asserts on the latter by type. The fallbacks the first design held in reserve are not needed.

## T5 Feature files and steps

Roadmap: "The `tlaup tlc` command path is tested end to end: exit codes, raw mode, missing Java and Ctrl-C." Decision D33.

**Layout.**

```
tests/features/
  tlc_run.feature  tlc_errors.feature  tlc_signals.feature  tlc_raw.feature  tlc_show_command.feature  tlc_live.feature
  sany.feature  pcal.feature  repl.feature
  tool_install.feature  tool_uninstall.feature  tool_pin.feature  tool_upgrade.feature  tool_list.feature
  first_run.feature  modules.feature  config.feature  cache.feature  doctor.feature  errors.feature
  completion.feature
tests/steps/
  given.py  when.py  then.py      the whole step vocabulary
tests/test_features.py            scenarios("features")   relative to this file's folder, so tests/features
```

**Example.**

```gherkin
Feature: Running TLC

  Background:
    Given the build "v1.7.4" is installed and pinned
    And a spec "Violation" from the golden specs

  Scenario: A violated invariant shows its message and its full trace
    Given java replays "tlc/v1.7.4/violation" with exit code 12
    When I run "tlaup tlc Violation"
    Then the exit code is 12
    And stdout contains "Invariant Small is violated."
    And stdout matches the expected file "tlc_run/violation.txt"
    And java was started with "-tool"

  Scenario: SIGTERM stops TLC and exits 143
    Given java replays "tlc/v1.7.4/big-states" with exit code 0
    And java hangs after line 40
    When I start "tlaup tlc Big" and send SIGTERM once java is running
    Then the exit code is 143
    And the java process has exited

  Scenario: Raw mode passes both streams through
    Given java writes "to-out" to stdout and "to-err" to stderr
    When I run "tlaup tlc Violation --raw" as a process
    Then stdout is exactly "to-out"
    And stderr is exactly "to-err"
    And java was started without "-tool"
```

**The step vocabulary is fixed.** A new step needs a reason in the pull request; a scenario that needs a one-off step is usually a plain pytest test instead. The second check of 2026-11-15 found that the first vocabulary could not express scenarios the other documents cite. Each of those now has a step below or is named under "What is a plain pytest test instead"; the documents that cite a scenario use these words for it. The whole set:

| Kind | Steps |
| --- | --- |
| Given: the store | `the build "<spec>" is installed` (optionally `and pinned`); `no build is installed`; `the module "<name>" is registered`; `the release list is cached from "<recording>", <n> minutes old`; `the jar of the build "<spec>" is truncated` |
| Given: files | `a spec "<name>" from the golden specs`; `a file "<path>" containing:` (doc string); `a module source "<name>" from the fake sources`; `the config file contains:` (doc string); `the folder "<path>" is read-only`; `I am in the folder "<path>"` |
| Given: what Java does | `java replays "<case>" with exit code <n>`; `java prints <n> lines`; `java writes "<text>" to stdout and "<text>" to stderr`; `java echoes its input`. Each of these declares one run of the fake. |
| Given: changes to the run declared last | `java hangs after line <n>`; `java pauses <n> ms between lines`; `java writes "<file>, ..." into its metadir` (into the timestamped folder it makes there); `java begins a checkpoint after line <n> and commits it before line <m>`; `java's output has "<text>" replaced by "<text>"` (fills T4's `replace`, with the placeholders below expanded in the second text; for S1's excerpt scenario); `java ignores <signal>`; `java exits with <n> on <signal>` |
| Given: which Java there is | `java is not installed`; `java is not executable`; `java is version "<v>"`; `java is replaced by version "<v>"`; `java takes <n> seconds to report its version`; `java answers its version check with "<text>" on <stream> and exit code <n>`; `JAVA_HOME is a JDK of version "<v>"`; `JAVA_HOME is an empty folder`; `javac is not installed`; `javac is version "<v>"`; `javac fails with "<recording>"` |
| Given: the editor | `the editor writes:` (doc string, which becomes the file's content); `the editor exits with code <n>` |
| Given: the rest | `GitHub answers from "<recording>"`; `GitHub answers <status> to "<path>"`; `GitHub is unreachable` (all three in-process only); `the environment variable "<name>" is "<value>"` |
| When: in-process | `I run "<command>"` |
| When: a real process | `I run "<command>" as a process`; `I run "<command>" as a process with input:` (doc string, written to stdin, then closed); `I run "<command>" as a process whose reader closes after <n> line(s)`; `I run "<command>" as a process with stdout on a closed pipe`; the same `with stdout and stderr on a closed pipe`; the same `with stdout on the null device and stderr on a closed pipe`; `I start "<command>" and send <signal> once java is running`; `I start "<command>" and send <signal> twice`; `I start "<command>" and send <signal> once java has begun its checkpoint`, optionally ending `, and again once stderr contains "<text>"`; each `send` form with `to the foreground group` added right after the signal (`I start "<command>" and send SIGINT to the foreground group once java is running`; placed so while building 18b) |
| When: a real process on a terminal | `I run "<command>" in a terminal <w> by <h>`; the same `with <stream> redirected to "<file>"` (stdout or stderr); the same `and answer "<text>"` (one or more answers, separated by commas, typed as the notes below say); `I start "<command>" in a terminal <w> by <h> and press Ctrl-C once the terminal has shown "<text>" and then "<text>"`; the same ending `and then an elapsed time <n> seconds later`; `I start "<command>" in a terminal <w> by <h> and press Ctrl-C once java has begun its checkpoint` |
| Then: result | `the exit code is <n>`; `stdout contains "<text>"`; `stderr contains "<text>"`; `stdout contains "<text>" <n> times`; `stderr contains "<text>" <n> times`; `stdout does not contain "<text>"`; `stderr does not contain "<text>"`; `stdout is exactly "<text>"`; `stderr is exactly "<text>"`; `stdout is empty`; `stderr is empty`; `stdout matches the expected file "<name>"`; `stderr matches the expected file "<name>"` |
| Then: files and store | `the file "<path>" exists` / `does not exist` / `contains "<text>"` / `matches the expected file "<name>"`; `the config file is unchanged`; `the pinned build is "<spec>"`; `no build is pinned`; `the installed builds are:` (table); `the registered modules are:` (table); `the cache holds no run folders`; `the cache holds <n> run folder(s)`; `the cache holds no lock files` |
| Then: the fakes | `<tool> was started <n> time(s)`; `<tool> was not started`; `<tool> was started with "<argument>"` / `without "<argument>"` (`<tool>` is `java`, `javac`, `git` or `the editor`); `java ran "<main class>" <n> time(s)` / `did not run "<main class>"`; `java was started in the folder "<path>"`; `java ran from JAVA_HOME` / `from PATH`; `the java command matches the expected file "<name>"`; `the java process has exited` |
| Then: GitHub | `<n> request(s) were sent to GitHub`; `<n> jar download(s) were made`; `no request carried a token to "<host>"` (in-process only) |
| Then: the terminal | `the terminal showed the layout`; `the last layout frame contains "<text>"`; `the terminal stayed on the main screen`; `the terminal ends with the expected file "<name>"`; `the terminal contains "<text>"`; `the terminal does not contain "<text>"` |

Paths in steps may use `{home}`, `{work}`, `{tools}`, `{modules}`, `{runs}`, `{config}`; they expand from `AppPaths`. `{kept}` is the run folder the previous run of the same scenario kept: the one folder under `{runs}` whose `run.json` says `"kept": true` when the step that uses it runs. It may appear in a later command (`I run "tlaup tlc Spec -- -recover {kept}/<name>"`) and in Then steps; with no kept folder, or more than one, the step fails and says so. Run ids are random, so without it a second run could not name the first one's folder. `{kept-id}` is the last part of `{kept}`, the run id alone, with the same failure, for the commands that take a run id (`cache clean <run-id>`, [23 C1](23-command-layout.md#c1-command-tree)).

Notes on the steps whose meaning is not plain from their words:

- **Where a declared run's output comes from.** Each declaring step writes one entry of the fake's script ([T4](#t4-fakes-at-the-edges)): `java replays` points it at the golden case's file; `java prints <n> lines` makes it print `line 1` to `line <n>` on stdout and exit 0; `java writes "<a>" to stdout and "<b>" to stderr` makes it write those two texts, each with a newline, and exit 0; `java echoes its input` copies stdin to stdout until end of input. A declared run answers the next start of a tool main class; the `-version` start that comes first is answered from the fake's version field and uses up no entry.
- **Counting.** `<stream> contains "<text>" <n> times` counts occurrences that do not overlap, for scenarios such as "the question was asked three times". The GitHub steps (`<n> request(s) were sent to GitHub`, `<n> jar download(s) were made`) count the last run only: `I run` clears the recorded requests before each call, so "the second time, one request" is a second `I run` followed by the step.
- **`the cache holds no lock files`** asserts that no `*.lock` file lies directly under `{runs}` ([11 R6](11-runner.md#r6-run-folders)).
- **Stdin of the real-process steps.** `I run ... as a process` gives the process the null device as stdin unless it is the `with input:` form. The `I start ...` steps give it a pipe that the step holds open until the process has ended, so a tool that reads its input (the REPL, the echoing fake) does not see end of input while the scenario waits to send its signal; the step closes the pipe after the process exits. On a terminal, stdin is the pty.
- **Declaring a run, then changing it.** `java replays ... with exit code 255` followed by `And java writes "queue.chkpt, vars.chkpt" into its metadir` and `And java hangs after line 40` is one run with all three properties. This replaces the first vocabulary's combined forms, which could not say "replays, writes a checkpoint and exits with 255" or "hangs and ignores SIGTERM". `java prints 100000 lines` followed by `java hangs after line 100000` is the fake that prints everything and then waits.
- **Two runs in one scenario.** A scenario may have a second `When I run`, with Given steps between the two (a kept run folder exists because a first run left it; then the fake is declared again and a second run resumes it). `I run` resets the application context before each call, as the isolation fixture does before each test ([00](00-overview.md#application-context)), so the second run reads the files the first one left and nothing from its memory. The Then steps speak about the last run; the fakes' logs hold both. pytest-bdd accepts a Given after a When in every version research 30 tried (top-up), so the fallback step the first design named is not needed.
- **`once java is running`** waits for a `start` line in the fake's log whose main class is the tool's, not the `-version` start that comes first (T4). Waiting for the first line of any kind would send the signal during the version check, before TLC exists.
- **`once java has begun its checkpoint`** waits for the fake's `checkpoint` log line (T4), written once the 2195 line is flushed to tlaup's pipe and the `.tmp` files exist, and sends the signal. The fake then waits for its release (T4's `release_file`), which this step gives: it waits until tlaup has shown the waiting line (`waiting for TLC to finish writing its checkpoint`, either wording of [11 R2](11-runner.md#r2-signals); on stderr for a process, on the screen for the terminal form) and then creates the file, so the fake commits and prints 2196 only after tlaup has shown that it holds the signal. If the fake logs its `exit` first (a raw run, where the fake gets the signal itself), the step gives no release. It is the one way to place a signal between 2195 and 2196, which the deferral of [11 R6](11-runner.md#r6-run-folders) and [20 G3](20-groundwork.md#g3-java-launcher) is about: `once java is running` sends at the JVM's start, `twice` waits for a signal the deferral holds back, and plain output prints nothing for either message. The form ending `and again once stderr contains "<text>"` sends the second signal once tlaup has printed that text (the waiting line, which shows that the first was held) and gives no release; it is the "second signal before 2196 kills at once" case. The terminal form types Ctrl-C at the same moment, for D60's scenario, and reads the screen for the waiting line, so its terminal must be wide enough to show the line whole. `java begins a checkpoint after line <n> and commits it before line <m>` sets `release_file` to a file in the scenario's folder, so a scenario that declares it uses one of these When forms; any `java hangs after line` in it names `m` or a later line.
- **The answers of `and answer`** are typed all at once, each with its newline, right after the start. On a pty in canonical mode the terminal hands the reader one line per read, and `Ui.ask` reads one line ([14 F6](14-config-and-cli.md#f6-messages)), so the process takes them one at a time as it asks. Nothing outside the process shows the moment it waits for input without a seam or a wait for time (T12 rule 5); the only visible difference is that the terminal echoes the answers before the questions appear, which no scenario asserts.
- **`the java command matches the expected file`** first replaces, in the logged argument list, the scenario's folders by their placeholders (`{work}`, `{runs}` and the others), the lifeline agent's process id and the run id, which change from run to run. The folder of the installed package's lifeline jar is written `<tlaup>`, so the agent argument reads `-javaagent:<tlaup>/lifeline.jar=pid=<pid>` (added while building 18a: the folder is the checkout or install path, machine data).
- **`java answers its version check with ...`** writes T4's object form of `version`; it is how J3's answer that is not a version and the macOS stub with no JDK are scripted ([13 J3](13-modules-and-java.md#j3-one-java-start)). `javac is version "<v>"` is the `javac` twin of `java is version` (M3).
- **`java ignores <signal>` and `java exits with <n> on <signal>`** take `SIGINT` or `SIGTERM` only, the two signals the fake `java` of T4 has fields for; another signal fails the step with a message (settled while building 18a).
- **`send <signal> twice`** sends the signal, waits until the fake has logged a signal of its own (tlaup has passed the first one on), and sends it again. It is used with `java ignores <signal>`, so the child is certainly still running when the second arrives. Sending the two back to back would not do: two pending signals of one kind are delivered as one.
- **`java is not executable`** leads to `JavaNotFound`, code 3 (T4).
- **`the config file contains:`** remembers what it wrote; `the config file is unchanged` compares the file with that, byte for byte.
- **`the release list is cached ...`** writes the lookup cache file from a recording with a fetch time that many minutes before now ([12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache)). The scenarios use ages far from the 60-minute limit (1 minute, 3 hours); the limit itself is a unit test with an injected clock.
- **`the jar of the build ... is truncated`** cuts the installed jar file to half its size, the damage `install --force` exists to repair ([12 V12](12-tools-and-downloads.md#v12-install)); no command produces that state.
- **`GitHub is unreachable`** makes every request fail with a connection error from `responses`. Without it, and without a recording, an in-process request is stopped by the socket block, which is a test failure, not a scenario about being offline.
- **`the folder "<path>" is read-only`** removes write permission and gives it back when the scenario ends, so the temporary folder can be deleted. Skipped with the reason when the suite runs as root, where permissions do not bind. A path `{tools}/<version>` that names exactly one installed build means that build's folder, found through the store, so no scenario writes a build id (widened while building 29a, 2026-11-25, a low-impact choice by the stage 5 lead; the one edit of an 18 step); any other path is taken as written.

(Stage 4 review, 2026-11-24, on the step vocabulary and its notes: the checkpoint steps, question Q10 of the packages index; `javac is version`, `{kept-id}`, how answers are typed and what the Java command comparison replaces, readings of packages 18, 30, 31, 45 and 46; the version-answer step, which 39's scenarios for J3 need; `completion.feature` and `version.feature` added to the layout, a clerical item.; the release that the checkpoint steps give, finding E1, settled with the maintainer on 2026-11-24; the notes moved to the end of the list, finding E13; the `replace` modifier, which S1's excerpt scenario needs, finding H2.)

`java was not started` counts every start, the version check included. The fake `java` is a script, and the Java check is remembered only for a plain binary ([13 J3](13-modules-and-java.md#j3-one-java-start)), so a scenario that runs a tool starts the fake twice: once for the version and once for the tool. `java did not run "tlc2.TLC"` is the step for scenarios in which the version check is allowed to run (Java too old, the version check timing out) and the tool must not.

**How a command is run.** There are two ways, and the step says which.

*In-process.* `I run "<command>"` calls the Typer application through `CliRunner`. It is fast, `responses` and `pytest-socket` apply, and coverage counts it. Probed on the locked Typer 0.29.1: `CliRunner` returns `result.stdout` and `result.stderr` separately with no extra argument; with the error mapping inside the application's root group ([14 F10](14-config-and-cli.md#f10-no-tracebacks)) a domain error gives its own exit code (3 in the probe), Typer's usage errors give 2, and `KeyboardInterrupt` gives 130. So every code of decision D29 is visible in-process, except 141, which needs a pipe. The fake `java` such a run starts is a real child process, but only where tlaup reads its output through pipes: the parsed path. In-process there is no terminal, so nothing ever asks.

*A real process.* The other When steps start `sys.executable -m tlaup` (which needs the `src/tlaup/__main__.py` that 14 F10 adds) with the environment of the isolation fixture. `the exit code is <n>` then reads the code as a shell reports it: a process ended by signal number s counts as 128 + s. They are needed in five situations, and a scenario in one of them must use them, because in-process the test would pass or fail for the wrong reason:

1. **The command reaches `run_passthrough`** (`tlc --raw`, `repl`). The child inherits the real file descriptors, not `CliRunner`'s replaced `sys.stdout`, so in-process the captured output is empty and the child reads an empty stdin. The review of 2026-11-15 ran this and saw it.
2. **A pipe whose reader goes away.** No shell is involved in either form.
   - `... whose reader closes after <n> line(s)` connects stdout to a pipe, reads that many lines in Python and closes it. It suits output much larger than a pipe's buffer, where the writer is certainly still writing when the reader leaves.
   - `... with stdout on a closed pipe` gives the process a pipe whose reading end was closed before the process started, so its first write fails whatever the size of the output and whatever the timing. That is how short output, such as help or a small table, is tested without a race. The two longer forms put stderr on such a pipe as well, or stdout on the null device and stderr on the pipe. A stream on a closed pipe cannot be read back, so a scenario asserts `stderr does not contain "Traceback"` only where stderr is not the closed one.

   The five scenarios of [02 X1](02-cross-cutting.md#x1-exit-codes) rule 8 use these steps, in `errors.feature` and `tlc_errors.feature`, and each asserts 141:
   - `java prints 100000 lines`, then `tlaup tlc Spec` whose reader closes after 1 line; also no `Traceback`, and the java process has exited ([11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are)). The path through the launcher and the reporter.
   - `tlaup tool list`, two builds installed, with stdout on a closed pipe; also no `Traceback`. The path through tlaup's own console.
   - `tlaup --help` with stdout on a closed pipe; also no `Traceback`. Typer prints help through a console tlaup does not own; `main()` turns its exit into 141 ([14 F10](14-config-and-cli.md#f10-no-tracebacks)).
   - An unknown option with stdout and stderr on a closed pipe.
   - An unknown option with stdout on the null device and stderr on a closed pipe.

   The design agents tried all five paths through a shell on the locked Typer and Rich (02 X1 lists the commands), and research 23 and 30 on every Typer from 0.22.0 and every Rich from 13.8.0 (top-up). The steps themselves were not run.

   Two rules for these steps, from research 23 (top-up, agreed in the walk-through of 2026-11-20). **The reader closes before tlaup writes**: the step makes the pipe and closes its read end before the process starts, rather than piping into `head -1`; with output shorter than the pipe's buffer, `| head -1` is a race between the reader closing and tlaup writing, and gives 0 or 141 from run to run. The long-output case (the 100,000 lines above) is the one exception, because there the reader always closes first. **A real-process child starts with SIGINT at its default disposition**: a test run started from a background job of a non-interactive shell (a CI script, for one) has SIGINT ignored, the child inherits that across `exec`, Python keeps it, and G3 rightly leaves an ignored signal ignored; every SIGINT scenario then timed out in research 23's first run. So the helper that starts tlaup sets SIGINT back to the default in the child before `exec` (`preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL)`, as research 23's helper does). That is test code; the rule against `preexec_fn` is the launcher's ([20 G3](20-groundwork.md#g3-java-launcher)). The scenarios that test the ignored case on purpose (G3's `nohup` rule) start their child without this reset.
3. **A signal**, which has to arrive at a process. The `send` steps signal the tlaup process alone, as `kill` and a service manager do. With `to the foreground group` the signal goes to the whole process group, as Ctrl-C in a terminal does; tlaup is started in a new group for that. Which of the two a scenario means is part of the scenario, since the two differ exactly where [11 R2](11-runner.md#r2-signals) and [20 G3](20-groundwork.md#g3-java-launcher) say who passes the signal on. What these steps cannot do is choose the moment a signal lands inside tlaup; the cases that need that are plain pytest (below).
4. **A terminal**: the `in a terminal` steps run the process as the leader of a new session on a pty, with the window size set, `TERM=xterm-256color` in place of the fixture's `TERM=dumb`, and `COLUMNS` and `LINES` removed (T2). Both streams and stdin are on the pty unless one stream is redirected to a file. The answers of `and answer` are typed into the pty, so prompts are tested on a real terminal with no seam in the product. `press Ctrl-C` writes the interrupt character to the pty, so the terminal itself sends SIGINT to tlaup and to the fake `java`, which is what a user's Ctrl-C does; the step first feeds the terminal emulator as bytes arrive and waits, with a timeout of ten seconds each, until the screen has shown the first text and then the second ([22 O4](22-reporters.md#o4-live-display) uses it to prove the display is redrawn while TLC is silent). In the `and then an elapsed time <n> seconds later` form the second wait is for a screen that still shows the first text and whose `elapsed HH:MM:SS` value is at least `<n>` seconds greater than the value on the screen where the first text was first seen; two values read from the screen are compared, so the step does not depend on how long the process took to get there. `the terminal showed the layout` asserts only the enter sequence, one frame with the four panel titles and the leave sequence; `the last layout frame contains` reads the last screen before the leave sequence (22 O4). The `Then: the terminal` steps read what was written to the pty; how a screen is rebuilt from it is in 22 O4.
5. **An environment variable the interpreter reads at start**, such as `PYTHONIOENCODING` ([11 R3](11-runner.md#r3-non-utf-8-output)); set in-process it has no effect.

The in-process step refuses situations 1 and 5 itself, so the choice is not left to each scenario (T12 rule 10).

Real processes cannot use `responses`; T4 says how they are kept off the network. A real-process scenario therefore cannot count requests; "nothing was asked of GitHub" shows there as the outcome, since a request would be refused at the closed port and change the exit code. Coverage counts real processes through coverage's subprocess support (T10).

**Prompts have one mechanism.** `Ui.__init__(stdout, stderr, stdin, *, color, env, interactive=None)`: `Ui.ask` writes the question to stderr and reads one line from the `stdin` stream it was given; the end of input raises `CannotAsk`; no Typer or Rich prompt is used ([14 F6](14-config-and-cli.md#f6-messages)). Tests reach a prompt in exactly two ways, and nothing else is built into the product for them:

- *A prompt alone* is a feature scenario on a real terminal: `I run "tlaup tool uninstall rolling" in a terminal 100 by 30 and answer "-1, 7, 2"`. The answers "no", the invalid answers that are asked again, and the "which build" question are of this kind.
- *A prompt whose answer leads to the network* (first run answered "yes", then a download) is plain pytest: the function is called with `Ui(io.StringIO(), io.StringIO(), io.StringIO("2\n"), color=False, env={}, interactive=True)` and `responses` serves the download. A real process cannot be served recordings, and in-process `CliRunner` has no terminal, so no scenario can do both.

`interactive=True` and the `stdin` argument are constructor arguments production code also passes (worked out from the real streams when `interactive` is `None`); there is no stream that pretends to be a terminal and no patched function.

**What is a plain pytest test instead.** The vocabulary is not stretched for these; each is a test in Python against the piece itself, with the edge's fake:

- A prompt answered so that a download follows ([12 V9](12-tools-and-downloads.md#v9-first-run-prompt), [V12](12-tools-and-downloads.md#v12-install)), as above.
- A signal at an exact moment ([11 R2](11-runner.md#r2-signals), [20 G3](20-groundwork.md#g3-java-launcher)): a SIGTERM before the child is started, and a second SIGINT during the summary. `run_tlc` is driven in the test process's main thread with the fake `java` and a reporter that sends the signal to its own process from `start` or from `finish`.
- A Ctrl-C that is left to the REPL and not recorded ([21 S3](21-other-tools.md#s3-repl)): the launcher, with `forward_interrupt=False`. From outside it would need a step that signals and then closes stdin, which the list does not have.
- A file that is found and cannot be started (`ToolStartError`, code 5): the launcher, given a path (T4).
- A second process holding a run folder's lock, a run folder locked while a run is in progress, and the sweep ([11 R6](11-runner.md#r6-run-folders)): the run-folder functions with a real second process started by the test. This replaces a scenario with a second tlaup command during a run.
- An error raised while the live layout is up ([22 O6](22-reporters.md#o6-snapshot-tests)): `run_tlc` with a terminal reporter on in-memory consoles and a command that cannot be started.
- Two results compared with each other, such as "the line `--show-command` prints equals the command a real run logged, apart from the run id" ([11 R9](11-runner.md#r9-show-command)): two `CliRunner` calls in one test.
- The download and GitHub failures (T6).
- The reporter driven with events, an injected clock and in-memory consoles ([22 O5 to O7](22-reporters.md#o5-refresh-interval)).
- The launcher's reader, its queue and its decoding ([20 G3](20-groundwork.md#g3-java-launcher)), with the fake `java`.

**What the `tlc` features cover** (the roadmap's list, as scenarios): each exit code TLC returns in the golden cases passes through; `--raw` writes TLC's two streams to tlaup's two streams unchanged and adds no `-tool`; spec not found, cfg not found, no pinned build, pinned build missing, missing Java (which includes a `java` that is not executable: code 3), Java too old, checked in that order (decision D45, [11 R11](11-runner.md#r11-preflight)), each give one `error:` line on stderr, the right code from D29, nothing on stdout and no start of TLC; with no build and a missing spec the code is 4; a usage error that Typer itself finds gives 2 and Typer's own usage text on stderr, not an `error:` line; Ctrl-C gives 130, SIGTERM 143, a second Ctrl-C still ends with 130 and no traceback (real processes; the second Ctrl-C landing during the summary is plain pytest); a reader that has gone gives 141, whoever was printing (five real-process scenarios); `--show-command` prints one line, starts nothing, never prompts or installs, and creates nothing in the cache; invalid UTF-8 bytes in the replayed output do not crash. `--raw` scenarios are real processes. Target from the roadmap: the command module above 80 percent covered; with the reporters moved out it is small, and the features should cover all of it.

**Rejected.** `behave`: a second test runner beside pytest, so fixtures, coverage and the isolation fixture would exist twice. Steps that take arbitrary Python or shell: they would bring the anti-patterns back.

**Depends on.** T2, T4, F10 (the error mapping inside the application and `__main__.py`), F6 (`Ui` takes its three streams and whether it is interactive as arguments). **Risks.** The step list is long, about ninety forms counting each variant, and grew by about a third in this revision; it is still a closed list, and the modifier steps and the `<tool>` parameter are what kept it from growing further. pytest-bdd (top-up, research 30): only 9.0.1 runs with the locked pytest 9.2.0 (7.3.0 to 9.0.0 fail inside pytest's fixture manager), so the bound is `pytest-bdd>=9.0.1,<10` ([30 B2](30-ci-and-release.md#b2-build-fixes)); doc strings reach a step as the reserved `docstring` argument, with the common indent removed; a Given may follow a When; `scenarios("features")` resolves against the test file's folder. The pty steps depend on the platform's `pty` module (Linux and macOS; none on Windows, where these scenarios are skipped with the reason); research 30 read the pty until the child had gone without losing bytes, on Linux and macOS, and `pyte` followed what Rich writes (22 O4). `once java has begun its checkpoint` leaves one window open: the fake logs its marker after the 2195 line is in tlaup's pipe, not after tlaup has read it, and a signal that lands while the line is still in the pipe or the launcher's queue is sent on at once (G3, finding FC8), so the deferral scenario would fail. The fake's writing of the `.tmp` files and the step's wait for the log line come between, which should be far longer than tlaup's read of one line; not tried. If the scenarios turn out flaky, the fake can wait until its stdout pipe is empty before it logs the marker (on Linux `FIONREAD` gives the unread byte count of a pipe; not tried), which leaves only the queue; adding a seam to the product is not the answer. Real-process scenarios need a few hundred milliseconds each for the interpreter to start; they are counted in tens, not hundreds, which is why in-process stays the default. The Typer facts above hold on every Typer from 0.22.0 to 0.29.2 (research 23); the bound is 0.27.2.

## T6 Download and GitHub failure tests

Roadmap: "Download and GitHub failure modes are tested." Plain pytest in `tests/unit/versioning/`, against the real client and downloader ([12 V5](12-tools-and-downloads.md#v5-download-and-verify), [V7](12-tools-and-downloads.md#v7-github-client)) with `responses`. Each asserts the error type and the state of the store afterwards, never the message.

| Case | Expectation |
| --- | --- |
| Connection drops mid-stream | `NetworkError`; no build folder; no temporary file left; a previous build of that tag untouched. |
| Body shorter than `Content-Length` or than the asset's size | `DownloadVerificationError`; same state. |
| Body longer than the asset's size | Reading stops at the size; `DownloadVerificationError`; same state. |
| Body is an HTML page (a proxy) | Verification fails on "not a zip"; same state. |
| Valid zip without `tlc2/TLC.class` | Verification fails; same state. |
| Digest differs from the release's `digest` | One fresh lookup and one retry; then `DownloadVerificationError`. |
| Digest given in upper case; digest with a prefix other than `sha256:` | The first compares equal; the second is treated as no digest, and the size check still applies ([12 V5](12-tools-and-downloads.md#v5-download-and-verify)). |
| Asset answers 404 once, then 200 (the upload gap of research 7) | Installed after one retry; the injected sleep was asked for 2 seconds. |
| Digest differs once, then matches (upstream replaced the asset) | Installed; the build recorded is the second one. |
| 403 with rate-limit headers; 429 | `RateLimited` carrying the reset time; no retry storm (at most the configured attempts, using the injected sleep). |
| 404 on a tag | `VersionNotFound`. |
| 500, then 200 | Succeeds after one retry. |
| Response is not JSON; JSON is an object where a list is expected | `RemoteDataError`. |
| Release without `tla2tools.jar` | Not offered as installable; asking for it is `VersionNotFound` with the reason. |
| Two pages of releases (Link header; the `releases-paged` recording, since the real list is one page) | Both read; the request for page 2 uses the URL from the header. |
| A `Link` header whose next address is on another host or is not `https` | Not followed; `RemoteDataError`. |
| List shuffled | The same "stable" is chosen (research 8). |
| All releases are prereleases | "stable" is `VersionNotFound`; never the first entry. |
| Redirect to `http://` | Refused before the request is made. |
| Token set | Sent to `api.github.com` and to a host listed in `tool.token_hosts`, and to no other (a repository setting naming another host gets no token; decision D41); absent from the asset download and from every log line and `--debug` output. |
| `--force` reinstall fails | The old build is still there and still pinned. |
| Two installs of one build at once (two threads, a barrier) | One build folder, valid metadata, no error. |

The roadmap's list also names "a tag without a commit". The design reads releases only and takes a build's commit from the jar ([12 V5](12-tools-and-downloads.md#v5-download-and-verify), [V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache)), so no code path reads a tag's commit and the case has no row. The nearest cases that do exist are the release without a jar and the jar whose manifest has no commit ([12 V1](12-tools-and-downloads.md#v1-version-store)).

The rate-limit and paging rows use the recordings research 29 made (T4, top-up); the 429 row is synthetic.

**Rejected.** These cases as feature scenarios: each needs a response built in Python (a body that stops half way, a header on the second of three answers), and a step per shape would double the vocabulary for cases a user never sees as such. Asserting the message text: rule 4 of T12.

**Depends on.** T2, T4 (the `github` fixture); V5, V7 and V8 for the code under test. **Risks.** The table follows the design of 12, not the present code, so a row can turn out to name a state the finished code cannot reach; such a row is removed with a line in the pull request saying why, not bent to fit. The short-body row asserts that tlaup catches `requests.exceptions.ChunkedEncodingError` and reports the download as failed (`DownloadVerificationError`), which is what research 30 found `responses` and `requests` give (T4, top-up).

## T7 Property tests for values

Roadmap candidate, accepted. `tests/parse/test_values_props.py` with Hypothesis.

A strategy builds a value tree (integers, booleans, strings with escapes, model values, sets, sequences, records, functions with non-string keys, intervals, nested to depth 4) and a printer writes it in TLC's notation. Properties:

- `parse_value(print(v)) == v` for every generated value. Equality is tree equality: `Value.text` is declared so that it is not compared ([10 P7](10-parser.md#p7-values)), since the strategy's tree has no source text.
- **Whitespace does not matter**: inserting newlines and indentation at any token boundary of the printed text gives the same parse. This stands in for TLC's own line wrapping, whose exact rules are not known; the real wrapped values in the golden files cover the rest.
- **Total**: for any text at all (`st.text()`), `parse_value` returns without raising, and the result's `text` equals the input.
- A parse that fails anywhere yields a single value of kind `raw`, never a partly parsed tree.

Hypothesis runs with a fixed profile in CI (`derandomize=True`, 200 examples) so a failure is reproducible; the example database is not committed.

One more property, for framing, lives beside these in `test_framing_props.py` ([10 P4](10-parser.md#p4-framing-and-never-losing-output)): for any sequence of lines drawn from start markers, end markers (with small codes, so that they often match), markers with text before or after them, malformed markers and plain text, writing the framer's output back with `render_framed` gives the input exactly. The design agent ran the framing rules as a script over 200,000 such sequences on 2026-11-15 without a failure.

**Rejected.** Generating whole TLC outputs: the printer would be a second implementation of TLC's formatting, and the golden files already are the real one. Comparing `Value.text` in the round trip: it would pin spacing the parser is meant to ignore.

**Depends on.** P7 for values, P4 for framing; `hypothesis` as a development dependency. **Risks.** The printer and the parser are written by the same hands and can share a misreading of TLC's notation; the golden values are the check from outside. A strategy that rarely produces a deep or odd value passes without having tested much; the first run prints Hypothesis's statistics and the pull request quotes them.

## T8 Expected-output files

One helper for every comparison against a stored file:

```python
def assert_matches(actual: str, expected: Path, request) -> None
```

It compares after normalising line endings, shows a unified diff on mismatch, and rewrites the file when pytest runs with `--update-expected`. Used for: the full parsed results (T3), reporter output ([22 O6](22-reporters.md#o6-snapshot-tests)), the printed Java command, `tool list` tables, and the generated CLI reference ([23 C5](23-command-layout.md#c5-help-and-the-cli-reference)). Expected files live beside the tests that use them, under `expected/`, with one exception: a golden case's full expected result, `<case>.json`, sits beside its `.out` in the golden folder, where T3's layout puts it, so that a capture and its result are read and moved together. (Stage 4 review, 2026-11-24: the exception, where T3 and this section disagreed; a clerical item of the packages index.)

A file updated with `--update-expected` is a change to review, not a formality: the reviewer of the pull request reads the diff of every expected file.

**Rejected.** A snapshot library (T1). Normalising volatile parts (times, paths) inside the helper: what is volatile is removed where it arises, by the injected clock and the `replace` field of the fake `java`, so that an expected file shows exactly what a user would see.

**Depends on.** Nothing. **Risks.** An update run rewrites every file a changed test touches, and a wrong change can ride along with a wanted one; the rule above is the only guard, which is why the helper prints the list of files it rewrote.

## T9 Integration tests

Roadmap: "Integration tests: registered markers with strict checking; working skip guards; the jar supplied through a fixture or an environment variable; assertions on parsed results."

**Design.**

- Marker `integration`, registered; `--strict-markers` and `--strict-config` are on. `tests/integration/conftest.py` marks everything in the folder.
- The jars come from `TLAUP_TEST_JARS`, a folder holding `<build>/tla2tools.jar` for one or more builds; a store's tool folder (`<cache>/tool/`, whose entries are `<id>/tla2tools.jar`) has that shape and may be named, as the integration job does ([30 I1](30-ci-and-release.md#i1-integration-job)). A stable jar's tag is read from its folder's `build.json` when there is one, else from the folder's name. Tests are parametrised over the builds found there. Each jar is matched to a golden folder by release line, through the folder's `build.toml` (T3): a jar with a build time uses the rolling folder even when its CalVer is newer, which is the normal case in CI; a jar without one uses the folder of its tag. A jar that matches no folder fails collection with a message naming it, so a third build cannot run silently against the wrong expectations. When the variable is unset or `java` is not on `PATH`, the whole folder is skipped at collection time with the reason, by `pytest.skip(allow_module_level=True)` in the conftest; the current guards test a `MagicMock` and never fire.
- Each test gets its own `TLAUP_HOME`; the jar is installed into it by copying into the store through the store's own API, so no network is used.
- The real `PATH` and `JAVA_HOME` are kept (real `java`, `javac`; T2); sockets stay disabled.
- **The JVM's own folders are moved too.** The JVM does not take `user.home` from `HOME`: the review of 2026-11-15 ran `java -XshowSettings:properties -version` with `HOME` pointing nowhere and it still reported the account's real home. The REPL writes `~/.tlaplus/history.repl` (research 12) and TLC and SANY leave `tlc-*` folders in the temporary folder. So the integration fixture sets `TLAUP_JAVA_OPTS` to `-Duser.home=<test home> -Djava.io.tmpdir=<test tmp>` ([13 J1](13-modules-and-java.md#j1-java-options)). Whether that is enough for every file the tools write was not tried; the integration job ends with the same "nothing appeared in the home folder" check as the unit job, extended to `~/.tlaplus` ([30 I1](30-ci-and-release.md#i1-integration-job)), which is the proof either way.

**What they assert**, through the Python API (`run_tlc(...)` with a `CollectingReporter`, [22 O1](22-reporters.md#o1-reporter-interface)), not through text:

| Test | Assertion |
| --- | --- |
| Every golden case whose spec needs no Java class | The facts of `facts.py` for the case and the jar's release line hold for the live run, and the exit code equals `cases.toml` of the matched folder. |
| A failing spec, a trace, a SANY error, a coverage run | Named in the roadmap; covered by the row above (`violation`, `sany-semantic-error`, `coverage`). |
| `module add` on `docs/examples/QueueModule`, then `tlc queue` | On a build that honours the overrides property: success. On v1.7.4: the warning of [11 R7](11-runner.md#r7-override-modules-that-do-not-load) and the spec's own assertion failure (research 13). |
| A project's own override class: the spec of `tests/fixtures/naming_fixed/` (moved beside these tests), its `TLCOverrides.java` compiled with the real `javac --release 11` into the project's `classes/`, then `tlc` on it | On both builds: success, and the spec's output holds the override's marker, so the class TLC loaded is the project's. v1.7.4 loads it by its fixed name, rolling builds through the property R7 fills (research 13). |
| `module add` on `docs/examples/sequences-ext`, then `tlc` on `docs/examples/spec/SequencesExtTest` | On both builds: success, with the module's `TLCOverrides` loaded (the spec prints that it is). A module with a jar in `lib/` and several TLA+ modules. Until the examples manifest exists; then it becomes one of its entries. |
| `sany` on a good and a bad spec; `pcal` on a copy of a PlusCal spec | Diagnostics with file, line and column; exit codes of D29; the three files `pcal` leaves. |
| `repl` with piped input (builds that have it) | Exit 0 and the value `2` for `1+1`. |
| Signals with the real JVM | Ctrl-C gives 130 and SIGTERM 143 and no `java` process is left. |
| The examples manifest | Each entry of `docs/examples/examples.toml` (documentation track) runs with its expected result. |

The CI job that runs them is [30 I1](30-ci-and-release.md#i1-integration-job). Locally: `uv run poe test-integration`, which prints how to set `TLAUP_TEST_JARS` when it is missing.

(Stage 4 review, 2026-11-24: the rows for a project's own override class and for `sequences-ext`, which the old integration tests covered and this table did not, preserved-behaviour rows R33 and R34; `TLAUP_TEST_JARS` naming a store's tool folder, and `JAVA_HOME` kept, readings of packages 52 to 58.)

**Depends on.** T3, G3, the runner; V1 for copying a jar into the store. **Rejected.** Golden folders and facts keyed by exact build: the rolling jar in CI is always newer than the capture, so nothing would match. Finding the jar under the home folder (today): breaks on macOS and reads the developer's real store. Downloading in a session fixture: needs the network and hides which build ran.

## T10 Coverage policy and pytest settings

Roadmap: "Coverage policy: branch coverage on; a `fail_under` near the current 83 percent; coverage only in the full-suite task; randomised test order; warnings as errors."

```toml
[tool.pytest.ini_options]
addopts = "--strict-markers --strict-config --disable-socket -p no:cacheprovider -m 'not pending'"
testpaths = ["tests"]
norecursedirs = ["tests/integration", "tests/lifeline", "tests/fakes", "tests/fixtures", ".*"]
filterwarnings = ["error"]
markers = [
    "integration: needs Java and real jars (TLAUP_TEST_JARS)",
    "lifeline: needs a real JDK; run by the lifeline job (30 I2), not the unit job",
    "pending: written before the code it tests (03); the work package that builds the code removes the marker",
]

[tool.coverage.run]
branch = true
parallel = true
patch = ["subprocess"]
source = ["tlaup", "tlaup_parse"]

[tool.coverage.report]
show_missing = true
# fail_under: set by the last milestone 2 package, see below
```

`".*"` in `norecursedirs` keeps pytest's default for hidden folders, which a `norecursedirs` list replaces: Hypothesis writes `.hypothesis/` in the repository root even with its database off, and warns when collection meets it, which `filterwarnings = ["error"]` turns into a failed run (found while building 03b, 2026-11-24; low impact, decided by the stage 5 lead).

- `poe test` runs `pytest --cov --cov-report=term-missing`; plain `pytest path::test` runs without coverage.
- **Real processes are counted.** The signal, raw-mode, pipe and terminal scenarios run tlaup as a child process (T5), and those are the paths the roadmap wants covered. `patch = ["subprocess"]` makes coverage measure Python child processes and `parallel = true` gives each its own data file, which `pytest-cov` combines; this needs coverage 7.10.6 or later (pytest-cov 7.1.0 requires it), set as the lower bound of the development dependency. Research 30 tried it (top-up) with pytest-cov 7.1.0 and coverage 7.10.6 and 7.17.3: lines run only in child processes are counted, including a child that ends with 130 after `KeyboardInterrupt`, one that exits 143 from its own SIGTERM handler, and one on a pty; the fake `java`, a Python file outside `source`, is not measured and its stderr stays empty. A child killed by a signal it does not handle, or ending with `os._exit`, loses its data; that is expected and needs no workaround, since tlaup's own signal paths exit through Python. `sigterm = true` under `[tool.coverage.run]` is added only if a test ever lets a child die of an unhandled SIGTERM.
- No `bdd_features_base_dir` setting: with it, `scenarios("features")` would look in `tests/features/features` (pytest-bdd joins the two, by its documentation; not run). Without it the path is relative to the test file.
- New development dependencies from this document: `pytest-bdd`, `hypothesis`, `responses`, `pytest-socket`, `pytest-randomly`, and `pyte` for the terminal steps ([22 O4](22-reporters.md#o4-live-display)). None of the six was installed or run for this design; research 30 then ran `pytest-bdd`, `responses`, `pytest-socket`, `pyte` and the coverage patch as the design uses them (top-up), and their bounds are in [30 B2](30-ci-and-release.md#b2-build-fixes). `hypothesis` was run for the stateful tests of the formal check ([03](03-run-stages-and-specs.md#specs-and-their-tests)); `pytest-randomly` was not run. Neither has a bound designed for it: each takes the locked version as its floor and the next major version as its cap. (Stage 4 review, 2026-11-24: the two bounds, a reading of package 03.)
- **No `fail_under` until the end of milestone 2.** The old tests go at the start of the wave (T11, D62), so the figure falls to almost nothing and climbs back as packages land; a threshold in that window would turn `main` red for a reason no package can fix, and D62 asks of `main` only that it be green. Every full run prints the figure. The last milestone 2 work package measures it and sets `fail_under` to it, rounded down to a whole number; the roadmap asks for "near the current 83", and a figure below 80, where branch coverage and the deleted dead code are expected to leave it, goes to the maintainer instead of being set (a departure, listed in the README). From then on it is never lowered to make a pull request pass. (Stage 4 review, 2026-11-24: the threshold of 80 from the first package could not hold under D62.)
- `pytest-randomly` randomises order on every run and prints the seed.
- `tests/integration` and `tests/lifeline` are excluded from the default run and have their own tasks; the lifeline tests start a real JVM and are the lifeline job's ([30 I2](30-ci-and-release.md#i2-unit-job)), which is why their marker is registered here. (Stage 4 review, 2026-11-24: the `lifeline` marker was missing, a clerical item.)
- `pending` marks the stateful tests of the formal check ([03](03-run-stages-and-specs.md#specs-and-their-tests)), which were written before their code, and the TLC facts of T3, which are written before the parser (the marker's line says "written before the code it tests", which covers both). The marker and its deselection are in today's `pyproject.toml` since 2026-11-18, and `tests/stateful` is in today's `testpaths`; CI runs `uv run poe test` and so follows both. When the last package has removed its marker, the marker and the `-m` option go. Under `filterwarnings = error` six reference-model tests of the formal check fail on `ResourceWarning`; the first testing package fixes them without changing what they check ([03, "Edits settled 2026-11-24"](03-run-stages-and-specs.md#specs-and-their-tests)).
- A third-party deprecation warning that cannot be fixed gets one `ignore` line naming the exact message and the issue it waits on.

**Rejected.** Coverage on every run: it slows the single-test loop and prints a failing total for a partial run. Leaving real processes out of the figure: the signal, pipe and raw paths would then count as untested, and the figure would push towards in-process tests that cannot see them. A per-file threshold: the suite tests through two boundaries, so a file's coverage says little about whether it is tested.

**Depends on.** T5 (which scenarios are real processes). **Risks.** `filterwarnings = error` makes a new deprecation in any dependency fail the suite on the day it is released; the weekly newest-dependencies job ([30 I3](30-ci-and-release.md#i3-newest-dependencies-job)) is where that shows first, and the `ignore` line above is the way out. The coverage figure moves when real-process data is lost for a reason outside tlaup (a child killed by a signal it does not handle, research 30).

## T11 The existing tests

**What there is.** The suite of 0.8.x: `tests/unit/` has 185 test functions in 40 files (207 items collected, counting parameters), `tests/integration/` has 4 in 3 files, and they share their conftests and the fixtures `tests/fixtures/releases.json`, `tags.json`, `naming_fixed/` and `naming_dynamic/`. The triage of 2026-11-15 read every one. They patch names by hand (T2), feed the parser invented TLC output, and assert on mocked calls (T1), so most of them test the old code's shape rather than what a user sees. `tests/stateful/` (the formal check, D46) and `tests/fixtures/research/` (evidence) are newer and not part of it.

**Design: the old tests go early, all at once** (decision D62). The first testing package (03b) deletes every old test file under `tests/unit/` and `tests/integration/`, their conftests, the fixtures `releases.json`, `tags.json` and `naming_dynamic/` (T3), the fixtures T2 removes, and `pytest-mock` (T12 rule 2). `naming_fixed/` stays for T9's project-override row. The folders themselves live on for the new tests (`tests/unit/` for the plain pytest tests, `tests/integration/` for T9).

What the old tests protected is kept as a list of requirements instead: [the preserved-behaviour inventory](preserved-behaviour-2026-11-22.md) lists each behaviour of 0.8.x that a user can observe, and says whether the redesign keeps it, specified or confirmed, or changes it on purpose. Each kept row names an owner package and a test in this document's forms. The owner writes that test, and its pull request names the rows it covers. Package 59, the last of milestone 2, walks the list: for every kept row it names the test that holds it and checks that the test exists and passes. A kept row with no such test is a finding against its owner and holds up the close of the wave. The behaviour the triage found with no test at all (`validate_java_version` raising, "stable" skipping prereleases, an unknown version, the offline and cached states of `tool list`, the trace and its value diff, the stopped state after Ctrl-C, finding override classes) has rows in the list like the rest.

**Between packages.** `main` need only be green, with D62's one exception for CI ([00, "What every package must respect"](00-overview.md#what-every-package-must-respect)). An old command a package breaks is protected by its inventory row, whose test arrives with its owner. The only old command CI runs is the `tlaup tools install` step, which gives the old unit tests a jar; it goes with them in 03b ([30 I2](30-ci-and-release.md#i2-unit-job)). The coverage threshold is not part of "green" in that window (T10).

**Rejected.** *Deleting each old file in the pull request that rewrites what it tests* (this section's design of 2026-11-15). It kept coverage from falling between packages. But about twenty old files patch names with `mocker`, and three of their fixtures stand for GitHub and TLC output; all of these would have stayed until their switch package, and with them `pytest-mock` and a hook against new `mocker` calls (question Q2 of the packages index). Every switch package would also have carried a list of files to delete, plus the edits that keep the old commands working meanwhile. *Porting the old tests to the isolation fixture first*: work on tests whose code is about to go.

**Risks.** From 03b until a kept behaviour's owner lands, nothing tests that behaviour, and a package that edits old code before its owner rewrites it can break it unnoticed. The exposure is largest where code is edited before it is replaced: the classpath (30 and 31 edit `classpath.py` before 33), and the old `tlc` command, which runs on the new store and registry from 29 and 31 until 39 (the inventory's last section). This is accepted with D62. Nothing is released inside the window (D6), and 59's check is where a dropped row shows.

**The development guide changes with the suite.** [`docs/contributing/development.md`](../contributing/development.md) names `tests/unit/` as the default suite in its code map and gives `uv run pytest tests/integration` in its commands. The first testing work package updates both in the same pull request: the folders become `tests/features`, `tests/parse`, `tests/unit`, `tests/integration`, and the integration command becomes `uv run poe test-integration` with `TLAUP_TEST_JARS`.

(Stage 4 review, 2026-11-24: rewritten for decision D62. The old tests are deleted in 03b, not file by file, and the inventory with 59's check takes the place of the per-file tables. This settles question Q2 of the packages index (no `pytest-mock` kept for old files) and corrects the counts, a clerical item.)

## T12 Rules for writing tests

Each is checked in review; rules 2, 3 and 10 are also enforced mechanically.

1. **Test through a boundary.** The command line; the `tlaup_parse` API; a pure function given real files in a temporary folder; a reporter given events and in-memory consoles; or a piece that sits on an edge (the launcher, `run_tlc`, the GitHub client, the run-folder locks), driven with that edge's fake. Anything else, in particular a function in the middle called with hand-built internals of another function, is tested through one of these.
2. **No patching of our own code.** `pytest-mock` is removed from the dependencies in the first testing package, with the old tests that use it (T11, D62), and ruff's banned-API rule (`TID251`) forbids `unittest.mock.patch` in `tests/`. `monkeypatch.setattr`, `setitem` and `delattr` on anything under `tlaup` or `tlaup_parse` are the same thing by another name; ruff cannot tell the target, so a pre-commit check fails on those three calls anywhere in `tests/` outside `conftest.py`, and review covers the conftests. `monkeypatch` stays for the environment and the working folder. Doubles exist only at the three edges of T1. (Stage 4 review, 2026-11-24: no old file keeps `pytest-mock` alive, so no list of exempt files is needed, D62, question Q2.)
3. **Tool output is captured, never typed.** Every piece of message-framed or multi-line TLC, SANY or PlusCal output in a test comes from a file under `tests/parse/golden/`. The exceptions are `synthetic/` and the Hypothesis printer and strategies. A pre-commit check fails on `@!@!@STARTMSG` in any `.py` or `.feature` file under `tests/`. Not covered by the rule, because they are inputs to one function and not tool output: a single TLA+ value given to `parse_value`, a short string given to the markup test of [10 P11](10-parser.md#p11-tlc-text-and-rich-markup), the literal marker text a raw-mode scenario has the fake `java` write to tell stdout from stderr, and the numbered lines of `java prints <n> lines`, which stand for a spec's own printed output. Nor the `PrintT` lines a golden spec prints, which a fact in `tests/parse/facts.py` expects as `output`: they hold the marker text only because the spec prints it, so `facts.py` builds them from a constant rather than spelling the marker (added while building 08a, 2026-11-24).
4. **Assert state and results, not wording.** The exit code, the files, the parsed fields, the arguments Java was given. Wording is checked only through expected files (T8), which are reviewed as a whole; a `contains` step is for one fact that matters (an invariant's name, a path), not for a sentence.
5. **No sleeping, no clock, no modification times, no dependence on order.** A test may wait for a condition with a timeout (a line in the fake's log, text on the terminal); it may not wait for an amount of time. One scenario depends on the real clock by its nature and is the named exception: the live display redrawing while TLC is silent ([22 O4](22-reporters.md#o4-live-display)), which runs for about two seconds. The launcher's grace-period test passes the period as a parameter (half a second) and waits for the kill, not for the time. A second exception (added while building 29a, 2026-11-25, a low-impact choice by the stage 5 lead): the in-process scenarios with `GitHub is unreachable` wait through the GitHub client's real retry delays (1 s, then 2 s), since the commands build the client with `time.sleep` and no seam is allowed; two scenarios, about 6 s in all.
6. **A test must be able to fail.** A pull request that fixes a defect shows the new test failing before the fix (the red run is pasted in the description).
7. **Environment through `monkeypatch` only.** Never assign to `os.environ`.
8. **No module-level state** in test files: no shared runner object, no cached settings.
9. **One fixture, one job.** A fixture that needs another edge's fake asks for it by name; fixtures do not overlap.
10. **In-process unless one of T5's five situations applies.** A command-line scenario runs in-process (`I run "<command>"`) unless it is in one of the five situations of T5, and then it uses the real-process step that situation names; nobody decides case by case. Situations 2 to 4 are visible in the scenario's own words (a pipe, a signal, a terminal step). The other two are not, so the in-process step checks them and fails the scenario, naming the step to use instead:
    - **Passthrough.** After the command, the step reads the fake `java`'s log; a `start` line whose stdout was not a pipe means the command reached `run_passthrough`, and the scenario fails with "this command passes the terminal through; use `as a process`". Under pytest's default capture, tlaup's stdout is a temporary file, so the check holds; with capture switched off and the test run's own output piped, it would not fire, and the scenario would fail on its empty output instead. Not tried. A scenario where passthrough is refused before Java starts (the REPL on v1.7.4, exit 3) has no such line and stays in-process.
    - **Startup-only variables.** Before the command, the step fails if the scenario set, with `the environment variable "<name>" is "<value>"`, a variable the interpreter reads only when it starts: any name beginning with `PYTHON`, and `LC_ALL`, `LC_CTYPE` and `LANG`, which set the encoding of Python's own streams. The list is one constant in the steps module.

    The check sits in the test steps and reads only the fake's log and the scenario's own settings, so the product has no seam for it (rule 2). Added at the stage 3 sign-off, 2026-11-18.

## Order of work

1. Folder overrides (F2), the isolation fixture (T2), the fakes (T4), the pytest settings (T10), deletion of the old tests (T11), the development guide update. No product behaviour changes. This is the early part of milestone 2. (Stage 4 review, 2026-11-24: all the old tests go here, not only the dead ones, D62.)
2. The golden move and `facts.py` (T3), failing. Then the parser work of [10](10-parser.md) makes them pass.
3. The step vocabulary and the first `tools` features (T5), as each area is rewritten. The error mapping inside the application (F10) comes before the first feature that asserts an exit code.
4. Integration tests (T9) with the launcher (G3) and the runner.
