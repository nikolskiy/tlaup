# 20. Java location and the remembered version check

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup/java/locate.py` finds `java` and `javac` (`JAVA_HOME` before `PATH`), checks their version with a timeout, tells the ways this can fail apart, and remembers the answer in `<cache>/java.json` so that a later call does not start Java for it. It is built beside today's `java/inspector.py`; no command uses it yet.

## Covers

- Roadmap items ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)):
  - "Use `JAVA_HOME` when set, falling back to `PATH`, for both `java` and `javac`." In part: the functions. The commands that call them are [39](39-tlc-command.md) (`tlc`, through the preflight of [33](33-tlc-invocation.md)), [31](31-module-commands.md) (`module add`, through [30](30-module-build.md)), [41](41-sany-command.md) to [43](43-repl-command.md) and [46](46-doctor.md).
  - "One Java start per run: read the TLC version from saved metadata instead of launching Java, and remember the Java version check. Report a timeout as a timeout, not as 'not installed'. ..." In part: remembering the check, and telling the failures apart. The rest is listed under "Design sections".
- Design sections:
  - [13 J2](../design/13-modules-and-java.md#j2-finding-java): all of the design and its unit tests. Its feature scenarios are written by the packages that give a command these functions (see "Out of scope").
  - [13 J3](../design/13-modules-and-java.md#j3-one-java-start), by bullet of its Design part:

    | J3 says | Owner |
    | --- | --- |
    | "The TLC version is never asked of Java": the header from `build.json` | [23](23-tool-store.md) (`build.json`), [22](22-version-spec-and-jarinfo.md) (reading the manifest), [38](38-terminal-reporter.md) (the header) |
    | The same bullet: TLC's own version line, message 2262 | [13](13-tlc-parser.md) (10 P9) |
    | The same bullet: `get_tlc_version` and `_extract_tlc_version` are deleted; `tlc --version` goes | `get_tlc_version` (`tlc/runner.py`) and the option: [39](39-tlc-command.md); `_extract_tlc_version` (`versioning/metadata.py`): [29](29-tool-commands.md), which deletes the old store code; the tree test: [48](48-command-tree.md) |
    | "What an install records when Java is absent" | [23](23-tool-store.md), [27](27-install-steps.md) |
    | "What a run does with missing or unreadable metadata" (`PinnedBuildMissing`) | [23](23-tool-store.md), [33](33-tlc-invocation.md) |
    | "The Java version check is remembered" | **This package** |
    | "Only a plain `java` binary is remembered", the macOS rules included | **This package** |
    | "Failures are told apart" | **This package** |
    | "The minimum is the setting `java.min_version`, 11" | The setting and its default: [19](19-layered-config.md), which owns inventory row J4 and asserts the default 11. Here it is the argument `min_version`, so no test here can show the default. |
  - [13 M3](../design/13-modules-and-java.md#m3-module-build-details), one bullet: "`javac` has its own version check" (`require_javac`, its own pattern, the same timeout and remembered answer). It lives in `locate.py`, so it is built here; the rest of M3 is [30](30-module-build.md).
- The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md): row J1 (the forms of `java -version` that 0.8.x understands), whose owner this package is. Row J4 (the default minimum 11) is [19](19-layered-config.md)'s, which holds the default.

## Depends on

- [02](02-errors-and-paths.md): `JavaNotFound`, `JavaTooOld`, `JavacNotFound` (family `NotSetUp`, code 3), `Failed` and `ToolStartError` (code 5) from `tlaup/errors.py`. `AppPaths.java_cache` exists there too, but only callers use it: this package takes the file as an argument.
- [03](03-test-foundation.md): the isolation fixture; the fake `java` of `tests/fakes/` with its `version` and `version_delay_ms` fields ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)), for the timeout test.

## Files

Creates:

- `src/tlaup/java/locate.py`.
- `tests/unit/java/test_locate.py`.

Changes: none under `src/`. `docs/contributing/development.md` only if its code map lists the modules of `java/` one by one (today it says "`java/` finds Java and builds classpaths", which stays true).

Deletes: nothing. See "Why this package does not replace `inspector.py`" below.

Shared with other packages of the groundwork track: none. [21](21-java-launcher.md) adds `launcher.py` to the same folder and touches no file of this package.

## Interfaces

Provides, from [13 J2](../design/13-modules-and-java.md#j2-finding-java):

```python
# tlaup/java/locate.py
@dataclass(frozen=True)
class JavaTool:
    path: Path
    source: str                       # "JAVA_HOME" or "PATH"

