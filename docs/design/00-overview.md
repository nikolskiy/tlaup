# 00. Overview: the shared pieces

Every item of milestones 1, 1b and 2 is designed to fit the picture in this document. The pieces are specified in full in the area documents; this one shows how they connect, names them, and gives the order of work.

## Words

| Word | Meaning |
| --- | --- |
| Build | One `tla2tools.jar`: a particular set of bytes. Identified by its SHA-256, its commit and, where the jar has one, its build time. |
| Name | What a build was installed as: a tag (`v1.7.4`), or `rolling`. Several builds can share a name. |
| CalVer | A build time written `YYYY.MM.DD.HHmmss` in UTC, the version rolling builds print. Derived from the manifest's `Build-TimeStamp` (research 14). |
| Store | The folder of installed builds, the pin, and the one class that reads and writes them. |
| Run folder | A folder tlaup makes for one TLC run and passes as `-metadir`. |
| Invocation | Everything needed to start one tool once, worked out before anything starts. |
| Result | What the parser builds from a tool's output. |
| Outcome | A result plus how the process ended (exit code, interrupted or not). |

## Packages after the first wave

```
src/
  tlaup_parse/          the parser package (D7, D39). Imports nothing from tlaup. No I/O.
    framing.py          lines -> messages and plain text                      10 P4
    codes.py            TLC message codes                                     10 P4
    values.py           TLA+ values                                           10 P7
    model.py            RunResult and its parts; to_dict()                    10 P3
    tlc.py              TlcParser: lines -> events and a RunResult            10 P5, P9
    sany.py             SanyParser: lines -> diagnostics                      10 P8
    pcal.py             PcalParser                                            21 S2
    exit_status.py      what a TLC exit code means                            02 X1
  tlaup/
    cli.py              the Typer app, the root options, the root group that maps errors     14 F10
    __main__.py         so `python -m tlaup` works; the real-process tests start it this way  14 F10
    context.py          AppContext: paths, settings, ui; built once                          below
    paths.py            AppPaths: every folder, from the environment                         14 F2
    errors.py           TlaupError and its four families                                     20 G2
    ui.py               the two consoles; error, warning, hint, note                         14 F6
    config/             schema.py, loader.py (layers)                                        14 F1
    java/
      locate.py         find java and javac; version check, remembered                       13 J2, J3
      classpath.py      ClasspathResolver (kept)
      launcher.py       JavaInvocation, run_streaming, run_passthrough                       20 G3
    tlc/
      invocation.py     TlcRequest -> TlcInvocation (the preflight)                          20 G1, 11 R11
      command.py        TlcInvocation -> JavaInvocation, a pure function                     20 G1
      runner.py         run_tlc: launcher -> parser -> reporter                              11 R1 to R3
      rundirs.py        run folders and their locks                                          11 R6
      overrides.py      which override classes will load on this build                       11 R7
    tools/              sany.py, pcal.py, repl.py: invocation and run for each               21
    reporters/          base.py, terminal.py, layout.py, collecting.py                       22
    versioning/
      spec.py           VersionSpec                                                          02 X3
      order.py          sort key, stable                                                     02 X4
      jarinfo.py        read a jar's manifest and capabilities                               12 V5
      store.py          ToolStore, Build, the pin, the lock                                  12 V1
      github.py         GitHubClient                                                         12 V7
      remote.py         releases, the lookup cache                                           12 V8
      download.py       download, verify                                                     12 V5
      install.py        install, upgrade, uninstall as functions                             12 V12, V3, V4
    modules/
      registry.py       registered modules; names                                            13 M1
      build.py          build_module                                                         13 M2
      classfile.py      read a class file's interfaces                                       13 M3
    cmd/                one thin module per command or group                                 23
```

Rules that hold across the tree, all taken from the roadmap's "Keep" list or its milestone 5 items:

- `tlaup_parse` imports nothing from `tlaup` and does no I/O. A test asserts it by importing the package in a subprocess with `tlaup` hidden.
- No package imports `tlaup.cmd`. Commands depend on domain code, never the reverse.
- Only `tlaup.ui`, the reporters and the commands print. Domain code returns values or raises `TlaupError`.
- Every subprocess is started from an argument list, never through a shell. Every HTTP request has a timeout.
- Domain functions take the paths and settings they need as arguments. Only commands reach for the context.

