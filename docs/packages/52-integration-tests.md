# 52. Integration tests

Size: L. Suggested model: most capable. Status: ready. One row of T9's table, the examples manifest, waits on the documentation track (`docs/examples/examples.toml` does not exist and has no design) and is not built here.

## Goal

`tests/integration/` is rewritten as [01 T9](../design/01-testing.md#t9-integration-tests) designs it: real Java and real jars supplied through `TLAUP_TEST_JARS`, each jar matched to its golden folder by release line, every test in its own isolated home with the JVM's own folders moved too, and assertions on parsed results and on what tlaup leaves behind. `uv run poe test-integration` runs it locally and refuses to pass with nothing run. The old integration files and the two old naming fixtures are gone. The CI job that runs it is [54](54-integration-job.md).

## Covers

- Roadmap items:
  - "Integration tests: registered markers with strict checking; working skip guards; the jar supplied through a fixture or an environment variable, not found under the home folder; assertions on parsed results, including a failing spec, a trace, a SANY error and a coverage run." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this), line 374). In full: the markers and strict checking are already on from [03](03-test-foundation.md); this package makes the rest true.
  - The integration halves of milestone 1 and 1b items whose other parts are built elsewhere: the signal and lifeline items (mechanism [21](21-java-launcher.md), command [39](39-tlc-command.md)), run folders ([35](35-run-folders.md)), override modules ([34](34-override-check.md), [31](31-module-commands.md)), `sany`, `pcal`, `repl` ([41](41-sany-command.md), [42](42-pcal-command.md), [43](43-repl-command.md)), completion ([47](47-completion.md)), one Java start ([20](20-java-location.md)). Each of those roadmap items is closed by its own package; this one adds the run against a real JVM that the design names under their Tests.
