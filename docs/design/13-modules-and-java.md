# 13. Milestone 1: modules and Java

Covers milestone 1's "Safety" items for modules, the recorded problem about the module build, and the three "Java" items. Relies on decisions D15, D20, D23 and research [13](../research/13-override-loading.md), [14](../research/14-jar-manifest.md), [15](../research/15-exit-codes-and-signals.md).

## M1 Module names

Roadmap: "Reject module names containing path separators or `..`, absolute paths, `.` and an empty name in `modules remove` and `modules add`; `modules remove ../tools` deletes the tools folder today."

**Problem.** `modules remove NAME` does `shutil.rmtree(get_modules_dir() / NAME)` with no check (`cmd/modules/remove.py:11`). `modules add PATH` takes the name from the folder's last component.

**Design.** One function, used by every code path that turns a name into a path:

```python
# tlaup/modules/registry.py
def validate_module_name(name: str) -> str        # returns the name or raises InvalidName (code 2)
```

A valid name matches `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` and is not `.` or `..`. That excludes the empty name, both path separators, absolute paths, a leading dot and anything with a drive letter. As a second, independent check, `Registry.path_of(name)` resolves the result and asserts its parent is the modules folder.

`module add PATH` resolves `PATH` first and validates the last component; a folder whose name is not valid (for example one with a space) is refused with the hint to rename it or, later, to name it in the project file. `PATH` not being a folder is `PathNotFound` (code 4).

**Rejected.** Checking only that the resolved path stays inside the modules folder: it lets through names that are legal paths but awkward everywhere else (spaces, a leading dash, a trailing dot on Windows), and the name is also written into `module.json` and shown in listings. Quoting or escaping odd names: nothing needs them.

**Tests.** A parametrised unit test over `../tool`, `..`, `.`, `""`, `/abs`, `a/b`, `a\b`, `.hidden`, `C:x`, a name with a space, a 65-character name, and valid names. `modules.feature`, in-process: `tlaup module remove ../tool` exits 2 and the pin file under the cache's `tool` folder still exists; `module add` of a folder named `my module` exits 2 with the hint.

**Changelog.** Fixed: "`tlaup modules remove ../tools` deleted the tools folder. Module names are now checked." Breaking: "A module name must start with a letter or digit and hold only letters, digits, `.`, `_` and `-`, at most 64 characters. `module add` refuses a folder whose name does not fit (for example one with a space); rename the folder." (Stage 4 review, 2026-11-24: the tests named the folder `tools`, which is now `<cache>/tool`, and the Fixed entry named `tlaup module remove`, a spelling that did not exist when the bug did; clerical; the note moved out of the quoted entries, finding E13.)

**Depends on.** G2. **Risks.** A module registered under an older release with a name the rule refuses can no longer be removed by name; its folder under the one `tlaup module dir` prints is deleted by hand. No migration is written for it (D14).

## M2 Build in a temporary folder

Roadmap: "`modules add` builds in a temporary folder and swaps it in only when compilation succeeds, so a `javac` error no longer destroys the working build; it says when it replaced a module of the same name (decision D23)."

**Problem.** `add_module` deletes the registered module first (`cmd/modules/add.py:61`), then copies and compiles; a compiler error ends with nothing registered. All of it lives in the command, prints as it goes, and cannot be called from anywhere else.

**Design.** The build becomes domain code. This is also the milestone 5 item "Move the module build pipeline out of `cmd/modules/add.py` into a modules domain package", done here because the temp-folder change rewrites the function anyway; it is listed as a departure in the README.

```python
# tlaup/modules/build.py
@dataclass(frozen=True)
class BuiltModule:
    name: str
    path: Path
    override_classes: tuple[str, ...]
    replaced: bool                      # a module of this name was registered before
    warnings: tuple[str, ...]           # 11 R7's, and those of the javac lookup (J2, M3); the command prints them

def build_module(source: Path, *, registry: Registry,
                 get_build: Callable[[], Build],          # the pinned build; raises NoPinnedBuild, NoToolsInstalled
                 get_javac: Callable[[], JavaRuntime],    # require_javac of J2 with its arguments bound; raises
                 release: int, now, timeout: float = 300.0) -> BuiltModule
```