Three of these are milestone 5 items (one registry for paths and config; module build as domain code; no printing from domain code). The first wave does them where it rewrites the code anyway and leaves the rest; [40](40-later-milestones.md#milestone-5-structure) lists what remains.

## Application context

```python
@dataclass(frozen=True)
class AppContext:
    paths: AppPaths        # 14 F2
    settings: Settings     # 14 F1; loaded on first use, not at start
    ui: Ui                 # 14 F6
    env: Mapping[str, str]
    debug: bool

def get_context() -> AppContext     # built once per process
def reset() -> None                 # for tests (01 T2)
```

The root callback builds it from the environment and the root options and stores it on Typer's context object; commands read it from there and pass pieces down. `settings` is loaded lazily, so `tlaup --help` and a command that reads no setting, such as `tlaup tool path`, do not import the settings schema or `yaml` ([14 F9](14-config-and-cli.md#f9-startup-cost)). pydantic itself is not kept out: Typer 0.29.1 imports it when any command runs, though not for `--help` (tried). This is the only process-wide cache.

## The run pipeline

One path for every tool in the jar. TLC uses all of it; the others use a part.

```
 command line
     |
     v
 TlcRequest ---------------> resolve_tlc_invocation()  -- the preflight (11 R11, decision D45) --
 (what the user typed)        1. spec         resolve_spec()            -> NotFound (4)
                              2. cfg          resolve_cfg(), if named   -> NotFound (4)
                              3. tool build   store.pinned()            -> NotSetUp (3), or the first-run prompt
                              4. Java         locate, version           -> NotSetUp (3)
                              5. project root, classpath, overrides, workers, extra arguments
                                     |
                                     v
                              TlcInvocation   (frozen; nothing has been created or started)
                                     |
                         build_tlc_command()  -- pure --
                                     |
                                     v
                              JavaInvocation  (java, JVM options, classpath, main class, arguments)
                                     |
            +------------------------+--------------------------+
            |                                                   |
     --show-command                              with run_folder(...) as folder:   (11 R6; both modes)
     print shlex.join(argv)                                     |
     exit 0; never prompts,                   +-----------------+------------------+
     installs or creates a folder             |                                    |
                                            --raw                           parsed (default)
                                     run_tlc_raw(): passthrough       run_tlc(): run_streaming(java_inv)
                                     child inherits stdio               stdout lines -> TlcParser.feed() -> events
                                     exit with its code                 stderr lines -> reporter.stderr_line()
                                                                        each event   -> reporter.handle(event, result)
                                                                      reporter.finish(outcome)
                                                                      exit with outcome.exit_code
```

What this replaces: today the spec is resolved up to five times and the config loaded four times per run; the command is built by one function and then edited by another (`-tool` and `-coverage` are inserted afterwards, so `--show-command` prints a different command from the one that runs); the process loop exists twice.

The order of the preflight is decision D45: the spec first, so a mistyped name is reported before any prompt or download, and so milestone 3 can choose the build from a project file beside the spec. A run folder with its lock exists for the raw path as well as the parsed one; the first design gave a raw run a folder with no lock, which the review caught.

**How each tool is started.** Each row is the arrangement the research actually ran.

| Tool | Main class | Working folder | Spec argument | Output | Evidence |
| --- | --- | --- | --- | --- | --- |
| `tlc` | `tlc2.TLC` | Unchanged (where tlaup was started) | Absolute path | Parsed, or passed through with `--raw` | Research 16 (rows B1 to B9, E2 and D6 of its tables) |
| `sany` | `tla2sany.SANY` | The spec's folder | File name | Parsed | Research 12 |
| `pcal` | `pcal.trans` | The spec's folder | File name | Parsed | Research 12 |
| `repl` | `tlc2.REPL` | Unchanged | none | Passed through | Research 12 |

The main class names live in one table, `tlaup.tools.ENTRY_POINTS`. When upstream ships its own entry point (research 3: nothing exists yet), the hand-off is one row there.

## What a build can do

Behaviour that depends on the TLC build is decided from the jar, once, at install, and stored with the build ([12 V1](12-tools-and-downloads.md#v1-version-store)). Nothing compares version strings at run time.

| Capability | How it is decided | Used by | Checked |
| --- | --- | --- | --- |
| `repl` | `tlc2/REPL.class` is in the jar. | `tlaup repl` | Research 3, 12: absent in v1.7.4, present in rolling. |
| `calver` | The manifest has `Build-TimeStamp`. | Display, sorting | Research 14. |
| `overrides_property` | The manifest has `Build-TimeStamp`. | Override check (11 R7) | Research 13 for the two supported builds only. For builds between them the rule is a guess; D19 does not support them. |
| `no_generate_spec_te` | The manifest has `Build-TimeStamp`. | `-noGenerateSpecTE` (11 R6) | Research 17 for the two supported builds only; same caveat. |

The two guessed rules are exact for the builds decision D19 supports. A user on an unsupported in-between build who hits a wrong guess sees TLC's own message, since nothing is lost (D9).

## Where state lives (first wave)

```
<config>/config.yaml                 written only when the user changes a setting (D10)
<cache>/tool/<build-id>/            tla2tools.jar, build.json                      12 V1
<cache>/tool/pin                    the pinned build's id
<cache>/tool/.lock
<cache>/module/<name>/              classes/, lib/, modules/, tlc2/, module.json   13 M2
<cache>/module/.tmp/<random>/      a module being built; moved into place on success
<cache>/module/.lock
<cache>/runs/<run-id>/               run.json and TLC's own folder                  11 R6
<cache>/runs/<run-id>.lock           held for the length of the run; beside the folder, not in it
<cache>/remote/<key>.json            GitHub lookups                                 12 V8
<cache>/java.json                    the remembered Java version check              13 J3
```

`<config>`, `<cache>` and `<data>` come from `AppPaths` (D25). Tools, the pin and modules stay under the cache folder in the first wave; milestone 3 moves them to `<data>` as a clean break (D14). `AppPaths` already has the data folder so tests and CI set one variable, `TLAUP_HOME`, for all three.

## New and removed dependencies

| Package | Change | Why |
| --- | --- | --- |
| `filelock` | New, runtime | One lock that works on Linux, macOS and Windows for the store, the module folder and run folders. |
| `pytest-bdd`, `hypothesis`, `responses`, `pytest-socket`, `pytest-randomly`, `pyte` | New, development | [01](01-testing.md). `pyte` rebuilds a terminal screen for the layout tests ([22 O4](22-reporters.md#o4-live-display)). None of them was installed or tried during the design. |
| `coverage` | Bound raised to 7.10, development | Its subprocess patch counts the real-process scenarios ([01 T10](01-testing.md#t10-coverage-policy-and-pytest-settings)); not tried. |
| `pytest-mock` | Removed | [01 T12](01-testing.md#t12-rules-for-writing-tests). |
| `rich`, `pydantic`, `pre-commit`, `setuptools`, `typer` | Bounds changed | [30 B2](30-ci-and-release.md#b2-build-fixes). The `typer` lower bound waits on question 23; the error handling and completion were probed on the locked 0.29.1 only. |

## Order of work

Milestones are groups, not a strict order (decision D6). The dependencies between items give this order; stage 4 cuts packages along it.

1. **One mechanical commit: `ruff format`** on the whole tree, then enforce it ([30 I5](30-ci-and-release.md#i5-workflow-hygiene)). First, because every later package would otherwise conflict with it.
2. **Test foundation** (early milestone 2): folder overrides F2, isolation T2, fakes T4, pytest settings T10, delete dead tests T11. CI, release and hygiene items of [30](30-ci-and-release.md) that do not touch `src/` can run in parallel from here on.
3. **Delete dead code**: display code O2, URL installs V6, old layouts V10. Pure removal; makes everything after it smaller.
4. **Parser**: move the golden files (T3), write the facts (failing), then P2 to P9. Independent of everything else in `src/tlaup`.
5. **Groundwork**: errors G2, messages F6 and the error handler F10, the launcher G3, Java location J2 and J3.
6. **Store and downloads**: V1, V2, then V5, V7, V8, then V3, V4, V9, V11. Independent of the runner.
7. **Runner**: invocation G1 with R4, R5, R8, R10, R11; run folders R6; signals and errors R1 to R3 inside the launcher; overrides R7; show-command R9.
8. **Reporters**: O1, O3, O4, after the golden tests pass (roadmap, milestone 1b).
9. **Other tools**: S1 to S5, on the launcher and the SANY parser.
10. **Config and commands**: F1, F3 to F5, then the command tree C1 to C5, modules M1 to M3, help and wording F7, F8, F11.
11. **Integration tests** T9 and the integration job I1, once `tlaup tool install` can use a token (V7) and the runner returns outcomes.

Items 4, 5 and 6 can run in parallel; so can 8, 9 and 10 once 7 is in.

## What every package must respect

- The [conventions](../contributing/conventions.md): a changelog entry in the same commit as each user-visible change; no aliases, shims or migrations (D14); no personal or machine data in captured output.
- The exit codes of [02 X1](02-cross-cutting.md#x1-exit-codes) and the stream rule of [02 X2](02-cross-cutting.md#x2-stdout-and-stderr).
- The test rules of [01 T12](01-testing.md#t12-rules-for-writing-tests).
- Decision D15: no Windows CI, but write code so it should work there. Use `os.pathsep` and `pathlib`; no `:` in folder names; signal code guarded by `hasattr(signal, ...)`; executables found with `shutil.which`, which adds `.exe`.
