# 16. How TLC resolves `-config` and the spec path

## Question

How does TLC resolve a relative `-config` path (against its working folder or the spec's folder)? Does it accept an absolute one? The same questions for the spec path itself: does it accept `dir/Spec.tla` or an absolute path, and where does it then look for EXTENDS modules? Checked on v1.7.4 and on the current rolling / 1.8.0 build. Then: does tlaup, as it passes the cfg and the spec today, make TLC read the file tlaup validated?

## Source

- Jars from GitHub releases of `tlaplus/tlaplus`, run directly with `java -cp tla2tools.jar tlc2.TLC` on Java 25.0.5 (`/usr/bin/java`).
  - v1.7.4: TLC 2.19, rev `5a47802b5c391f59ecdd44117981f4ff8c0656ba`.
  - v1.8.0: TLC 2026.11.15.002146, rev `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`.
  - The `rolling` release jar is byte-identical to the v1.8.0 jar (`cmp` clean, same rev `bc1b506`). Everything below for "1.8.0" holds for rolling. (The v1.8.0 release shows `publishedAt` 2026-11-15, one day after today's date; this was not investigated.)
- Upstream source at those two commits (links below).
- tlaup source in this checkout: `src/tlaup/tlc/runner.py` (`resolve_spec_file`, `resolve_cfg_file`, `build_tlc_command`, `run_tlc`), `src/tlaup/cmd/tlc.py`, `src/tlaup/project/core.py`.
- Test layouts under `<tmp>/q16/` (`t/`, helper scripts `run.sh`, `tl.sh`, raw outputs `results1.txt`, `results2.txt`). Not kept in the repository.

## Short answer

1. **Relative `-config`.** TLC looks it up with the same resolver as modules: first against a "user dir", then against the library path. The user dir is TLC's cwd when the spec was given as a relative path or a bare name. It is the spec's folder when the spec was given as an absolute path (TLC sets `ToolIO.userDir` to it). When the spec was given as a relative path with a folder (`dir/Spec.tla`), that folder is also tried second, so a cfg name not found in cwd falls back to the spec's folder. Cwd wins if both exist.
2. **Absolute `-config`.** Accepted in 1.8.0 in every layout. In 1.7.4 it works unless the spec was also given as an absolute path and the cfg lies outside the spec's folder; that case fails with "File not found" (the resolver glues the cfg path onto the spec folder). The `.cfg` extension is optional in both versions (TLC strips it and re-adds it). Spaces in the path are fine (the argument must reach TLC as one argv item).
3. **Spec path.** `dir/Spec.tla`, `../x/Spec` and absolute paths are all accepted, and so is the name without `.tla`. EXTENDS modules are looked up in this order: user dir (cwd, or the spec's folder for an absolute spec path), then the spec's folder (relative spec path with a folder), then `-DTLA-Library` (only if the spec has no folder part, or is absolute), then the standard modules in the jar, then the Java classpath. There is no `-lib` option in either version. A cwd copy of a module (or in 1.7.4 even of the spec itself) shadows the one in the spec's folder when the spec is given by relative path with a folder.
4. **tlaup today does not reliably make TLC read the file it validated.** `resolve_cfg_file` validates the right file, but passes TLC only `cfg_file.name` unless the file is under the project root (or the spec folder when there is no root). Results (v1.8.0, real runs):
   - A cfg outside the project, given absolutely or as `../outside/out.cfg`, is passed as `-config out.cfg`. TLC then reads whatever `out.cfg` it finds from the root: a different file with that name in the project root was read (N=34 instead of N=4). With no such file, TLC fails with "File not found".
   - With no project root, `--cfg sub/a.cfg` is passed as `-config a.cfg`, and TLC silently read `a.cfg` in the spec folder (N=10 instead of N=2).
   - A cfg given as `../outside/out.cfg` from inside a project root is passed as `-config ../outside/out.cfg` by accident of lexical `relative_to`, and it works.
   - Passing the validated absolute path would have worked in every case tried on 1.8.0 (see table C). On 1.7.4 an absolute cfg with a relative spec works too; the only failure is absolute cfg plus absolute spec outside the spec folder.

## Confidence

Verified for behaviour: every row of the tables was run on both versions (unless marked), outcomes identified by distinct CONSTANT values and distinct module markers. Partly verified for the source explanation: I read the arg handling, resolver and `TLAFile` code, but did not trace the line that makes 1.7.4 parse a cwd `Spec.tla` before the one in the given folder, nor why 1.8.0 does not. The behaviour is shown by the runs; the cause is not pinned to a line. Not tested: Windows paths (the `TLAFile` regex has a Windows branch), symlinks, `-lib`-like options in the Toolbox, `MonolithSpecExtractor` (1.8.0 `.tla` with embedded cfg).

## Evidence

### Test layout

All under `t/`. Each cfg contains `SPECIFICATION Spec` and `CONSTANT N = <number>`. `Spec.tla` prints `<<"N", N>>` and a `Marker` from `EXTENDS Helper`, so the output shows which cfg and which Helper were used. A decoy `work/Spec.tla` additionally prints `"spec-file-work-decoy"` (used to tell which Spec was parsed; the `spec=` column in `results*.txt` shows the parsed path).

| file | N / marker |
|---|---|
| `proj/Spec.tla`, `proj/Helper.tla` | Helper marker `helper-from-spec-dir` |
| `proj/Spec.cfg` | 1 |
| `proj/sub/a.cfg` | 2 |
| `proj/cfgs/b.cfg` | 3 |
| `outside/out.cfg` (outside the project) | 4 |
| `work/Spec.cfg`, `work/a.cfg`, `work/sub/a.cfg` (cwd decoys) | 5, 6, 8 |
| `proj/my cfgs/with space.cfg` | 9 |
| `proj/a.cfg` | 10 |
| `work/Helper.tla`, `work/Spec.tla` | `helper-from-cwd`, decoy spec |
| `tlalib/Helper.tla` | `helper-from-lib` |
| `spec2/Spec.tla`, `spec2/Spec.cfg` | N=21, Helper only in `tlalib` |

Command form: `cd t/<cwd> && java -XX:+UseParallelGC [-DTLA-Library=...] -cp <jar> tlc2.TLC -nowarning -metadir <tmp> [-config X] <spec>`. Cwd names are folders under `t/`; `.` is `t/` itself; `$T` is `t/` absolute. "same" means 1.7.4 and 1.8.0 gave the same result. (Early runs shared one metadir; one 1.7.4 run came back blank for that reason and was not reproducible with separate metadirs. All reported rows were rerun or are unaffected.)

### A. Relative `-config`, relative spec

| # | cwd | `-config` | spec | N read (file) | 1.7.4 vs 1.8.0 |
|---|---|---|---|---|---|
| A1 | proj | (none) | `Spec` | 1 (proj/Spec.cfg, default name from spec) | same |
| A2 | proj | `Spec`, `Spec.cfg` | `Spec` | 1 | same |
| A3 | proj | `sub/a.cfg` | `Spec` | 2 (cfg in subfolder) | same |
| A4 | proj | `a` / `a.cfg` | `Spec` | 10 | same |
| A5 | work | `a.cfg` / `a` | `../proj/Spec` | 6: cwd copy wins over spec folder copy (10) | same |
| A6 | empty | `a.cfg` | `../proj/Spec` | 10: not in cwd, falls back to spec folder | same |
| A7 | work | `sub/a.cfg` | `../proj/Spec` | 8 (cwd) over 2 (spec folder) | same |
| A8 | work | `cfgs/b.cfg` | `../proj/Spec` | 3: only exists in spec folder, found | same |
| A9 | work | `../proj/cfgs/b.cfg` and `../proj/cfgs/b` | `../proj/Spec` | 3 (relative to cwd) | same |
| A10 | work | `../outside/out.cfg`, `../outside/out` | `../proj/Spec` | 4 (outside project, relative to cwd) | same |
| A11 | work | `my cfgs/with space.cfg`; `../proj/my cfgs/with space.cfg` | `../proj/Spec` | 9 | same |
| A12 | work | `nosuch.cfg` | `../proj/Spec` | not found | 1.7.4: "TLC threw an unexpected exception ... File not found."; 1.8.0: "TLC encountered the following error when trying to read the configuration file nosuch.cfg: File not found." |
| A13 | `.` | `sub/a.cfg` | `proj/Spec` | 2 (not in cwd, spec folder fallback) | same |
| A14 | `.` | `proj/sub/a.cfg` | `proj/Spec` | 2 (relative to cwd) | same |
| A15 | `.` | `out.cfg` | `proj/Spec` | not found (outside project, name only) | same (error wording as A12) |
| A16 | `.` | `outside/out.cfg` | `proj/Spec` | 4 | same |

No `-config`: the default cfg name is the spec path with `.cfg` (A1; `../proj/Spec` from work read `../proj/Spec.cfg` = 1, not `work/Spec.cfg` = 5; bare `Spec` from work read `work/Spec.cfg` = 5).

### B. Absolute spec path (TLC uses the spec folder as its "user dir")

| # | cwd | `-config` | spec | N read | 1.7.4 vs 1.8.0 |
|---|---|---|---|---|---|
| B1 | work | (none) | `$T/proj/Spec` and `$T/proj/Spec.tla` | 1 (proj/Spec.cfg, not work/Spec.cfg = 5) | same |
| B2 | work / empty | `a.cfg` | `$T/proj/Spec` | 10: relative cfg is resolved against the spec folder, NOT cwd (work/a.cfg = 6 ignored) | same |
| B3 | work | `sub/a.cfg` | `$T/proj/Spec` | 2 (spec folder; work/sub/a.cfg = 8 ignored) | same |
| B4 | work | `../proj/sub/a.cfg` | `$T/proj/Spec` | 2 (relative to spec folder, so `proj/../proj/sub/a.cfg`) | same |
| B5 | work | `$T/proj/sub/a.cfg` (abs, inside spec folder) | `$T/proj/Spec` | 2 | same |
| B6 | work | `$T/outside/out.cfg` (abs, outside spec folder) | `$T/proj/Spec` | **1.7.4: File not found. 1.8.0: 4** | differs |
| B7 | work | `$T/proj/my cfgs/with space.cfg` | `$T/proj/Spec` | 9 | same |
| B8 | work | relative `my cfgs/with space.cfg` | `$T/proj/Spec` | 9 | same |
| B9 | empty | `$T/outside/out.cfg` | `$T/proj/Spec.tla` | **1.7.4: File not found. 1.8.0: 4** | differs |

### C. Absolute `-config`, relative spec

| # | cwd | `-config` | spec | N read | 1.7.4 vs 1.8.0 |
|---|---|---|---|---|---|
| C1 | work | `$T/outside/out.cfg` and without `.cfg` | `../proj/Spec` | 4 | same |
| C2 | work | `$T/proj/my cfgs/with space.cfg` and without `.cfg` | `../proj/Spec` | 9 | same |

### D. The spec path and EXTENDS modules

| # | cwd | spec arg | Spec parsed | Helper found in | 1.7.4 vs 1.8.0 |
|---|---|---|---|---|---|
| D1 | proj | `Spec` | proj | proj (cwd = spec folder) | same |
| D2 | work | `Spec` (decoy in cwd) | work/Spec.tla | work | same |
| D3 | work | `../proj/Spec` and `../proj/Spec.tla` | **1.7.4: work/Spec.tla (the cwd decoy). 1.8.0: proj/Spec.tla** | work/Helper.tla (cwd) in both, though the spec folder has one | differs for Spec |
| D4 | empty | `../proj/Spec` | proj | proj (spec folder fallback) | same |
| D5 | `.` | `proj/Spec` | proj | proj | same |
| D6 | work | `$T/proj/Spec(.tla)` | proj | proj (user dir = spec folder, not cwd) | same |

D3 note: in 1.7.4 the default cfg for D3 was still `../proj/Spec.cfg` (N=1) while the parsed spec was the cwd one, so a run can mix a spec from one folder with a cfg from another.

`-DTLA-Library` (`TLA-Library` property), with `Helper.tla` only in `tlalib/`:

| # | cwd | spec arg | result (both versions) |
|---|---|---|---|
| E1 | spec2 | `Spec` | found in `tlalib` |
| E2 | empty | `$T/spec2/Spec` (absolute) | found in `tlalib` |
| E3 | runner | `../spec2/Spec` | **not found** ("File does not exist ... spec2/Helper.tla" in 1.7.4, "Cannot find source file for module Helper" in 1.8.0) |
| E4 | `.` | `spec2/Spec` | **not found** |
| E5 | spec2 | `Spec`, `-DTLA-Library=tlalib:tlalib2` | `tlalib` (first entry) wins |
| E6 | spec2 | `Spec`, no property | not found (control) |

So `-DTLA-Library` is ignored when the spec argument has a folder part and is relative. TLC builds the resolver as `SimpleFilenameToStream(dir)`, and that constructor does not read the property. Absolute spec paths are exempt because TLC strips the folder before the resolver is built (see Source code below).

### F. What tlaup does (v1.8.0 installed through `tlaup tools install v1.8.0` into a private XDG folder, real runs with `--raw`, `--show-command` for the command)

`rootproj/` has `lib/` and `modules/` (so it is a project root), `spec/Spec.tla`, `spec/Spec.cfg` (31), `spec/sib.cfg` (36), `cfgs/x.cfg` (32), `root.cfg` (33), `out.cfg` (34, a decoy with the same name as the outside file), `my cfgs/sp.cfg` (35). The outside cfg is `outside/out.cfg` (4). tlaup runs TLC with cwd = project root if there is one, else the spec's folder.

| # | cwd | tlaup args | `-config` / spec tlaup passes | N read | file TLC read vs validated |
|---|---|---|---|---|---|
| F1 | rootproj | `spec/Spec --cfg sib` | `spec/sib.cfg` / `spec/Spec.tla` | 36 | same file |
| F2 | rootproj | `--cfg cfgs/x.cfg` | `cfgs/x.cfg` | 32 | same |
| F3 | rootproj | `--cfg "my cfgs/sp.cfg"` | `my cfgs/sp.cfg` (one argv item) | 35 | same |
| F4 | rootproj | `--cfg ../outside/out.cfg` | `../outside/out.cfg` | 4 | same, by accident (lexical `relative_to`) |
| F5 | rootproj | `--cfg $T/outside/out.cfg` (also without `.cfg`) | **`out.cfg`** | **34** | **different file** (rootproj/out.cfg) |
| F6 | rootproj | `--cfg out` | `out.cfg` | 34 | the name-only candidate; there is a file `rootproj/out.cfg`, so it is the same file here |
| F7 | work | `$T/rootproj/spec/Spec --cfg $T/outside/out.cfg` | **`out.cfg`** | **34** | **different file** |
| F8 | work | same spec, `--cfg ../outside/out.cfg` | **`out.cfg`** | **34** | **different file** |
| F9 | work | same spec, `--cfg $T/rootproj/cfgs/x.cfg` | `cfgs/x.cfg` | 32 | same |
| F10 | work | `../rootproj/spec/Spec` (spec path containing `..`) | `Spec.tla`, no `-config` | not found | TLC runs in rootproj but gets `Spec.tla`; the lexical `relative_to` fails on `..`, so the spec arg falls back to the bare name |
| F11 | proj (no root) | `Spec --cfg ../outside/out.cfg` | **`out.cfg`** | not found | TLC fails: "reading the configuration file out.cfg: File not found" |
| F12 | work (no root) | `$T/proj/Spec --cfg sub/a.cfg` | **`a.cfg`** | **10** | **different file** (proj/a.cfg, not proj/sub/a.cfg = 2) |
| F13 | proj (no root) | `Spec --cfg "my cfgs/with space.cfg"` | `with space.cfg` | not found | TLC fails |
| F14 | proj (no root) | `Spec --cfg cfgs/b` | `b.cfg` | not found | TLC fails |

Where tlaup does this: `resolve_cfg_file` (`src/tlaup/tlc/runner.py`) validates `spec folder/<cfg>`, `cwd/<cfg>`, `project root/<cfg>` (in that order, `.cfg` optional). `cfg_arg = cfg_file.name` is then replaced by the path relative to the project root only if that works lexically. Note the order differs from TLC's: tlaup prefers the spec folder, TLC prefers cwd (A5).

Also seen: with `-DTLA-Library=<root>/modules` and a relative spec like `spec3/Spec.tla`, TLC ignores the property (E3). The runs through tlaup still found a module placed only in `modules/`, because tlaup puts `modules/` on `-cp` too and both versions fall back to the classpath. A module found only through `TLA-Library` (not on the classpath) would not be found by TLC when the spec has a folder.

### Source code (pinned)

Commits: v1.7.4 = `5a47802b5c391f59ecdd44117981f4ff8c0656ba`, v1.8.0 = rolling = `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`.

- `-config` parsing, strips a trailing `.cfg`: [v1.7.4 TLC.java L527-535](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L527-L535), [1.8.0 TLC.java L686-694](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L686-L694).
- Spec path handling, the comment calls it a "clutch": if `mainFile` is absolute, `specDir` is its parent, `mainFile` becomes the basename, and `ToolIO.setUserDir(specDir)` is called "to avoid a ConfigFileException"; if no `-config`, `configFile = mainFile`: [v1.7.4 L930-947](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L930-L947), [1.8.0 L1256-1273](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1256-L1273).
- Resolver built in `main` from the (not yet massaged) main file: a non-empty directory part gives `new SimpleFilenameToStream(dir)`, otherwise the default constructor: [v1.7.4 L265-280](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L265-L280), [1.8.0 L335-354](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L335-L354). The order between this and the massaging block is why absolute specs get the default resolver (which honours `TLA-Library`) and relative ones with a folder do not. I inferred the order from behaviour (E2 vs E3) and the line positions; I did not step through it.
- `ModelConfig` reads the cfg through `resolver.resolve(configFileName, false)`, error text "File not found.": [v1.7.4 ModelConfig.java L150](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/impl/ModelConfig.java#L150), [1.8.0 L174](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/impl/ModelConfig.java#L174). `Spec.java` appends `.cfg` in 1.7.4 ([L92](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/impl/Spec.java#L92)); 1.8.0 goes through `MonolithSpecExtractor.getConfig` ([L99](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/impl/Spec.java#L99)), not read.
- 1.7.4 resolution order in `locate`: user dir first (`new TLAFile(ToolIO.getUserDir(), name)`) or, if no user dir, `"" + name` relative to cwd; then each library path; then standard modules; then the classpath: [SimpleFilenameToStream.java L161-235](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/util/SimpleFilenameToStream.java#L161-L235). The constructor with a directory argument does not read `TLA-Library` (L119-149: the property is read only when `libraries == null`).
- 1.7.4 absolute cfg failure cause: `TLAFile(parent, child)` strips `parent` from `child` only when `child` starts with `parent`, otherwise `new File(parent, child)` concatenates, so `/spec/dir` + `/abs/out.cfg` becomes `/spec/dir/abs/out.cfg`: [FilenameToStream.java L51-58](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/util/FilenameToStream.java#L51-L58). This matches B5 working (inside spec folder) and B6 failing.
- 1.8.0 rewrite: searches `ToolIO.userDir` or the JVM cwd, then the given library paths (`TLA-Library` only when the default constructor is used), then jar standard modules, then the classpath: [SimpleFilenameToStream.java L46-125](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/util/SimpleFilenameToStream.java#L46-L125); `FilesystemResourceLocator` uses `Path.resolve`, so an absolute name wins over the prefix: [FilesystemResourceLocator.java](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/util/FilesystemResourceLocator.java). This matches B6/B9 working in 1.8.0.
- No `-lib` option: no match in either `TLC.java`, and `-help` of the 1.8.0 jar has none.
- Related upstream history: the comment in TLC.java cites [tlaplus issue 24](https://github.com/tlaplus/tlaplus/issues/24) (absolute spec path). I did not search for other issues.

## Implications for the roadmap

- The Milestone 1 item "pass a `--cfg` file outside the project root so that TLC reads the validated file" is feasible on 1.8.0: TLC accepts an absolute `-config` path in every layout tried, with or without `.cfg`, with spaces.
- On v1.7.4 an absolute cfg fails in one combination: the spec is also an absolute path and the cfg is outside the spec's folder. tlaup passes the spec as a path relative to the project root or just its name (with cwd set), so it does not hit that combination today. If the runner ever passes an absolute spec path, it must stay away from that combination on 1.7.4 (or pass the cfg relative to the spec's folder, e.g. `../outside/out.cfg`, which works there).
- The safest rule for any version: run TLC with a cwd and a relative spec argument, and pass the cfg as an absolute path (works on both) or as a path relative to cwd. Do not pass a name-only cfg for anything that is not in cwd. Because TLC tries cwd before anything else, a name-only cfg can silently pick a different file (F5, F7, F8, F12). If the runner passes the absolute validated path, there is no ambiguity at all.
- A relative cfg means different things to tlaup and TLC: tlaup tries spec folder, then cwd, then project root; TLC tries cwd (the project root for tlaup), then the spec's folder. The pre-run validation should return the resolved absolute path and TLC should be given that path, not the original string.
- Smaller points found on the way, to feed the design:
  - `spec_file.relative_to(project_root)` is lexical, so a spec path that contains `..` (F10) makes tlaup pass a bare `Spec.tla` while TLC runs in the project root, and it fails. Resolve paths (`resolve()`) before comparing.
  - `-DTLA-Library` has no effect when the spec argument is relative with a folder part (E3/E4). tlaup works today only because `modules/` is also on `-cp`. Anything that depends on `TLA-Library` alone (the roadmap's reproducible toolchain, a shared module folder) needs either the classpath or a bare spec name with cwd set to the spec folder, or an absolute spec path.
  - A cwd copy of a module shadows the one next to the spec when the spec is a relative path with a folder (D3), and in 1.7.4 the same holds for the spec file itself. This matters if cwd is ever a folder other than the project root.
  - Behaviour differs between 1.7.4 and 1.8.0 in two places only (B6/B9 and D3). Everything else was identical.

## Open follow-ups

- Trace why 1.7.4 parses the cwd `Spec.tla` for a `../proj/Spec` argument while 1.8.0 parses the one in the given folder (likely `SpecObj`/`ParseUnit` name handling); only needed if the spec's folder ever differs from cwd.
- Re-run the key rows (C1, B6, F5) on the intermediate releases tlaup lets users pin (1.7.3, 1.7.2) if those need support; only 1.7.4 and 1.8.0/rolling were checked.
- Windows: `TLAFile` has a drive-letter branch and tlaup would pass `C:\...` paths; not tested here.
- Whether the `Path.resolve` behaviour for absolute `-config` in 1.8.0 is intended or incidental was not looked up in upstream issues or the changelog.
- Not tested: the cfg given through a relative path that contains `..` combined with an absolute spec path on 1.7.4 beyond B4.

## Date checked

2026-11-14.
