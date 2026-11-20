# 24. Path-taking flags with an absolute spec, and symbolic links

## Question

With the spec given as an absolute path and TLC running in another folder (the arrangement of [decision D34](../roadmap.md) and [design R4](../design/11-runner.md#r4-spec-cfg-and-working-folder)):

1. Where does TLC resolve a relative path given to `-dump`, `-dumpTrace` (1.8.0 only), `-metadir`, `-userFile`, `-teSpecOutDir` (1.8.0 only) and every other path-taking flag? Which flags are those, at both pinned commits?
2. On v1.7.4, is a cfg outside the spec's folder, reached with `..` and a relative `-config`, read when the spec is absolute? (Question 16 listed it as not tested beyond row B4.)
3. When the spec is reached through a symbolic link to a folder, where does TLC look for the modules the spec EXTENDS or INSTANCEs: beside the link path, or beside the real path? The same for a link to the spec file itself.
4. Does the relative `-config` that tlaup computes in R4 step 4 (`os.path.relpath(realpath(cfg), realpath(spec.parent))`) still name the validated file when the spec's folder is behind a link and the cfg is reached with `..`?

## Source

- Jars, run directly with `java -cp tla2tools.jar tlc2.TLC` on Linux x86-64 (12 cores), OpenJDK 25.0.5; the CI script was also run on Temurin 11.0.33 with identical results.
  - v1.7.4: `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`, commit `5a47802b5c391f59ecdd44117981f4ff8c0656ba`, sha256 `936a2620...`.
  - 1.8.0 (rolling): `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`, commit `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`, sha256 `7e53aa63...`. `rolling` and `v1.8.0` hold the same jar.
- Upstream source at both commits (links below); the option parser is `tlc2/TLC.java`, `handleParameters`.
- Research [16](16-config-path.md), [17](17-metadir.md), design R4, R6, R8, decision D34.
- Experiment scripts, layout and captured output: [`tests/fixtures/research/24-path-flags-and-links/`](../../tests/fixtures/research/24-path-flags-and-links/). Below `<T>` is the generated test tree, `<tmp>` the scratch folder.

## Short answer

**Headline (second CI run included): the Windows rule is now verified: on Windows, with the spec behind a link, a relative `-config` computed from `abspath` (text, no `realpath`) names the validated file in every row where the file exists, on both builds. Everything below holds on Linux and macOS. On Windows the flag results, the `..` cfg with an absolute spec and the file link hold, but `..` after a symbolic link does not: Windows collapses `..` as text before following the link, so the relative `-config` of R4 step 4 misses the validated file there (details in point 4).**

1. **Every relative path given to a TLC flag is read against TLC's own working folder (the folder tlaup was started from), not the spec's folder, with one exception: `-config`** (and the spec itself), which go through TLC's module resolver and so use the spec's folder when the spec is absolute (question 16, rows B2 to B9). This holds on both builds for `-dump`, `-metadir`, `-userFile`, `-recover`, `-simulate file=`, and on 1.8.0 for `-dumpTrace`, `-loadTrace` and `-teSpecOutDir`. Flags that take a path, from the option parser:

   | flag | v1.7.4 | 1.8.0 | relative path lands in | notes |
   | --- | --- | --- | --- | --- |
   | `-config` | yes | yes | spec folder (absolute spec) | question 16 |
   | `-dump [dot...] FILE` | yes | yes | working folder | `.dump` or `.dot` appended unless already there; the folder must exist (`sub/rel` gives "Unable to write to file", exit 1); `${metadir}/x` is replaced by the run's metadir |
   | `-metadir DIR` | yes | yes | working folder | `../x` works too |
   | `-userFile FILE` | yes | yes | working folder | the folder must exist (exit 1 otherwise) |
   | `-recover DIR` | yes | yes | working folder | from another folder: `FileNotFoundException ... vars.chkpt` |
   | `-simulate file=PREFIX,num=N` | yes | yes | working folder | writes `PREFIX_<n>_<m>` |
   | `-dumpTrace FORMAT FILE` | no | yes | working folder | creates missing folders; its help text says "relative to the same directory as the main spec", which is wrong for an absolute spec |
   | `-loadTrace FORMAT FILE` | no | yes | working folder | a file that exists only in the spec's folder is not found (exit 75) |
   | `-teSpecOutDir DIR[/NAME.tla]` | no | yes | working folder | see point 4 |

   No other flag in either option parser takes a path. `-DTLA-Library` (a JVM property, not a flag) takes a list of folders and is honoured with an absolute spec (question 16, E2).

2. **Two defaults that do not follow the working folder, both written beside the spec.** Without `-metadir`, TLC creates `states/` in the spec's folder when the spec is absolute (both builds); tlaup always passes `-metadir`, so this does not arise. On a violation 1.8.0 writes `<Spec>_TTrace_<n>.tla` and `.bin` into the spec's folder (default, no flag needed), and v1.7.4 writes `SpecTE.tla` and `SpecTE.cfg` there only with `-generateSpecTE`. `-noGenerateSpecTE` (1.8.0) suppresses it. `-cleanup` deletes `states/` in the working folder, not in the spec's.

3. **Question 2: yes.** On v1.7.4 and 1.8.0, with an absolute spec, a relative `-config ../out.cfg` reads `<spec folder>/../out.cfg`, outside the spec's folder (`../out.cfg`, `../other/o.cfg`, `../../outside/o.cfg`: all three read the right file on both builds). Only an absolute `-config` outside the spec's folder fails on v1.7.4, as question 16 found.

4. **Symbolic links: TLC never resolves them.** It builds paths from the spec path as given and hands them to the operating system; it does not tidy `..` as text.
   - Spec reached through a link to a folder: the modules and the default cfg are read from the folder the link leads to (which is, by definition, the "beside the link path" folder; there is no second folder to prefer). A `..` after the link is walked by the operating system from the link's target, so `-config ../out.cfg` names the file next to the target's parent, not next to the link's parent (row M2: 12 against a decoy 99). A spec path itself containing `link/../x/Spec.tla` works (L4, M5).
   - **Windows differs.** With the spec behind a link to a folder, a `..` after the link is collapsed as text, not walked from the target: `link/../out.cfg` reads `<link's parent>/out.cfg` (the decoys, N=44 and 99, were read on both builds), and a spec path `link/../proj/Spec.tla` is not found. Python's `open` on the same path gave the same lexical answer on the runner (the script's "validated" N matched TLC's), so this is the Windows file API (inferred: the script does not separate Java from Win32). Consequence: R4 step 4's `relpath(realpath(cfg), realpath(spec.parent))` is wrong on Windows when the spec is behind a link: TLC read nothing (N=None, "File not found") in 5 of 6 link rows; the sixth (cfg `link/../out.cfg` with a one-level link) coincided. Without links it is fine (no-link row passes everywhere).
   - Spec given as a link to the file: modules and the default cfg are looked up **beside the link, not beside the target** (also on macOS and Windows; F1, F2: `Helper` from the link's folder, `Spec.cfg` = 77 from the link's folder, not 1 from the target's). The same for a relative spec path (F3, F5).

5. **Question 4: yes on Linux and macOS; no on Windows when a link is involved.** In all ten layouts tried (twenty runs, both builds) the relative `-config` computed as in R4 step 4 makes TLC read the validated file: spec behind a link to a folder, cfg reached with `..` (inside and outside the target's tree), a cfg beside the link's parent, a cfg in a folder elsewhere, spec a link to a file, and the no-link control. (Windows: see point 4.) The computation is correct on POSIX because TLC joins the relative value to the spec's folder as given and the operating system walks it; the realpath-to-realpath `relpath` is the same answer the operating system would give for the walk.

## Confidence

**Verified** on Linux (Java 25 and, for the CI script, Java 11) for every row, on both builds, with distinct constants and module markers identifying the file read. The source explanation (no canonicalisation, `ToolIO.userDir` only used by the resolver) is read, not stepped through. **macOS and Windows: run in CI** (run [44489200898](https://github.com/nikolskiy/tlaup/actions/runs/44489200898), branch `research/top-up-experiments`, commit 0d43a75, 2026-11-19 08:37-08:48 UTC; images ubuntu26 20261111.82.6 x86-64, macos26 20261112.0504.1 arm64, win25-vs2026 20261103.298.1 x86-64; Temurin 11.0.33+10 and 21 on PATH; logs `ci_ubuntu.out`, `ci_macos.out`, `ci_windows.out`): 26 lines each; Linux and macOS identical to my Linux run, Windows differs as in point 4. **Not run:** `-dumpTrace` formats other than `json` (the `tlc` format produced no file in the run and I did not find out why; the others need CommunityModules); builds between v1.7.4 and the CalVer jar; the Toolbox.

## Evidence

### Test layout

`mklayout.sh` builds `<T>` with a spec `Spec.tla` (prints its `CONSTANT N` and a `Marker` from `EXTENDS Helper`, and violates the invariant `x < 2` so TLC exits 12 and produces a trace) and cfgs whose `N` identifies the file. Real folders: `real/proj` (spec, `Spec.cfg` N=1, `sub/a.cfg` N=2, `Helper` marker `helper-real-proj`), `real/out.cfg` (4), `real/other/o.cfg` (5), `outside/o.cfg` (6). Links: `L/lnk -> ../real/proj` with decoys `L/out.cfg` (44) and `L/Helper.tla`; `L2/lnk -> ../deep/a/b` (spec there, `Spec.cfg` 11; `deep/a/out.cfg` 12, `deep/out.cfg` 13, decoy `L2/out.cfg` 99); `Lf/Spec.tla -> ../real/proj/Spec.tla` with `Lf/Helper.tla` (marker `helper-beside-file-link`) and `Lf/Spec.cfg` (77). The working folder `work/` holds decoys. Every run: `cd work && java -cp <jar> tlc2.TLC -nowarning -workers 1 -metadir <tmp>/... [flags] <T>/real/proj/Spec.tla` (absolute spec). Raw tables: `exp1_path_flags.out`, `exp2_links.out`; scripts in `scripts/`.

### A. Where relative flag paths land (spec `<T>/real/proj/Spec.tla`, cwd `work/`)

"cwd" is `<T>/work/`, "spec" is `<T>/real/proj/`. Same result on both builds unless marked. The first rows are in `exp1_path_flags.out`.

| # | flags | result |
| --- | --- | --- |
| P1, P2 | `-dump rel`, `-dump rel.dump` | `work/rel.dump` |
| P3 | `-dump dot rel.dot` | `work/rel.dot` |
| P4, P5 | `-dump sub/rel` (folder only in spec folder), `-dump dumps/rel` (nowhere) | "Unable to write to file sub/rel.dump", exit 1: the folder is looked up in the working folder, and is not created |
| P6 | `-dump '${metadir}/rel'` | `<metadir>/rel.dump` (checked once, 1.8.0) |
| P7 | `-dump <abs>` | the absolute path |
| M1, M2 | `-metadir relmeta`, `-metadir ../relmeta` | `work/relmeta/<timestamp>`, `<T>/relmeta/<timestamp>` |
| M3 | no `-metadir` | `real/proj/states/<timestamp>` (spec folder) |
| U1, U2 | `-userFile rel.out`, `-userFile sub/rel.out` | `work/rel.out`; the second: "Failed to create user output log file", exit 1 |
| T0 | 1.8.0, violation, no flag | `real/proj/Spec_TTrace_<n>.tla` and `.bin` (spec folder) |
| T1 | v1.7.4 `-generateSpecTE` | `real/proj/SpecTE.tla`, `SpecTE.cfg`; no `.bin`. Without the flag nothing is written. |
| S1 | `-config ok.cfg -deadlock -simulate file=rel,num=2` | `work/rel_0_0`, `work/rel_0_1` |
| D1 | 1.8.0 `-dumpTrace json rel.json` | `work/rel.json` |
| D2, D3 | `-dumpTrace json sub/rel.json`, `dumps/rel.json` | created `work/sub/`, `work/dumps/`: missing folders are created |
| D4 | `-dumpTrace json <abs>` | the absolute path |
| D5 | `-dumpTrace tlc rel.tlc` | no file anywhere (`tlc` format; not explained) |
| E1 | 1.8.0 `-teSpecOutDir te`, folder missing | the `.tla` is written to `work/te/` (folder created), the `.bin` fails: "Evaluating postcondition _TLCTraceSilent ... te/Spec_TTrace_<n>.bin (No such file or directory)"; exit code stays 12 |
| E1b | same, folder `work/te` exists | `.tla` and `.bin` both in `work/te/` |
| E2 | `-teSpecOutDir te/MyTE.tla` | `work/te/MyTE.tla`, same `.bin` failure when `te/` is missing |
| E3 | `-teSpecOutDir <abs dir>` | the absolute folder, both files |
| E4 | `-noGenerateSpecTE` | no TE files |
| L1 | 1.8.0 `-loadTrace json tr.json` | read from `work/` (exit 11, deadlock at the trace's end); with the file only in `real/proj/`: "tr.json (No such file or directory)", exit 75; an absolute path works |
| C1 | `-cleanup` | removes `work/states/` (checked: a planted folder was deleted) |
| K1 | `-checkpoint 1 -metadir relck`, kill, then `-recover relck/<ts>` | same folder: recovery completes (v1.7.4 and 1.8.0). From another working folder: `java.io.FileNotFoundException: relck/<ts>/vars.chkpt` on both. (`-checkpoint 0` writes none; a long-running test spec was needed for the first 1-minute checkpoint; it ends in a deadlock, which is unrelated.) Output: `exp3_recover_174.out`, `exp3_recover_180.out`. |

### B. Source (pinned)

Commits: v1.7.4 `5a47802b5c391f59ecdd44117981f4ff8c0656ba`, 1.8.0 `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`.

- Option parser, all path-taking flags: [v1.7.4 `TLC.java` L527-L741](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L527-L741) (`-config`, `-dump`, `-recover`, `-metadir`, `-userFile`; `-simulate file=` at L357-L368), [1.8.0 `TLC.java` L652-L1004](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L652-L1004) (adds `-teSpecOutDir` L652, `-loadTrace` L741, `-dumpTrace` L768; `-simulate file=` at L476-L500). The usage text lists the same set (plus `-recover`, undocumented there).
- Every one of them stores the string unchanged (`new File(arg)`, `Paths.get(arg)`, `fromChkpt = arg + separator`, `TLCGlobals.metaDir = arg + separator`); `ToolIO.setUserDir(specDir)` is called once, for an absolute spec ([1.8.0 L1256-L1283](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1256-L1283), [v1.7.4 L930-L958](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L930-L958)). A search on `ToolIO.getUserDir` finds only `SimpleFilenameToStream` (the resolver) in the TLC tools, so only module, spec and cfg lookup see the spec's folder; the file opens of the flags above go to the JVM's working folder.
- Default metadir: `Paths.get(specDir).resolve("states")` when `-metadir` is absent ([1.8.0 `FileUtil.java` L268-L281](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/util/FileUtil.java#L268-L281)); `specDir` is the absolute spec's parent. `-cleanup` calls `FileUtil.deleteDir(TLCGlobals.metaRoot, true)` with the relative name `states` (L1274-L1276).
- Default TE spec folder: `getTlaFileParentDir(mainFile)` ([1.8.0 L1236-L1239, L1719-L1728](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1225-L1250)), the parent of the spec path as given; with `-teSpecOutDir` the given path, relative to the working folder.
- No canonicalisation: `SimpleFilenameToStream` builds `TLAFile(userDir, name)` (v1.7.4) or `FilesystemResourceLocator(Path.of(userDir))` (1.8.0) from the string as given; neither calls `getCanonicalPath`, `toRealPath` or `normalize`, so links and `..` are left to the operating system ([v1.7.4](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/util/SimpleFilenameToStream.java#L161-L235), [1.8.0](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/util/SimpleFilenameToStream.java#L46-L125)). Read, not stepped through; the runs confirm it.

### C. Links (`exp2_links.out`, both builds, cwd `work/`, spec absolute)

"same" means v1.7.4 and 1.8.0 gave the same result in every row.

| # | spec, flags | result |
| --- | --- | --- |
| L1 | `<T>/L/lnk/Spec.tla` | N=1, `helper-real-proj` (the link's folder is the target; decoy `L/Helper.tla` not used) |
| L2 | same, `-config ../out.cfg` | **N=4** (`real/out.cfg`; the decoy `L/out.cfg`=44, the lexical result, is not read) |
| L3 | same, `-config sub/a.cfg` | N=2 |
| L4 | `<T>/L/lnk/../proj/Spec.tla` (lexically `L/proj`, which does not exist) | runs, N=1: the operating system walks the link |
| L5 to L7 | no link, `<T>/real/proj/Spec.tla`, `-config ../out.cfg`, `../other/o.cfg`, `../../outside/o.cfg` | N=4, 5, 6 on **v1.7.4 and 1.8.0** (answers question 2) |
| M1 | `<T>/L2/lnk/Spec.tla` (link to `deep/a/b`) | N=11 |
| M2 | same, `-config ../out.cfg` | **N=12** (`deep/a/out.cfg`; lexical would be `L2/out.cfg`=99) |
| M3 | same, `-config ../../out.cfg` | N=13 (`deep/out.cfg`; lexically `<T>/out.cfg` does not exist) |
| M4 | same, `-config ../../../L2/out.cfg` | N=99 (three `..` from `deep/a/b` reach `<T>`) |
| M5 | `<T>/L2/lnk/../b/Spec.tla` | runs, N=11 |
| F1 | `<T>/Lf/Spec.tla` (link to the file), default cfg | **N=77, `helper-beside-file-link`**: beside the link, not the target (target side: `Spec.cfg` N=1, `helper-real-proj`) |
| F2 | same, `-config Spec.cfg` | N=77 |
| F3 | relative `Spec.tla`, cwd `Lf/` | N=77, same helper |
| F4 | relative `../Lf/Spec.tla`, cwd `work/` | N=77 cfg; the Helper is the working folder's decoy (`helper-in-cwd`), as question 16 row D3 found for a relative spec with a folder |
| F5 | bare `Spec`, cwd `Lf/` | N=77 |

R4's relative `-config` (`exp2_links.sh`, function `relcfg`, the same expression as R4 step 4), spec as typed (through the link), cwd `work/`:

| # | spec | cfg validated | `-config` computed | TLC read |
| --- | --- | --- | --- | --- |
| R1 | `L/lnk/Spec.tla` | `L/lnk/../out.cfg` (the file `real/out.cfg`, N=4) | `../out.cfg` | N=4 |
| R2 | `L/lnk/Spec.tla` | `L/out.cfg` (44) | `../../L/out.cfg` | 44 |
| R3 | `L2/lnk/Spec.tla` | `L2/lnk/../out.cfg` (12) | `../out.cfg` | 12 |
| R4 | `L2/lnk/Spec.tla` | `L2/lnk/../../out.cfg` (13) | `../../out.cfg` | 13 |
| R5 | `L2/lnk/Spec.tla` | `L2/out.cfg` (99) | `../../../L2/out.cfg` | 99 |
| R6 | `L2/lnk/Spec.tla` | `work/out.cfg` (55) | `../../../work/out.cfg` | 55 |
| R7 | `L2/lnk/Spec.tla` | `outside/o.cfg` (6) | `../../../outside/o.cfg` | 6 |
| R8 | `L/lnk/Spec.tla` | `real/proj/sub/a.cfg` (2) | `sub/a.cfg` | 2 |
| R9 | `Lf/Spec.tla` (file link) | `real/out.cfg` (4) | `../real/out.cfg` | 4 |
| R10 | `real/proj/Spec.tla` (no link) | `outside/o.cfg` (6) | `../../outside/o.cfg` | 6 |

All twenty runs (ten rows, two builds) read the validated file. Note for R9: `spec.parent` is `Lf/`, the folder of the link itself, and the relative value is computed from there; TLC also joins to `Lf/` (the link path's folder), so the two agree.

### E. Second CI run: which `-config` value reads the validated file (`windows_links.py`)

Run [44491714376](https://github.com/nikolskiy/tlaup/actions/runs/44491714376) (branch `research/top-up-experiments`, commit 8647da2; ubuntu26 20261111.196.1 x86-64, macos26 20261102.0473.1 arm64, win25-vs2026 20261103.298.1 x86-64; Temurin 11.0.33+10 and 21; logs `ci2_ubuntu.out`, `ci2_macos.out`, `ci2_windows.out`). Rows R1 to R9 as in section C; "validated" is what Python reads from the cfg path as typed. Three values tried per row and jar: `relative-real` (R4 step 4 as designed), `relative-abs` (`relpath(abspath(cfg), abspath(spec.parent))`), `absolute-real` (`realpath(cfg)`).

| system | `relative-real` | `relative-abs` | `absolute-real` |
| --- | --- | --- | --- |
| Linux, macOS (identical) | OK 18 of 18 | OK in R1, R3, R4, R8, R9; wrong or no file in R2, R5, R6, R7 (cfg outside the link's tree) | 1.8.0: OK 9 of 9; v1.7.4: no file in 9 of 9 (cfg outside the spec's folder) |
| Windows | OK in R1, R2, R8, R9; no file in R3, R5, R6, R7 | OK in all 8 rows where the file exists | 1.8.0: OK in all 8; v1.7.4: no file in 9 of 9 |

- **Row R4 (`L2/lnk/../../out.cfg`) on Windows:** the cfg path collapses as text to `<T>/out.cfg`, which does not exist, so Python reports it missing (the "validated" value is `missing`) and every value fails on both builds. That is the correct outcome: tlaup's own validation would say `CfgNotFound`, and no value is wrong. On Linux and macOS the same string names `deep/out.cfg` (N=13) and all is as in section C.
- Windows R1 and R2 both validate N=44 (`..` after the link collapses to the link's parent).
- On Linux and macOS `relative-abs` is wrong for cfgs outside the link's tree, so the rule is per operating system, not a replacement.

### D. The same checks as one script, run on Linux, macOS and Windows

`scripts/path_flags_and_links.py` runs a subset (flag landing for `-dump`, `-metadir`, `-userFile`, `-dumpTrace`, `-teSpecOutDir`; the `..` cfg with an absolute spec; the link cases; R4's relative `-config`) with the standard library only. Linux results, Java 25 and Java 11 identical, and the CI results for all three systems (`ci_*.out`; the Windows rows that differ are `link-folder-config-dotdot`, `link-deep-config-dotdot`, `link-spec-path-with-dotdot` and `r4-relative-config-*`, all on both builds): `ci_linux_java25.out`, `ci_linux_java11.out` (26 lines, all as above).

## Implications for the roadmap

- **R4 step 3 and step 4 are right as written, and the two "Waiting on question 24" notes in R4 can be replaced by these results.** The relative `-config` from `relpath(realpath(cfg), realpath(spec.parent))` names the validated file with the spec passed as typed (links unresolved, `..` kept when it follows a link), on both builds; `..` out of the spec's folder works on v1.7.4. The R4 test rows "the same with the spec's folder reached through a symbolic link, including a cfg outside it reached with `..`" are a faithful encoding: they are rows R1 to R10 above, ready to be copied as integration tests (the integration run needs a symlink-capable filesystem; on Windows the test must skip when links cannot be created).
- **R4, "What changes for users", can state the rule for the other flags**: relative paths after `--` for `-dump`, `-dumpTrace`, `-loadTrace`, `-metadir`, `-userFile`, `-recover`, `-teSpecOutDir` and `-simulate file=` are read against the folder tlaup was started from; only `-config` is read against the spec's folder. Do not copy TLC's own help for `-dumpTrace` ("relative to the same directory as the main spec"): it is wrong when the spec is absolute. The help text can say "paths are relative to where you run tlaup; `-config` is relative to the spec's folder" and still advise absolute paths. `-recover DIR` from R6 is therefore resolved the same way; since R6 gives the user `-metadir` inside the cache, tlaup passes absolute paths there already.
- **R6 (run folders)**: 1.8.0 writes `<Spec>_TTrace_<n>.tla` and `.bin` into the spec's folder on every violation regardless of the working folder, and v1.7.4 writes `SpecTE.*` there only with `-generateSpecTE`. The only way to redirect them on 1.8.0 is `-teSpecOutDir`, which takes an absolute folder reliably but leaves the `.bin` unwritten (with an error message and no change of exit code) if a relative folder does not exist yet. If tlaup ever points TE output into the run folder, pass an absolute, existing folder. R8's table row for `-teSpecOutDir` can add this.
- **R8 table**: `-dump`, `-dumpTrace`, `-loadTrace`, `-userFile`, `-recover` and `-teSpecOutDir` can be passed through; none needs a conflict rule. A relative `-dump` or `-userFile` into a folder that does not exist makes TLC exit 1 before checking anything; `-dumpTrace` creates the folder.
- **Windows (verified by the second run, changes R4 step 4).** The `realpath`-based relative `-config` is correct on Linux and macOS only. On Windows the operating system collapses `..` before following a link, so with the spec behind a link the value must be computed as text from the paths as typed (`os.path.relpath(os.path.abspath(cfg), os.path.abspath(spec.parent))`, no `realpath`), which is also what Windows' own file opening will validate. This rule is **verified** by the second CI run (section E): `relative-abs` read the validated file in 8 of 8 rows where the file exists, on both builds; `relative-real` missed in 4 of 8 (R3, R5, R6, R7). R4's integration test rows R1 to R9 must run on Windows too, expecting the lexical file there. R4 step 3 (the spec passed as typed, `..` removed textually when `samefile`) still stands; on Windows a `..` after a link in the *spec* path makes the spec not found (the spec's `..` must be collapsed textually first on Windows, so the result then names the same file as the user's typed path only by that reading), so step 3's "otherwise the path is passed with its `..` in place" fails there and tlaup should report the spec as not found or, better, pass the textual form only when it names the same file.
- **Links**: R4 rejects resolving links in the spec's path, because TLC would then search beside the target. This is confirmed: TLC searches beside the path it is given, for a folder link (trivially, the same folder) and for a link to the spec file (beside the link, not the target, F1 to F3). So a spec file linked into a project with modules next to the link keeps its project modules, as R4's "Rejected" paragraph assumes. A user who linked a spec file and keeps its modules only beside the real file will not find them; that is TLC's rule, and R4 can say so in one line.

## Open follow-ups

- Second Windows run: done and confirmed (section E). One residue: an absolute `-config` works on 1.8.0 on Windows but fails on v1.7.4 outside the spec's folder, so it cannot replace the relative value; use it at most as a 1.8.0-only fallback.
- macOS: nothing open (runner `/tmp` links were avoided by using `realpath` for the tree root; Linux and macOS agree on all 26 rows).
- `-dumpTrace tlc FILE` wrote no file in my run and I did not find out why (it may be an input-format counterpart of `-loadTrace`, or silently disabled without `-loadTrace` machinery); only `json` was relied on.
- `-teSpecOutDir` with a relative, non-existing folder leaves the `.bin` unwritten and still exits 12; I did not look for an upstream issue.
- `-recover` on v1.7.4 and 1.8.0 reuses the metadir path as given; whether the recovered run's later files land in the old timestamped folder was not looked at (research 17 covers `-recover` otherwise).
- The Toolbox's own handling of these paths is not covered.

## Date checked

2026-11-18 (local), Linux x86-64, 12 cores; other agents were running on the machine at the time, so no timings are reported except the rough duration of the checkpoint runs.
