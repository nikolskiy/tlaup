# 06. Building tla2tools.jar from source

## Question

How is `tla2tools.jar` built from source (github.com/tlaplus/tlaplus) at a CalVer tag? Which build tool and target, which Java version, how long it takes, what needs the network (and whether a second build works offline), and whether the result matches the published jar byte for byte. If not, what differs, and do the class files match after normalising. Can a build older than the first CalVer tag (2026-04-27) be built at its commit with the same result?

## Source

- Upstream CI: https://github.com/tlaplus/tlaplus/blob/master/.github/workflows/main.yml (read at commit bc1b506), `DEVELOPING.md`, `tlatools/org.lamport.tlatools/customBuild.xml`.
- Published jars: `gh release download rolling -R tlaplus/tlaplus -p tla2tools.jar` and the same for `v1.7.4`.
- Built here from `git clone` of https://github.com/tlaplus/tlaplus, with Apache Ant 1.10.12 (https://archive.apache.org/dist/ant/binaries/) and Temurin JDK 17.0.21+9 and 11.0.33+10 (api.adoptium.net), plus the system OpenJDK 25.0.5.

## Short answer

- Build tool: Apache Ant, not Maven. `ant -f tlatools/org.lamport.tlatools/customBuild.xml info compile compile-test dist` writes `tlatools/org.lamport.tlatools/dist/tla2tools.jar` (target `dist`). Upstream CI reaches the same `dist` target through Maven (`default-maven` in `customBuild.xml`, called from the Tycho/Maven build that also builds the Toolbox). Maven is not needed for the jar.
- Java: the CI builds with Temurin 17 (`main.yml`: "Set up JDK 17"; the published jar says `Created-By: 17.0.21+9 (Eclipse Adoptium)`). `customBuild.xml` compiles with `java.release=11`, so JDK 11 or newer builds. `DEVELOPING.md` says JDK 11+ and Ant 1.9.8+.
- Time: 15 to 35 seconds for the jar on this machine (34 s JDK 17 and 27 s JDK 11 for the current tag, 18 s JDK 25, 22 s for the first CalVer tag). The unshallow git clone adds about 1.5 minutes.
- Network: only to get the source. The shallow clone fails; the build needs the full history. Everything else is vendored in `tlatools/org.lamport.tlatools/lib/` and the build ran with no network at all (`unshare -rn`). Ant and a JDK have to be present beforehand.
- Byte for byte: no, never. But with the same JDK major version as the CI used, every file in the zip is identical in name, order, compression and content, except `META-INF/MANIFEST.MF` (and zip entry timestamps, which cannot be matched). The class files are identical. With a different JDK major version, many class files differ.
- Older builds: the pre-CalVer release v1.7.4 (2024-08-08) built at its commit with JDK 11 (the version its CI used) matches the published jar the same way (all entries identical except the manifest). With JDK 17 it does not (770 of 1066 entries differ). The first CalVer tag builds in 22 s, but no published jar of that commit exists to compare with.
- A source build reports a different CalVer unless the timestamp is pinned. See the finding on `ISO8601` below.

## Confidence

Verified for the current rolling jar (commit bc1b506), and for v1.7.4. Partly verified for "older CalVer tags": the first CalVer tag was built, but there is nothing published to compare it with.

## Evidence

### Which commit the rolling jar is

```
$ unzip -p rolling.jar META-INF/MANIFEST.MF
Ant-Version: Apache Ant 1.10.12
Created-By: 17.0.21+9 (Eclipse Adoptium)
Built-By: runner
Build-TimeStamp: 2026-11-15T00:21:46.50Z
X-Git-Revision: bc1b506bdcad80bb518bf3776a9161c34ff0fc4c
X-Git-Commits-Count: 9089
$ java -cp rolling.jar tlc2.TLC
TLC2 Version 2026.11.15.002146 (rev: bc1b506)
$ git ls-remote --tags https://github.com/tlaplus/tlaplus | grep bc1b506
bc1b506b...  refs/tags/2026.11.15.002146^{}    (annotated tag, f9f142cc...)
bc1b506b...  refs/tags/rolling
bc1b506b...  refs/tags/v1.8.0
```

So the newest CalVer tag `2026.11.15.002146`, `rolling` and `v1.8.0` all point at bc1b506 (committed 2026-11-14T16:05:18-08:00), and the rolling jar is that commit. The CalVer string is the build time (UTC) from `Build-TimeStamp`: tag name `2026.11.15.002146` is `2026-11-15T00:21:46`. The `rolling` GitHub release is published as a pre-release; its jar is replaced (`gh release upload --clobber`) on every push to master, so only the newest one can be downloaded. Upstream has 168 CalVer tags (`git ls-remote`, first `2026.04.27.203507`, whose commit is e3142ca3b).

The workflow's "Update tags" step takes the CalVer from the freshly built jar: `java -cp dist/tla2tools.jar tlc2.REPL 'TLCGet("revision").calver'`, then tags the commit and force-moves `rolling` and `v1.8.0`.

