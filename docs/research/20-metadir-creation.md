# 20. Does TLC create a missing `-metadir` folder?

## Question

Does TLC create the folder given to `-metadir`, and its missing parents, when it does not exist, on v1.7.4 and on
1.8.0 (rolling)? Which cases fail (a parent that is a file, a parent without write permission, a relative path)? What
does TLC create inside it? Decides whether the command printed by `--show-command` can be pasted as it is
([11 R9](../design/11-runner.md#r9-show-command), [R6](../design/11-runner.md#r6-run-folders)). Question 17 read the
code (v1.7.4 uses `mkdirs`; the rolling build's handling of the parent was not traced) and did not run it.

## Source

- Jars (already downloaded, not fetched again), Linux x86-64, 12 cores, other agents' runs on the same machine:
  - v1.7.4: `TLC2 Version 2.19 of 08 August 2024`, rev `5a47802b5c391f59ecdd44117981f4ff8c0656ba`, sha256 `936a2620...`.
  - 1.8.0 (rolling): `TLC2 Version 2026.11.15.002146`, rev `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`, sha256
    `7e53aa63...` (the `rolling` and `v1.8.0` assets are byte-identical).
  - Java: OpenJDK 25.0.5, OpenJDK 21, Temurin 11.0.33+10 (every case was run on each).
- Upstream source, pinned:
  - `FileUtil.makeMetaDir`, v1.7.4: [lines 229-258](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/util/FileUtil.java#L229-L258).
  - `FileUtil.makeMetaDir`, `createExclusiveDirectory`, `createExclusiveDirectoryWithApproximateName`, 1.8.0:
    [lines 268-340](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/util/FileUtil.java#L268-L340).
  - Callers: `TLC.handleParameters`, [v1.7.4 line 958](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L958),
    [1.8.0 line 1283](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1283).
    The option text is stored as `args[i] + File.separator` ([v1.7.4 line 717](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L717),
    [1.8.0 line 980](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L980)).
- Experiments: `tests/fixtures/research/20-metadir-creation/` (`cases.sh` the driver, `specs/` the specs,
  `out_<version>_j<java>.txt` the six full outputs, `file-parent-failure.txt`, `violation-tree.txt`,
  `metadir_creation.py` the cross-platform script prepared for CI).

## Short answer

**Yes, on both versions, on Linux, macOS and Windows.** TLC creates the `-metadir` folder and all its missing parents. Before it does any other
work it calls `makeMetaDir`, which creates `<metadir>/<timestamp>` together with every missing folder above it:

- v1.7.4: `new File(metadir + timestamp).mkdirs()` (creates parents).
- 1.8.0: `Files.createDirectories(parent)` followed by `Files.createDirectory(dir)` (the parent is created, the
  timestamped folder itself must be new; if the name is taken it falls back to `Files.createTempDirectory(parent,
  name)`).

Measured, all identical on both versions and all three Java versions:

| Case | Result |
|---|---|
| `-metadir` exists (control) | exit 0 |
| one level missing (`b1`) | created, exit 0 |
| three levels missing (`c1/c2/c3`) | all three created, exit 0 |
| missing, with a trailing `/` | created, exit 0 |
| relative, `rel1/rel2` and `./relx`, from the cwd | created under the cwd, exit 0 |
| parent is a symlink to an existing folder | works, created in the target |
| a parent is a regular file (`afile/md`, `afile/m1/m2`) or `-metadir` itself is a file | fails, exit 1, nothing created |
| parent folder without write permission (mode 555), one or two levels below it | fails, exit 1, nothing created |
| dangling symlink as parent, or as `-metadir` itself | fails, exit 1 |

A failure is an uncaught Java exception printed before any TLC output (no banner, no SANY line), exit code 1:
`Exception in thread "main" util.Assert$TLCRuntimeException: TLC could not make a directory <metadir>/<timestamp> for
the disk files it needs to write.` followed by a four-line stack trace (`makeMetaDir`, `TLC.handleParameters`,
`TLC.main`). The text names the timestamped folder, not the folder the user gave; it does not say why (file in the
way, permission). With a relative `-metadir` (file-parent-failure.txt) v1.7.4 prints the absolute path (`getAbsolutePath`) and 1.8.0 prints it as given.

Inside the folder: only the timestamped subfolder `<metadir>/<yy-MM-dd-HH-mm-ss[.SSS]>` and what research 17 lists in it
(`<Spec>_0.fp`, `<Spec>_1.fp`, `<Spec>.st`, `<Spec>-<w>.st`, queue pool files, checkpoint files with `-checkpoint`).
TLC creates nothing else at any level: the missing parents stay empty. After a clean finish the timestamped folder is
deleted and `-metadir` and the parents stay as empty folders (all cases). After a violation 1.7.4 deletes it too and
1.8.0 keeps four empty files (`Viol_0.fp`, `Viol_1.fp`, `Viol.st`, `Viol-0.st`), as research 17 found.

## Confidence

Verified on Linux (pinned jars, Java 25, 21 and 11; source of both commits read) and on the CI run's three runners
(below): the same results on macOS and Windows for every case run there. Not tested: a metadir on a filesystem that is
full or read-only as a whole, paths with spaces or non-ASCII characters, very long paths (Windows MAX_PATH),
`-recover` (it passes the folder through and creates nothing, from the source), and on Windows the not-writable-parent
case and symlink cases (the script skips them).

## Evidence

### Source trace

v1.7.4 (`FileUtil.java` lines 229-258): `fromChkpt != null` returns it unchanged. Otherwise `metadir = TLCGlobals.metaDir`
(the `-metadir` text plus a separator) or `<specDir>states/`; appends the timestamp; then

```
Assert.check(!filedir.exists(), EC.SYSTEM_METADIR_EXISTS, ...);          // line 252
Assert.check(filedir.mkdirs(),  EC.SYSTEM_METADIR_CREATION_ERROR, ...);  // line 255
```

`File.mkdirs()` creates "all necessary and nonexistent parent directories" and returns false when the leaf could not
be made, including when a parent is a file or not writable. The `Assert` turns false into the exception seen.

1.8.0 (`FileUtil.java` lines 268-340): `Paths.get(TLCGlobals.metaDir)` (or `<specDir>/states`) `.resolve(timestamp)`,
then `createExclusiveDirectoryWithApproximateName`, whose first step `createExclusiveDirectory` does
`Files.createDirectories(directory.toAbsolutePath().getParent())` then `Files.createDirectory(directory)`. The javadoc
says "all missing parent directories are created first". Any `IOException` other than `FileAlreadyExistsException` goes
to `Assert.fail(EC.SYSTEM_METADIR_CREATION_ERROR, ...)` (line 300): the same message and the same exit code 1.
`createDirectories` throws `FileAlreadyExistsException` when the parent path is a file; that is caught by the same
`catch`, so the fallback `Files.createTempDirectory(parent, name)` runs and fails with an `IOException`, which ends in the
same `Assert.fail`. This matches the runs (parent-is-file gives the same message, exit 1). The call sits in
`TLC.handleParameters` (line 1283), which runs while the arguments are parsed, before the spec is parsed: so a bad
`-metadir` fails fast, before SANY runs.

### Runs

`cases.sh <label> <jar> <java>` (spec `Small`: 6 states, `CHECK_DEADLOCK FALSE`), every case from a private empty cwd,
`-workers 1`. The six outputs are `out_<version>_j<java>.txt`; their per-case exit codes and trees are the same in all
six. The tree after each case (`d` folder, `f` file, `l` symlink, relative to the case folder; the timestamped folder is
already deleted) for the 1.8.0 / Java 25 run:

```
B_one_level_missing           exit=0   d b1
C_three_levels_missing        exit=0   d c1, d c1/c2, d c1/c2/c3
E_relative_missing rel1/rel2  exit=0   d cwd/rel1, d cwd/rel1/rel2
G_parent_is_file              exit=1   f afile                      (nothing created)
J_parent_not_writable         exit=1   d ro                         (nothing created)
```

Failure output, both versions (`file-parent-failure.txt`):

```
Exception in thread "main" util.Assert$TLCRuntimeException: TLC could not make a directory <W>/afile/md/26-11-18-22-01-54 for the disk files it needs to write.
	at util.Assert.check(Assert.java:91)
	at util.FileUtil.makeMetaDir(FileUtil.java:255)
	at tlc2.TLC.handleParameters(TLC.java:958)
	at tlc2.TLC.main(TLC.java:246)
```

(1.8.0: `Assert.fail(Assert.java:86)`, `FileUtil.java:300`, `TLC.java:1283`, `TLC.java:320`.)

Violation spec into a missing `vm/b/c` (`violation-tree.txt`): v1.7.4 leaves `vm`, `vm/b`, `vm/b/c` (empty); 1.8.0 leaves the
same plus `vm/b/c/<timestamp>` with the four zero-byte files. Exit 12 in both.

### CI run (macOS and Windows)

Run <https://github.com/nikolskiy/tlaup/actions/runs/44489200898> (branch `research/top-up-experiments`, commit 0d43a75,
2026-11-19 08:37-08:48 UTC, success). Runner images: ubuntu-latest ubuntu26 20261111.82.6 x86_64, macos-latest macos26
20261112.0504.1 arm64, windows-latest win25-vs2026 20261103.298.1 x86_64. Java: Temurin 11.0.33+10 and 21 on PATH
(`java` is the one setup-java put first; the log does not say which). Jars as in the brief. Logs:
`tests/fixtures/research/20-metadir-creation/ci/q20-<os>.txt`.

| Case (both versions) | Linux | macOS | Windows |
|---|---|---|---|
| existing | exit 0 | exit 0 | exit 0 |
| one level missing | created, 0 | created, 0 | created, 0 |
| three levels missing | created, 0 | created, 0 | created, 0 |
| relative `rel1/rel2` | created, 0 | created, 0 | created, 0 |
| parent is a file | exit 1, nothing | exit 1, nothing | exit 1, nothing |
| parent not writable | exit 1, nothing | exit 1, nothing | not run (POSIX only) |

The failure text is the same on all three ("TLC could not make a directory <metadir>/<timestamp> ...", with `\`
separators on Windows). Windows is the one place the creation could have differed; it did not.

## Implications for the roadmap

- **R9: the printed command can be pasted as it is.** The `-metadir <cache>/runs/<run-id>` it names does not need to
  exist; TLC creates it and `<cache>/runs` above it, on both pinned versions. The "Waiting on question 20" paragraph
  of R9 can be closed: no `mkdir` line, no variant of the command, no option to create the folder.
- It does fail the way the user must be able to understand if the folder cannot be made (a file in the way, no
  permission): exit 1 with a Java exception that names the timestamped path. That is the pasted-command case only; a real
  run has `run_folder` (R6), which makes the folder and the lock itself and maps a failure to `FileOperationError`
  (code 5) before TLC starts. The two are consistent: tlaup need not pre-create the folder for TLC's sake, but the
  runner creates it anyway for the lock.
- A pasted command leaves `<cache>/runs/<run-id>` behind as an empty folder after a clean finish (and a populated one after
  a violation on 1.8.0 or a signal). That matches R9's rule that the sweep removes a folder with no `run.json` after 30
  days; nothing new.
- A relative `-metadir` given by the user is created below the cwd of the TLC process (tlaup's `cwd`), which is
  what a user pasting from the project root expects. tlaup itself prints an absolute path, so this does not arise.
- Windows and macOS behave the same as Linux for creation and for the file-in-the-way failure: no platform note for R9.

## Open follow-ups

- Windows: the not-writable-parent and symlink cases were not run.
- The 1.7.4 `mkdirs` is not atomic with the `exists` check above it (research 17); not relevant to creation.

## Date checked

2026-11-18 (jars as of 2026-11-19 UTC per the brief: still the current rolling and v1.8.0 asset).