- Design sections:
  - [01 T9](../design/01-testing.md#t9-integration-tests): all of it except the row "The examples manifest" (waits, see Context). The CI job is [30 I1](../design/30-ci-and-release.md#i1-integration-job), package 53.
  - [01 T2](../design/01-testing.md#t2-isolation): the integration folder's own `isolated` fixture ("keeps the real `PATH` and sets the JVM's own folders").
  - [01 T3](../design/01-testing.md#t3-golden-files): "`facts.py` is also used by the integration tests", and the deletion of `naming_fixed` and `naming_dynamic` "once the integration tests are rewritten".
  - [01 T11](../design/01-testing.md#t11-the-existing-tests): "Rewritten as T9: all three integration files and their conftest".
  - The "Integration" parts of the Tests of: [11 R2](../design/11-runner.md#r2-signals), [11 R3](../design/11-runner.md#r3-non-utf-8-output), [11 R4](../design/11-runner.md#r4-spec-cfg-and-working-folder), [11 R6](../design/11-runner.md#r6-run-folders), [11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load), [11 R8](../design/11-runner.md#r8-passthrough-and-workers), [13 J3](../design/13-modules-and-java.md#j3-one-java-start), [20 G3](../design/20-groundwork.md#g3-java-launcher) (the signal scenarios with the real JVM, the REPL under a pseudo-terminal with the agent), [21 S1](../design/21-other-tools.md#s1-sany), [21 S2](../design/21-other-tools.md#s2-pcal), [21 S3](../design/21-other-tools.md#s3-repl), [23 C3](../design/23-command-layout.md#c3-completion) (the bash script sourced in bash, the zsh and fish syntax checks).

## Depends on

- [08](08-golden-facts.md): `tests/parse/facts.py` (`Fact`, `facts_for(case, line)`) and `tests/parse/drive.py` (`golden_root`, `build_folders`, `line_of`, `cases_of`). Through 08, [07](07-golden-files.md)'s golden folders with `build.toml` and `cases.toml`, and the specs under `tests/parse/golden/specs/`.
- [23](23-tool-store.md): `ToolStore.add`, `ToolStore.pin`, `Build`, `Source`, to copy a jar into each test's store; [22](22-version-spec-and-jarinfo.md)'s `read_jar` through it.
- [39](39-tlc-command.md): the `tlc` command on the new runner, and with it `resolve_tlc_invocation` and `build_tlc_command` ([33](33-tlc-invocation.md)), `run_tlc` and `RunOutcome` ([37](37-run-tlc.md)), `CollectingReporter` ([36](36-reporter-interface.md)), the launcher and the lifeline in every JVM ([21](21-java-launcher.md), [06](06-lifeline-agent.md)), run folders ([35](35-run-folders.md)), the override check ([34](34-override-check.md)), spec resolution ([32](32-spec-resolution.md)), one Java start ([20](20-java-location.md)). 39 also deletes the old integration files if they are still there.
- [31](31-module-commands.md): `tlaup module add`, for `docs/examples/QueueModule`.
- [41](41-sany-command.md): `resolve_tool_invocation`, `build_tool_command`, `run_sany`, `SanySink`, `SanyOutcome`.
- [42](42-pcal-command.md): `run_pcal`, `PcalSink`, `PcalOutcome`.
- [43](43-repl-command.md): `tlaup repl`.
- [45](45-cache-commands.md): `tlaup cache clean <run-id>`, for R6's test with a killed tlaup.
- [47](47-completion.md): `tlaup completion bash|zsh|fish` and the completers, for C3's integration check.
- [03](03-test-foundation.md): the pytest settings (the `integration` marker, `--strict-markers`, `--disable-socket`, `tests/integration` in `norecursedirs`), the `test-integration` task, the `no-new-mocker` hook's list; [18](18-feature-harness.md): the real-process runner in `tests/steps/_process.py` (`sys.executable -m tlaup`, SIGINT reset to its default in the child, T5) and the terminal runner `run_on_terminal` in `tests/steps/_terminal.py`. Both are written for the fakes' `PATH`; called from this folder they run with the real one, which is what the fixture here sets.

Changed from the draft (39, 41, 42, 43, 31): 08, 18 and 23 are added because the tests use them directly (all three are below 39 already); 47 for the bash check C3 hands to the integration tests; 45 for the `cache clean` refusal of R6.

## Files

Creates:

| File | What |
| --- | --- |
| `tests/integration/conftest.py` | The collection guard and the jar discovery (below), the `integration` marker on every item, the `isolated` fixture of this folder, the `live_build` fixture (one jar copied into the test's store and pinned), and small helpers to run tlaup as a real process and find the JVM it started. |
| `tests/integration/test_golden_live.py` | The facts of every golden case a live run can reproduce, on the live result. |
| `tests/integration/test_tools.py` | `sany`, `pcal`, `repl`, and the REPL under a pseudo-terminal with the lifeline. |
| `tests/integration/test_modules.py` | `docs/examples/QueueModule`, then a run of `docs/examples/spec/queue.tla`. |
| `tests/integration/test_runner.py` | R3 encoding, R4 cfg rows, R6 run folders, R8 `--workers auto`, J3's remembered Java check. |
| `tests/integration/test_signals.py` | The six signal scenarios with the real JVM, and tlaup killed with SIGKILL. |
| `tests/integration/test_completion.py` | C3's shell checks (Linux job only). |
| `tests/integration/specs/` | The few TLA+ specs these tests need that no golden spec provides: one that runs until stopped, one whose distinct-state count is known by construction and that runs past one checkpoint, one whose trace holds `é` and `日`, the cfg layouts of R4. A TLA+ spec is an input, not tool output, so T12 rule 3 does not apply; each file starts with a comment saying what it is for. |

Changes:

- `pyproject.toml`: the `test-integration` task (03 made it `pytest tests/integration --no-cov`) becomes a small script task that refuses to run with nothing to run (Context, "The task"). One task entry.
- `.pre-commit-config.yaml`: the `no-new-mocker` hook's `exclude` loses the lines of the old integration files. If that empties the list, the hook goes and `pytest-mock` leaves the development dependencies (`pyproject.toml`, `uv.lock`), as [03](03-test-foundation.md) says of the package that removes the last line.
- `docs/contributing/development.md`: the integration command with `TLAUP_TEST_JARS` and what the folder must hold; drop the sentence 03 wrote that the folder holds the old tests until this package.

Deletes:

- `tests/integration/test_tlc_integration.py`, `test_naming.py`, `test_community_modules.py` and the old `conftest.py`, if [39](39-tlc-command.md) has not already deleted them (39 deletes them when it removes the modules they import). `tests/integration/__init__.py` stays if the folder needs it for imports; the worker decides and says so.
- `tests/fixtures/naming_fixed/` and `tests/fixtures/naming_dynamic/` (T3).

Shared files: `pyproject.toml` with every package that changes a task or a dependency (one task line here); `.pre-commit-config.yaml` with [57](57-repo-hygiene.md) and [58](58-lint-rules.md) (different hooks); `docs/contributing/development.md` with [53](53-ci-workflows.md) and 57 (different sections). Nothing under `src/` changes.

## Interfaces

Provides (all written by stage 4 from T9's words; a worker may adjust a name if the behaviour and the tests stay, and says so in the pull request):

```python
# tests/integration/conftest.py
@dataclass(frozen=True)
class TestJar:
    build: str          # the name under TLAUP_TEST_JARS: the folder's name, or build.json's "name" in a store folder
    jar: Path           # <TLAUP_TEST_JARS>/<folder>/tla2tools.jar
    info: JarInfo       # read_jar(jar)                                             (22)
    golden: Path        # the tlc/ golden folder matched by release line (T3, T9)
    line: str           # "stable" or "rolling", line_of(golden)                    (08)

def find_test_jars(root: Path) -> list[TestJar]      # at collection; raises a collection error naming a jar that matches no folder

@dataclass(frozen=True)
class Isolated:                                       # the same shape as tests/conftest.py's (03)
    home: Path; work: Path; paths: AppPaths
    tmp: Path                                         # the JVM's java.io.tmpdir

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch) -> Isolated       # replaces the root fixture for this folder (T2)

@pytest.fixture
def live_build(request, isolated) -> Build            # parametrised over the found jars; copied into the store and pinned
```

**Jar discovery** (T9). `TLAUP_TEST_JARS` names a folder; every direct subfolder whose name does not start with a dot and which holds `tla2tools.jar` is one build. That shape covers both a hand-made folder (`<root>/v1.7.4/tla2tools.jar`) and the store's own tool folder, which the integration job passes ([54](54-integration-job.md); there the subfolders are build ids such as `v1.7.4-<12 hex digits>` beside `pin`, `.lock` and `.tmp/`, which are skipped). Each jar is matched to a folder of `tests/parse/golden/tlc/` through `build.toml`: a jar whose `JarInfo.built_at` is set takes the one folder whose `line` is `rolling`, whatever its CalVer; a jar without one takes the stable folder whose `tag` equals the jar's name (`TestJar.build`, cut at the first `-` followed by twelve hexadecimal digits when it is a store id, or the `name` in `build.json` beside the jar). A jar that matches no folder fails collection with a message naming the jar and the folders there are, so a third build cannot run silently against the wrong expectations. The variable is read at collection time, before any fixture runs (the `isolated` fixture removes every `TLAUP_*` variable).

**Skip guards.** When `TLAUP_TEST_JARS` is unset, or `java` is not found (through `JAVA_HOME`, then `PATH`, as tlaup finds it), the conftest calls `pytest.skip(reason, allow_module_level=True)` and the whole folder is skipped with the reason. The guard tests the real condition, not a fixture value. The task refuses that case itself (Context).

**The `isolated` fixture of this folder** does what the root fixture does (03, T2), with these differences:

- `PATH` stays the real one: real `java`, `javac`, `bash`, `zsh`, `fish`, `taskset`, `pgrep`.
- `JAVA_HOME` stays as it is, so the tests run the Java of the CI cell. [30 I1](../design/30-ci-and-release.md#i1-integration-job) says the job "keeps the `JAVA_HOME` that `setup-java` sets, so the tests run the Java of the cell and not the one the macOS `/usr/bin/java` stub would pick"; T2's list of variables the fixture removes includes `JAVA_HOME`, and its sentence about this folder names only `PATH` (reported to the index as a clerical gap; this package keeps `JAVA_HOME`).
- `TLAUP_JAVA_OPTS` is set to `-Duser.home=<home> -Djava.io.tmpdir=<tmp>`, both under `tmp_path` (T9: the JVM takes `user.home` from the system, not from `HOME`; the REPL writes `~/.tlaplus/history.repl`, and TLC and SANY leave `tlc-*` folders in the temporary folder). A test that adds its own JVM options adds them through `TlcRequest.java_opts` or `--java-opt`, which come after the variable ([13 J1](../design/13-modules-and-java.md#j1-java-options)).
- `TLAUP_TOOL_REPOSITORY` points at the closed local port, as in the root fixture; sockets stay disabled. No test uses the network: the jars are copied in.
- No fakes are written, and `tests/fakes` is not on `PATH`.

**`live_build`.** `ToolStore(isolated.paths, now=...).add(jar, info, name=<"rolling" or the tag>, prerelease=<line == "rolling">, source=Source(kind="local", url=jar.as_uri(), asset_id=None, asset_updated_at=None, digest_checked=False))`, then `pin`. `Source.kind` is `"github-release"` in the first wave ([12 V1](../design/12-tools-and-downloads.md#v1-version-store)); a copied jar did not come from a release, so `"local"` is written by stage 4. If the store refuses a kind it does not know, use `"github-release"` with the jar's file address and say so in the pull request. Parametrised with the id `TestJar.build`, so every test that asks for it runs once per jar found.

Consumes: `read_jar`, `JarInfo` (22); `ToolStore`, `Build`, `Source` (23); `TlcRequest`, `resolve_tlc_invocation`, `build_tlc_command` (33); `run_tlc`, `run_tlc_raw`, `RunOutcome` (37); `CollectingReporter` (36); `resolve_tool_invocation`, `build_tool_command`, `run_sany`, `SanySink` (41); `run_pcal`, `PcalSink` (42); `facts_for`, `golden_root`, `build_folders`, `line_of`, `cases_of` (08); `AppPaths` (02); `tlaup.context.reset()` (02); the real-process and pseudo-terminal helpers of 18. The commands `tlaup module add` (31), `tlaup repl` (43), `tlaup cache clean` (45), `tlaup completion` (47), `tlaup tlc` (39).

## Tests that must pass

All in `tests/integration/`, marked `integration` by the conftest, plain pytest, run by `uv run poe test-integration` with a JDK and `TLAUP_TEST_JARS`. Each test that takes `live_build` runs once per jar. "Both builds" means: on each of the two supported builds when both are given, which in CI is one build per job ([54](54-integration-job.md)). The Python API is used where T9 says so (`run_tlc` with a `CollectingReporter`, `run_sany`, `run_pcal`); tlaup runs as a real process where the command passes the terminal through or a signal must reach a process (T5's situations 1 and 3); otherwise the command runs in-process with `CliRunner`.

**T9's table.**

| Test | Assertion | Form |
| --- | --- | --- |
| `test_golden_live.py::test_case_live` | For every case of the matched folder's `cases.toml` that a live run can reproduce (Context, "Which golden cases run live"): every fact of `facts_for(case, line)` holds for `RunOutcome.result`, and `RunOutcome.exit_code` equals the case's `exit` where `cases.toml` has one. Parametrised per case, with the id `<build>/<case>`. | `run_tlc` with a `CollectingReporter`, on a copy of `golden/specs/` in the work folder |
| `test_golden_live.py::test_named_cases_run` | `violation`, `sany-semantic-error` and `coverage` are among the cases run live on every build (T9: "a failing spec, a trace, a SANY error, a coverage run ... covered by the row above"), so a skip rule cannot drop them unnoticed. | plain |
| `test_golden_live.py::test_skip_table` | Every entry of the skip table names a case that exists in some `cases.toml` and has a reason. | plain |
| `test_modules.py` | `tlaup module add <copy of docs/examples/QueueModule>`, then `tlaup tlc queue` on a copy of `docs/examples/spec/`: on a build that honours the overrides property (`overrides_property` in `Build.capabilities`), success (exit 0, verdict success). On v1.7.4, the warning of [11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load) in `RunOutcome.warnings` and the spec's own assertion failure in the result (research 13, as R7 restates it). The add is in-process; the run is `run_tlc`. | `CliRunner`, then `run_tlc` |
| `test_tools.py::test_sany_good_and_bad` | `run_sany` on a good spec gives no diagnostic and exit 0; on a spec with a semantic error and on one with a parse error, diagnostics with file, line and column, and exit 150 (D29). | `run_sany`, collecting sink |
| `test_tools.py::test_pcal_copy` | `run_pcal` on a copy of a PlusCal spec: exit 0, and the three files of [21 S2](../design/21-other-tools.md#s2-pcal) (the rewritten `.tla`, `X.old`, `X.cfg`) appear. | `run_pcal` |
| `test_tools.py::test_repl_piped` | Builds that have the `repl` capability: `tlaup repl` with `1+1` on stdin prints `2` and exits 0; nothing appears under the test's real-home stand-in, since `user.home` is moved. Builds without it: skipped with the reason (the refusal with exit 3 is 43's feature scenario). | real process |

The examples manifest row is not written (Context).

**From the other sections.**

| Test | From | Assertion | Form |
| --- | --- | --- | --- |
| `test_tools.py::test_sany_streams_and_modules` | [21 S1](../design/21-other-tools.md#s1-sany) | Real SANY, both builds: a spec that extends a module that does not exist gives the missing-module diagnostic, and on v1.7.4 the `File does not exist` line, which v1.7.4 writes to stderr, is in the result (the one pipe of S1 keeps it); a spec that extends a registered module (registered by `tlaup module add` first) parses with no error; a spec beside which a module `M.tla` lies, while another `M.tla` lies in the starting folder, is checked against the spec's own (a diagnostic only one of the two can cause tells which). | `run_sany` |
| `test_tools.py::test_pcal_existing_cfg` | [21 S2](../design/21-other-tools.md#s2-pcal) | On a copy of a PlusCal spec, both builds: an existing `X.cfg` with the translator's marker line keeps the lines after the marker; an existing `X.cfg` without one keeps the user's lines under a new marker and loses the generated `SPECIFICATION` line ([42](42-pcal-command.md) restates research 12's finding). | `run_pcal` |
| `test_tools.py::test_repl_on_a_terminal` | [20 G3](../design/20-groundwork.md#g3-java-launcher), last sentence of "The lifeline, with a real JVM" | On a pseudo-terminal, `tlaup repl` (whose JVM carries the lifeline agent) still reads a line from stdin: `1+1` typed into the terminal shows `2`. Builds with `repl` only; Linux and macOS. | real process, pty |
| `test_runner.py::test_non_ascii_output` | [11 R3](../design/11-runner.md#r3-non-utf-8-output) | A spec whose trace holds `é` and `日`, run with `LC_ALL=C` in the environment on both builds: both characters are in the parsed values (the launcher's three encoding options work). The same characters in a comment of a PlusCal spec are in the `.tla` byte for byte after `run_pcal`. | `run_tlc`, `run_pcal` |
| `test_runner.py::test_cfg_rows` | [11 R4](../design/11-runner.md#r4-spec-cfg-and-working-folder) | For each layout of R4's unit test (rows F1 to F14, built as [32](32-spec-resolution.md) builds them), real TLC on both builds reads the cfg that was validated: each layout's cfg sets a constant to a value of its own and the spec prints it, and the test asserts the printed value. Research 24's link rows (R1 to R10) on Linux and macOS, skipped with the reason where a link cannot be made. | `run_tlc` |
| `test_runner.py::test_no_leftovers_rolling` | [11 R6](../design/11-runner.md#r6-run-folders) | On a rolling build, a real violation leaves nothing under `paths.runs` and no `_TTrace_` file beside the spec. On v1.7.4, the command built has no `-noGenerateSpecTE`. | `run_tlc` |
| `test_runner.py::test_keep_and_resume_exact` | [11 R6](../design/11-runner.md#r6-run-folders), D52, D54 | A run of the known-count spec with `-checkpoint 1 -workers 2` under `--keep`, both builds, is interrupted (SIGINT to tlaup) after its first complete checkpoint (`queue.chkpt` and `vars.chkpt` in TLC's folder); the folder is kept; running the printed resume command finishes with the distinct-state count the spec has by construction, which is the count of a run never stopped. This also checks that the `-fp` and `-seed` tlaup passes are accepted by both builds ([33](33-tlc-invocation.md)'s range of `-seed`). | real process |
| `test_signals.py::test_sigkill_leaves_no_java` | [11 R6](../design/11-runner.md#r6-run-folders), [20 G3](../design/20-groundwork.md#g3-java-launcher), D51 | tlaup killed with SIGKILL during a real parsed run of the spec that runs until stopped: no `java` process it started is alive five seconds later. On Linux and macOS, while that JVM is still alive, `tlaup cache clean <run-id>` (a second tlaup) is refused (code 5), because the JVM holds the run's lock. | real process |
| `test_runner.py::test_workers_auto_one_cpu` | [11 R8](../design/11-runner.md#r8-passthrough-and-workers) | `tlaup tlc Spec --workers auto` started under `taskset -c 0`: the start message reports one worker, both builds. Linux only (`taskset`), skipped elsewhere with the reason. | real process |
| `test_runner.py::test_java_check_remembered` | [13 J3](../design/13-modules-and-java.md#j3-one-java-start) | After one real run, `paths.java_cache` holds an entry for the real `java`; a second run leaves the file as it was (content and `os.stat` unchanged). | `CliRunner` |
| `test_signals.py` (six) | [11 R2](../design/11-runner.md#r2-signals), [20 G3](../design/20-groundwork.md#g3-java-launcher), T9 row "Signals with the real JVM" | With the spec that runs until stopped, in parsed and in raw mode: SIGTERM to tlaup gives 143; one SIGINT gives 130; two SIGINTs give 130 and no `Traceback` on stderr; in every case no `java` process tlaup started is left. The signal goes to the tlaup process alone. | real process |
| `test_completion.py::test_bash` | [23 C3](../design/23-command-layout.md#c3-completion) | The script `tlaup completion bash` prints is sourced in a non-interactive `bash`, and the function it defines is called with `COMP_WORDS` and `COMP_CWORD` set as bash would set them for `tlaup tool pin `; `COMPREPLY` holds the installed build. Linux only. | real process (`bash -c`) |
| `test_completion.py::test_zsh_fish_syntax` | [23 C3](../design/23-command-layout.md#c3-completion) | `zsh -n` and `fish --no-execute` accept the scripts, each when its shell is on `PATH`, else skipped with the reason. Linux only. | real process |

Old test files deleted: the three integration files and their conftest of [01 T11](../design/01-testing.md#t11-the-existing-tests) ("Rewritten as T9"), unless 39 already did. No stateful test applies; no `pending` marker is removed here.

## Changelog

None. Tests only.

## Context for the worker

**State of `main` when this starts.** Every command group is switched: `tlc` (39), `tool` (29), `module` (31), `sany`, `pcal`, `repl` (41 to 43), `cache` (45), `completion` (47). The old runner and parser are gone. `tests/integration/` holds either nothing but what 03 left (the old files and a conftest with the old fixtures and a do-nothing `isolated`) or nothing at all, depending on whether 39 deleted the old files. The golden folders, `facts.py` and `drive.py` exist, and the facts' `PENDING` tuple should be empty (package 13 emptied it); if a pattern is left, the facts it matches are not run live either, and the pull request says which.

**Which golden cases run live** (T9: "every golden case whose spec needs no Java class"; [07](07-golden-files.md)'s `cases.toml` keys). A case is run live unless one of these rules leaves it out, each from a key of `cases.toml`:

- it has no `spec` (`version-bad-option`, `tool-noargs`): `run_tlc` needs a spec;
- `plain = true`: not parsed, only replayed by raw-mode scenarios;
- it has `java_sources` or `classpath`, or its `jvm_options` name an override class: its spec needs a Java class (research 13's override cases, research 28's Java 11 cases);
- it has `stopped` (`checkpoint-run`; `generate-success` on rolling, ended by the capture driver with 137) or `recover_from` (`checkpoint-recover`): a live run cannot reproduce how the capture ended.

The rest run with `args` as TLC's extra arguments (`TlcRequest.extra_args`), `jvm_options` as `TlcRequest.java_opts`, and `cwd` where given. A case with no `exit` (research 2's three) has its facts checked and no exit code compared.

Beside the rules, one table in `test_golden_live.py`, `LIVE_SKIP: dict[str, str]`, names the cases a live run cannot reproduce for a reason the keys do not carry, each with that reason: `tool-oom` (exhausting a 64 MB heap depends on the JVM and the machine), and any case whose facts hold only for the random seed of the capture (simulation and `-generate` runs, since tlaup passes a seed of its own). A case enters the table only for such a reason. A fact that fails on a live run for any other reason is a finding: upstream changed its output and the answer is a new capture, never a weaker fact or a skip (T3, Risks). The pull request lists every entry of the table and why.

The specs are copied from `golden_root() / "specs"` into the test's work folder before the run, so that what TLC writes beside a spec (v1.7.4 writes `_TTrace_` files, R6) never lands in the repository. `docs/examples/` is copied the same way for `test_modules.py`.

**Release line, never exact build** (T3, T9). The rolling jar in CI is always newer than the capture, so it is checked against the rolling folder's facts and exit codes. A fact that fails there means upstream changed; the weekly run of [54](54-integration-job.md) is meant to show it.

**Finding the JVM a real tlaup started**, for "no `java` process is left": while tlaup runs, `pgrep -P <tlaup pid>` lists its children (Linux and macOS; written by stage 4, the design names no method). The test keeps that process id and, after tlaup has ended, asserts the process is gone (`os.kill(pid, 0)` raises `ProcessLookupError`), waiting up to the stated time. Waiting is for a condition with a timeout (T12 rule 5): the moment to send a signal is "TLC has created its timestamped folder under the run's metadir", which is a file the test can see, not a sleep and not a line of TLC text. The real-process helper of 18 resets SIGINT to its default in the child (T5); use it, since a CI shell may start the test run with SIGINT ignored.

**The `cache clean` refusal** ([11 R6](../design/11-runner.md#r6-run-folders), D51). After the SIGKILL, the JVM ends within about two seconds by its lifeline, and holds the run's lock until then. The test runs `cache clean <run-id>` in-process at once, and asserts the refusal only when the JVM was alive both before and after the command (checked as above). If the JVM was already gone before the command ran, the attempt is repeated with a new run, up to three times, and the test then fails naming the timing. Say in the pull request how often the repeat was needed.

**The known-count spec and `-checkpoint 1`.** TLC's `-checkpoint` takes minutes, so the resume test runs at least a minute per build. The spec's state space is a product of bounded counters whose size is known by construction (for example `(N+1) * (M+1)` states), sized so that a run lasts a few minutes on a hosted runner; comparing with that number replaces a second, never-stopped run. With `-workers 2`. The test waits for both `queue.chkpt` and `vars.chkpt` in TLC's folder (D52's completeness rule), then sends SIGINT; the kept folder and its resume command come from `run.json` and tlaup's stderr note (35, 39).

**The spec that runs until stopped**: an unbounded counter, so TLC never ends by itself; used by the signal tests and the SIGKILL test. It must not run out of memory before the signal: a counter adds one state per step, which is slow growth.

**The task** (`uv run poe test-integration`). T9: it "prints how to set `TLAUP_TEST_JARS` when it is missing". Written by stage 4: it also exits non-zero then, and when the folder holds no jar or no `java` is found, instead of letting pytest skip the folder and pass, so that a misconfigured CI job cannot be green with nothing run ([06](06-lifeline-agent.md) applies the same rule to the lifeline job). A plain `pytest tests/integration` keeps the skip with its reason. Naming the folder explicitly overrides `norecursedirs`: tried with pytest 9.2.0 on 2026-11-21, `pytest tests/integration` collected a test in a folder listed there. The task passes `--no-cov` (03) and runs with `-m integration` only if needed; `addopts` already deselects `pending`.

**The examples manifest row** (T9: "Each entry of `docs/examples/examples.toml` (documentation track) runs with its expected result"). The manifest does not exist; the documentation track's examples item ([roadmap, line 496](../roadmap.md#documentation-track-parallel-start-with-milestone-1)) writes it, and [design 40](../design/40-later-milestones.md#what-to-check-before-the-second-wave-designs-this) sketches its format (spec, cfg, expected outcome word, expected state counts, following the tlaplus/Examples manifest). No design says more. Do not write the manifest or a test for it; the row is built with the manifest, by whoever builds that item.

**Platform rules (D15).** No Windows CI. Signals through `hasattr(signal, ...)`; `pgrep`, `taskset`, ptys and links skipped with a reason where the system lacks them; `pathlib` and `os.pathsep` throughout.

**Network.** None. `--disable-socket` stays on; the jars are copied, not downloaded. A test that needed the network would be wrong here.

**`no-new-mocker`.** The old integration files are on 03's list of files that may still use `mocker`. Remove their lines. If the list is then empty, remove the hook and `pytest-mock` too (03's rule); otherwise the package that empties it does, and [59](59-closing.md) checks.

## Done when

- `uv run poe test-integration` passes locally with a JDK and `TLAUP_TEST_JARS` holding both supported builds (v1.7.4 and the current rolling build); the pull request says on which systems and Java versions it was run, how long it took, and which tests were skipped there and why.
- `uv run poe test-integration` with the variable unset exits non-zero and prints how to set it; `uv run pytest tests/integration` with it unset skips the folder with the reason.
- A jar that matches no golden folder fails collection with a message naming it (tried once by hand; say so).
- `uv run poe lint`, `uv run ruff format --check .` and `uv run poe test` pass; CI is green (the integration job itself is 54).
- No file under `tests/integration/` or `tests/fixtures/naming_*` from before is left.
- The skip table is listed in the pull request with a reason per case.

## Out of scope

- The CI job, its matrix, the cache, the token and the schedule: [54](54-integration-job.md).
- The examples manifest and its row (above): documentation track.
- The lifeline tests that start `java` by hand: [06](06-lifeline-agent.md), run by [53](53-ci-workflows.md)'s lifeline job.
- Running the TLA+ specs of `specs/` in the integration job: "a later step and not part of this plan" ([03](../design/03-run-stages-and-specs.md#specs-and-their-tests)).
- Interactive completion in zsh and fish: checked by hand once before the release ([23 C3](../design/23-command-layout.md#c3-completion), Risks), not here.
- v1.7.4's shared temporary copies of library modules ([21 S1](../design/21-other-tools.md#s1-sany), a known gap postponed by research 27): do not try to test or fix it.
- Any change to product code. A live run that shows a defect is reported against the package that owns the code.

## Risks

- From T9: whether moving `user.home` and `java.io.tmpdir` is enough for every file the tools write was not tried; the integration job's clean-home check ([54](54-integration-job.md)) is the proof either way.
- From T3: a rolling build newer than the capture can change its output; then a fact fails on the live run and `main` turns red with no change of ours (accepted, roadmap risks).
- From the cut: this is the largest test package. If one pull request is too much for one review, the natural seam is two: the folder, the jar discovery, `test_golden_live.py`, `test_tools.py` and `test_modules.py` first; then `test_runner.py`, `test_signals.py` and `test_completion.py` (proposed to the index).
- The `cache clean` refusal races the lifeline's two seconds by nature; the repeat rule above bounds it but does not remove it.
- The resume test lasts minutes and sizes its spec by a guess at runner speed; a much faster runner could finish before the first checkpoint. Then the test fails saying the run ended before a checkpoint, and the spec is made larger.
- Facts written from one capture can hold only for that capture's seed or timing; the skip table makes each such case visible rather than hiding it.
