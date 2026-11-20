# 23. How Typer behaves across the allowed version range

## Question

`pyproject.toml` allows `typer>=0.22.0,<1.0.0`; the lock holds 0.29.1. The design ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks),
[23 C3](../design/23-command-layout.md#c3-completion), [23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference))
was tried on 0.29.1 only. For several versions (the lowest allowed, some in between, the locked one, the newest on PyPI):

1. Does Typer bundle Click or depend on it?
2. What exit codes come out under `typer.testing.CliRunner`, through a real closed pipe (`| head -1`, expect 141) and on
   Ctrl-C (SIGINT, expect 130), for a small app built the way F10 describes (a root group subclass mapping errors to the
   D29 codes, and the two Rich measures of F10)?
3. Do completion scripts and completion itself work, and through which modules (private or public)?
4. Can the output of `typer <module> utils docs` serve as the CLI reference (C5)?
5. Which is the earliest version that behaves like 0.29.1 for what the design relies on, and which feature sets that bound?

Rich's own closed-pipe behaviour across its versions is question 30; here Rich is the locked 13.9.4 plus the lowest Rich
each Typer accepts.

## Source

- Roadmap question 23; `pyproject.toml` (`typer>=0.22.0,<1.0.0`, `rich>=13.7.0,<14.0.0`); `uv.lock` (typer 0.29.1, rich 13.9.4).
- Typer releases on PyPI, read with the JSON API and by opening every wheel from 0.22.0 to 0.29.2 (script
  `wheel_scan.py`, output `results/wheel_scan.txt`). Upstream tags (fastapi/typer, commit SHAs):
  [0.25.1](https://github.com/fastapi/typer/commit/cfcc2ef9f948bcce67897a6c7e689d39da690bf9),
  [0.26.0](https://github.com/fastapi/typer/commit/8f44149ca511ebd26fcaf36c4712e7d8a8004a4d) (release note: "Vendor Click",
  Typer no longer depends on Click),
  [0.27.1](https://github.com/fastapi/typer/commit/fe2aa0e2f9c853de378e60ca24ec3b256144decf),
  [0.27.2](https://github.com/fastapi/typer/commit/99eb220df7c69a0f14a0b69214042677e0760b9d) (release note: "Create
  `exceptions` module and `TyperException` base class"),
  [0.29.1](https://github.com/fastapi/typer/commit/73500169e87b4e31717d687818c5ed955b584c18),
  [0.29.2](https://github.com/fastapi/typer/commit/2517edde5a1292a712e2f16e600754c52c6f00d9) (uploaded 2026-11-18, the
  newest on PyPI that day; it needs Python 3.11 or later, like tlaup).
- Everything run is under `tests/fixtures/research/23-typer-versions/`: `app.py` (the small app), `inproc.py` (metadata and
  `CliRunner`), `proc.py` (real processes), `comp.py` and `comp_inner.py` (completion), `docs.py` (`utils docs`),
  `pubcomp.py` (the public `--show-completion`), `getcommand.py` (`typer.main.get_command`), `wheel_scan.py`,
  `verdict.py`, `run_all.sh` (builds the environments and runs everything), and `results/`.
- Linux x86-64, 12 cores, Python 3.13.5 for every environment, uv. Other agents ran at the same time (load average above 20
  for part of the run); nothing here is a timing measurement except that Ctrl-C was always answered within 0.1 s.

## Short answer

1. **Click.** Typer 0.22.0 to 0.25.1 depend on `click` (0.22.0 and 0.23.0/0.23.1 allow `click>=8.0.0`, from 0.23.2 on
   Python 3.10+ it is `click>=8.2.1`; all installed 8.5.1 here). **From 0.26.0 Typer vendors Click** as the private package
   `typer._click`, `click` is not installed and `import click` fails. So the F10 sentence "Typer carries its own copy of
   Click" is true for 0.26.0 and later only.
2. **Exit codes.** Every one of the 13 Typer versions tried (0.22.0, 0.23.2, 0.24.2, 0.25.1, 0.26.0, 0.26.8, 0.27.1, 0.27.2,
   0.27.3, 0.28.0, 0.29.0, 0.29.1, 0.29.2), each with the locked Rich 13.9.4 and with the lowest Rich it accepts (13.7.0 up
   to Typer 0.24.2, 13.8.0 from 0.25.1), gave **identical** results to 0.29.1 on every deterministic check: 3 for a domain
   error in a nested command, 5 for an unexpected error (also in the eager `--version` callback), 2 for usage errors and a
   bare group, 130 for `KeyboardInterrupt`, `typer.Abort` and `typer.prompt` at end of input, 3 for `EOFError`, and a
   command's own `typer.Exit(1)` and `typer.Exit(12)` kept; under `CliRunner` and as real processes; **141 through a closed
   pipe** for a command, `--help`, a nested `--help`, no arguments, and an unknown option with both streams dead; **130 on
   a real SIGINT** within 0.1 s for a command printing without end and for one sleeping. No traceback anywhere.
   Without F10's measures, Typer on its own gives 1 for `--help` into a dead pipe on most versions and 120 for an unknown
   option with both streams dead; the measures turn all of those into 141 on every version.
3. **Completion.** `typer._completion_classes.completion_init()` (no arguments) and
   `typer._completion_shared.get_completion_script(*, prog_name, complete_var, shell)` exist, with the same signatures, in
   **every release from 0.22.0 to 0.29.2** (all 26 wheels read), and the three protocols (bash with `COMP_WORDS` and
   `COMP_CWORD`, zsh and fish with `_TYPER_COMPLETE_ARGS`, fish also `_TYPER_COMPLETE_FISH_ACTION`) gave the same words in
   every environment. Both modules are private on every version; the public route (`add_completion=True`, `--show-completion`)
   also exists on every version tried. One difference: **without** `completion_init()` and with `add_completion=False`,
   0.26.0 and later answer "Shell bash not supported." with exit 1 (as C3 says), whereas 0.22.0 to 0.25.1 answer in Click's
   own format (`plain,rolling`), which the generated bash script cannot read. tlaup always calls `completion_init()` when
   the variable is set, so it is not affected.
4. **`typer <module> utils docs`** works on every version tried (`python -m typer app.py utils docs --name app --output f`)
   and gives Markdown (usage, description, arguments, options, subcommands, epilog) that is **identical at `COLUMNS=100` and
   `COLUMNS=60`, with colour off and forced, and on a second run**. So it does not need the fixed width of C5. But its
   notation changes between Typer releases (four different files over the 13 versions: `INTEGER` against `<int>`, `[CODE]`
   against `code <int>`), it writes quotes as `&#x27;`, and it ignores `rich_help_panel` groups. It can serve as the
   reference if the checked-in copy is allowed to change when Typer is upgraded (the lock makes that a deliberate step); it
   cannot serve if the file must stay stable across Typer versions.
5. **Earliest version that behaves like 0.29.1 for what the design relies on: 0.22.0, the current floor, with two
   caveats.** (a) The design names `typer.TyperException` (F10's `mapped`, the contract tests); it is **public from 0.27.2**
   (absent in 0.22.0 to 0.27.1, where the usage-error base class is `click.ClickException` up to 0.25.1 and only the
   private `typer._click.exceptions.ClickException` from 0.26.0 to 0.27.1). (b) Typer 0.22.0 to 0.23.1 allow Click older than
   8.2.1, and with Click 8.0.0 and 8.1.8 a bare group (`tlaup`, `tlaup tool`) exits **0** instead of 2 and `typer.prompt`
   under `CliRunner` with empty input never returns; with Click 8.2.1 and later everything matches.

**Proposed lower bound: `typer>=0.27.2,<1.0.0`.** It is the earliest version where F10 and C3 can be written as they stand
(public `TyperException`, vendored Click so `import click` fails the same way everywhere, argument help readable on the
command objects), and from there every version up to the newest gave the same results. The next choices, if a lower floor
is wanted: `>=0.26.0` (adds only a private import for the base class), or `>=0.24.0` (Click is then a dependency but at
least 8.2.1; needs the fallback `getattr(typer, "TyperException", click.ClickException)` and a test run in both worlds).
Nothing found forces the bound up to the locked 0.29, so the stage 3 review's reason for it falls away.

## Confidence

**Verified** on Linux x86-64 with Python 3.13 for the 13 versions tried (26 Typer and Rich pairs, plus three Click
versions with Typer 0.22.0), and for the names in all 26 releases from 0.22.0 to 0.29.2 by reading the wheels. **Partly
verified** for versions not run (0.23.0, 0.23.1, 0.24.0, 0.24.1, 0.25.0, 0.26.1 to 0.26.7, 0.27.0
were only scanned, not run), for Python 3.11, 3.12 and 3.14 (only 3.13), and for macOS and Windows (no experiment was
prepared: the closed-pipe measures use `select.poll`, which F10 already says is untried on macOS, and Windows has neither
`poll` nor SIGINT in this sense). Not tried: a real shell's own completion (only the calls the generated scripts make).

## Evidence

### Method

One uv environment per (Typer, Rich) pair under `<tmp>/q23/envs/`, built by `run_all.sh` with `uv venv --python 3.13` and
`uv pip install typer==X rich==Y`. In each, four probes ran: `inproc.py` (metadata, signatures, `CliRunner`), `proc.py`
(real processes), `comp.py` (completion), `docs.py` (`utils docs`); `pubcomp.py` and `getcommand.py` afterwards.

The app (`app.py`) is F10's design reduced: `TlaupGroup` becomes `AppGroup(typer.core.TyperGroup)` with `make_context` and
`invoke` wrapped in `mapped()` (the F10 code, with `typer.TyperException` replaced by a fallback that records which name it
found), `PipeConsole` (a Rich `Console` whose `on_broken_pipe` raises `BrokenPipeError`) for all output, and `main()` with
the null-device test, `reader_gone` (`select.poll`), `own_exit` and the final flush. `APP_BARE=1` starts the same app
with `app()` only, to show what Typer and Rich do alone. Commands: a nested `tool pin` (domain error for `nosuch`, with a
completer), `lines`, `boom`, `interrupt`, `abort`, `eof`, `exit N`, `badparam`, `prompt`, `spin` (prints without end),
`wait` (sleeps), and an eager `--version` that can be made to raise.

### The table, one row per version

Rich: first the locked 13.9.4, then the lowest accepted by that Typer. "Same" means every deterministic check equals the
0.29.1 row (`results/verdict.txt`: zero differences for all 26 pairs).

| Typer | Rich tried | Click | `typer.TyperException` public | `CliRunner` codes | Real pipe and SIGINT (F10 measures) | Completion modules and protocols | `utils docs` form |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.22.0 | 13.9.4, 13.7.0 | dependency (`click>=8.0.0`, 8.5.1 installed); `import click` works | no (`click.ClickException`) | same (with Click 8.2.1 or later) | same: 141 x5, 130 x2 | same | A (`INTEGER`, `[CODE]`) |
| 0.23.2 | 13.9.4, 13.7.0 | dependency (`click>=8.2.1` on 3.10+) | no | same | same | same | A |
| 0.24.2 | 13.9.4, 13.7.0 | dependency (`click>=8.2.1`) | no | same | same | same | A |
| 0.25.1 | 13.9.4, 13.8.0 | dependency (`click>=8.2.1`) | no | same | same | same | A |
| 0.26.0 | 13.9.4, 13.8.0 | vendored (`typer._click`); `import click` fails | no (private only) | same | same | same | B (`INTEGER`, `[CODE]`, adds argument help) |
| 0.26.8 | 13.9.4, 13.8.0 | vendored | no (private only) | same | same | same | B |
| 0.27.1 | 13.9.4, 13.8.0 | vendored | no (private only) | same | same | same | C (`<int>`, `code`) |
| 0.27.2 | 13.9.4, 13.8.0 | vendored | **yes** | same | same | same | C |
| 0.27.3 | 13.9.4, 13.8.0 | vendored | yes | same | same | same | C |
| 0.28.0 | 13.9.4, 13.8.0 | vendored | yes | same | same | same | C |
| 0.29.0 | 13.9.4, 13.8.0 | vendored; needs `pydantic>=2.5.3` | yes | same | same | same | D (`code <int>`) |
| 0.29.1 (locked) | 13.9.4, 13.8.0 | vendored; needs `pydantic>=2.5.3` | yes | reference | reference | reference | D |
| 0.29.2 (newest, 2026-11-18) | 13.9.4, 13.8.0 | vendored; needs `pydantic>=2.5.3`, Python 3.11+ | yes | same | same | same | D |

Where the columns come from: Click and `TyperException` from the wheels (`results/wheel_scan.txt`, all releases, and
`inproc.json` for the ones run); codes from `results/*/inproc.json` and `proc.json` (full detail kept for 0.22.0, 0.26.0 and
0.29.1; the rest are summarised by `verdict.txt`); docs forms from the checksums in each `docs.json` (13 versions, four
distinct files, the differences read with `diff`).

### 1. Click

`results/wheel_scan.txt` (excerpt):

```
0.25.1 | requires click: True  | bundled typer/_click: False | TyperException public: False
0.26.0 | requires click: False | bundled typer/_click: True  | TyperException public: False
0.27.1 | requires click: False | bundled typer/_click: True  | TyperException public: False
0.27.2 | requires click: False | bundled typer/_click: True  | TyperException public: True
```

In the 0.29.1 environment `importlib.metadata` finds no `click` and `import click` raises `ImportError`; the `TyperGroup`
base classes are `typer._click.core.Command` and `abc.ABC`. In the 0.22.0 environment they are `click.core.Group` and
`click.core.Command`. `TyperGroup.make_context(self, info_name, args, parent=None, **extra)` and `invoke(self, ctx)` have the
same shape on every version, so F10's two overrides apply on all of them.

### 2. Exit codes

Under `CliRunner` (`results/t0.22.0-r13.7.0/inproc.json`, `t0.26.0-r13.9.4`, `t0.29.1-r13.9.4`), identical on all versions:

| Case | Code | Case | Code |
| --- | --- | --- | --- |
| `tool pin nosuch` (domain error) | 3 | `abort` (`typer.Abort`) | 130 |
| `boom` (`RuntimeError`) | 5 | `eof` (`EOFError` in a command) | 3 |
| eager `--version` raising `RuntimeError` | 5 | `exit 1`, `exit 12` | 1, 12 |
| `interrupt` (`KeyboardInterrupt`) | 130 | `badparam`, unknown command, unknown option, bad value, missing argument | 2 |
| no arguments, `tool` alone | 2 | `--help`, `--version`, `lines` | 0 |

Real processes (`proc.json`; `<VENV>` is each environment's Python). Deterministic cases, all the same on every pair:

| Case | With F10's measures | Typer and Rich alone (`APP_BARE=1`) |
| --- | --- | --- |
| `lines --n 200000`, reader reads one line and leaves | 141 | 141 |
| `lines` (3 lines), stdout's reader gone before the start | 141 | 141 |
| `--help`, stdout's reader gone before the start | 141 | **1** (141 with Typer 0.22.0 to 0.24.2 and Rich 13.7.0) |
| `tool --help`, no arguments, same | 141 | 1 (same exception) |
| unknown option, stdout and stderr on one dead pipe | 141 | 120 |
| domain error or `RuntimeError` with stderr's reader gone | 141 | 141 |
| `exit 1`, `exit 12` with stdout's reader gone | 1, 12 | 1, 12 |
| `--help | cat`, unknown option, domain error, with nothing closed | 0, 2, 3 | same |
| SIGINT while printing without end, and while sleeping | 130 (about 0.05 s) | 130 |

`results/closed-pipe-bare-vs-f10.txt` has the bare and measured codes for each of the 26 pairs. The three-measure design
is needed: Typer's `--help` into a dead pipe is 1 on 23 of the 26 pairs and 120 for the unknown option on all of them.
The 141 that Typer 0.22.0 to 0.24.2 give on their own with Rich 13.7.0 for `--help` was not investigated (it is Rich's side,
question 30); with the measures it is 141 either way.

Racy checks, not counted: a short output into `| head -1` (`--help | head -1`, `tool --help | head -1`, an unknown option
with `2>&1 | head -1`). The writer can finish before `head` leaves, so the code is 0, 1, 2 or 141 depending on timing
(seen on identical environments). The deterministic form is a pipe whose reader closed before the start, used above. F10
lists the `2>&1 | head -1` case among those giving 141; a test should use the closed-before-start form.

**Two traps found while testing**, both relevant to the real-process tests of [01 T5](../design/01-testing.md#t5-feature-files-and-steps)
and [02 X1](../design/02-cross-cutting.md#x1-exit-codes):

- A process started from a background job of a non-interactive shell inherits SIGINT as "ignored", and Python then keeps it
  ignored: `KeyboardInterrupt` never comes and the child runs on. The first full run timed out on every SIGINT check for
  this reason. `proc.py` now starts the child with `preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL)`. A
  test helper that sends SIGINT must do the same.
- With Click older than 8.2 (Typer 0.22.0 only, see below) `CliRunner.invoke` of a command that calls `typer.prompt` with
  empty input loops at full CPU until killed. Real processes give 130.

**Click older than 8.2.1 with Typer 0.22.0** (`results/t0.22.0-r13.9.4-click8.*/`): with Click 8.0.0 and 8.1.8, no arguments
and a group alone exit 0 (the same under `CliRunner` and as a real process), where 0.29.1 gives 2; every other deterministic
check matched. With Click 8.2.1 everything matched. Typer 0.24.0 and later require `click>=8.2.1`, and 0.23.2 does on
Python 3.10 and later, so this concerns 0.22.0, 0.23.0 and 0.23.1 only (their metadata says `click>=8.0.0`; 0.23.0 and
0.23.1 were not run).

### 3. Completion

`comp_inner.py` and `comp.py`, same output on every version except the one row marked:

```
typer._completion_classes : BashComplete, FishComplete, Shells, ZshComplete, completion_init
typer._completion_shared  : Shells, get_completion_script, install
typer.completion          : Shells, completion_init, get_completion_inspect_parameters, get_completion_script, install, ...
get_completion_script signature : (*, prog_name: str, complete_var: str, shell: str) -> str
completion_init signature       : () -> None
bash script names COMP_WORDS, COMP_CWORD, complete_bash, _APP_COMPLETE
zsh  script names _TYPER_COMPLETE_ARGS, complete_zsh, _APP_COMPLETE
fish script names _TYPER_COMPLETE_ARGS, _TYPER_COMPLETE_FISH_ACTION, complete_fish, _APP_COMPLETE
```

| Call (real process, `add_completion=False`, `completion_init()` called first) | Result on every version |
| --- | --- |
| `_APP_COMPLETE=complete_bash COMP_WORDS="app tool pin " COMP_CWORD=3` | exit 0, `rolling`, `rolling@bc1b506`, `v1.8.0`, `v1.7.4` |
| the same with `COMP_WORDS="app tool pin rolling @ "`, `COMP_CWORD=5` | exit 0, nothing (the bash `@` limit of C3) |
| `COMP_WORDS="app tool pin rolling@"`, `COMP_CWORD=3` | exit 0, `rolling@bc1b506` |
| `complete_fish`, `_TYPER_COMPLETE_ARGS="app tool pin "`, action `get-args` | exit 0, the four builds |
| `complete_zsh`, `_TYPER_COMPLETE_ARGS="app tool pin "` | exit 0, `_arguments '*: :(("rolling" "rolling@bc1b506" ...))'` |
| `complete_bash` **without** `completion_init()` | 0.26.0 and later: exit 1, `Shell bash not supported.`; 0.22.0 to 0.25.1: exit 0, Click's `plain,rolling` lines |

The public route, `pubcomp.py`: `add_completion=True` gives `--show-completion` and `--install-completion` in `--help`, and
`--show-completion` prints the bash script on every version tried (0.22.0, 0.25.1, 0.26.0, 0.27.1, 0.27.2, 0.29.1,
0.29.2), with the shell found from the `SHELL` variable in that probe. It takes no shell argument (the eager option exits
before the extra word is read). So the "Rejected" reasons in C3 hold across the range.

### 4. `utils docs`

`python -m typer app.py utils docs --name app --output f.md`, exit 0 on every version. The file for the small app (about
2.6 kB) lists usage, description, options, subcommands and the epilog, then a section per command with usage, arguments and
options. Findings:

- Bytes identical at `COLUMNS=100`, `COLUMNS=60`, with `FORCE_COLOR=1`, and on a repeat (all 13 versions).
- Four distinct files over the 13 versions: 0.22.0 to 0.25.1 (`--n INTEGER`, `[CODE]`), 0.26.0 to 0.26.8 (the same, with
  argument help), 0.27.1 to 0.28.0 (`--n <int>`, argument `code`), 0.29.0 to 0.29.2 (`code <int>`, `build <str>`).
- Quotes in descriptions come out as `&#x27;`; `rich_help_panel="Extras"` is ignored (the option is listed with the others);
  the `Enum` choices appear as `<bash|zsh>` (newer) or `[bash|zsh]` (older).
- It imports the module by file or name, so for tlaup it would be `python -m typer tlaup.cli utils docs --name tlaup`.
  Not tried on the real tlaup.
- `typer.main.get_command(app)` (the script of C5) returns the root group object on every version, with `commands`,
  `params`, `help` and `epilog`; a `TyperArgument`'s `help` is `None` up to 0.25.1 and holds the text from 0.26.0
  (`results/get-command.txt`). So an argument's description is readable from the command objects only from 0.26.0.

### Commands run

```
python3 fx/wheel_scan.py                         # every wheel 0.22.0 to 0.29.2
fx/run_all.sh <work-dir>                         # 26 environments, four probes each (about 25 minutes on a busy machine)
python3 fx/proc.py <venv-python> --sigint-only   # the SIGINT checks again, after the trap above was found
python3 fx/verdict.py <out-dir>                  # zero deterministic differences from 0.29.1 for all 26 pairs
python3 fx/pubcomp.py <venv-python>; <venv-python> fx/getcommand.py
```

Three more environments, Typer 0.22.0 with Click 8.0.0, 8.1.8 and 8.2.1 (`uv pip install typer==0.22.0 rich==13.9.4
click==X`), ran `inproc.py` (with `SKIP_PROMPT=1`), `proc.py` and `comp.py`.

## Implications for the roadmap

- **[30 B2](../design/30-ci-and-release.md#b2-build-fixes):** the `typer` bound need not stay at `0.29`. Proposed `>=0.27.2,<1.0.0`
  (see Short answer). The Rich floor stays `13.8.0` for Typer 0.25 and later; Rich 13.7.0 works only with Typer up to 0.24.2.
  Typer 0.29.0 and later add `pydantic>=2.5.3` to the dependencies, which does not constrain tlaup's own, higher pydantic bound.
- **[14 F10](../design/14-config-and-cli.md#f10-no-tracebacks):** the "tried on 0.29.1 only" notes can say "0.22.0 to 0.29.2, Linux".
  "Typer carries its own copy of Click" holds from 0.26.0. `typer.TyperException` is public from 0.27.2 only, so it is what
  sets the bound. F10's list of `| head -1` cases that give 141 should say that short outputs are racy and the
  closed-before-start form is the test. The real-process helper must reset SIGINT to the default (trap above). The contract tests run in the newest-dependencies job (I3) against 0.29.2 as well.
- **[23 C3](../design/23-command-layout.md#c3-completion):** the "waiting on question 23" paragraph can be closed. Both private
  modules, the signatures and the three protocols are the same on all 26 releases, so the three real-process tests and the contract
  test hold on any bound chosen above. The bash `@` limit holds on all of them.
- **[23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference):** `typer ... utils docs` is width- and colour-independent
  and deterministic, so it can replace the script if the maintainer accepts its notation and the loss of panels; its format changes
  with Typer's minor versions, so a Typer bump means a regenerated file. The script of C5 stays possible: `get_command` and
  `commands`, `params`, `help`, `epilog` work on all versions, but an argument's help text is on the object only from 0.26.0.
  This is a choice for stage 3; nothing here decides it.
- **[01 T5](../design/01-testing.md#t5-feature-files-and-steps)** (real-process tests): reset SIGINT in the child; avoid
  `| head -1` on short output.
- No change to D29 or the exit-code table: every code held on every version.

## Open follow-ups

- macOS and Windows were not run (see Confidence). `select.poll` for `reader_gone` on macOS is still untried (F10 says so).
- Python 3.11, 3.12 and 3.14 were not run; Typer 0.29.2 needs 3.11, so no allowed Python is excluded by it.
- A real interactive bash, zsh and fish session with the generated scripts (C3 plans a hand check before the release).
- `typer utils docs` on the real tlaup app (hidden commands, `rich_help_panel` use, command order) once the command tree exists.
- Why Typer 0.22.0 to 0.24.2 with Rich 13.7.0 give 141 for `--help` into a dead pipe on their own: Rich's side, question 30.
- Typer 0.23.0, 0.23.1, 0.24.0, 0.24.1, 0.25.0, 0.26.1 to 0.26.7 and 0.27.0 were read (wheels) but not run.

## Date checked

2026-11-18 (local time; PyPI listed Typer 0.29.2, uploaded the same day, as the newest release).
