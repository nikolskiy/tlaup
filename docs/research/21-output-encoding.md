# 21. Output encoding of TLC, SANY and the PlusCal translator

## Question

Which character encoding do TLC, SANY and the PlusCal translator write their output in, on v1.7.4 and 1.8.0 (rolling),
for Java 11, 21 and 25, under a UTF-8 locale and a non-UTF-8 locale? Does a JVM option (`-Dfile.encoding`,
`-Dstdout.encoding`, `-Dsun.stdout.encoding`, `-Dstderr.encoding`) make it UTF-8 everywhere? Decides whether the Java
launcher ([20 G3](../design/20-groundwork.md#g3-java-launcher), [11 R3](../design/11-runner.md#r3-non-utf-8-output))
adds an encoding option by default, and which.

## Source

- Jars (not downloaded again): v1.7.4, `TLC2 Version 2.19 of 08 August 2024`, commit
  `5a47802b5c391f59ecdd44117981f4ff8c0656ba`, sha256 `936a2620...0e050e88`, SANY 2.1, `pcal.trans` 1.11. "1.8.0
  (rolling)": CalVer `2026.11.15.002146`, commit `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`, sha256 `7e53aa63...fb84f`,
  SANY 2.2, `pcal.trans` 1.12.
- Java: Temurin 11.0.33+10, OpenJDK 21.0.13, OpenJDK 25.0.5. Linux x86-64, 12 cores, Debian. Other agents were
  running on the machine (load average 20 to 40), so only results were recorded, never timings.
- Locales on the machine (`locale -a`): `C`, `POSIX`, `C.utf8`, `en_US.utf8`. **There is no Latin-1 locale and none was
  installed.** The Latin-1 case is therefore only approximated, with `-Dfile.encoding=ISO-8859-1` (see below).
- Upstream source, pinned (read only, `gh api`):
  - `ToolIO.out` and `ToolIO.err` are `System.out` and `System.err` (lines 70 and 77, identical in both commits):
    [v1.7.4](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/util/ToolIO.java#L70),
    [1.8.0](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/util/ToolIO.java#L70).
    So TLC names no charset of its own: its text goes out through the JVM's standard streams.
  - SANY's `SimpleCharStream` builds `new InputStreamReader(stream)` with no charset (line 303 in both commits), that is
    the JVM default: [v1.7.4](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tla2sany/parser/SimpleCharStream.java#L303),
    [1.8.0](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tla2sany/parser/SimpleCharStream.java#L303).
    The runs below nevertheless show 1.8.0 reading the spec as UTF-8 on Java 11 in a C locale; I did not find where in
    the 1.8.0 source that is done.
- Everything captured is under `tests/fixtures/research/21-output-encoding/`: the specs (`specs-rolling/`,
  `specs-v1.7.4/`), the scripts (`cell.sh`, `extra.sh`, `cells.sh`, `fn.sh`, `summarize.py`, `merge.py`,
  `excerpts.py`; set `TMP` to the scratch root), the two result tables (`tables/`) and hexdumps of the relevant lines
  (`excerpts/`). The raw per-run output files (about 540 runs) are not kept; the tables and hexdumps are what they
  produced.

## Short answer

1. **TLC, SANY and the translator all write through the JVM's standard streams, and the bytes are exactly what the
   JVM's `stdout.encoding` / `stderr.encoding` produce.** They add no encoding of their own. That is the same on
   v1.7.4 and 1.8.0 and on Java 11, 21 and 25, for the error trace, `Print` and `PrintT`, SANY messages that quote the
   source, the translator's messages, and the "file not found" messages (both streams).
2. **Under a UTF-8 locale (`C.utf8`, `en_US.utf8`) the output is UTF-8 everywhere**, with every Java, both versions.
3. **Under `LC_ALL=C` or `POSIX` it is US-ASCII**, with every Java: each unrepresentable character (an accented
   letter, a CJK character, an emoji) becomes one `?` (an emoji outside the BMP is one `?`, not two). The bytes `3f` are
   not recoverable. JEP 400 is confirmed: Java 21 and 25 report `file.encoding = UTF-8` in the C locale, but
   `stdout.encoding = native.encoding = ANSI_X3.4-1968` when the output is a pipe (the same on a pseudo-terminal on
   Linux). So on Java 18 and later the default is UTF-8 for files and the locale's encoding for the streams; on Java
   11 `file.encoding` is the locale's encoding and the streams follow it.
4. **A Latin-1 locale could not be tested.** With `-Dfile.encoding=ISO-8859-1` as a stand-in: on Java 11 the output
   becomes Latin-1 (`é` is `e9`, CJK and emoji are `?`), which is what a Latin-1 locale would give; on Java 21 and 25
   that option does not change the streams at all. A real Latin-1 locale on Java 21 and 25 would change
   `stdout.encoding` (it is derived from the locale), so the Java 11 result is the better stand-in for it.
5. **Which options work** (rolling; the "tlc / print / SANY quote / pcal message" columns were identical):

   | Option | Java 11 | Java 21 | Java 25 |
   |---|---|---|---|
   | `-Dfile.encoding=UTF-8` | UTF-8 for stdout, stderr, spec reading, files written | no effect on the streams (still `?`) | no effect on the streams |
   | `-Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` | **ignored without a warning** (still `?`) | UTF-8 | UTF-8 |
   | `-Dsun.stdout.encoding=UTF-8 -Dsun.stderr.encoding=UTF-8` | UTF-8 | UTF-8 | UTF-8 (still honoured, undocumented) |
   | `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` | UTF-8 | UTF-8 | UTF-8 |

   The last row is the smallest set that fixed every case, in both versions, in the C and POSIX locales, for all of:
   trace values, `Print`/`PrintT`, SANY's quote of a string token, the translator's message, and the `.tla` file the
   translator rewrites. (Not run under a UTF-8 locale, where the defaults are already UTF-8; the same options there
   change nothing but the three properties.)
6. **v1.7.4 also reads the spec in the JVM default charset**, so on Java 11 in a C locale a UTF-8 spec is decoded as
   ASCII before TLC sees it (the trace shows one `?` per UTF-8 *byte*: `caf??`), and no output-only option repairs
   that (`-Dsun.stdout.encoding` alone prints U+FFFD). 1.8.0 reads the spec as UTF-8 whatever the default is.
   Only `-Dfile.encoding=UTF-8` fixes it on Java 11 (and Java 21 and 25 already default to UTF-8 for reading).
7. **The PlusCal translator rewrites the user's `.tla`.** On v1.7.4 with Java 11 in a C or POSIX locale it writes
   non-ASCII characters in the comments of the spec back as `?` (verified: bytes `63 61 66 3f 3f` where `caf\xc3\xa9`
   was), that is, it destroys text in the user's file. With `-Dfile.encoding=UTF-8`, on Java 21 and 25, and on 1.8.0 on
   every Java, the comments came back byte for byte. So the encoding option is not only cosmetic for `pcal`.
8. **A JVM option cannot fix non-ASCII file names.** In a C or POSIX locale a spec path or `-config` path with
   `é` or CJK in it is decoded with `sun.jnu.encoding` (ASCII): 1.8.0 on Java 11, 21 and 25 dies with
   `java.nio.file.InvalidPathException: Malformed input or input contains unmappable characters`; v1.7.4 looks for a
   file called `caf?????.tla`. `-Dsun.jnu.encoding=UTF-8` did not help (tried). In a UTF-8 locale these paths work.
   Only a UTF-8 locale in the child's environment fixes this.
9. **Files TLC writes follow `file.encoding`.** `-dumpTrace json FILE` (1.8.0 only) wrote UTF-8 on Java 25 in the C
   locale and `?` on Java 11 in the C locale; `-Dfile.encoding=UTF-8` fixed Java 11.
10. **Side findings about what the specs may contain** (they decide what a golden file can use):
    - v1.7.4's lexer rejects some non-ASCII characters in a string literal with `Lexical error ... Encountered:
      "本"` (the message is ASCII-escaped): U+672C, 中, 字, あ, ひ, я, 한 failed; é, 日, 語, 文, α, Ω, ß, ñ, €, ø
      passed. An emoji outside the BMP in a string fails (`Could not parse module`), in a comment it is fine. 1.8.0
      accepted all of them.
    - The translator (both versions) rejects any non-ASCII character inside an algorithm string: ` -- Illegal
      character in string `café' found at line 4, column 15.` (it quotes the text up to the offending character, so
      the message itself is a usable probe). Non-ASCII in comments, inside or outside the algorithm, is fine.
    - TLC's `-tool` output was captured for the same cells that had it (Java 11, 21, 25 in C and C.utf8): identical to
      the plain mode in encoding.
11. **macOS and Windows (CI run, pipes).** macOS is UTF-8 everywhere with no option (`stdout.encoding`, `native.encoding`,
    `file.encoding`, `sun.jnu.encoding` all UTF-8; Java 11 and 21, both jars): nothing to fix. **Windows is the
    platform that needs the option**: Java 21 `stdout.encoding = native.encoding = sun.jnu.encoding = Cp1252`,
    `file.encoding = UTF-8` (JEP 400). Without options TLC writes **cp1252** (`é` is the single byte `e9`; CJK becomes
    `?`) on both jars; with `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` it is UTF-8 on Java 11
    and 21, both jars, trace and `Print`. So the proposed default set fixes Windows too. On Windows with Java 11 and
    v1.7.4 and no option, TLC could not even parse the spec (exit 150): the UTF-8 spec is read as cp1252 (Java 11's
    `file.encoding = Cp1252`); the option cures it. `pcal` kept the comment bytes in every Windows cell (also Java 11
    v1.7.4 with no option: cp1252 round-trips those particular bytes, so this is luck of the characters chosen, not
    safety; the Linux C-locale run shows the destructive case).

## Confidence

**Verified** on Linux, for the three Javas and both jars, for the locales `C`, `POSIX`, `C.utf8`, `en_US.utf8`.
**Verified on macOS and Windows too** by one CI run (below), with pipes, BMP-safe spec, Java 11 and 21 only. **Partly verified**: no real Latin-1 locale (stand-in only, see short answer 4); a Windows console (as opposed to a pipe) and non-ASCII file names on Windows and macOS were not tried; the TTY case was
checked only on a Linux pseudo-terminal, once, with SANY; the source of 1.8.0 reading specs as UTF-8 was not found.
No GUI or Toolbox output was looked at.

## Evidence

### What the JVM reports (`-XshowSettings:properties`, output piped, `LC_ALL` set per row)

File `tables/java-default-encodings.txt`. Summary:

| Java | `LC_ALL=C` or `POSIX` | `C.utf8`, `en_US.utf8` |
|---|---|---|
| 11.0.33 | `file.encoding = ANSI_X3.4-1968`, `sun.jnu.encoding = ANSI_X3.4-1968` (no `stdout.encoding` property) | all `UTF-8` |
| 21.0.13 | `file.encoding = UTF-8`, `native.encoding`, `stdout.encoding`, `stderr.encoding`, `sun.jnu.encoding = ANSI_X3.4-1968` | all `UTF-8` |
| 25.0.5 | same as 21 | same as 21 |

This is JEP 400 (UTF-8 by default for `file.encoding` from Java 18) and the Java 19 split of the standard stream
encodings into `stdout.encoding` and `stderr.encoding`; on Java 11 neither `stdout.encoding` nor `native.encoding`
exists, and `-Dstdout.encoding=UTF-8` is accepted and does nothing (matrix below).

### Matrix

Each cell ran, with `env -i PATH HOME LC_ALL=<locale>` and stdout and stderr captured to separate files:
`TLC Enc.tla` (a spec with a trace whose values are `"café"`, `"日本語"` and `"😀"`, invariant violated on the third
state; `-tool` mode too in some cells), `TLC EncPrint.tla` (`PrintT` and `Print` of `"café 日本語 😀"`), `SANY` on a
spec with a parse error that quotes the string token (`Foo == 1 "café 日本語 😀"`), `pcal.trans` on a spec with a
non-ASCII string (the message) and on a spec with non-ASCII only in comments (the rewritten file). v1.7.4 ran the
variants in `specs-v1.7.4/` (BMP characters that its lexer accepts, `日語文` and `ø` instead of the emoji; the emoji
only in a comment). About 540 runs, 2 versions x 3 Javas x (C, POSIX, C.utf8 plus 5 option sets in C, `en_US.utf8`
and the final "minimal" set).

Legend of the tables: `UTF8` bytes equal the UTF-8 encoding; `ASCII?` one `?` per character; `BYTE?` one `?` per UTF-8
byte of the *input*; `L1` Latin-1.

Rolling (1.8.0), columns: trace values (`café` / `日本語` / `😀`), `Print`, translator message, SANY quote.

| Java | Locale and option | trace | Print | pcal msg | SANY quote | `.tla` rewritten by pcal |
|---|---|---|---|---|---|---|
| 11, 21, 25 | `C.utf8`, `en_US.utf8` | UTF8 x3 | UTF8 | UTF8 | UTF8 | intact |
| 11, 21, 25 | `C`, `POSIX`, no option | ASCII? x3 | ASCII? | ASCII? | ASCII? | intact |
| 11 | `C` + `-Dfile.encoding=UTF-8` | UTF8 | UTF8 | UTF8 | UTF8 | intact |
| 21, 25 | `C` + `-Dfile.encoding=UTF-8` | ASCII? | ASCII? | ASCII? | ASCII? | intact |
| 11 | `C` + `-Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` | ASCII? | ASCII? | ASCII? | ASCII? | intact |
| 21, 25 | `C` + the same | UTF8 | UTF8 | UTF8 | UTF8 | intact |
| 11, 21, 25 | `C` + `-Dsun.stdout.encoding=UTF-8 -Dsun.stderr.encoding=UTF-8` | UTF8 | UTF8 | UTF8 | UTF8 | intact |
| 11, 21, 25 | `C`, `POSIX` + `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` | UTF8 | UTF8 | UTF8 | UTF8 | intact |
| 11 | `C` + `-Dfile.encoding=ISO-8859-1` (Latin-1 stand-in) | `L1` / `?` / `?` | `é` as e9, rest `?` | L1 | e9 then `?` | intact |
| 21, 25 | `C` + `-Dfile.encoding=ISO-8859-1` | ASCII? | ASCII? | ASCII? | ASCII? | intact |

v1.7.4 (the rows that differ from rolling are marked):

| Java | Locale and option | trace | Print | pcal msg | SANY quote | `.tla` rewritten by pcal |
|---|---|---|---|---|---|---|
| 11, 21, 25 | `C.utf8`, `en_US.utf8` | UTF8 x3 | UTF8 | UTF8 | UTF8 | intact |
| 21, 25 | `C`, `POSIX`, no option | ASCII? x3 | ASCII? | ASCII? | ASCII? | intact |
| **11** | `C`, `POSIX`, no option | `caf??` / `BYTE?` / `BYTE?` | `BYTE?` (spec read as ASCII) | ASCII? | `BYTE?` | **comments destroyed (`?`)** |
| 11 | `C` + `-Dfile.encoding=UTF-8` | UTF8 | UTF8 | UTF8 | UTF8 | intact |
| **11** | `C` + `-Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` | `BYTE?` | `BYTE?` | ASCII? | `BYTE?` | **destroyed** |
| **11** | `C` + `-Dsun.stdout.encoding=UTF-8 -Dsun.stderr.encoding=UTF-8` | **U+FFFD per input byte** (`ef bf bd`), written as UTF-8 | same | same | same | **destroyed** |
| 21, 25 | `C` + `-Dfile.encoding=UTF-8` | ASCII? | ASCII? | ASCII? | ASCII? | intact |
| 21, 25 | `C` + `-Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8`, or the `sun.*` pair | UTF8 | UTF8 | UTF8 | UTF8 | intact |
| 11, 21, 25 | `C`, `POSIX` + `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` | UTF8 | UTF8 | UTF8 | UTF8 | intact |
| 11 | `C` + `-Dfile.encoding=ISO-8859-1` | bytes pass through unchanged (read and written as Latin-1, so they look right) | same | partly cut | same | intact |
| 21, 25 | `C` + `-Dfile.encoding=ISO-8859-1` | `BYTE?` (spec read as Latin-1, output ASCII) | `BYTE?` | ASCII? | `BYTE?` | intact |

(The v1.7.4 "ASCII? / BYTE?" labels are from `tables/table-v174.txt` and `tables/table-v180.txt`, one row per cell;
those two files are the complete result, the tables above are their summary.)

### Hexdumps (selected; the full set is in `excerpts/`)

Rolling, Java 25, trace line `s = "..."` for the three values:

```
LC_ALL=C.utf8   73 20 3d 20 22 63 61 66 c3 a9 22          s = "café"
                73 20 3d 20 22 e6 97 a5 e6 9c ac e8 aa 9e 22   s = "日本語"
                73 20 3d 20 22 f0 9f 98 80 22             s = "😀"
LC_ALL=C        73 20 3d 20 22 63 61 66 3f 22             s = "caf?"
                73 20 3d 20 22 3f 3f 3f 22                s = "???"
                73 20 3d 20 22 3f 22                      s = "?"
```

Rolling, Java 25, SANY parse error, LC_ALL=C: `Encountered ""caf? ??? ?"" at line 3, column 10 and token "1"`
(bytes `63 61 66 3f 20 3f 3f 3f 20 3f`); with `-Dstdout.encoding=UTF-8` the same line holds `63 61 66 c3 a9 20 e6 97 a5 ...`.

v1.7.4, Java 11, C locale, no option, trace line for `"café"`: `73 20 3d 20 22 63 61 66 3f 3f 22` (two `?` for the two
UTF-8 bytes of `é`); with `-Dsun.stdout.encoding=UTF-8` only: `63 61 66 ef bf bd ef bf bd` (two U+FFFD).

Translator rewrite, v1.7.4, Java 11, C locale, first comment line of the rewritten `.tla` (`excerpts/pcal-rewrite-hex.txt`):
`... 3a 20 63 61 66 3f 3f 20 3f 3f 3f 3f 3f 3f 3f 3f 3f 0a` instead of `... 63 61 66 c3 a9 20 e6 97 a5 e8 aa 9e e6 96 87 0a`.

### stderr is independent of stdout

SANY on a missing file `café日.tla` writes `Cannot find the specified file ...` to stdout and `File does not exist: ...`
to stderr (1.8.0; v1.7.4 the same split). With `LC_ALL=C.utf8` and a deliberately different charset set for stderr only
(`excerpts/stderr-and-dumptrace-hex.txt`): `-Dstderr.encoding=ISO-8859-1` turned the stderr copy into `63 61 66 e9 3f` while
stdout stayed UTF-8, on Java 21 and 25; on Java 11 `-Dstderr.encoding` did nothing and `-Dsun.stderr.encoding` did it.
So the stderr property has to be set too; setting only the stdout one leaves stderr on the locale encoding.
TLC itself wrote nothing to stderr in any non-ASCII case captured; SANY (both versions) and the JVM's own error
messages do.

### `-dumpTrace json FILE` (1.8.0 only)

Bytes of the `"s"` values in the written file (`excerpts/stderr-and-dumptrace-hex.txt`):

| Java, locale, option | file content |
|---|---|
| 25, C, none | UTF-8 (`63 61 66 c3 a9`, ...) |
| 25, C.utf8, none | UTF-8 |
| 25, C, `-Dstdout.encoding=UTF-8` | UTF-8 |
| 11, C, none | `63 61 66 3f`, `3f 3f 3f`, `3f` (the file is lossy) |
| 11, C, `-Dsun.stdout.encoding=UTF-8` | still `?` |
| 11, C, `-Dfile.encoding=UTF-8` | UTF-8 |

### File names (`fn.sh`)

`LC_ALL=C`, any of the Javas, any option set including `-Dsun.jnu.encoding=UTF-8`: 1.8.0 `SANY café日.tla` and
`TLC <path with é日 in a folder name>` exit 1 with `java.nio.file.InvalidPathException ... caf?????.tla` (printed with
`?`, or with U+FFFD when `-Dstderr.encoding=UTF-8` is set); v1.7.4 prints `Cannot find the specified file caf?????.tla` and
exits 255. `LC_ALL=C.utf8`: the files are found (1.8.0 exit 12 for the invariant violation, v1.7.4 150 because of
its lexer, see side findings).

### macOS and Windows (CI run)

Run: <https://github.com/nikolskiy/tlaup/actions/runs/44489200898> (branch `research/top-up-experiments`, commit
`0d43a75`, 2026-11-19 08:37-08:48 UTC). Runner images: ubuntu-latest = ubuntu26 20261111.82.6 x86-64; macos-latest =
macos26 20261112.0504.1 arm64; windows-latest = win25-vs2026 20261103.298.1 x86-64. Java: Temurin 11.0.33+10 (via
`JAVA11_HOME`) and Temurin 21 (21.0.13+9 ubuntu, 21.0.13.1+2 macOS, 21.0.13 on the Windows `PATH`). Script
`ci_encoding.py`; logs in `ci-run/q21-{ubuntu,macos,windows}.txt` and `ci-run/RUN-INFO.txt`. Output captured through
pipes only (no console). Spec: `café`, `日語文`, `ø`.

| OS, Java | no option | with the three UTF-8 options |
|---|---|---|
| ubuntu (UTF-8 locale), 11 and 21 | UTF-8 | UTF-8 |
| macOS (all four properties UTF-8), 11 and 21 | UTF-8 | UTF-8 |
| Windows 21 (`stdout/native/sun.jnu = Cp1252`, `file = UTF-8`) | **cp1252** (`636166e9`; CJK `?`), both jars | UTF-8 (`636166c3a9`) |
| Windows 11 (`file/sun.jnu = Cp1252`), rolling | **cp1252** (`636166e9`) | UTF-8 |
| Windows 11, v1.7.4 | **rc 150, no trace** (spec misread as cp1252) | UTF-8, rc 12 |

`pcal-rewrite`: comments kept in all 24 cells of the three OSes.

## Implications for the roadmap

(For the coordinator; no design decision is changed here.)

0. (CI result) **The same set fixes Windows**, where it matters most: the default there is cp1252 for the streams on Java 11 and 21, and on Java 11 with v1.7.4 it even breaks parsing of a UTF-8 spec. macOS needs nothing and is unharmed by it. Windows console output (code page 437/850 or UTF-8 console) was not exercised; tlaup reads pipes, so it is not what the launcher sees.
1. **The launcher should add an encoding option by default. The set that fixes everything that can be fixed by an
   option, on every supported Java, is `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8`.** Each
   part is needed: `file.encoding` is the only one that Java 11 honours of the three and the one that makes v1.7.4 read
   the spec correctly and keeps `pcal` from corrupting the user's file; `stdout.encoding` and `stderr.encoding` are the
   ones Java 21 and 25 read. Unknown `-D` properties are not an error on any of the three Javas, so no version check is
   needed. `-Dsun.stdout.encoding`/`-Dsun.stderr.encoding` also worked on all three but are undocumented internal
   names; they are a possible fallback, not the first choice.
2. With that option tlaup can decode every line as UTF-8 (the design's `errors="replace"` stays as the guard for the
   remaining cases, such as a user's own `JAVA_TOOL_OPTIONS` or a tool jar of another vendor). Without it, in a C or
   POSIX locale the bytes are ASCII with `?` and nothing in tlaup can restore the characters, so R3's current claim
   ("what TLC writes does not follow the locale tlaup sees") should be corrected: it follows the JVM's own locale-derived
   default, which is the locale of the process the launcher starts, and a launcher that adds the option takes that
   dependence away. The R3 risk "waiting on question 21" can be closed on this answer.
3. **The option also belongs to `pcal` and `sany`** (every Java tool the launcher starts, G3 puts them all through one
   launcher), not only `tlc`: v1.7.4's `pcal.trans` on Java 11 in a C locale destroys non-ASCII comments in the user's
   `.tla`. This is a correctness reason, not a display one, and it is the case for adding it to the shared launcher
   rather than to the TLC command only.
4. **Not fixable by an option: non-ASCII file names in a C or POSIX locale** (short answer 8). If the maintainer wants
   those to work, the launcher has to set `LC_ALL=C.UTF-8` (or `LANG`, with `LC_ALL` removed) in the child's
   environment when the parent's is not UTF-8. It worked here on glibc; availability of `C.UTF-8` on macOS is not
   known (follow-ups). Otherwise tlaup can detect a non-ASCII path with a non-UTF-8 locale and give a hint instead of a
   Java stack trace.
5. A golden file (S5, T3) that must run on both versions can use non-ASCII only in the BMP set that v1.7.4 accepts
   (é, 日, 語, 文, α, Ω, ß, ñ, €, ø) and in strings outside the translator's input; an emoji only in a comment or on
   1.8.0 only.
6. The `sany` and `pcal` commands should pass the same option; the tests in R3 (fake `java` replaying `FF FE` and a
   Latin-1 `é`) stay valid for a user's own options and for old bytes.
7. R3's real-process test with `PYTHONIOENCODING=ascii` is about tlaup's own streams and is unaffected.

## Open follow-ups

- A real Latin-1 locale (`de_DE.ISO-8859-1`) on a machine that has one, to confirm the Java 11 stand-in for Java 21 and
  25 (expected: `stdout.encoding = ISO-8859-1` there, `é` as `e9`).
- Where 1.8.0 reads the spec as UTF-8 (the `SimpleCharStream` in the pinned commit uses the default), since it affects
  whether the option is needed for reading on 1.8.0 (it is not, observed).
- A JVM that was given a `JAVA_TOOL_OPTIONS` or `_JAVA_OPTIONS` with its own encoding: not tried; it prints a
  `Picked up ...` line on stderr (an ASCII line), which the stderr handling of the launcher already has to tolerate.
- The `Print` output of a *non-BMP* character through a Latin-1 stream was not looked at beyond `?`.

## Date checked

2026-11-18 (local time; the machine clock and the jars' state as in the brief, rolling CalVer 2026.11.15.002146).
