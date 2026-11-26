# 06. The lifeline agent

Size: M. Suggested model: mid-tier. Status: built.

## Goal

The repository holds the source of a small Java agent that ends its JVM when a given process is gone, the jar built from it is checked in beside it as package data of `tlaup` at `tlaup/java/lifeline.jar`, and tests show that the jar matches its source and that the agent does what [20 G3](../design/20-groundwork.md#g3-java-launcher) says. Nothing starts a JVM with it yet: that is package 21.

## Covers

- Roadmap items: "The lifeline agent (decision D51): a small Java agent jar, built from source kept in the repository with `--release 11`, shipped as package data in the wheel, ..." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)), in part. This package has the source, the checked-in jar, the package data, the build recipe and the tests. "Added by the launcher to every Java start" is [21](21-java-launcher.md). "Checked in CI" (the lifeline job and the wheel's file list) is [53](53-ci-workflows.md). The release workflow has no part in it: the jar is in git, so `uv build` packs it as it is.
- Design sections: [20 G3](../design/20-groundwork.md#g3-java-launcher), the part "The lifeline" (the agent's behaviour, "The jar") and the test bullet "The lifeline, with a real JVM", apart from its last sentence (see "Tests that must pass"). The rest of G3 is [21](21-java-launcher.md). [30 I2](../design/30-ci-and-release.md#i2-unit-job) (the lifeline job) and [30 I4](../design/30-ci-and-release.md#i4-build-check) (the wheel check) are [53](53-ci-workflows.md); this package provides what they run and check.

## Depends on

- [01](01-ruff-format.md): the formatted tree, so that the Python files added here do not conflict with the format commit.

Nothing else. The package touches no existing module under `src/`. Its tests sit beside the test foundation of [03](03-test-foundation.md) without needing it; "Context for the worker" says what to do in either merge order.

## Files

Creates:

- The agent's Java source, beside the jar under `src/tlaup/java/` (G3: "its Java source is in the repository beside it"). One class. The file's exact place and the Java package name are the worker's; a sub-folder such as `src/tlaup/java/lifeline/` keeps it apart from the Python modules.
- `src/tlaup/java/lifeline.jar`, checked in (see "The jar is checked in" below).
- `scripts/build_lifeline.py`: the build recipe. It compiles the source with `javac --release 11` into a temporary folder and writes the jar. One function does the compile, so the comparison test and the recipe share it. It finds `javac` from `JAVA_HOME` first, then `PATH`, and takes the output path as an argument.
- `tests/lifeline/conftest.py`, `tests/lifeline/test_jar_matches_source.py`, `tests/lifeline/test_lifeline.py`, and the Java sources the tests compile themselves (a class that sleeps; the reused-id stand-in), for example under `tests/lifeline/java/`. These need a real JDK.
- `tests/unit/java/test_lifeline_jar.py`: checks of the jar that need no Java, in the default suite.

Changes:

- `pyproject.toml`: package data for `tlaup.java` (the jar; see the note on the source below); the marker line of [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings), `"lifeline: needs a real JDK; run by the lifeline job (30 I2), not the unit job"`, in `[tool.pytest.ini_options] markers`; the poe tasks `build-lifeline` and `test-lifeline`. [03](03-test-foundation.md) rewrites the pytest block with T10's text, which has the same marker line and `tests/lifeline` in `norecursedirs`, and [56](56-build-and-metadata.md) the build settings of the same file; the conflict is one marker line, one package-data line and two task lines.
- `MANIFEST.in`, if it still exists when this package merges ([56](56-build-and-metadata.md) deletes it): nothing is needed for a file that is package data, since setuptools puts package data into the sdist by itself.
- `docs/contributing/development.md`: how to rebuild the jar and how to run the lifeline tests, a few lines.

Deletes: nothing.

## Interfaces

Provides:

- **The agent**, from [20 G3](../design/20-groundwork.md#g3-java-launcher), "The lifeline". It is started as `-javaagent:<lifeline jar>=pid=<process id>`. Its `premain` starts a daemon thread that looks the process up with `ProcessHandle.of(pid)` and polls `isAlive()` every 500 milliseconds; when the process is gone, or was already gone when the agent started, it calls `System.exit(143)`. It touches no stream, no file descriptor and no signal disposition. The argument form `pid=<digits>` is fixed: package 21 writes it.
- **The jar**, checked in at `src/tlaup/java/lifeline.jar`, so `tlaup/java/lifeline.jar` in the wheel: the agent's class file or files, compiled with `--release 11`, and a manifest with `Premain-Class`. A few kilobytes.
- **`uv run poe build-lifeline`**: runs `scripts/build_lifeline.py` and writes the jar to its place. A developer runs it after changing the source and commits the new jar with the source.
- **`uv run poe test-lifeline`**: runs `tests/lifeline` with a real JDK. This is the command the lifeline job of [53](53-ci-workflows.md) calls. Written by stage 4: [30 I2](../design/30-ci-and-release.md#i2-unit-job) says only that "the lifeline tests are marked so that [the unit job] skips them and this job runs them". The arrangement here mirrors the one the design already has for the integration tests ([01 T2](../design/01-testing.md#t2-isolation), [T9](../design/01-testing.md#t9-integration-tests), [T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)): a folder of its own, outside the default run, with a registered marker (`lifeline`) that its conftest puts on everything in the folder, and its own fixture named `isolated` that keeps the real `PATH` and `JAVA_HOME`.

Consumes: nothing from another package.

Consumed by: [21](21-java-launcher.md) (`JavaInvocation.argv()` names the jar's path), [53](53-ci-workflows.md) (the lifeline job; `scripts/check_wheel.py` asserts the jar is in the wheel), [52](52-integration-tests.md) (real runs carry the agent). [55](55-release-tooling.md) needs nothing of it: the release workflow builds the wheel from what is in git.

## Tests that must pass

Lifeline tests, plain pytest, with a real JDK, in `tests/lifeline/`, marked `lifeline`, not part of `uv run poe test`. From G3's bullet "The lifeline, with a real JVM"; each uses the jar that ships, not one built for the test:

- `test_jar_matches_source.py`: compile the agent's source with `javac --release 11` into a temporary folder; the set of class files equals the set in the jar and each file is equal byte for byte. This is the check that "a binary nobody can read is never shipped".
- A parent Python process starts `java -javaagent:<jar>=pid=<parent> <a class that sleeps>` and is killed with SIGKILL (on Windows, ended with `TerminateProcess`, which is what `Popen.kill()` does there); the JVM is gone within three seconds.
- The same with `-Xrs` among the JVM's options.
- Started with the id of a process that has already exited, the JVM exits at once.
- A reused process id (Linux only): a stand-in in a small process-id namespace (`unshare --pid --fork`) takes a handle as the agent does, ends that process, starts processes until one has the same id, and asserts that the handle's `isAlive()` is false. G3: "the idea is to confirm the JDK's behaviour, not to test tlaup". It rests on Java 11, the oldest supported Java, which is why the lifeline job uses Temurin 11.

Unit, plain pytest, no Java, in the default suite (`tests/unit/java/test_lifeline_jar.py`). G3's Risks call it "the package's own test of the jar": the file is where `tlaup.java` is installed; it is a zip; its manifest has `Premain-Class` and that class is in the jar; every class file in it has major version 55 (Java 11), read from the file's header. A missing or broken jar would stop every Java start, so this one runs everywhere.

Who has the other lifeline tests of G3:

| Test | Owner |
| --- | --- |
| The five above | This package writes them; the lifeline job of [53](53-ci-workflows.md) runs them on `ubuntu-latest` and `macos-latest` with Temurin 11 and is a required check. |
| "Under a pseudo-terminal with `tlaup repl`'s arguments, the REPL still reads a line from stdin" (last sentence of the same bullet) | [52](52-integration-tests.md), in `tests/lifeline/test_repl_terminal.py`, marked `lifeline`. It needs a real `tla2tools.jar` with `tlc2.REPL` and the `repl` command (43). The lifeline job of [53](53-ci-workflows.md) runs it, with the current rolling build that [54](54-integration-job.md) installs into that job from the integration job's cache, since v1.7.4 has no REPL ([30 I2](../design/30-ci-and-release.md#i2-unit-job) as revised). This package does not keep it among the integration tests. |
| `argv()`: "the lifeline comes first and names `os.getpid()`", and `lifeline=False` leaves it out | [21](21-java-launcher.md), unit. |
| tlaup killed with SIGKILL during a real run: no `java` process is left after five seconds ([11 R6](../design/11-runner.md#r6-run-folders), Tests, "Integration"; [01 T9](../design/01-testing.md#t9-integration-tests)) | [52](52-integration-tests.md). |
| `test_child_ends_with_tlaup` in `tests/stateful/test_signals.py` | Runs against the throwaway model only and is deleted by [21](21-java-launcher.md); it never tests this agent. |

No old test is touched (none is left after 03b, and this package may land before it). Preserved-behaviour rows: none is this package's. No stateful test applies.

## Changelog

None. The entry that describes the agent's effect ("If tlaup is killed, the Java tool it started stops within about two seconds.", G3) is true only once a command starts Java through the launcher; the switch package [39](39-tlc-command.md) writes it.

## Context for the worker

**The decision.** D51: a JVM that tlaup started must end when tlaup ends, however tlaup ended, SIGKILL included, on every system. Without help the JVM outlives a killed tlaup, holds every core, and its run folder can be deleted under it. The agent in the JVM is the one way that works the same on Linux, macOS and Windows and for every tool.

**The jar is checked in** (G3, "The jar", leaves the choice to the work package; settled for this package on 2026-11-24 as a low-impact choice, and the one [30 I4](../design/30-ci-and-release.md#i4-build-check) calls "the simpler of the two"). In git: the source and the jar. Why: every test run and every wheel then uses the same bytes; a fresh checkout works at once without a JDK; `tests/unit/java/test_lifeline_jar.py` runs in the unit job, which has no Java; and neither the build job of [53](53-ci-workflows.md) nor the release workflow of [55](55-release-tooling.md) needs to set up a JDK for it. The guard against a jar that drifted from its source is the comparison test, which the lifeline job of 53 runs on every push. What the design requires holds: the jar is never compiled on the user's machine, which may have only a JRE; it is compiled with `--release 11`; it is package data at `tlaup/java/lifeline.jar` in the wheel; a CI test compiles the source and compares the class files with those in the jar; the lifeline tests run against the jar that ships. A change to the source without a rebuilt jar fails the comparison; the fix is `uv run poe build-lifeline` and committing both.

**Facts from the investigation that the design restates, and what it measured.** A worker does not need the research files; these are the points.

- The experiment's agent polled `ProcessHandle.of(pid)` every 500 ms and ended the JVM 0.1 to 1.6 seconds after its parent was killed, on Linux, macOS and Windows, with Java 25 and 11 on Linux and Java 21 on the three CI runners, also with `-Xrs` among the options. Java 11 on macOS and Windows was tried for the kill check alone. It added 19 to 43 ms to a JVM's start.
- `ProcessHandle.isAlive` compares the process's start time as well as its id, so a reused id is not taken for tlaup. That is the JDK's documented behaviour and the reason the agent keeps the handle it got at the start instead of asking for a new one at every poll. The reused-id test confirms it on Java 11.
- If the process is already gone when the agent starts, `ProcessHandle.of` finds nothing and the JVM exits at once. This closes the race at start-up.
- The agent was compiled with `javac --release 11` and printed no warning on Java 11, 21 or 25.
- The experiment built its jar from Python with `zipfile` (the class files, and a manifest with `Premain-Class`), so the JDK's `jar` tool is not needed. The experiment's manifest also had `Agent-Class`; tlaup never attaches the agent to a running JVM, so `premain` is all it needs.
- Exit code 143 is never seen by anyone: tlaup is gone when the agent acts.

**Traps.**

- *The byte-for-byte comparison depends on the compiler.* Two JDKs given the same source and `--release 11` need not write the same bytes. Whether JDK 11, 21 and 25 do so for this source was not tried. The lifeline job compiles with Temurin 11, so the jar that ships must be built with a `javac` whose output equals Temurin 11's: in practice, build it with Temurin 11. Record the JDK that built it where a reader finds it (for example a `Created-By` line in the jar's manifest; the manifest is not a class file, so the comparison ignores it). Try the comparison with the JDKs you have and say in the pull request what you found. If the bytes differ between JDKs, the comparison test must say in its failure message which `javac` it ran and which one built the jar, so that a developer on another JDK reads a reason and not a mystery.
- *An exception that leaves `premain` stops the JVM before the tool starts.* The agent must not let one out.
- *"Touches no stream" binds error handling too.* The agent prints nothing, ever: the REPL's terminal, the parser's stdout and the inherited lock descriptors of [11 R6](../design/11-runner.md#r6-run-folders) must be exactly as without it.
- *A malformed argument.* The design is silent on what the agent does when its argument is not `pid=<digits>`. The launcher of 21 is the only caller and always passes that form. Pick the behaviour, keep the two rules above, cover it with a test, and say in the pull request what you chose.
- *The daemon thread.* It must be a daemon, or a tool that finishes would never exit.
- *The reused-id test was not tried by the design, on any machine.* The design gives the command `unshare --pid --fork` and the idea. Three things to find out, none of them tried: making a process-id namespace needs privileges (root, or a user namespace, which some systems restrict), so the test must skip with the reason where it cannot, and the lifeline job on Linux must not skip it (tell the worker of 53 what the job needs, for example `sudo`); on Linux the JDK reads a process's start time from `/proc` (stated from general knowledge of the JDK), so the namespace needs a `/proc` of its own (`--mount-proc`); and in a new namespace ids start at 1 but, on kernels without a per-namespace limit, still wrap only at the system's `pid_max`, so "starts processes until one has the same id" may need millions of processes unless the next id is set through `/proc/sys/kernel/ns_last_pid` inside the namespace (also from general knowledge). If a reused id cannot be arranged on the CI runner, report that; do not drop the test quietly.
- *The tests must not sleep for an amount of time* ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 5): wait for "the JVM is gone" with a three-second timeout, and for "the JVM is up" on a condition (a line it prints, a file it writes), not on a delay.
- *A killed parent leaves the JVM an orphan,* so the test cannot `wait()` for it; it watches the process id. An orphan that has ended may stay a zombie until it is reaped; `tests/stateful/test_signals.py` (`tlaup_dies`) shows one way to tell the two apart on Linux. Find the way that also works on macOS.

**The test folder and the two merge orders.** `tests/lifeline/` is outside the default run. Today `testpaths` is `["tests/unit", "tests/stateful"]`, so it is simply not collected. After [03](03-test-foundation.md) `testpaths` is `["tests"]` with `norecursedirs` naming `tests/integration` and `tests/lifeline` (T10), and an autouse fixture `isolated` in `tests/conftest.py` sets `PATH` to a folder of fakes and removes `JAVA_HOME` ([01 T2](../design/01-testing.md#t2-isolation), [T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)). So:

- `tests/lifeline/conftest.py` defines its own `isolated` fixture, which replaces the root one for this folder as `tests/integration/conftest.py` does. These tests start no tlaup and read none of its folders; the fixture only has to leave `PATH` and `JAVA_HOME` alone.
- `tests/lifeline` must be in `norecursedirs` once that setting exists. T10's block, which 03b writes, has it and the `lifeline` marker line; whichever of 03b and this package merges second keeps one copy of each. `--strict-markers` makes a forgotten marker fail loudly.
- A missing JDK is an error in these tests, not a skip: they run only when asked for, and the lifeline job is a required check that must not pass with nothing run. Platform skips (the reused-id test off Linux) carry a reason.
- The hosted runners have a Java on `PATH` even in the unit job, which is why "skip when there is no `javac`" would not keep these tests out of it. Keeping the folder out of the default run does.

**Platform rules (D15).** No Windows CI. Write the tests so they should work there: `Popen.kill()` rather than `os.kill(pid, SIGKILL)` where the parent is a `Popen` object, `java.exe` found with `shutil.which`, no `os.fork`.

**Linting.** `scripts/build_lifeline.py` is checked by ruff and by mypy in strict mode (mypy excludes `tests/` only). A `.jar` is not text, so the secret and personal-data hooks skip it; the large-file hook passes a file of a few kilobytes.

**The Java source and the built distributions.** The design says where the jar goes and does not say whether the source ships. [56](56-build-and-metadata.md) deletes `MANIFEST.in`, after which only package data reaches the sdist. Making the source package data too keeps it in the sdist and puts the readable source beside the binary in every install; the wheel check of 30 I4 names the files that must be there and does not forbid it. Decide, and say so in the pull request, so that the worker of 53 writes `scripts/check_wheel.py` to match.

**State of `main` when this starts.** Release 0.8.x code. `src/tlaup/java/` holds `__init__.py`, `inspector.py` and `classpath.py`. `[tool.setuptools.package-data]` has `tlaup = ["py.typed"]` and `"tlaup.resources" = ["*.yaml"]`. The one CI job does not run `tests/lifeline`; before 03b it sets up Java 17 for the old tests, after 03b it has no Java.

## Done when

- The lifeline tests pass locally with a JDK 11 (`uv run poe test-lifeline`); the pull request says on which systems and JDKs they were run and what was not tried.
- `tests/unit/java/test_lifeline_jar.py` passes in `uv run poe test`.
- `uv run poe lint` and `uv run poe test` pass; CI is green.
- A wheel built with `uv build` contains `tlaup/java/lifeline.jar` (look at the file list; the scripted check is 53's).
- The pull request names the JDK that built the jar, the result of comparing builds from the JDKs at hand, the behaviour chosen for a malformed argument, whether the source is package data, and what the reused-id test needs to run on the Linux runner.
- `docs/contributing/development.md` says how to rebuild the jar and run the lifeline tests.

## Out of scope

- Adding the agent to a Java start, `JavaInvocation.lifeline`, and `--show-command` leaving it out: [21](21-java-launcher.md) and [39](39-tlc-command.md).
- The lifeline job in `test.yml`, `scripts/check_wheel.py` and the build job: [53](53-ci-workflows.md).
- The release workflow: [55](55-release-tooling.md).
- The REPL under a pseudo-terminal with the agent, and a killed tlaup in a real run: [52](52-integration-tests.md).
- The inherited lock (`pass_fds`), which D51 pairs with the agent on Linux and macOS: [21](21-java-launcher.md) and [35](35-run-folders.md).
- Other ways to end the JVM with tlaup (the parent-death signal, a pipe the agent waits on, a watcher process, a Windows job object, `ProcessHandle.onExit()`): rejected in G3, each for a reason given there. Do not add one as a second line of defence.

## Risks

- From G3: a broken or missing jar stops every Java start. The no-Java unit test and the wheel check of 53 are the guards.
- From G3: the agent costs 20 to 40 milliseconds per Java start and a poll every half second.
- On Windows the agent is the only thing that ends an orphan JVM, and nothing in CI runs it there (D15).
- The comparison test can turn red because the JDK on the runner changed its output, with no change of ours. The fix is a rebuilt jar and a pull request that says which JDK built it.
- The reused-id test rests on a mechanism nobody has run. It may need privileges the runner gives only through `sudo`.
- From the cut: this package and 53 agree only through `uv run poe test-lifeline` and the jar's path. A change to either name must reach 53.
- From the cut: until 21 and 52 land, nothing checks the agent through tlaup's own launcher. The tests here start `java` by hand.