The build and the compiler are passed as functions, not values, for the reason `resolve_tlc_invocation` takes `get_build` ([20 G1](20-groundwork.md#g1-tlc-invocation)): they are asked for only when step 3 finds Java sources. `get_javac` is `require_javac` (J2), which finds `javac`, checks its version (M3) and needs the environment, the minimum version and the remembered-answers file; the command binds those. Passed as a value, the command would have had to find `javac` before knowing whether the module has any Java, and a module of TLA+ files alone would fail on a machine with no JDK. `module add` never prompts and never installs: its `get_build` is the store's pinned build.

Steps:

1. Validate the name (M1). Remove what an earlier, killed `module add` left: every entry of `<cache>/module/.tmp/` older than one day. Then make `<cache>/module/.tmp/<random>/`. The age keeps a second `module add` that is running now safe; a build cannot take a day (the compiler has a timeout, M3).
2. Copy `lib/`, `modules/`, `tlc2/` from the source (the `test`/`tests` copy goes: nothing reads it).
3. If there are `.java` files under `modules/tlc2/overrides/` or `tlc2/overrides/`: call `get_build()` for the classpath (`NoPinnedBuild` or `NoToolsInstalled`, code 3) and `get_javac()` (`JavacNotFound` or `JavaTooOld`, code 3); compile into `classes/` (M3). **The compile classpath is narrow** (decision D61): the build's `tla2tools.jar`, then the `*.jar` files directly in the module's own `lib/` (the copy made in step 2), sorted by name, and nothing else. Not another registered module, not `module_lib_path`, which acts at run time only ([14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay)), and nothing else on the machine: what tlaup compiles must come out the same on every machine, whatever else is registered or configured there. A failure raises `ModuleBuildError` (code 5) whose details are the compiler's output and the classpath it was given. A module with no Java sources needs neither, as today (`cmd/modules/add.py:87-98` looks for the jar only when there are Java files).
4. Find the override classes and write the service file (M3).
5. Write `module.json`: `{"schema": 1, "name", "built_at" (UTC with Z), "source", "javac" (the version `require_javac` read, such as `"25.0.5"`; `null` when the answer could not be read), "release", "built_against" (the build's `name@commit`), "override_classes"}`; `javac`, `release` and `built_against` are `null` for a module with no Java sources.
6. Under the modules lock: if `<cache>/module/<name>` exists, move it aside, into `.tmp/` under another random name; move the temporary folder into place; delete the old one. If the second move fails, the old one is moved back.
7. On any failure the temporary folder is removed and the registered module is untouched.

The command prints `Added module X` or `Replaced module X` (D23: no prompt; it says what it did), then any override warnings ([11 R7](11-runner.md#r7-override-modules-that-do-not-load); the check needs a pinned build and is skipped without one). It no longer clears run folders ([11 R6](11-runner.md#r6-run-folders)).

`Registry` owns `<cache>/module/`: `list() -> list[RegisteredModule]`, `path_of(name)`, `remove(name)`, `locked()`. `.tmp` is not a module: its name fails M1's rule, and `list()` returns only folders with a valid name and a `module.json`. `list()` returns the modules sorted by name, in Python's string order (by code point, so `Zeta` comes before `alpha`), and wherever registered modules are taken in turn they are taken in this order, as 0.8.x applies them. `tlaup module list` prints them as a table on stdout; with none registered, stdout is empty, so a script reads no rows, stderr holds one note (`no modules are registered`), and the exit is 0.

**The classpath of a run.** `ClasspathResolver` asks the registry for the module folders instead of walking the cache itself. The order is unchanged from 0.8.x (roadmap, "Keep"), and is written out here because a reordering changes, silently, which class TLC loads. The layers are, most specific first, the command line, the project ([11 R10](11-runner.md#r10-project-root)), the config (`module_path`, `module_lib_path`) and the registered modules; no command of the first wave passes folders of its own, so the command-line layer is empty, and the resolver keeps it first in steps 2 and 5 for when one does. The entries, in this order:

1. the project's `classes/`, ahead of the tools jar, so that its classes win over the jar's;
2. the folders of TLA+ modules: the project's `modules/`, the folder `module_path` names, then each registered module's `modules/`;
3. each registered module's `classes/`;
4. the build's `tla2tools.jar`;
5. the jars: those directly in the project's `lib/`, in the folder `module_lib_path` names, and in each registered module's `lib/`, in that order, each folder's `*.jar` files sorted by name.

An entry that appears twice, compared as an absolute path, keeps only its first place. `-DTLA-Library` holds the folders of step 2 in the same order ([20 G1](20-groundwork.md#g1-tlc-invocation)). The two legacy fallback entries of 0.8.x go ([12 V10](12-tools-and-downloads.md#v10-remove-old-layouts)). (Stage 4 review, 2026-11-24: the compile classpath was not specified and is now narrow, finding B8 and preserved-behaviour row M5, decision D61; the name order, the full runtime order and an empty `module list` were kept but not written, rows M18, S11 and M14.)

**Rejected.** Building in place with a backup copy: two copies of every module on every add. Compiling in the user's source folder: writes into a folder tlaup does not own. Compiling against the other registered modules and the jars of `module_lib_path` as well, as 0.8.x does: the same module would compile on one machine and fail on another, depending on what else is registered there and on a user setting; a wider classpath can be added later without breaking anything, a narrower one could not (D61).

**Tests.** `modules.feature` with the fake `javac`: a first add registers the module (`the registered modules are:`), and the logged `javac` command holds `-encoding UTF-8`, `--release 11` and `-d` under the temporary folder, and, with another module registered and `module_lib_path` naming a folder that holds a jar, its `-cp` value is exactly the build's jar followed by the module's own two `lib/` jars in name order; a second add with `javac fails with "syntax-error"` exits 5, shows the compiler's output and the classpath, and the first build's `classes/` is still there; a successful second add says "Replaced"; `no javac` exits 3; a module with only `.tla` files is added with no build pinned and no `javac`, and neither fake is started; with nothing registered, `module list` exits 0 with an empty stdout and one line on stderr. All in-process. Unit, `build_module`: with `get_build` and `get_javac` that raise when called, a module with no Java sources is built; a folder in `.tmp/` older than a day is gone after any build and one made a minute ago is still there. Unit, `ClasspathResolver`, with real folders and jars under a temporary folder: a project with `classes/`, `modules/` and two jars in `lib/` created in reverse name order; `module_path` and `module_lib_path` set, `module_lib_path` naming the project's `lib/` so that its jars are reachable twice; two registered modules created in the reverse of their name order, each with `modules/`, `classes/` and a jar: the whole runtime classpath equals one expected list, entry for entry, with each jar once, and the `-DTLA-Library` folders equal step 2. Integration: a real add of `docs/examples/QueueModule` and a run.

**Changelog.** Breaking: "Modules are stored in the cache's `module` folder (was `modules`), each with a `module.json`. Modules added by earlier versions are not found: run `tlaup module add` again. The old `modules` folder can be deleted." "`module add` compiles a module's Java sources against the TLA+ tools jar and the module's own `lib/*.jar` only. Other registered modules and the jars of `module_lib_path` are no longer on the compile classpath (they still take part in runs); a module that needs a jar to compile puts a copy in its own `lib/`." Fixed: "A compile error in `tlaup module add` deleted the module's previous, working build." Changed: "`module add` says when it replaced a module of the same name; it no longer copies a `test` folder."

**Depends on.** M1, J2, V1, F2. **Risks.** A module larger than the free space in the cache folder fails at the copy; the registered one survives. A folder cannot be renamed over another that is not empty, so step 6 is two moves, and a tlaup killed between them leaves the name unregistered with the old build in `.tmp/` for a day; the window is two renames long and the fix is to add the module again.

## M3 Module build details

Roadmap (recorded without a solution): "The module build strips `//` comments with a regex that corrupts string literals; `javac` runs with no `-encoding` and no timeout."

**Problem.** `find_override_classes` removes `//.*` from the source before looking for `class X implements ITLCOverrides`, so `"http://..."` inside a string cuts the line, and a class declared after such a string can be missed or mis-read. `javac` is run with the platform's default encoding and can hang forever.

**Design.**

- **Find override classes in the compiled output, not the source.** After compiling, read each `.class` file under `classes/` and take those whose interface list contains `tlc2/overrides/ITLCOverrides`. A class file states its interfaces exactly; there is nothing to strip.

  ```python
  # tlaup/modules/classfile.py
  @dataclass(frozen=True)
  class ClassInfo:
      name: str                        # "tlc2.overrides.QueueOverrides"
      super_name: str | None
      interfaces: tuple[str, ...]
      is_abstract: bool; is_interface: bool
  def read_class(data: bytes) -> ClassInfo        # raises ValueError if not a class file
  ```

  The reader walks the header: magic number, versions, the constant pool (skipping each entry by its tag's size; `long` and `double` take two slots), access flags, this class, super class, interfaces. About 60 lines, standard library only. A class that reaches the interface only through a superclass in the same module is found by following `super_name` among the compiled classes. Abstract classes and interfaces are skipped.
- If the source folder has its own `META-INF/services/tlc2.overrides.ITLCOverrides`, it is used as written and the scan is skipped.
- If nothing is found and there were Java sources, no service file is written (today the configured default class name is written whether or not it exists), and the command says that no override index class was found.
- **`javac` arguments**: `javac -encoding UTF-8 --release <java.min_version> -cp <classpath> -d <classes> <sources>`, where the classpath is M2's narrow one (Stage 4 review, 2026-11-24: decision D61). `--release 11` makes the classes loadable by every Java the tool supports. Without it the class files carry the version of the JDK that built them, and a JVM refuses class files newer than itself, so a module built with JDK 25 could not be loaded when TLC runs on Java 17. Top-up ([research 28](../research/28-java-11-and-macos-java.md)): classes from javac 25 `--release 11`, javac 21 `--release 11` and javac 11 load and are used on Java 11, 21 and 25 with both builds, and javac printed no warning for the flag; without it a JDK 25 build is refused on Java 11 and 21. TLC reports the refusal of an index class with message 2173, which names the class and both class-file versions, and of a listed class with a 1000 holding `UnsupportedClassVersionError`; the hint of [11 R7](11-runner.md#r7-override-modules-that-do-not-load) names both versions and this command.
- **`javac` has its own version check.** `java` and `javac` are found separately (J2) and can belong to different JDKs, so the minimum checked for `java` says nothing about `javac`. `--release` needs JDK 9 or newer. `require_javac` reads `javac -version` with the same timeout and the same remembered answer as `java -version` (J3), and a `javac` older than `java.min_version` is `JavaTooOld` naming `javac` and its path.

  `javac` answers in a form of its own. JDK 25 on the machine this was written on prints `javac 25.0.5`, on stdout, with nothing on stderr (tried); the two patterns the code has today look for the word `version` (`version "11.0.2"`, `version 11`) and match neither, so a check that reused them would never see a version and never fire. `javac` therefore gets its own pattern, `^javac (\d+(\.\d+)*(_\d+)?(-\w+)?)`, matched line by line (`re.MULTILINE`) over everything the tool printed on either stream, because another line can come first: with `JAVA_TOOL_OPTIONS` set the JVM prints `Picked up JAVA_TOOL_OPTIONS: ...` before the answer, and without the flag `^` would only try the first line (tried on the pattern with such a text: no match without the flag, `25.0.5` with it); the major number is taken as for `java`, with `1.8` meaning 8. From memory JDK 8 prints `javac 1.8.0_202` and prints it on stderr; that was not tried. An answer the pattern does not match is treated as for `java` (J3): a warning that says what was printed, nothing remembered, and the compile goes ahead, where a `javac` too old for `--release` fails with its own message.
- **Timeout**: 300 seconds; a timeout is `ModuleBuildError("javac did not finish in 300 seconds")`.
- **Output**: `javac` is run with captured output decoded with replacement; warnings on success are shown only with `--verbose` (milestone 4), errors always.

**Rejected.** A proper Java lexer for the source: more code than the class-file reader and still a guess about what `javac` will produce. Asking Java (a small helper class run with reflection): one more JVM start and a class to ship.

**Tests.** Unit, `read_class` on the real class files of `tests/fakes/classes/`: one implementing the interface, one not, one abstract, one implementing it through a superclass, one with `long` constants; and on truncated and random bytes (raises `ValueError`, never anything else; a Hypothesis test over `st.binary()`). A source file with `String u = "http://x"; // implements ITLCOverrides` in a non-override class is not reported. Unit: the `javac` pattern on `javac 25.0.5`, `javac 11.0.2`, `javac 1.8.0_202` and `javac 17-ea`, and that the `java` patterns match none of them. Feature, in-process: a fake `javac` that answers `javac 1.8.0_202` gives code 3 and a message naming `javac`; one that answers `javac 25.0.5` compiles. Unit: `build_module` called with a timeout of half a second and a fake `javac` that sleeps raises `ModuleBuildError` whose message names the timeout, and the fake has exited.

**Changelog.** Fixed: "`module add` could misread which classes provide overrides when a source file had `//` inside a string." Breaking: "Override classes are compiled with `-encoding UTF-8 --release 11`. A module whose sources use language features or library classes newer than Java 11 no longer compiles; set `java.min_version` higher to raise the release. `javac` must be version 11 or newer."

**Depends on.** M2, J2, J3. **Risks.** A source that uses language features or APIs newer than Java 11 no longer compiles; the compiler's error names the feature or API, and raising `java.min_version` raises the release. Both supported builds run on Java 11 (research 28, top-up); the integration matrix keeps running it ([30 I1](30-ci-and-release.md#i1-integration-job)). Whether the class-file reader fits in about 60 lines is an estimate.

## J1 Java options

Roadmap: "Java options: a `TLAUP_`-prefixed variable and a repeatable flag, both adding to the configured options instead of replacing them; quoted values split correctly; `JAVA_OPTS` is no longer read (decision D20)."

**Problem.** A pydantic validator reads `JAVA_OPTS` and *replaces* `java.opts` with `env.split()` (`config/schema.py:36-43`), so setting a heap size drops `-XX:+UseParallelGC` and a quoted value with a space is split in two.

**Design.** The JVM options of a run are, in this order (later options win in the JVM for repeated flags):

1. the setting `java.opts` (default `-XX:+IgnoreUnrecognizedVMOptions`, `-XX:+UseParallelGC`);
2. `TLAUP_JAVA_OPTS`, split with `shlex.split` (so `-Dname="a b"` is one option);
3. each `--java-opt TEXT` on the command line, in order, each one option as given.

`--java-opt` exists on `tlc`, `sany`, `pcal` and `repl`. Its value nearly always starts with a dash; both `--java-opt=-Xmx8g` and `--java-opt -Xmx8g` work (tried on the locked Typer 0.29.1), and the help and the documentation show the `=` form. `JAVA_OPTS` is not read; the validator is deleted. An unbalanced quote in `TLAUP_JAVA_OPTS` is a usage error naming the variable.

**Rejected.** Keeping `JAVA_OPTS`: decision D20; other Java programs on the machine read it too, and a value meant for them silently changed TLC's heap. Letting the environment replace the setting (today): the garbage collector option is lost by setting a heap size. A single `--java-opts "..."` string option: needs a second layer of quoting on the command line.

**Tests.** Unit: the three sources combine in order; quoted values; an unbalanced quote. Feature, in-process: `TLAUP_JAVA_OPTS='-Xmx2g -Dx="a b"' tlaup tlc Spec --java-opt=-Xss8m` logs a Java command with the default options first, then `-Xmx2g`, `-Dx=a b` as one argument, then `-Xss8m`; `--java-opt -Xss8m` without `=` gives the same command; with `JAVA_OPTS=-Xmx1g` set, the command does not contain it.

**Changelog.** Breaking: "`JAVA_OPTS` is no longer read. Use `TLAUP_JAVA_OPTS` or `--java-opt`; both add to the configured options instead of replacing them." Added: "`--java-opt`."

**What the launcher adds before these** (top-up, [20 G3](20-groundwork.md#g3-java-launcher)): the lifeline agent (D51) and `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` (D56), for every Java tool. They are not part of `java.opts`, so a user who sets the setting does not lose them, and they come first, so a user's own encoding option still wins.

**A known gap: v1.7.4's shared temporary module copies** (top-up, [research 27](../research/27-sany-library-path.md); postponed). v1.7.4 copies every module it reads from a jar or the classpath to `<java.io.tmpdir>/<Module>.tla`, a fixed name shared by every run, so two v1.7.4 runs at once write the same files (read from the source, not tried). Rolling copies to a fresh folder per run. A per-run `-Djava.io.tmpdir` inside the run folder would remove the collision, and also the copies a JVM killed with SIGKILL leaves behind (`deleteOnExit` does not run then, research 35). It needs one run on both builds before the design relies on it, and the maintainer postponed that run and this option until after the first implementation ([notes](top-up-notes-2026-11-20.md)): the case is narrow (one build, runs at the same time, usually the same module text), and the fix only adds a launcher option, so nothing built before it has to change.

**Depends on.** F1 (the `java.opts` setting), G1. **Risks.** An option given twice with different values is resolved by the JVM (the later one wins for the common flags); tlaup does not de-duplicate. A bad option makes the JVM exit 1 before TLC starts, and its message is on stderr, which tlaup passes on. The shared temporary copies above.

## J2 Finding Java

Roadmap: "Use `JAVA_HOME` when set, falling back to `PATH`, for both `java` and `javac`."

**Problem.** `java` and `javac` are taken from `PATH` only (`shutil.which`), so a user who points `JAVA_HOME` at the JDK they want gets another one.

**Design.**

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

`locate`: if `JAVA_HOME` is set and `$JAVA_HOME/bin/<name>` (with `.exe` on Windows) is an executable file, that; otherwise `shutil.which(name)`. If `JAVA_HOME` is set and has no such file, it falls back to `PATH` and returns a warning naming the variable, because a stale `JAVA_HOME` is a common cause of "wrong Java". These functions print nothing ([00](00-overview.md#packages-after-the-first-wave): domain code returns values); the warnings travel in `JavaRuntime.warnings` to `TlcInvocation.warnings` or `ToolInvocation.warnings`, and the command prints them as `warning:` lines on stderr.

Messages: `JavaNotFound`: "Java was not found (looked in JAVA_HOME and PATH)" / "install Java 11 or newer"; `JavaTooOld`: "Java 11 or newer is needed; <path> is version 8"; `JavacNotFound`: "javac was not found; `module add` needs a JDK, not only a Java runtime".

`tlaup doctor` prints both tools with their source ([23 C1](23-command-layout.md#c1-command-tree)).

**Rejected.** `PATH` first, `JAVA_HOME` as the fallback: the variable is how users and CI images say which JDK they mean, and Maven and Gradle read it first. Failing when `JAVA_HOME` is set but holds no `java`: a stale variable would stop a setup that works today through `PATH`. Searching well-known install folders: guesses, and different on every platform.

**Tests.** Feature, in-process, with fake JDK folders: `JAVA_HOME` set and valid is used although another `java` is on `PATH` (the log shows which fake ran); `JAVA_HOME` set to an empty folder gives one `warning:` line on stderr and uses `PATH`; neither gives code 3; a `java` on `PATH` without the execute bit, and no other, also gives code 3 (`JavaNotFound`), not a start failure: a file that cannot be executed is not found in the first place. Unit: `locate` for `javac`, and that it prints nothing.

**Changelog.** Changed: "`JAVA_HOME` is used to find `java` and `javac` when it is set; `PATH` is the fallback."

**Depends on.** G2. **Risks.** A user whose `JAVA_HOME` points at an old JDK while a newer `java` is first on `PATH` now gets the old one, and `JavaTooOld` if it is below the minimum; the message names the path and that it came from `JAVA_HOME`.

## J3 One Java start

Roadmap: "One Java start per run: read the TLC version from saved metadata instead of launching Java, and remember the Java version check. Report a timeout as a timeout, not as 'not installed'. One function reads the TLC version instead of two. Define what an install records when Java is absent or the read fails ... and what a run does with empty metadata."

**Problem.** A formatted run starts Java three times: `java -version` for the check, `tlc2.TLC -version` for the header (`get_tlc_version`), then TLC. Install starts Java with no timeout to read the version (`_extract_tlc_version`) and writes an empty string if that fails. `-version` is not a TLC option at all; both functions work only because TLC prints its banner before rejecting the flag (research 3, 15).

**Design.**

- **The TLC version is never asked of Java.** Before the run, the header shows the build as the store knows it: `rolling@bc1b506 (2026.11.15.002146)` or `v1.7.4@5a47802`, from `build.json`, which was filled from the jar's manifest at install with no JVM ([12 V5](12-tools-and-downloads.md#v5-download-and-verify)). During the run, the parser reads TLC's own version line (message 2262, [10 P9](10-parser.md#p9-tlc-version)) and the reporter shows it. `get_tlc_version` and `_extract_tlc_version` are both deleted; `tlc --version` goes ([23 C1](23-command-layout.md#c1-command-tree)).
- **What an install records when Java is absent**: everything, because nothing needs Java. There is no `tlc2_version_string` field. For a jar without a build time (v1.7.4 and older) the version shown before the run is the tag; the string "2.19 of 08 August 2024" appears once TLC prints it.
- **What a run does with missing or unreadable metadata**: the folder is not a build ([12 V1](12-tools-and-downloads.md#v1-version-store)); if the pin names it, `PinnedBuildMissing` with the hint to install again.
- **The Java version check is remembered.** `require_java` runs `<java> -version` with a 10-second timeout, parses the version (the existing two patterns; `javac` has its own, M3), and stores it in `<cache>/java.json` keyed by the executable's resolved path, size and modification time:

  ```json
  {"schema": 1, "entries": {"<resolved path>": {"size": 12345, "mtime_ns": 17..., "version": "25.0.5", "major": 25}}}
  ```

  On the next run, if the key matches, Java is not started for the check. A JDK update changes size or modification time and the check runs again. The file is written atomically; if it cannot be read it is ignored. `javac -version` is remembered the same way (M3).
- **Only a plain `java` binary is remembered.** If the resolved file starts with `#!`, or is not named `java` or `javac` (with `.exe` on Windows), or, on macOS, is any `java` or `javac` directly under `/usr/bin`, or is the same file as `/usr/libexec/java_home` (same device and inode), the answer is not stored and the check runs every time. Version managers put a launcher on `PATH` that picks a JDK from the current folder or the environment, either a script named `java` or a link to the manager's own program, so one path can be a different Java in every project. Which managers do which was not surveyed; the rule does not depend on it. The macOS case is named because the rule would miss it (top-up, [research 28](../research/28-java-11-and-macos-java.md)): `/usr/bin/java` there is a compiled binary named `java`, a hard link of Apple's one launcher program, the same file as `/usr/libexec/java_home`, that picks a JDK every time it runs (the one `JAVA_HOME` names, else the newest registered JDK, not the next `java` on `PATH`) and then `exec`s it. Its size and modification time do not change when JDKs are installed or `JAVA_HOME` changes, so a remembered answer would be stale exactly when the user switches JDK. Excluding it costs macOS users without `JAVA_HOME` one extra Java start per run. `/usr/bin/javac` was not checked and is excluded by the same rule. Through the stub the JVM keeps the stub's process id, so signals and the lifeline reach it directly ([20 G3](20-groundwork.md#g3-java-launcher)).
- **Failures are told apart**: the executable is missing, or is there without the execute bit, which `locate` treats the same (`JavaNotFound`, code 3); it was found and the system cannot start it, for example a file that is not a program for this machine (`ToolStartError`, code 5, with the path and the system's message, as the launcher gives for the tool itself, [11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are)); it did not answer in 10 seconds (`Failed`: "`<path> -version` did not answer within 10 seconds"); it exited non-zero and printed no version at all, which is what the macOS stub does when no JDK is installed (exit 1, nothing on stdout, `Unable to locate a Java Runtime.` on stderr; research 28): `JavaNotFound`, code 3, showing what it printed and the usual hint to install Java 11 or newer (top-up); it answered something else that is not a version (`JavaRuntime.version` and `major` are `None`, a warning says what was printed, the answer is not remembered, and the run goes on, as today); it is too old (`JavaTooOld`).

So a run starts Java once; the first run after installing or updating Java starts it twice, and so does every run through such a launcher.

The minimum is the setting `java.min_version`, 11. Both supported builds run on Java 11 (top-up, research 28): a passing spec, a violation, a liveness property that holds and one that is violated, and an override module gave the same results on Java 11, 21 and 25, on Linux and the macOS and Ubuntu runners. v1.7.4 is Java 8 bytecode throughout; the rolling build's own classes are Java 11 (`--release 11`). Nothing in either jar points higher, so the minimum stays 11.

**Rejected.** Checking the Java version on every run: a JVM start for an answer that changes a few times a year. Skipping the check and letting TLC fail: TLC's message for an old Java is a class-version error with no hint. Reading the `release` file in the JDK folder instead of running Java: not present in every distribution.

**Tests.** The fake `java` of the feature tests is a script, so by the rule above it is never remembered. The remembering is therefore tested one level down:

- Unit, `require_java` with real files in a temporary folder and `ask_version` passed in as a counting function (the same kind of parameter as the clock): a file named `java` that does not start with `#!` is asked once across two calls; after its size changes, again; a `#!` script named `java`, and a link named `java` that points at a file of another name, are asked on every call; an unreadable or corrupt `java.json` is ignored and rewritten.
- Feature, in-process: on every `tlaup tlc Spec` the fake `java` is started twice, once with `-version` and once with `tlc2.TLC`, and never with `tlc2.TLC -version`; a fake reporting version `1.8.0_202` gives code 3; a fake that prints something that is not a version gives a warning and the run goes on; a fake that prints `Unable to locate a Java Runtime.` on stderr and exits 1 gives code 3 and that text (top-up). In these rows TLC is not started; `java` is, for `-version`.
- Unit, parametrised: the two `java` patterns read `version "1.8.0_202"` as major 8, `version "11.0.2"`, `version "17"` and `version "21.0.1"` as 11, 17 and 21, and a bare `version 21` as 21, the forms 0.8.x understands. (Stage 4 review, 2026-11-24: kept but with no test, preserved-behaviour row J1.)
- Unit: `ask_version` with a timeout of half a second and a fake that sleeps raises `Failed` with the word "seconds", not "not found"; `ask_version` on an executable file of random bytes raises `ToolStartError`; with the platform reported as macOS, `/usr/bin/java`, `/usr/bin/javac` and a file that is the same file as a stand-in for `/usr/libexec/java_home` are asked on every call.
- Integration, real Java: after one run `java.json` holds an entry for the real `java`, and a second run leaves the file untouched. `tool_install.feature`: with `java is not installed`, `tlaup tool install rolling` succeeds and `tool current` shows commit and CalVer.

**Changelog.** Changed: "A run starts Java once instead of three times; the Java version check is remembered until the Java installation changes." Fixed: "Installing tools without Java present recorded an empty version." "A Java that did not answer was reported as 'not installed'." Removed: "`tlaup tlc --version`; use `tlaup tool current`."

**Depends on.** V1, V5, F2, P9. **Risks.** A launcher that is a compiled binary named `java` and still picks a different JVM from the environment is remembered, and the answer is stale until the Java installation or the cache changes; `tlaup doctor` always re-runs the check and rewrites the entry. Every feature scenario that runs a tool starts the fake `java` twice, which costs test time, not correctness.
