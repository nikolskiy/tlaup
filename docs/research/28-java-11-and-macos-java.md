# 28: Java 11 with both builds, newer override classes on an older Java, and the macOS `java`

## Question

Roadmap investigation list, question 28: whether both supported builds run on Java 11 (questions 1 and 13 used Java 25), and what TLC prints when an override class compiled by a newer JDK is loaded on an older Java. Also whether the `java` that macOS puts on the path is a stub that picks a JDK by itself (stated from memory in the second check), since tlaup would remember it as a plain binary. Serves milestone 1, Java and modules: [13 J3](../design/13-modules-and-java.md#j3-one-java-start) (the minimum Java, and whether the macOS system `java` may be remembered), [13 M3](../design/13-modules-and-java.md#m3-module-build-details) (`--release`, and the message the hint of [11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load) can name), [30 I1](../design/30-ci-and-release.md#i1-integration-job) (the Java axis of the integration matrix).

## Source

- Jars: v1.7.4 (`TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`, sha256 `936a2620...e050e88`) and 1.8.0 (rolling) (`TLC2 Version 2026.11.15.002146 (rev: bc1b506)`, sha256 `7e53aa63...fb84f`; `rolling` and `v1.8.0` are the same file).
- Javas, Linux x86-64, 12 cores: Temurin 11.0.33+10 (JDK, with `javac`), OpenJDK 21.0.13 (Debian, runtime only, no `javac`), OpenJDK 25.0.5 (Debian, JDK).
- Scripts, all in `tests/fixtures/research/28-java-11-and-macos-java/`:
  - `class-versions.py`: class-file major version histogram of a jar, standard library; output `class-versions.txt`.
  - `java_matrix.py` (parts 1 and 2): four specs per jar per Java, then the override module of research 13 (`ok_warn_true`: `Add2` annotated with `warn = true`, index class `tlc2.overrides.TLCOverrides`) compiled by every `javac` with its default release and with `--release 11` and `--release 21`, plus a mixed build, each loaded by every Java with both jars, with and without `-tool`. The `java` command is the one tlaup prints with `--show-command` (research 13, Evidence 1), plus `-workers 1`. Summary `java_matrix-linux.txt`; selected full captures in `out/` (`<name>.txt`, `<name>.exit`; the Java 11 runs of part 1, and every refused-class run).
  - `java_launcher.py` (part 3): what the `java` on `PATH` is and which JDK it runs. Written for macOS, run here on Linux for comparison; output `java_launcher-linux.txt`. Paths and machine details in the local captures are replaced by `<tmp>`, `<kernel>` and similar.
  - CI run on GitHub Actions: https://github.com/nikolskiy/tlaup/actions/runs/44489200898 (branch `research/top-up-experiments`, commit `0d43a75`, 2026-11-19 08:37 to 08:48 UTC, success). Images: ubuntu-latest `ubuntu26 20261111.82.6` x86_64; macos-latest `macos26 20261112.0504.1` arm64 (Darwin 25.6.0); windows-latest `win25-vs2026 20261103.298.1` x86_64. Java from `actions/setup-java` v6.3.0: Temurin 11.0.33+10 and Temurin 21 (21.0.13+9 on Ubuntu, 21.0.13.1+2 on macOS and Windows), with 21 on `PATH` and in `JAVA_HOME`. `java_launcher.py` ran on all three (`Q28_ALLOW_SUDO=1` on macOS), `java_matrix.py` on Ubuntu and macOS. Logs, unchanged, in `ci-run-1/<os>-{launcher,matrix}.txt` (runner paths as the runner prints them, its home as `~`).
  - Second CI run: https://github.com/nikolskiy/tlaup/actions/runs/44491714376 (commit `8647da2`, 2026-11-19 UTC, success; macos-latest image `macos26 20261102.0473.1` arm64). `stub_pid.py` (in the fixtures folder) starts a single-file Java program (`ProcessHandle.current().pid()`, its parent and its command) through `/usr/bin/java`, with `JAVA_HOME` at Temurin 21 and unset, and compares that PID with the one `Popen` returned. Log: `ci-run-2/macos-stub-pid.txt`.
- Upstream source, pinned (full SHAs 5a47802b5c391f59ecdd44117981f4ff8c0656ba and bc1b506bdcad80bb518bf3776a9161c34ff0fc4c):
  - `TLAClass.loadClass`, the outer `catch (Throwable e)` and `Assert.fail(EC.TLC_ERROR_REPLACING_MODULES, ...)`: [v1.7.4 lines 57-97](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/impl/TLAClass.java#L57-L97), identical at [bc1b506](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/impl/TLAClass.java#L57-L97).
  - `EC.TLC_ERROR_REPLACING_MODULES = 2173`: [v1.7.4 EC.java line 155](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/output/EC.java#L155), [bc1b506 line 188](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/output/EC.java#L188); text in `MP.java` [v1.7.4 line 910](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/output/MP.java#L910), [bc1b506 line 1109](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/output/MP.java#L1109).
  - Where override index classes are loaded: `SpecProcessor.java` [bc1b506 line 2206](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/impl/SpecProcessor.java#L2206) (`this.tlaClass.loadClass(ovrde)`), and per module for the older convention at line 2125.
  - Build settings: `customBuild.xml` at [v1.7.4 line 122](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/customBuild.xml#L122) (`source="1.8" target="1.8"`), at [bc1b506 line 11](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/customBuild.xml#L11) (`java.release` = 11, used as `release=` by every `javac` task); the README at bc1b506, line 18: "The TLA⁺ tools require Java 11+ to run."

## Short answer

1. **Both builds run on Java 11.** A passing spec (exit 0), an invariant violation (12), a liveness property that holds (0), one that is violated (13), and the override module (used, `<<"Inv sees", 3, 30>>`) give the same exit codes and results on Java 11, 21 and 25, on both jars. Nothing failed on 11. Class files: v1.7.4 is Java 8 bytecode throughout (major 52 and older, built by JDK 11.0.3 with `target="1.8"`); the 1.8.0 (rolling) build's own classes are major 55 (Java 11, built by JDK 17 with `--release 11`, so the Java 11 API is checked at build time too), bundled libraries 51 to 55. Neither manifest has `Multi-Release: true`; the rolling jar carries one `META-INF/versions/9/module-info.class` (a library's), which the JVM ignores without that attribute. **The minimum stays 11** and nothing in the jars points higher.
2. **A newer override index class on an older Java** (javac 25 default, major 69, on Java 11 or 21; javac 25 `--release 21`, major 65, on Java 11): exit **255**, message **2173**, severity 1 (error), right after `2185` "Starting..." and before any state work (`2189` never comes), then `2186` "Finished". Text, the same on both jars:

   ```
   @!@!@STARTMSG 2173:1 @!@!@
   Found a Java class for module tlc2.overrides.TLCOverrides, but unable to read
   it as a Java class object. tlc2/overrides/TLCOverrides has been compiled by a more recent version of the Java Runtime (class file version 69.0), this version of the Java Runtime only recognizes class file versions up to 55.0
   @!@!@ENDMSG 2173 @!@!@
   ```

   Without `-tool` it is the same text with `Error: ` in front. The words `UnsupportedClassVersionError` do not appear: `TLAClass.loadClass` catches the `Throwable` and passes only its message. The message **names the class twice** (dotted, as "module", and in the JVM's slashed form) and gives both class-file versions. It is **not message 1000**, so the hint of 11 R7 part 4 as written would not fire.
3. **A newer class listed by an index class that loads** (index built with `--release 11`, the class its `get()` returns built by javac 25's default): exit **255**, message **1000** severity 1, "TLC threw an unexpected exception ... The exception was a java.lang.UnsupportedClassVersionError\n: tlc2/overrides/Newer has been compiled by a more recent version of the Java Runtime (class file version 69.0), this version of the Java Runtime only recognizes class file versions up to 55.0". Here the exception's name appears and the JVM's text names the listed class (slashed form). Same on both jars, Java 11 and 21.
4. **`--release 11` works**: classes from javac 25 `--release 11`, javac 21 `--release 11` (CI) and javac 11 (all major 55) load and are used on Java 11, 21 and 25 with both jars; javac printed no warning for `--release 11`. `--release 21` output loads on 21 and 25 and is refused on 11 as in point 2.
5. **Points 1 to 4 hold on macOS (arm64) and Ubuntu runners too**: `java_matrix.py` with Temurin 11 and 21 gave the same exit codes, the same 2173 and 1000 texts and the same "override used" rows as on this machine (the two logs differ only in the OS name). Both jars also ran a passing spec on Java 11 on Windows.
6. **The macOS `/usr/bin/java` is a stub that picks a JDK every time it runs.** It is not a symlink: a 135376-byte universal Mach-O binary (x86_64 and arm64e) named `java`, and the *same file* as `/usr/libexec/java_home` (hard links: link count 37, same size and date; one Apple launcher program under many names). Which JDK it runs:
   - `JAVA_HOME` set to a JDK: that JDK (Temurin 11 when it pointed at 11, Temurin 21 when at 21).
   - `JAVA_HOME` unset: the newest JDK that `/usr/libexec/java_home` lists (25.0.5 on the runner, registered in `/Library/Java/JavaVirtualMachines`), not the one first on `PATH` (21).
   - `JAVA_HOME` pointing at an empty or a missing folder: silently ignored; the newest JDK runs, exit 0, no warning.
   - `JAVA_VERSION=1.6`: ignored (25.0.5 ran).
   - **No JDK registered** (the runner's `/Library/Java/JavaVirtualMachines` moved aside with `sudo`, `JAVA_HOME` unset): exit **1**, nothing on stdout, on stderr `The operation couldn’t be completed. Unable to locate a Java Runtime.` and `Please visit http://www.java.com for information on installing Java.` (with a typographic apostrophe). `java_home -V` printed the same and exited 1. It returned at once; whether a desktop session would also show an install prompt cannot be seen on a runner.
   - TLC through `/usr/bin/java` with `JAVA_HOME` at Temurin 11 ran both jars normally.
   - **The JVM keeps the stub's process id** (second CI run): a Java program started through `/usr/bin/java` reported the same PID that Python's `Popen` got, with `JAVA_HOME` at 21 and unset. Its own command was the chosen JDK's `bin/java`, so the stub replaces itself with that JDK's `java` (an `exec`, not a child). Signals tlaup sends to the process it started reach the JVM directly.

   On Linux (here and on the Ubuntu runner) `/usr/bin/java` is a symlink via `/etc/alternatives` to a real JDK binary that ignores `JAVA_HOME`. On Windows there is no system `java`, only `java.exe` inside each JDK folder (PE executables; `JAVA_HOME` changes nothing about what they run). The `setup-java` JDKs on all three runners are real binaries inside the JDK.

## Confidence

Verified. Parts 1 and 2: on Linux here (Java 11, 21, 25) and on the Ubuntu and macOS arm64 runners (Java 11, 21); every row is a captured run, and the source explains the message. Part 3: verified on one macOS 26 arm64 runner image; the stub's file identity and its choice of JDK were observed, not taken from Apple documentation. Not covered: Java 17 and Java 8 (v1.7.4's Java 8 bytecode does not prove it runs on 8, and upstream says 11+); the older module convention (`tlc2.module.<Module>`) with a newer class (2173 expected from the source, not run); Intel Macs and `/usr/bin/javac` on macOS; a Mac that never had a JDK (approximated by moving the registered JDKs aside); the Oracle installer's `javapath` launcher on Windows (not on the runner); the parts 1 and 2 matrix on Windows (not run; Windows is not supported, D15). Timings were not measured.

## Evidence

### 1. Class files and manifests (`class-versions.txt`)

```
== v1.7.4  Multi-Release attribute: absent
  classes per major version: {48: 21, 51: 187, 52: 769}
== rolling  Multi-Release attribute: absent
  classes per major version: {48: 21, 51: 197, 52: 580, 53: 2, 55: 1221}
    META-INF/versions/9            {53: 1}
    module-info.class              {53: 1}
```

v1.7.4's TLC packages (`tlc2`, `tla2sany`, `pcal`, `tla2tex`, `util`, `model`) are all 52; the 1.8.0 (rolling) build's are all 55, as are `formatter` and part of `org`. Manifest `Created-By`: v1.7.4 `11.0.3+7-LTS (Azul Systems, Inc.)`, rolling `17.0.21+9 (Eclipse Adoptium)`. Major 55 is Java 11, 65 Java 21, 69 Java 25.

### 2. The four specs (`java_matrix-linux.txt`, `out/<jar>-java11-<spec>.txt`)

| Spec | v1.7.4 on 11 / 21 / 25 | rolling on 11 / 21 / 25 |
| --- | --- | --- |
| `pass` (invariant holds) | 0 / 0 / 0 | 0 / 0 / 0 |
| `violation` (invariant `x < 3` fails) | 12 / 12 / 12 | 12 / 12 / 12 |
| `liveness_ok` (`<>(x = 3)` with `WF`) | 0 / 0 / 0 | 0 / 0 / 0 |
| `liveness_violated` (same, no fairness) | 13 / 13 / 13 | 13 / 13 / 13 |

TLC's start line on Java 11 shows the JVM it ran on, for example `(Linux <kernel> amd64, Eclipse Adoptium 11.0.33 64bit, MSBDiskFPSet, DiskStateQueue)` on v1.7.4 and `... 11.0.33 x86_64 ...` on rolling.

### 3. Override classes across Javas (both jars alike, `-tool` and plain alike)

| Classes built by | Class major | Java 11 | Java 21 | Java 25 |
| --- | --- | --- | --- | --- |
| javac 11, default | 55 | used, 0 | used, 0 | used, 0 |
| javac 25 `--release 11` | 55 | used, 0 | used, 0 | used, 0 |
| javac 25 `--release 21` | 65 | 2173, 255 | used, 0 | used, 0 |
| javac 25, default | 69 | 2173, 255 | 2173, 255 | used, 0 |
| index `--release 11`, listed class javac 25 default | 55 / 69 | 1000, 255 | 1000, 255 | used, 0 |

Captures: `out/ovr-<build>-<jar>-java<N>-{tool,plain}.{txt,exit}`. The `-tool` output of a refused index class, after SANY (`2262`, `2187`, `2220`, parsing, `2219`):

```
@!@!@STARTMSG 2185:0 @!@!@
Starting... (<date>)
@!@!@ENDMSG 2185 @!@!@
@!@!@STARTMSG 2173:1 @!@!@
Found a Java class for module tlc2.overrides.TLCOverrides, but unable to read
it as a Java class object. tlc2/overrides/TLCOverrides has been compiled by a more recent version of the Java Runtime (class file version 65.0), this version of the Java Runtime only recognizes class file versions up to 55.0
@!@!@ENDMSG 2173 @!@!@
@!@!@STARTMSG 2186:0 @!@!@
Finished in 2313ms at (<date>)
@!@!@ENDMSG 2186 @!@!@
```

Plain output: `Error: Found a Java class for module tlc2.overrides.TLCOverrides, but unable to read` / `it as a Java class object. tlc2/overrides/TLCOverrides has been compiled ...`, then `Finished in 02s ...`.

Why 2173 and not 1000: `TLAClass.loadClass` tries a `URLClassLoader` on the TLA+ library path, then `Class.forName(name)`, then `Class.forName(pkg + name)`; each inner try catches only `Exception`. `UnsupportedClassVersionError` is a `LinkageError` (an `Error`), so it reaches the outer `catch (Throwable e)`, which calls `Assert.fail(EC.TLC_ERROR_REPLACING_MODULES, {name, e.getMessage()})`. A class that is merely missing (`ClassNotFoundException`, an `Exception`) is swallowed, which is why research 13's missing-class cases are silent. The mixed case fails later, in `index.get()` (loading `Newer.class` there), outside `loadClass`, so it is the generic 1000 like research 13's `get_throws`.

The JVM's text (`... has been compiled by a more recent version of the Java Runtime (class file version X.0), this version of the Java Runtime only recognizes class file versions up to Y.0`) was the same on Temurin 11 and Debian's OpenJDK 21.

### 4. Linux comparison for part 3 (`java_launcher-linux.txt`)

```
RESULT q28 which-a-java linux : 2 found: /usr/bin/java, /bin/java
  /usr/bin/java: symlink=True -> /usr/lib/jvm/java-25-openjdk-amd64/bin/java size=14384 header=ELF
  file: /usr/bin/java: symbolic link to /etc/alternatives/java
RESULT q28 java-home[/usr/bin/java][JAVA_HOME-unset] linux : exit=0 version=25.0.5 java.home=/usr/lib/jvm/java-25-openjdk-amd64
RESULT q28 java-home[/usr/bin/java][JAVA_HOME=JAVA11_HOME] linux : exit=0 version=25.0.5 java.home=/usr/lib/jvm/java-25-openjdk-amd64
RESULT q28 java-home[/usr/bin/java][JAVA_HOME=JAVA21_HOME] linux : exit=0 version=25.0.5 java.home=/usr/lib/jvm/java-25-openjdk-amd64
RESULT q28 tlc-pass-v1.7.4-JAVA11_HOME linux : exit=0 no-error-found=True TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
RESULT q28 tlc-pass-rolling-JAVA11_HOME linux : exit=0 no-error-found=True TLC2 Version 2026.11.15.002146 (rev: bc1b506)
```

`/usr/bin/java` and `/bin/java` are the same file (merged `/usr`), so J3's key (resolved path) gives one entry for both.

### 5. macOS runner (`ci-run-1/macos-launcher.txt`)

`...` below shortens `~/hostedtoolcache/Java_Temurin-Hotspot_jdk`.

```
RESULT q28 which-a-java macos : 3 found: .../21.0.13-100000002.0.LTS/aarch64/Contents/Home/bin/java, .../11.0.33-10/aarch64/Contents/Home/bin/java, /usr/bin/java
RESULT q28 usr-bin-java-symlink macos : exists=True symlink=False
RESULT q28 usr-bin-java-file macos : /usr/bin/java: Mach-O universal binary with 2 architectures: [x86_64:Mach-O 64-bit executable x86_64] [arm64e:Mach-O 64-bit executable arm64e]
  ls -l: -rwxr-xr-x  37 root  wheel  135376 Oct 22 10:38 /usr/bin/java
  ls -l java_home: -rwxr-xr-x  37 root  wheel  135376 Oct 22 10:38 /usr/libexec/java_home
--- /usr/libexec/java_home -V (exit 0)
  Matching Java Virtual Machines (4):
      25.0.5 (arm64) "Eclipse Adoptium" - "OpenJDK 25.0.5" .../25.0.5-8.0/arm64/Contents/Home
      (and 21.0.13, 17.0.21, 11.0.33)
  /Library/Java/JavaVirtualMachines: Temurin-Hotspot-11.jdk Temurin-Hotspot-17.jdk Temurin-Hotspot-21.jdk Temurin-Hotspot-25.jdk
RESULT q28 java-home[/usr/bin/java][as-given] macos : exit=0 version=21.0.13.1 java.home=.../21.0.13-100000002.0.LTS/aarch64/Contents/Home
RESULT q28 java-home[/usr/bin/java][JAVA_HOME-unset] macos : exit=0 version=25.0.5 java.home=.../25.0.5-8.0/arm64/Contents/Home
RESULT q28 java-home[/usr/bin/java][JAVA_HOME=JAVA11_HOME] macos : exit=0 version=11.0.33 java.home=.../11.0.33-10/aarch64/Contents/Home
RESULT q28 java-home[first-on-PATH][JAVA_HOME=JAVA11_HOME] macos : exit=0 version=21.0.13.1 (a real JDK binary: JAVA_HOME does nothing)
RESULT q28 usr-bin-java-no-jdk[JAVA_HOME=empty-folder] macos : exit=0    (stderr: openjdk version "25.0.5" ...)
RESULT q28 usr-bin-java-no-jdk[JAVA_HOME=missing-folder] macos : exit=0  (stderr: openjdk version "25.0.5" ...)
RESULT q28 usr-bin-java-JAVA_VERSION=1.6 macos : exit=0 version=25.0.5
--- java_home -V with JDK folders aside (exit 1)
  The operation couldn’t be completed. Unable to locate a Java Runtime.
  Please visit http://www.java.com for information on installing Java.
RESULT q28 usr-bin-java-no-jdk-registered macos : exit=1 moved=1
--- stderr
  The operation couldn’t be completed. Unable to locate a Java Runtime.
  Please visit http://www.java.com for information on installing Java.
RESULT q28 tlc-pass-v1.7.4-/usr/bin/java+JAVA_HOME=11 macos : exit=0 no-error-found=True TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
RESULT q28 tlc-pass-rolling-/usr/bin/java+JAVA_HOME=11 macos : exit=0 no-error-found=True TLC2 Version 2026.11.15.002146 (rev: bc1b506)
```

Second run (`ci-run-2/macos-stub-pid.txt`):

```
RESULT q28 stub-pid-JAVA_HOME=21 macos : popen-pid=3093 same-pid=True rc=0 | pid=3093 parent=3091 cmd=~/hostedtoolcache/Java_Temurin-Hotspot_jdk/21.0.13-100000002.0.LTS/aarch64/Contents/Home/bin/java
RESULT q28 stub-pid-JAVA_HOME-unset macos : popen-pid=3100 same-pid=True rc=0 | pid=3100 parent=3091 cmd=~/hostedtoolcache/Java_Temurin-Hotspot_jdk/25.0.5-8.0/arm64/Contents/Home/bin/java
```

The parent (3091) is the Python script in both rows, and the JVM's command is the JDK's own `java`, not `/usr/bin/java`: the stub executes that file in place of itself.

Notes: `java_home -v 1.6` also returned the 25 JDK, exit 0. Only `/Library/Java/JavaVirtualMachines` existed to move (`moved=1`); its entries point into the runner's tool cache, which is why `java_home -V` lists tool-cache paths. The `setup-java` JDKs were not registered there and stayed reachable through `PATH` and `JAVA_HOME`, so the "no JDK" row is the stub with no JDK registered, not a machine with none at all.

### 6. Windows and Ubuntu runners (`ci-run-1/windows-launcher.txt`, `ubuntu-launcher.txt`, `*-matrix.txt`)

- Windows: three `java.exe` on `PATH` (setup-java's 21 and 11, a preinstalled 17), all PE32+ files inside their JDK folders, none a link; `java.home` is always that JDK, whatever `JAVA_HOME` says. Both jars passed a spec on Java 11.
- Ubuntu: setup-java's JDKs first on `PATH` (real ELF files; the tool-cache path resolves into `/usr/lib/jvm/temurin-*-jdk-amd64`), then `/usr/bin/java` linked through `/etc/alternatives` to Temurin 25; `JAVA_HOME` moves neither.
- `java_matrix.py` on Ubuntu and macOS (Java 11 and 21; builds: javac 11 default, javac 21 default, javac 21 `--release 11`, mixed): the four specs on both jars and both Javas exit 0, 12, 0, 13; the override built for 11 is used everywhere; built by javac 21 (major 65) it is refused on 11 with 2173 and exit 255; the mixed build is refused on 11 with 1000 `java.lang.UnsupportedClassVersionError` and exit 255; all are used on 21.

## Implications for the roadmap

- **J3 / I1: the minimum Java stays 11**; both builds ran all four kinds of spec and an override on Temurin 11. The "Waiting on question 28" note in J3 about the minimum can go; M3's `--release 11` stays. 30 I1's Java 11 axis is expected to pass on both OSes of its matrix (the same runs passed on the Ubuntu and macOS runners).
- **M3: `--release <java.min_version>` is confirmed to be what makes a module load on every supported Java**: without it a JDK 25 build is refused on 11 and 21; with `--release 11` it loads on 11, 21, 25.
- **11 R7 part 4 (the hint) misses the class-version case as written.** The refusal of a newer index class is message **2173**, severity 1, not 1000. It names the class and states both class-file versions, so tlaup can say exactly what to do. Suggested for the designer: treat 2173 (any text) as an override load failure, and when its text contains `has been compiled by a more recent version of the Java Runtime`, add a hint like "the override classes were compiled for a newer Java than the one running TLC; rebuild the module with `tlaup module add` (it compiles with `--release <java.min_version>`) or run TLC on a newer Java". The mixed case (a listed class newer than its index) is a 1000 whose text contains `java.lang.UnsupportedClassVersionError`, so R7's existing 1000 hint fires, and the same text test can make it specific. The parser should know 2173 as an error kind (it is severity 1 in `-tool` output, exit 255).
- **A before-the-run check is possible and cheap**: the M3 class-file reader already reads the version (bytes 6 to 7 of each class). tlaup could compare the highest major under `classes/` with the running Java's major (known from J3) and warn before TLC starts. Only a suggestion; the TLC message is clear enough that the hint alone would do.
- **J3, macOS `java`: the exclusion by path is needed and right, and cannot be dropped.** `/usr/bin/java` is a compiled binary named `java`, so the `#!` and name rules would remember it. Its size and modification time are the stub's own, and they do not change when JDKs are installed or removed or `JAVA_HOME` changes, so a remembered answer would be stale exactly when the user switches JDK. Suggested: exclude, on macOS, every `java` or `javac` directly under `/usr/bin` (and, if wanted, any file that is the same file as `/usr/libexec/java_home`, by device and inode). `/usr/bin/javac` was not checked; it is expected to be the same stub. On Linux the system `/usr/bin/java` is a plain link to a real binary that ignores `JAVA_HOME`, so remembering it there is right.
- **Launcher signals ([research 15](15-exit-codes-and-signals.md))**: nothing special for macOS. Through the stub, the process tlaup starts is the JVM itself (same PID, the stub `exec`s the JDK's `java`), so signals and waiting work as with a direct JDK path.
- **J2 and the stub**: tlaup prefers `$JAVA_HOME/bin/java`, so the stub is reached only when `JAVA_HOME` is unset or holds no `java`. The stub then runs the newest registered JDK, not the next `java` on `PATH`. With a stale `JAVA_HOME` (empty or missing folder) J2 warns and falls back to `PATH`; if that is `/usr/bin/java`, the stub ignores the stale value silently too, so J2's warning is the only one the user gets. Nothing to change; worth a line in J2.
- **J3, a failure case to add**: on macOS with no JDK registered, `/usr/bin/java -version` exits 1 and prints `Unable to locate a Java Runtime.` on stderr. By J3 as written that is "answered something that is not a version": a warning, and the run goes on; TLC then fails with the same text and exit 1, which [research 15](15-exit-codes-and-signals.md) lists as TLC's usage error. Suggested: treat a non-zero exit from `-version` with no version in the answer as `JavaNotFound` (code 3), showing what the stub printed and the usual "install Java 11 or newer" hint. A feature test with a fake `java` that prints that text and exits 1 covers it.
- **30 I1**: a macOS arm64 runner already has Temurin 11, 17, 21 and 25 registered, and the stub is on `PATH` after setup-java's JDKs. The integration job should keep the `JAVA_HOME` that setup-java sets, so tests run the Java of the matrix cell and not the stub's choice (25). Runner images are arm64; Intel Macs are not covered by I1.

## Open follow-ups

- Java 17 and Java 8 were not run; Intel macOS and `/usr/bin/javac` on macOS were not checked.
- What a Mac that never had a JDK shows in a desktop session (from memory, Apple has offered an install dialog): not observable on a runner.
- The older convention (`tlc2.module.<Module>` or a class named like the module) with a newer class file: expected 2173 by source, not run.
- What the formatted `tlaup tlc` output shows today for 2173 was not run (research 13 ran tlaup on five cases, none of them 2173).

## Date checked

2026-11-18 (local), Linux x86-64; jars as in the brief (rolling and v1.8.0 checked as identical on 2026-11-19 UTC). Javas: Temurin 11.0.33+10, OpenJDK 21.0.13 (Debian), OpenJDK 25.0.5 (Debian). CI run 2026-11-19 UTC (see Source).