### How CI builds the jar

`.github/workflows/main.yml`: JDK 17 (Temurin), Maven 3.9.9, Ant from the runner image (1.10.12 in the manifest). Steps: `ant -f tlatools/org.lamport.tlatools/customBuild.xml info compile compile-test test`, then `mvn ... verify` (Tycho, builds the Toolbox too), whose antrun step calls `customBuild.xml` target `default-maven` (compile, compile-test, git-revision, `dist`, test-dist). The jar uploaded to the release is `tlatools/org.lamport.tlatools/dist/tla2tools.jar`. For a jar-only build, the Ant line from `DEVELOPING.md` is enough: `ant -f customBuild.xml info compile compile-test dist`. `compile-test` is run because `dist` packages a few test classes (`CommonTestCase*`, `ModelCheckerTestCase*`, etc., see the fileset in `dist`).

### Build commands and timings

```
export JAVA_HOME=.../jdk-17.0.21+9 PATH=$JAVA_HOME/bin:.../apache-ant-1.10.12/bin:$PATH
cd tlatools/org.lamport.tlatools
unshare -rn ant -f customBuild.xml info compile compile-test dist     # no network namespace
```

| Ref | JDK | Result | Time |
|---|---|---|---|
| 2026.11.15.002146 (bc1b506) | Temurin 17.0.21 | BUILD SUCCESSFUL, offline, 4,510,909 bytes | 34 s |
| 2026.11.15.002146 | Temurin 11.0.33 | success | 27 s |
| 2026.11.15.002146 | OpenJDK 25.0.5 (Debian) | success (6+2 javac warnings, Unsafe) | 18 s |
| 2026.04.27.203507 (e3142ca) | Temurin 17 | success, offline, 4,356,785 bytes | 22 s |
| v1.7.4 (5a47802) | Temurin 17 | success, offline | 14 s |
| v1.7.4 | Temurin 11 | success | 17 s |

Published jar size for rolling: 4,510,884 bytes (the rebuilt one is 25 bytes larger because of manifest text). Ant 1.10.12 worked with JDK 25. Tests were not run (`test` not part of the command; CI runs them separately).

### The shallow clone fails

```
$ git clone --depth 1 --branch v1.8.0 https://github.com/tlaplus/tlaplus   (1 min)
$ ant ... info ...
Caused by: org.eclipse.jgit.errors.MissingObjectException: Missing commit d8fb231d...
```

The `git-revision` target uses a bundled `jgit-buildnumber` task (jgit 2.3.1, in `lib/`) to count commits and read branch and tags. It needs the whole history (the CI comment says "jgit task nested in customBuild.xml fails without history"). `git fetch --unshallow --tags` took 32 s and made `.git` 161 MB; the count then matched the manifest (`git rev-list --count HEAD` = 9089 = `X-Git-Commits-Count`). Also, jgit 2.3.1 does not understand `git worktree` checkouts (`.git` as a file): `Missing unknown 5a47802...`. Use a normal clone and `git checkout`.

### What is downloaded

Nothing at build time. `lib/` holds javacc-4.0.jar (parser generation, `generate` target), the jgit jars, `javax.mail/*.jar`, `jline/*.jar`, `gson`, the test jars and the community modules; `lib/vendored-jars.json` lists them. Build ran inside `unshare -rn` (no network interface) and succeeded, so there is no first-fetch cache to keep, unlike Maven. The Maven build (Toolbox, Tycho, p2) does need the network and about 300 MB in `~/.m2/repository` (CI cache comment); it is not needed for the jar.

### Comparison with the published jar (JDK 17, same commit)

Script: Python `zipfile` comparing entry names, order, content, mtime, compression, external attributes, extra fields.

```
entries 2231 2231, only-in-either: none, order same: True
content diffs 1: META-INF/MANIFEST.MF
mtime diffs 1154   (the rest are files copied from vendored jars, keeping their old mtimes)
compress_type / external_attr / create_system / extra diffs: 0
zip comment: empty in both
cmp: differ at byte 11 (first local file header mtime); sha256 differs
```

Manifest diff (default build, run in a sandbox where user name is `root`):

```
Built-By: runner            -> root (user.name)
Build-TimeStamp / Implementation-Version  -> time and date of the build
X-Git-Branch: master        -> empty (detached HEAD checkout)
X-Git-Tag:                  -> 2026.11.15.002146;rolling;v1.8.0   (the tags that exist at build time)
X-Git-BuildNumber: master__bc1b506 -> _2026.11.15.002146;rolling;v1.8.0_bc1b506
```

So all class files and resources match after ignoring the manifest and zip timestamps. The jar is not reproducible byte for byte: `<jar>` stores the file mtimes of the build, and the manifest carries the build time.