@dataclass(frozen=True)
class Located:
    tool: JavaTool | None
    warning: str | None               # for example a JAVA_HOME that holds no such tool

@dataclass(frozen=True)
class JavaRuntime:
    tool: JavaTool
    version: str | None               # "25.0.5"; None when the answer could not be read (J3)
    major: int | None
    warnings: tuple[str, ...]

def locate(name: Literal["java", "javac"], env: Mapping[str, str]) -> Located
def require_java(env: Mapping[str, str], *, min_version: int, cache_file: Path,
                 ask_version=ask_version) -> JavaRuntime          # raises JavaNotFound, JavaTooOld, Failed
def require_javac(env: Mapping[str, str], *, min_version: int, cache_file: Path,
                  ask_version=ask_version) -> JavaRuntime         # raises JavacNotFound, JavaTooOld, Failed (M3)
def ask_version(tool: Path, timeout: float = 10.0) -> str         # runs `<tool> -version`, returns what it printed
```

Two additions, written by stage 4 from what the design says in words:

- **A way to check again.** "`tlaup doctor` always re-runs the check and rewrites the entry" (J3, Risks; [23 C1](../design/23-command-layout.md#c1-command-tree)). No parameter is written for it. `require_java` and `require_javac` take `refresh: bool = False`: with `True` the remembered answer is not read, the tool is asked, and the entry is rewritten under the usual rules. Package [46](46-doctor.md) passes it.
- **The exit status of the version call.** J3 tells "exited non-zero and printed no version at all" apart from "answered something that is not a version", so the caller of `ask_version` needs the exit status as well as the text; `-> str` cannot carry it. Return both (for example a small frozen value with `text` and `exit_code`), and keep `ask_version` a parameter of the two `require_` functions, since the tests pass a counting stand-in.

The remembered answers ([13 J3](../design/13-modules-and-java.md#j3-one-java-start)), one file for `java` and `javac`:

```json
{"schema": 1, "entries": {"<resolved path>": {"size": 12345, "mtime_ns": 17..., "version": "25.0.5", "major": 25}}}
```

The messages ([13 J2](../design/13-modules-and-java.md#j2-finding-java)): `JavaNotFound`: "Java was not found (looked in JAVA_HOME and PATH)", hint "install Java 11 or newer"; `JavaTooOld`: "Java 11 or newer is needed; <path> is version 8" (the number is `min_version`; when the tool came from `JAVA_HOME` the message says so, J2 Risks; for `javac` it names `javac` and its path, M3); `JavacNotFound`: "javac was not found; `module add` needs a JDK, not only a Java runtime"; the timeout, a `Failed`: "`<path> -version` did not answer within 10 seconds".

Consumes: the error classes of [02](02-errors-and-paths.md).

Consumed by: [33](33-tlc-invocation.md) (`JavaRuntime` in `TlcInvocation.java`; `require_java` in the preflight; `JavaRuntime.warnings` into `TlcInvocation.warnings`), [30](30-module-build.md) (`require_javac` bound as `get_javac`; the version it read goes into `module.json`), [41](41-sany-command.md) to [43](43-repl-command.md), [46](46-doctor.md) (`locate` for both tools with their source; `refresh=True`).

## Tests that must pass

All plain pytest, unit, in `tests/unit/java/test_locate.py`, with real files in a temporary folder and no patching ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests)). Each asserts the type of the error and the values returned, not the wording, except where the design names a word.

From J2:

- `locate` for `java` and for `javac`: with `JAVA_HOME` set and holding the tool, that one is returned with source `JAVA_HOME` although another is on `PATH`; with `JAVA_HOME` set to an empty folder, the one on `PATH` is returned with a warning that names the variable; with neither, `tool` is `None`; a file of the right name without the execute bit is not found, in `JAVA_HOME` and on `PATH` alike.
- `locate` prints nothing (both captured streams are empty).

From J3:

- `require_java` with `ask_version` passed in as a counting function: a file named `java` that does not start with `#!` is asked once across two calls; after its size changes, again; a `#!` script named `java`, and a link named `java` that points at a file of another name, are asked on every call; an unreadable or corrupt `java.json` is ignored and rewritten.
- With the platform reported as macOS: `/usr/bin/java`, `/usr/bin/javac`, and a file that is the same file as a stand-in for `/usr/libexec/java_home` are asked on every call.
- `ask_version` with a timeout of half a second and the fake `java` set to take longer (`version_delay_ms`) raises `Failed` whose message has the word "seconds" and not "not found". This test also stands in for [11 R11](../design/11-runner.md#r11-preflight)'s row "the check timed out", which has no scenario because the timeout is ten real seconds (settled 2026-11-24; [39](39-tlc-command.md) writes no scenario for it).
- `ask_version` on an executable file of random bytes raises `ToolStartError`.
- An answer with a non-zero exit status and no version in it, such as `Unable to locate a Java Runtime.` with exit 1, is `JavaNotFound` (code 3) whose details hold what was printed.
- An answer that is not a version with exit status 0: `version` and `major` are `None`, `warnings` has one entry that holds what was printed, nothing is written to `java.json`, and no error is raised.
- A version below `min_version` (`1.8.0_202` against 11) is `JavaTooOld`.
- The version patterns, one parametrised test (row J1 of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md), owner this package; [13 J3](../design/13-modules-and-java.md#j3-one-java-start)): the two `java` patterns read `version "1.8.0_202"` as major 8, `version "11.0.2"`, `version "17"` and `version "21.0.1"` as 11, 17 and 21, and a bare `version 21` as 21, the five forms 0.8.x understands; also `openjdk version "11.0.2" 2019-01-15` gives the version `11.0.2`, and `9.0.4` gives 9.

From M3:

- The `javac` pattern on `javac 25.0.5`, `javac 11.0.2`, `javac 1.8.0_202` (major 8) and `javac 17-ea`; on a text whose first line is `Picked up JAVA_TOOL_OPTIONS: ...` and whose second is the answer; and that the two `java` patterns match none of them.
- `require_javac` with a `javac` that answers `javac 1.8.0_202` is `JavaTooOld` naming `javac`; with none found, `JavacNotFound`.

From the addition above: with `refresh=True` a remembered tool is asked again and its entry rewritten.

Old tests: none is left; `tests/unit/check_java/test_check_java.py` went with the rest of the old suite in 03b ([01 T11](../design/01-testing.md#t11-the-existing-tests), decision D62), and the J1 test above holds what it protected. No stateful test applies.

## Changelog

None in this package: nothing a user sees changes until a command calls these functions. The entries of J2 and J3, and which switch package writes each:

- Changed (J2): "`JAVA_HOME` is used to find `java` and `javac` when it is set; `PATH` is the fallback." Written by [39](39-tlc-command.md); `module add` follows in [31](31-module-commands.md), which adds no second line.
- Changed (J3): "A run starts Java once instead of three times; the Java version check is remembered until the Java installation changes." [39](39-tlc-command.md).
- Fixed (J3): "A Java that did not answer was reported as 'not installed'." [39](39-tlc-command.md).
- Fixed (J3): "Installing tools without Java present recorded an empty version." [29](29-tool-commands.md).
- Removed (J3): "`tlaup tlc --version`; use `tlaup tool current`." [39](39-tlc-command.md).

## Context for the worker

**Why this package does not replace `inspector.py`.** `java/inspector.py` has two callers that live on after this package: the old runner (`tlc/runner.py` calls `validate_java_version`) and the old command `check-java` (`cmd/check_java.py`, registered in `cli.py`). Switching them here would be work on code that its switch packages rewrite anyway (exceptions of a new type that the old `cmd/tlc.py` does not expect, `JAVA_HOME` used for `java` while `module add` still calls a bare `javac`), and nothing asks the old commands to change before then (decision D62). So this is a domain package in the plain sense: `locate.py` is added, and `inspector.py`, `tlaup/java/__init__.py` (which re-exports its three functions) and `cmd/check_java.py` stay as they are. They go with their last caller: [39](39-tlc-command.md) removes the old runner's use, and [46](46-doctor.md), where `check-java` becomes `doctor`, deletes `inspector.py`, the re-exports and `cmd/check_java.py`. Do not import anything from `inspector.py`: write the two `java` patterns again in `locate.py` (they are `version "(\d+(\.\d+)*(_\d+)?(-\w+)?)"` and, as the fall-back, `version (\d+(\.\d+)*)`), so that deleting the old module later touches nothing here.

**Decisions this rests on.**

- D29 ([02 X1](../design/02-cross-cutting.md#x1-exit-codes)): a missing or too old Java is "not set up", code 3; a Java that cannot be started or does not answer is "failed", code 5. tlaup never returns 1.
- D15: no Windows CI, but the code should work there. Here: `java.exe` and `javac.exe` under `JAVA_HOME/bin` on Windows; `shutil.which`, which adds `.exe`; `pathlib` throughout; the "starts with `#!`" and "same device and inode" tests must not raise on Windows.
- D45 (the preflight order) is why these functions print nothing and return their warnings: the caller collects warnings and prints them only after every check has passed.
- A design agent's decision ([README](../design/README.md#decisions-the-design-agent-made)): "The Java version check is remembered only for a plain binary named `java`", because with a version manager's shim the answer depends on the folder.

**Rules a worker could miss.**

- *`locate` reads the `env` it is given, not `os.environ`.* `shutil.which(name)` reads the process environment; pass `path=env.get("PATH")`. Domain functions take what they need as arguments ([00](../design/00-overview.md#packages-after-the-first-wave)).
- *A stale `JAVA_HOME` is a warning, not an error.* When the variable is set and `$JAVA_HOME/bin/<name>` is not an executable file, fall back to `PATH` and return a warning that names the variable.
- *A file that cannot be executed is not found.* `JavaNotFound`, code 3, not a start failure. `ToolStartError` (code 5) is for a file that was found, is executable, and that the system then cannot start, for example a file that is not a program for this machine; it carries the path and the operating system's own message.
- *The key is the resolved path, the size and the modification time in nanoseconds.* A JDK update changes size or time and the check runs again.
- *What is never remembered* (the check then runs on every call): the resolved file starts with `#!`; the resolved file is not named `java` or `javac` (`.exe` on Windows), which is what catches a link named `java` to a version manager's own program; on macOS, any `java` or `javac` directly under `/usr/bin`; on macOS, a file that is the same file as `/usr/libexec/java_home` (same device and inode). The macOS stub is a compiled binary named `java` that picks a JDK each time it runs (the one `JAVA_HOME` names, else the newest registered JDK), and its size and time do not change when JDKs are installed, so the general rule would remember it and go stale exactly when the user switches JDK. `/usr/bin/javac` was not checked by the investigation and is excluded by the same rule.
- *The macOS rules must be testable on Linux.* The test reports the platform as macOS and uses a stand-in for `/usr/libexec/java_home`, so the platform, the `/usr/bin` folder and the `java_home` path have to reach the rule as values (parameters with the real ones as defaults), not as `sys.platform` read deep inside. No patching of `tlaup` in tests (T12 rule 2).
- *The macOS stub with no JDK installed* exits 1, prints nothing on stdout and `Unable to locate a Java Runtime.` on stderr. That is `JavaNotFound` with what it printed and the usual hint, not the "not a version" warning.
- *An answer that is not a version does not stop the run.* `version` and `major` are `None`, one warning says what was printed, nothing is remembered. For `javac` the compile then goes ahead and a `javac` too old for `--release` fails with its own message (M3).
- *`javac` answers differently from `java`.* JDK 25 prints `javac 25.0.5` on stdout with nothing on stderr (tried by the design agent); the `java` patterns look for the word `version` and match neither. The `javac` pattern is `^javac (\d+(\.\d+)*(_\d+)?(-\w+)?)` with `re.MULTILINE`, over everything printed on either stream, because `Picked up JAVA_TOOL_OPTIONS: ...` can come first. From memory, not tried: JDK 8 prints `javac 1.8.0_202` on stderr. `1.8` means 8, as for `java`.
- *`java -version` prints to stderr.* Read both streams. Decode with replacement so a banner in another encoding cannot raise.
- *The file is written atomically* (write beside it, then rename) *and a file that cannot be read is ignored*, as is one whose `schema` is not 1; the next successful check rewrites it. Two tlaups may write at once: the last rename wins, and a lost entry only costs one more Java start. The design asks for no lock here.
- *The timeout ends the child.* After ten seconds the `-version` process must be killed and reaped, not left behind.
- *Every subprocess is started from an argument list* with a timeout, never through a shell ([00](../design/00-overview.md#packages-after-the-first-wave)).

**What the feature tests will look like, and why remembering is tested here.** The fake `java` of the feature tests is a `#!` script, so by the rule above it is never remembered, and every scenario that runs a tool starts it twice (once for `-version`). That is expected. The remembering is therefore tested one level down, with real files and a counting `ask_version`.

**Known gaps the design leaves; do not close them.** Which version managers put a script and which a link on `PATH` was not surveyed; the rule does not depend on it. A launcher that is a compiled binary named `java` and still picks a JVM from the environment is remembered, and the answer is stale until the installation or the cache changes; `doctor` is the way out (J3, Risks).

**State of `main` when this starts.** After 01 to 03: release 0.8.x code with `tlaup/errors.py` and `tlaup/paths.py` beside it, the isolation fixture and the fakes in place (the fake `javac` answers `-version`, [01 T4](../design/01-testing.md#t4-fakes-at-the-edges)), no old test (03b). `src/tlaup/java/` holds `__init__.py`, `inspector.py`, `classpath.py`, perhaps `launcher.py` and the lifeline files of 06 and 21. `tlaup tlc` still runs through the old runner and `check-java` still exists.

## Done when

- The tests above pass; `uv run poe lint` (mypy in strict mode covers `locate.py`) and `uv run poe test` pass; CI is green.
- No file outside `src/tlaup/java/locate.py`, `tests/unit/java/test_locate.py` and, if needed, the development guide has changed.
- The pull request names the inventory row it covers (J1) and says that the timeout test stands in for R11's timed-out row.
- The pull request says how the exit status travels from `ask_version`, names the `refresh` parameter, and lists any other change to a signature.
- No changelog entry (none is due).

## Out of scope

- The J2 feature scenarios with fake JDK folders (a valid `JAVA_HOME` wins over `PATH`; an empty `JAVA_HOME` gives one `warning:` line; neither gives code 3; a `java` without the execute bit gives code 3), in-process: [39](39-tlc-command.md), with the steps of [18](18-feature-harness.md).
- The J3 feature scenarios (the fake `java` is started twice per `tlaup tlc Spec` and never with `tlc2.TLC -version`; version `1.8.0_202` gives code 3; a non-version gives a warning and the run goes on; `Unable to locate a Java Runtime.` with exit 1 gives code 3): [39](39-tlc-command.md). `tool_install.feature` with `java is not installed`: [29](29-tool-commands.md).
- The M3 feature scenarios with a fake `javac` that answers `javac 1.8.0_202` or `javac 25.0.5`: [31](31-module-commands.md).
- The integration test (after one real run `java.json` holds an entry for the real `java`, and a second run leaves the file untouched): [52](52-integration-tests.md).
- Calling `require_java` in a preflight and carrying its warnings: [33](33-tlc-invocation.md) for `tlc`, [41](41-sany-command.md) for the other tools. Binding `require_javac` for the module build: [30](30-module-build.md), [31](31-module-commands.md).
- `tlaup doctor`: [46](46-doctor.md). It also deletes `java/inspector.py` and `cmd/check_java.py`.
- Java options (13 J1): [33](33-tlc-invocation.md). Starting Java for a tool: [21](21-java-launcher.md).
- Everything in J3 about the TLC version (the table under "Covers").

## Risks

- From J2: a user whose `JAVA_HOME` points at an old JDK while a newer `java` is first on `PATH` now gets the old one, and `JavaTooOld` if it is below the minimum; the message names the path and that it came from `JAVA_HOME`.
- From J3: a compiled launcher named `java` that picks its JVM from the environment is remembered and can go stale.
- From J3: every feature scenario that runs a tool starts the fake `java` twice, which costs test time, not correctness.
- From the cut: for a while `main` has two ways to find Java, `inspector.py` for the old commands and `locate.py` for nothing yet. The old one goes with 39 and 46. Until then a fix to version parsing has to be made in the new code only; the old code is frozen, and no test covers it (D62).
- From the cut: the feature scenarios of J2 and J3 arrive only with 39, so a mistake in how the pieces fit a command shows there, not here. The unit tests above cover each rule one by one.
