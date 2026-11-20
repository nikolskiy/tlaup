# 27: Does standalone SANY honour `-DTLA-Library` and extra classpath entries like TLC does?

## Question

Does `java tla2sany.SANY` find modules through `-DTLA-Library=<folders>` and through extra classpath entries (a
folder or a jar that holds `.tla` files, such as a CommunityModules jar) the way TLC does, on v1.7.4 and on 1.8.0
(rolling)? Where does it search, in what order, when a module exists in several places (spec folder, library,
classpath folder, classpath jar, the standard modules)? Decides whether `tlaup sany` can pass the same classpath and
`-DTLA-Library` as `tlaup tlc` ([design 21 S1](../design/21-other-tools.md#s1-sany), step 2 and "Waiting on
question 27").

## Source

- Jars (sha256 and commits as in research 17): v1.7.4 `TLC2 Version 2.19 of 08 August 2024`, commit
  `5a47802b5c391f59ecdd44117981f4ff8c0656ba`; "1.8.0 (rolling)" CalVer 2026.11.15.002146, commit
  `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`.
- CommunityModules release `202611060952` (tlaplus/CommunityModules, latest on the day), each asset in its own folder:
  `CommunityModules.jar` (145180 bytes, sha256 `f9ceeef4...c6e28`) and `CommunityModules-deps.jar` (4930534 bytes,
  sha256 `a3b27c40...2b5fb`).
- Java: OpenJDK 25.0.5 for all cases; the SANY half (cases 01 to 17) repeated on Temurin 11.0.33+10 with the same
  results. Linux x86-64, 12 cores.
- Upstream source, read at both pinned commits (`tlatools/org.lamport.tlatools/src/`):
  - `util/SimpleFilenameToStream.java`: [v1.7.4](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/util/SimpleFilenameToStream.java)
    (`getLibraryPaths` line 119, `locate` line 161, the classpath fallback line 223),
    [1.8.0](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/util/SimpleFilenameToStream.java)
    (constructor line 78, `getInstallationBasePath` line 89, `searchUserDirOrCWD` line 112, `parsePaths` line 145,
    `locate` line 164).
  - `util/ToolIO.java` `getDefaultResolver` (line 200 in 1.8.0): the resolver SANY uses when `new SpecObj(file, null)`
    is built (`tla2sany/drivers/SANY.java`, passes `null`).
  - `tlc2/TLC.java` calls `ToolIO.setUserDir(specDir)` ([v1.7.4 line 942](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L942),
    [1.8.0 line 1267](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1267)).
    SANY's driver never calls it.
- Experiments: `tests/fixtures/research/27-sany-library-path/` (`setup.sh` builds the tree, `run.py` runs every case
  against both jars and both tools; `java25/<version>-<tool>-<case>.{cmd,out,err,exit}`, `java11-sany-only/`,
  `summary-cases-01-17.txt`, `summary-ladder-20-27.txt`).

## Short answer

- **Yes, both honour both, identically, on both versions.** `tla2sany.SANY` builds the same `SimpleFilenameToStream`
  resolver that TLC builds. It reads `-DTLA-Library` (entries separated by the platform path separator, `:` on Linux) and falls
  back to the Java classpath for `<Module>.tla`, whether the classpath entry is a folder or a jar. SANY and TLC
  agree on module lookup in every case of the table below except two: the spec's own folder (case 16, SANY does
  not search it) and the CommunityModules jars on v1.7.4 (cases 11 and 12, where SANY finds the modules and TLC
  then fails loading the Java classes).
- **Search order** (same in both tools and both versions, confirmed by a ladder in which a module `Dup` existed in
  every place and the winner was removed step by step):
  1. the working folder (for TLC: the spec's folder, since TLC sets the user directory to it; for SANY: the
     JVM's working folder, because SANY never sets a user directory);
  2. the `-DTLA-Library` entries, in the order given;
  3. the standard modules inside `tla2tools.jar`;
  4. the Java classpath, in classpath order (a folder and a jar are interleaved by position, not folders first).
  A module in the library or in the working folder with the name of a standard module (`Naturals`) shadows the
  standard one; the same module in a classpath folder does not (step 3 comes before step 4).
- **SANY does not look in the spec's folder** when the spec is named by an absolute path and SANY runs elsewhere:
  `Cannot find source file for module Dup imported in module S`, exit 255, on both versions, where TLC finds it (it
  sets the user directory). `tlaup sany` must therefore run in the spec's folder (as S1 already says), or add the
  folder to `-DTLA-Library`. Question 32 (working folder) can use this.
- **A jar is not accepted as a `-DTLA-Library` entry** (neither tool, both versions): jars go on the classpath.
- **Library entries are forgiving**: a trailing separator, an entry that does not exist, an empty entry (`a::b`) and a
  relative entry (resolved against the working folder) all work, in both tools, both versions.
- **CommunityModules**: `-cp <jar>` with `EXTENDS Functions` (which pulls in `Folds`) works in SANY on both
  versions, and in TLC on 1.8.0. TLC on **v1.7.4 fails** with both jars with `NoClassDefFoundError:
  tlc2/value/impl/KSubsetValue` (exit 255): the CommunityModules classes were built against a newer TLC than 1.7.4.
  That is a TLC and CommunityModules compatibility fact and does not touch SANY, which never loads the Java classes.
- **Differences between the versions** that tlaup may notice, none affecting what is found: v1.7.4 copies every
  module it reads out of a jar or off the classpath to `<java.io.tmpdir>/<Module>.tla` (a shared, fixed name:
  `Parsing file /tmp/Naturals.tla`, even for the standard modules); 1.8.0 copies to a fresh `tlc-<digits>`
  folder per run and prints the jar URL after the path. Two concurrent v1.7.4 runs write the same temporary
  files (not tried; read from `read`/`TMPDIR` in the source).

## Confidence

Verified, on Linux with Java 25 (and Java 11 for SANY cases 01 to 17), for both jars, with both a hand-made jar and
the real CommunityModules jars. Not tested: Windows and macOS (path separator `;` on Windows, drive letters in a
library entry, case-insensitive file systems), a library path with spaces or non-ASCII characters, a symbolic link
as a library entry, a `.tla` file whose module name differs from its file name, `-DTLA-Library` given twice.

## Evidence

### 1. How the resolver is built (source)

v1.7.4, `SimpleFilenameToStream.getLibraryPaths`: the list is the property split on `File.pathSeparator`, each entry
given a trailing separator, with the standard-modules location appended last. `locate(name)`:
index 0 is `ToolIO.getUserDir()` when it is set, otherwise the bare relative name (so the JVM's working folder);
then every library entry; then the standard modules (a jar location is read from `tla2sany/StandardModules/` as a
resource and copied to the temporary folder); and when nothing exists, a last attempt
`cl.getResourceAsStream(name)` on the class loader, that is the whole classpath ("the use case ... additional TLA+
module collections ... which ship a single jar", comment at line 217-222).

1.8.0 rewrote this with locators and the same order: `userFileResourceLocator` = working folder (user directory or
`user.dir`), then the `TLA-Library` entries (`parsePaths`; the property absent gives no entries); then
`standardLibraryResourceLocator` = classpath resource `tla2sany/StandardModules/`, then the bare classpath root.
`SANY` creates it through `ToolIO.getDefaultResolver()`, so the property is read by SANY exactly as by TLC. The one
source-level difference between the tools is `ToolIO.setUserDir(specDir)`, called by TLC only.

### 2. Cases (`summary-cases-01-17.txt`; both versions give the same row unless noted)

| Case | SANY | TLC |
| --- | --- | --- |
| 01 module only in `-DTLA-Library=libA` | found, exit 0 | found, exit 0 |
| 02 same, no property (control) | `Cannot find source file for module OnlyInLibA`, 255 | same, 150 |
| 03 two folders `libA:libB`, spec extends one module of each | found | found |
| 04 module only in the second folder | found | found |
| 05 trailing separator after the last entry | found | found |
| 06 first entry does not exist | found | found |
| 07 empty entry (`libA::libB`) | found | found |
| 08 relative entry `../libA` (working folder `spec`) | found | found |
| 09 module only in a classpath folder, no property | found | found |
| 10 module only in a jar on `-cp`, no property | found | found |
| 11 `CommunityModules.jar` on `-cp`, `EXTENDS Functions` | found | 1.8.0 found; v1.7.4 `NoClassDefFoundError` (see above), exit 255 |
| 12 `CommunityModules-deps.jar` on `-cp` | found | same split as 11 |
| 13 `EXTENDS Functions`, no jar (control) | not found, 255 | not found, 150 |
| 14 `CommunityModules.jar` as a `-DTLA-Library` entry | not found, 255 | not found, 150 |
| 15 library folder and classpath folder together | found | found |
| 16 working folder `other`, spec given by absolute path, sibling module `Dup` next to the spec | **not found, 255** | found (user directory = spec folder) |
| 17 working folder `other`, spec given as relative `S.tla` | not found (the spec is not there), 255 | cfg error `File not found`, 150 (v1.7.4) / 151 (1.8.0) |

The SANY lines show where each module came from, for example 1.8.0 case 11:
`Parsing file /tmp/tlc-<n>/Functions.tla (jar:file:<work>/cm/CommunityModules.jar!/Functions.tla)`.

### 3. Precedence (`summary-ladder-20-27.txt`)

`Dup` in the spec folder, `libA`, `libB`, a classpath folder (`cpdir`) and a classpath jar (`dup.jar`); each file
defines `Where == "<its place>"` and the spec prints it under TLC. Winner (TLC printed value; SANY's
`Parsing file` line agrees):

| Case | Setup | Winner (both versions, both tools) |
| --- | --- | --- |
| 20 | all five exist, `-DTLA-Library=libA:libB`, `-cp ...:cpdir:dup.jar` | spec folder |
| 21 | spec copy removed | `libA` |
| 22 | `libA` copy removed | `libB` |
| 23 | no library; `-cp ...:cpdir:dup.jar` | `cpdir` |
| 24 | no library; `-cp ...:dup.jar:cpdir` | `dup.jar` (the classpath order decides) |
| 25 | `Naturals.tla` in `libA`, `-DTLA-Library=libA` | the library copy shadows the standard `Naturals`; the spec then fails on `Sequences` (which needs `..` from the real Naturals): exit 150 under TLC, SANY reports it as semantic errors with exit 0 |
| 26 | `Naturals.tla` in the spec folder | same: the spec-folder copy shadows |
| 27 | `Naturals.tla` in a classpath folder | **not used**: the standard `Naturals` is read (`Unknown operator Where` proves it) |

On v1.7.4 the SANY line for classpath hits says `/tmp/Dup.tla` for both a folder and a jar (the copy), so only
the TLC `Where` value shows which one won; on 1.8.0 a folder hit prints the folder path.

## Implications for the roadmap

- S1, step 2 can stay as written: `tlaup sany` passes the same classpath and `-DTLA-Library` as `tlaup tlc`; the
  fallback "the help says SANY cannot see registered modules" and "step 2 passes the jar alone" is not needed.
  Registered modules, project `modules/` folders and a CommunityModules jar on the classpath are all found by SANY.
- `tlaup sany` must run in the spec's folder (or put it on the library path) for modules next to the spec to be
  found; this is a fact for question 32 and for D34: SANY, unlike TLC, does not take the spec's folder as the
  user directory.
- A jar given in the library list is silently useless for both tools; if tlaup ever lets a user name a jar module
  source, it belongs on the classpath.
- Help text for `sany` can say: modules are searched in the working folder, then the library folders, then the standard
  modules, then the classpath.
- On v1.7.4, `tlaup tlc` with the CommunityModules jar fails in TLC itself (`NoClassDefFoundError`, not SANY); worth
  a note where tlaup documents CommunityModules (research 4) and for the integration tests.

## Open follow-ups

- Windows and macOS: `;` as separator and drive-letter paths in `-DTLA-Library`, case-insensitive file systems,
  `java.io.tmpdir` copies. No CI script was prepared; the parts that depend on the OS are only the separator and
  paths, and `tlaup` builds those with `os.pathsep`. Say if a CI check of cases 01, 03 and 10 is wanted.
- Whether two concurrent v1.7.4 SANY or TLC runs, both extracting modules to the same `/tmp/<Module>.tla`, can
  corrupt each other (source says the name is fixed; not run).
- `-DTLA-Library` entries with spaces or non-ASCII characters.

## Date checked

2026-11-18.