Pinning inputs: `customBuild.xml` sets `ISO8601` and `TODAY` with `<tstamp>`, so `-DISO8601=2026-11-15T00:21:46.50Z -DTODAY=2026-11-15 -Duser.name=runner` overrides them (Ant properties are immutable). The rebuilt jar then differs from the published one only in the three `X-Git-*` manifest lines above (branch/tag come from the checkout), and `java -cp ... tlc2.TLC` prints `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`, the same as the published jar. Without the override a source build prints `TLC2 Version 2026.11.15.082400 (rev: bc1b506)` (build time, not the tag), and `TLCGet("revision").calver` returns the same wrong string. The `tag |-> "bc1b506"` field and commit count are right.

### Effect of the JDK version

- JDK 17 build vs published (JDK 17): 1 differing entry (the manifest).
- JDK 11 build vs the same published jar: 978 of 2231 entries differ (class files).
- JDK 25 build vs the same published jar: 526 entries differ, and `tlc2/util/PartialBoolean$1.class` is missing, and the entry order changes (2230 entries).
- v1.7.4: published jar says `Created-By: 11.0.3+7-LTS (Azul Systems)`, `Ant-Version: Apache Ant 1.9.4`. JDK 17 build: 770 of 1066 entries differ. JDK 11.0.33 build (Ant 1.10.12): 1 differing entry (the manifest). Different patch versions of the same major (11.0.3 vs 11.0.33, Azul vs Temurin) and a different Ant did not matter.

The jar built with JDK 25 started and ran (`tlc2.REPL` evaluated an expression); I did not run the TLC test suite or a model check on any rebuilt jar beyond that.

### Older than the first CalVer tag

v1.7.4 (commit 5a47802, 2024-08-08) built with the same command and `customBuild.xml` and matched its published jar apart from the manifest, as above. The Ant file layout at the first CalVer tag (e3142ca) is the same, and it built fine on JDK 17. What was not tested: other commits between v1.7.4 and the first CalVer tag, and JDKs for old tags other than 11 and 17. There is no published jar for any CalVer tag except the newest one, so the first CalVer build is not comparable.

## Implications for the roadmap

- Building an older rolling build from its CalVer tag is feasible: it needs a full-history git clone (or a source archive plus the history, because of `jgit-buildnumber`), Ant, and a JDK, no other downloads. "Java build tools fetched automatically" means two things: Ant (binary from archive.apache.org, tens of MB) and a JDK. Maven is not needed.
- The JDK choice decides whether the class files match the CI output. For tags built by the current CI use Temurin 17; for old release tags use the JDK its CI used (11 for v1.7.4). A different JDK gives a working jar but different class bytes. The release tooling cannot read the JDK from the tag, so a lookup table (tag range to JDK) is needed, or the digest is taken from the build rather than compared with upstream (next point). `Created-By` in an upstream jar's manifest names the JDK, but only for a jar that can still be downloaded.
- "How a digest is trusted for a jar built from source": the built jar can never have the same SHA-256 as the published one (zip timestamps), so a digest of the whole file is only meaningful for a jar tlaup built itself and then pinned (trust on first build). For checking against upstream, compare per-entry digests of everything except `META-INF/MANIFEST.MF` (done here with the JDK that CI used), or pin the digest of the commit and the toolchain. This was checked only for one rolling commit and v1.7.4.
- Source builds report a CalVer from the build time. To make `tlc2.TLC` and `TLCGet("revision")` print the tag's CalVer, pass `-DISO8601=<tag time as 2026-11-15T00:21:46.50Z>` and `-DTODAY=<date>`; the CalVer tag name converts to that timestamp (`yyyy.MM.dd.HHmmss`, UTC). The fractional second in the manifest (`.50Z`) is not in the tag, so the manifest line will not match exactly.
- Build time is about 20 to 40 seconds plus the clone (about 1.5 minutes with history, about 160 MB). A shallow clone cannot be used. Cloning needs the network; a git clone with the tag fetched is enough, but the git directory must be an ordinary clone, not a worktree.
- If a build has to be done on a machine whose time zone differs: zip mtimes only affect the whole-file digest, not the content.

## Open follow-ups

- Build several CalVer tags between 2026-04-27 and now (CI JDK changes?) and read `.github/workflows/main.yml` at each to build a tag-to-JDK table. Nothing to compare against, since older rolling jars are not published; a copy held by someone, or the Maven Central snapshot repo, could answer it (not checked).
- Test that a jar built from a source archive (GitHub tarball plus a fake history) can be used instead of a clone. Not tested; jgit needs a real history, so probably not without patching.
- Check commits older than v1.7.4 (for example v1.7.3 and v1.6.0) against their published jars and JDKs.
- Check Windows and macOS builds (CI runs `ant` on all three; not tested here, Linux only).
- Confirm that the Temurin 17 build reproduces the CI result on a second machine and a different `user.name`/timezone (only one machine tried).

## Date checked

2026-11-14. Upstream state at check time: master and `rolling` at bc1b506; GitHub release `v1.8.0` marked pre-release, `v1.7.4` marked Latest.
