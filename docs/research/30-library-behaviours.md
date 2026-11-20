# 30: Library behaviours the design relies on, across the allowed versions

## Question

Which versions of the libraries the design leans on behave the way the design says, so that `pyproject.toml` can get
real lower bounds and the test tools can be used as [01](../design/01-testing.md) describes? In priority order:

1. The earliest `filelock` that, after it has the lock, looks again for a lock file that was unlinked under it, and any
   other `filelock` behaviour [11 R6](../design/11-runner.md#r6-run-folders) relies on (timeout, release on process
   death, a second lock object in the same process refused like a second process, and how the thread-local,
   singleton and reentrant behaviour changed). macOS and Windows as CI scripts.
2. Rich's closed-pipe handling (`Console.on_broken_pipe`, behind the 141 of [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)
   and [02 X1](../design/02-cross-cutting.md#x1-exit-codes)), Rich's `Live` on the alternate screen
   ([22 O4](../design/22-reporters.md#o4-live-display)), and what `select.poll` reports on a pipe whose reader has gone.
3. Whether `pyte` reads what Rich draws well enough for the screen checks.
4. coverage's subprocess patch with tests that start real processes ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)).
5. pytest-bdd: doc strings in steps; whether a Given may follow a When ([01 T5](../design/01-testing.md#t5-feature-files-and-steps)).
6. `responses` serving a body shorter than its `Content-Length`, and `responses` with `pytest-socket` ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)).
7. The lowest Pydantic the settings model works on ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration), [30 B2](../design/30-ci-and-release.md#b2-build-fixes)).

## Source

- Roadmap, investigation list item 30; design README, "Waiting on a top-up investigation", row 30.
- `filelock`: clone of github.com/tox-dev/filelock at `f80f6a8d09315ad314a388523b1e470d1f08c986` (tag 4.2.12, 2026-11-18),
  its `docs/changelog.rst`, and every release from 3.12.0 to 4.2.12 that has files on PyPI (110 versions), each
  installed in its own uv environment.
- Rich: PyPI releases 12.6.0 to 15.0.0 (15.0.0 is the newest, 2026-04-12), source read from the installed packages;
  tags `v13.8.0` = `9ec419154102acce7363e3958bec6c261864d7fb`, `v15.0.0` = `6ac483cbea39cab124dfd3483bba70ffafb71050`
  (read with `gh api`; a full clone timed out).
- Typer 0.29.1 (locked), pyte 0.8.2 (newest), coverage 7.10.6 / 7.10.7 / 7.17.3 (locked) with pytest-cov 7.1.0 (locked),
  pytest 9.2.0 (locked), pytest-bdd 7.3.0 / 8.0.0 / 8.1.0 / 9.0.0 / 9.0.1 (newest), responses 0.23.3 to 0.26.3 (newest),
  pytest-socket 0.6.0 / 0.7.0 / 0.8.1 (newest), requests 2.34.2 and urllib3 2.8.0 (locked), pydantic 2.0 to 2.14.3 (locked).
- Linux x86-64, 12 cores; CPython 3.11.15 and 3.14.3 (uv-managed) and 3.13.5 (system). No Java or TLC was needed.
  Other agents ran on the machine at the same time; no result below depends on timing beyond "under a second".
- The probes and their captured output are in `tests/fixtures/research/30-library-behaviours/`; the scripts under
  `ci/` there are the ones prepared for the macOS and Windows CI run (copies of `<tmp>/ci/q30/`).
- CI run 1: https://github.com/nikolskiy/tlaup/actions/runs/44489200898 (branch `research/top-up-experiments`, commit
  `0d43a75`, 2026-11-19 08:37 to 08:48 UTC, success). Runner images: ubuntu-latest = ubuntu26 20261111.82.6 x86_64;
  macos-latest = macos26 20261112.0504.1 arm64; windows-latest = win25-vs2026 20261103.298.1 x86_64. Python 3.13.18
  (ubuntu) and 3.13.17 (macOS, Windows), uv 0.13.9. Its logs are in `ci-run-1/<os>/q30-*.txt` in the fixtures folder:
  `q30-poll.txt` = `select_poll_probe.py`, `q30-filelock.txt` = `filelock_versions.py`, `q30-rich.txt` =
  `rich_versions.py`.
- CI run 2 (Windows only for this question): https://github.com/nikolskiy/tlaup/actions/runs/44491714376 (commit
  `8647da2`, 2026-11-19 UTC, success), windows-latest = win25-vs2026 20261103.298.1 x86_64, Python 3.13.17, uv 0.13.9.
  Logs in `ci-run-2/windows/`: `q30-windows-pipe.txt` = `windows_pipe_probe.py` with Rich 13.9.4,
  `q30-filelock-4212.txt` = `filelock_probe.py` with filelock 4.2.12.

## Short answer

1. **filelock.** The second look (after `flock`, `fstat` the descriptor and start over when `st_nlink == 0`) first
   shipped in **3.20.4** (2026-02-12), from PR #408, which 3.21.0 carries too; 3.20.3 and every earlier version fail
   the R6 property exactly as the formal check predicted (the waiter holds a lock on an unlinked file and a third lock
   object gets the lock). But the same PR also made the library **delete the lock file on release**, and in
   3.20.4 to 3.29.4 that release-time unlink removes whatever file is at the name, including the lock file of a
   process that took the lock after tlaup removed its own: the third object then gets the lock, so mutual exclusion
   breaks in a different place. 3.29.5 stopped deleting on release (PR #577). From 3.29.5 up to 4.2.0 the library
   still **truncates the lock file when it takes the lock** (`O_TRUNC`, later `ftruncate` after the lock), which
   changes the file's modification time on Linux, and R6's one-hour rule reads that time. **4.2.1** (2026-10-17,
   PR #835) is the first version where everything R6 relies on holds on Linux: the second look, the file kept after
   release, the modification time untouched by taking or releasing, a timeout that raises `Timeout` on time, a free
   lock as soon as the holder is killed, and a second lock object in the same process (same or another thread)
   refused like another process. Those last three hold for every version from 3.12.0. No version is a singleton by
   default; the same object re-acquired is reentrant (a counter) in every version; since at least 3.29.6 a second
   object on a held path in the same thread raises `RuntimeError("Deadlock ...")` when it waits with no timeout
   (`timeout=-1`), while any finite timeout still gives `Timeout`. **macOS** (CI, arm64) gave exactly the Linux
   results for all eight versions run, the truncation's mtime change included. **Windows** (CI) is a different world:
   a held lock file cannot be unlinked (`PermissionError`) in any version, so the situation the second look guards
   against cannot arise and the R6 property holds in every version tried (3.20.3 included); the library deletes the
   lock file on release in every version (so R6's "the file stays after release" and the one-hour rule for folderless
   lock files do not apply there); taking the lock leaves the modification time alone from 3.29.4 (3.20.3 and 3.20.4
   changed it); timeout, same-process refusal, release on process death and creation hold in every version. The
   proposed bound `>=4.2.1` holds on all three systems.
2. **Rich.** `Console.on_broken_pipe` appeared in **13.8.0** (PR #3468); its body is the same in 13.8.0, 13.9.4,
   14.0.0, 14.3.4 and 15.0.0: point descriptor 1 at the null device and raise `SystemExit(1)`. Through a real closed
   pipe and through `| head -1`, every version from 13.8.0 to 15.0.0 gave what F10 expects: exit 1 with descriptor 1
   on the null device for a plain console and for Typer 0.29.1's `--help`, and 141 with a subclass that raises
   `BrokenPipeError`. 13.7.x has no such method: the `BrokenPipeError` leaves `print` and the process exits 120. One
   detail F10 does not state: a stderr console on a closed stderr also points **stdout** (descriptor 1) at the null
   device, never descriptor 2, so without F10's final guarded flush the process exits 120 (on the CI runners it exited
   1 instead; the same 1 appears here with `PYTHONUNBUFFERED=1`, so it depends on whether stderr holds unwritten
   bytes at exit, and F10's flush guard and `reader_gone(2)` cover both). `Live(screen=True)` on a
   real pty wrote the enter and leave sequences, redrew from its refresh thread with no outside call, and `Live.stop`
   does not refresh on the alternate screen, in 13.8.0, 13.9.4, 14.0.0, 14.3.4 and 15.0.0. `select.poll` on Linux
   reports `POLLERR` (with `POLLOUT`) on a pipe whose reader has gone, nothing on a full pipe whose reader is alive,
   and `POLLNVAL` on a closed descriptor. **macOS** (CI) reports `POLLHUP` alone (no `POLLOUT`) for a gone reader,
   but **nothing at all when the descriptor is registered with an empty mask**, and `POLLNVAL` for the null device;
   so "`POLLERR` or `POLLHUP`, registered for `POLLOUT`" is right on both. **macOS** Rich results equal Linux for
   every case, and the Live/pyte check passes there too. **Windows** has no `select.poll`, and a write to a pipe whose
   reader has gone raises **`OSError` errno 22 (`EINVAL`), not `BrokenPipeError`**, in every Rich version: Rich never
   calls `on_broken_pipe`, the subclass never sees anything, Typer's `--help` leaves with that `OSError`, and every
   case exits 1 with a traceback. CI run 2 showed the same `OSError` with `errno` 22 and **`winerror` None** for plain
   `print` and for a Rich console, both when the reader closed before the child started and when the reader read one
   line and quit while the child was writing 200,000 lines. F10's closed-pipe handling therefore does not give 141 on
   Windows as designed, and the only mark of the case is `EINVAL` from a write to a stream that is a pipe.
3. **pyte** 0.8.2 follows what Rich 13.8.0 to 15.0.0 draws on a 100 by 30 pty: the four panel titles on one screen,
   the refresh thread's changing counter (12 to 14 distinct frames in 1.5 s), the last frame, colours (`green`,
   `brightgreen` for bold green, `red`), the `…` of a cut line, and the plain text after the leave sequence. Cutting
   the stream at the two sequences, as O4 says, works. The same on macOS (CI: 8 to 10 distinct frames, the rest
   identical), where reading the pty master until the child had gone lost no bytes. Resizing was not tried.
4. **coverage** `patch = ["subprocess"]` with `parallel = true` works with pytest-cov 7.1.0 and coverage 7.10.6 and
   7.17.3: lines run only in child processes are counted, including a child that ends with 130 after
   `KeyboardInterrupt`, one that exits 143 from its own SIGTERM handler, and one on a pty. A child killed by a signal it
   does not handle, or ending with `os._exit`, loses its data. The fake `java` (a Python file outside `source`) is not
   measured and its stderr stays empty. pytest-cov 7.1.0 itself requires coverage 7.10.6 or later.
5. **pytest-bdd**: only **9.0.1** works with the locked pytest 9.2.0 (7.3.0, 8.0.0, 8.1.0 and 9.0.0 fail with
   `AttributeError: 'FixtureManager' object has no attribute '_arg2fixturedefs'`; 9.0.0 works with pytest 9.0.2 and
   9.1.0). Doc strings reach a step as the reserved `docstring` argument (from 8.0; 7.x appended them to the step
   text), with the common indent removed and inner indent and quotes kept. A Given after a When is accepted in every
   version tried, and `scenarios("features")` resolves against the test file's folder.
6. **responses** 0.23.3 to 0.26.3 keep a `Content-Length` header longer than the body; `requests` then raises
   `requests.exceptions.ChunkedEncodingError` wrapping urllib3's `IncompleteRead(3 bytes read, 7 more expected)`, both
   for `.content` and for `iter_content` (which yields nothing before raising); `raw.read()` returns the 3 bytes
   without an error. With `pytest-socket --disable-socket`, mocked requests work and an unregistered URL gets
   `responses`' own `ConnectionError`; a request with `responses` not active is blocked at `socket.getaddrinfo` by
   pytest-socket 0.8.x (at `socket.socket` by 0.6 and 0.7), and under `-W error` 0.8.x's `UserWarning` is what
   surfaces, not `SocketBlockedError`.
7. **Pydantic**: a model shaped like F1 and F3 (nested frozen models with defaults, `extra="ignore"`,
   `Literal["auto"] | int` with a bound, a `field_validator` that lower-cases hosts, `json_schema_extra` marks,
   `TypeAdapter` for one key, `ValidationError.errors()` with `loc`, `msg`, `type` and `input`, `model_dump(mode="json")`)
   works on every version from **2.0** to 2.14.3 on Python 3.11. Installable wheels set the practical floor per
   Python: 2.8 on 3.13, 2.12 on 3.14 (older pydantic-core does not build there). The present unit tests pass with
   pydantic 2.8.0 on 3.13. pydantic-settings is not used (F1 rejected it).

## Confidence

- Part 1: **verified** on Linux for every PyPI release from 3.12.0 to 4.2.12, by a deterministic test, and matched to the
  source and changelog; **verified** on macOS and Windows (CI run 1) for 3.20.3, 3.20.4, 3.29.4, 3.29.5, 4.2.0, 4.2.1,
  4.2.10 and 4.2.12 (the Windows second-look check of 4.2.12 in CI run 2, after the probe was fixed for a renamed
  helper).
- Part 2: **verified** on Linux for Rich 13.7.0, 13.8.0, 13.9.4, 14.0.0, 14.3.4, 15.0.0, and on macOS and Windows for
  13.8.0, 13.9.4, 14.3.4, 15.0.0; `select.poll` **verified** on Linux and macOS. Windows **verified** (CI runs 1 and 2): `OSError`
  errno 22, `winerror` None, for a reader gone before and during the writes.
- Part 3: **verified** on Linux and macOS (no pty on Windows); resizing **not answered**.
- Parts 4 to 7: **verified** on Linux for the versions named; not run on macOS or Windows.

## Evidence

### 1. filelock

**The test.** `ci/filelock_probe.py` makes the R6 interleaving deterministic instead of hoping for it: it wraps
`fcntl.flock` (on Windows the module's `_lock_fd_nonblocking`, or `msvcrt.locking` in old versions) so that the
waiter's first lock attempt stops after the waiter has opened the lock file and before it locks; the holder then
removes the lock file and releases; the waiter then locks. The check passes when the waiter ends up holding a lock on
the file that is at the path (same device and inode) and a third lock object with `timeout=0` gets `Timeout`. It runs
once with the waiter as a thread and once as a second Python process (`recheck_proc`). The other checks: `timeout`
(`Timeout` after about 0.5 s for `timeout=0.5`), `same_process` (two objects are not one; the second is refused, also
from another thread), `death` (a child holding the lock is killed; the lock is free at once), `left_behind` (the file
is still there after release), `mtime` (a lock file dated two hours ago keeps that time while held and after release),
`foreign_file` (the holder removes its file, a second object takes a new file at the name, the first releases: the new
file must survive and a third object must be refused), `creates` (acquiring creates a missing file).

```
cd <tmp>/ci
for v in $(cat ../q30/fl_versions.txt); do      # every release 3.12.0 .. 4.2.12 with files on PyPI
  Q30_TMP=<tmp>/q30 uv run --no-project -q -p 3.13 --with filelock==$v python q30/filelock_probe.py
done
```

Summary of the 110 rows (full table: `filelock-matrix-linux.txt`):

| Versions | recheck (thread, process) | timeout, same process, death, creates | file kept after release | other's file kept, third refused | mtime unchanged |
| --- | --- | --- | --- | --- | --- |
| 3.12.0 to 3.20.3 | FAIL: `waiter's file vs path: path-missing; third-GOT-LOCK` | PASS | yes | PASS | no |
| 3.20.4 to 3.29.4 | PASS | PASS | **no** (deleted by the library) | **FAIL**: `other's file REMOVED by old holder's release; third-GOT-LOCK` | no (file gone) |
| 3.29.5 to 4.2.0 | PASS | PASS | yes | PASS | **no**: `while held: CHANGED` |
| 4.2.1 to 4.2.12 | PASS | PASS | yes | PASS | yes |

Also run on Python 3.11.15 and 3.14.3 with 4.2.1 and 4.2.10: all nine checks pass.

**Where it comes from in the source** (links pinned to the release commits):

- 3.20.3 (`41b42dd2c72aecf7da83dbda5903b8087dddc4d5`) opens with `O_CREAT | O_TRUNC`, locks, and keeps the descriptor
  without looking at it again: [`_unix.py`](https://github.com/tox-dev/filelock/blob/41b42dd2c72aecf7da83dbda5903b8087dddc4d5/src/filelock/_unix.py).
- Commit [`03b0ab7`](https://github.com/tox-dev/filelock/commit/03b0ab7ea566b1d1385274d185e5e590cdaa6872)
  ("feat(unix): delete lock file on release", PR #408, 2026-02-11) added both the second look and the unlink in
  `_release`. Tag 3.20.4 (`afa79d567faf98332ac5700fa670b3425a0cbc29`, published ten minutes before 3.21.0) already
  contains it although the changelog lists the PR under 3.21.0 only and gives 3.20.4 one CI fix:
  [`st_nlink == 0` check, line 71](https://github.com/tox-dev/filelock/blob/afa79d567faf98332ac5700fa670b3425a0cbc29/src/filelock/_unix.py#L71),
  [`Path(self.lock_file).unlink()` in `_release`, line 80](https://github.com/tox-dev/filelock/blob/afa79d567faf98332ac5700fa670b3425a0cbc29/src/filelock/_unix.py#L80).
  The release unlinks by name, before `LOCK_UN`, so it can remove a file another process created and locked after
  tlaup removed its own.
- Commit [`ea594a5`](https://github.com/tox-dev/filelock/commit/ea594a5cbca43cec92d62f740a8e510a7db0ceed)
  ("Keep Unix lock files after release", PR #577) is in 3.29.5 (`be562277636140c26578a98a2a487fdb6f446ee6`, 2026-07-02);
  the class docstring from then on says unlinking a locked file "can split waiters across different inodes".
- 4.2.0 (`e2e7d709890ac08ec9e35eece65ef51f62df5cf5`) no longer opens with `O_TRUNC` but
  [`os.ftruncate(fd, 0)` after the lock, line 154](https://github.com/tox-dev/filelock/blob/e2e7d709890ac08ec9e35eece65ef51f62df5cf5/src/filelock/_unix.py#L154),
  which on Linux sets the modification time even for an empty file.
- Commit [`e1e825b`](https://github.com/tox-dev/filelock/commit/e1e825b1992f69fb6b346dc395d5ae4893536c0a)
  ("fix(open): keep lock files intact, honor deadlines and mode", PR #835, in 4.2.1,
  `60331bb89f325020b48bc51bde904c6446384e4a`) removed the truncation.
- 4.2.10 (`f9e562169e2580019e3fd96e66d8e0accf57fe4a`, locked):
  [`_finalize_locked_fd`, lines 171 to 178](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_unix.py#L171-L178)
  returns `False` for `st_nlink == 0`, the caller closes the descriptor and the retry loop opens the name again.
  The check sees an unlinked file, not a file renamed or hard-linked over the name; R6 only unlinks.
- Windows in 4.2.10: the file is opened through `NtCreateFile` with a share mode that
  [omits delete (line 322)](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_windows.py#L322),
  so no process can unlink a held lock file; [`_release`](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_windows.py#L303-L314)
  unlocks, closes and then unlinks the file unless `preserve_lock_file` was given. Locking is `LockFileEx` on one byte.

**Same process, threads, singleton, reentrancy.** From the probe and `deadlock_probe.py`:

```
same_process linux : PASS (filelock 3.12.0 ... 4.2.12) - singleton=False; second-object-refused;
                     same-object-reentrant(counter=2); other-thread-object-refused
3.23.0 / 3.24.0 / 3.29.6 / 3.29.7 / 4.2.1 / 4.2.10 / 4.2.12:
    t=0:Timeout@0.00s; t=0.5:Timeout@0.5s; t=2:Timeout@2.0s; nonblocking:Timeout
3.29.6 / 3.29.7 / 4.2.10, timeout=-1, same thread:
    RuntimeError Deadlock: lock '<tmp>/q30/.../x.lock' is already held by a different FileLock instance
```

The changelog dates the detection: "Detect a same-thread self-deadlock" (PR #481) in 3.24.0, "Detect cross-instance
reentrant deadlocks before the poll loop" in 3.29.7 (3.29.6 already raised it in the run above). `is_singleton`
defaults to false in every version, and the state of a lock object is thread-local by default (`thread_local=True`):
the probe had to read the waiter's descriptor from the waiter's own thread.

**Released when the holder dies**: the `death` check passes for every version (free within 0.00 s of `SIGKILL`); it is
the operating system's `flock`, not the library.

**CI run 1, macOS and Windows** (`ci-run-1/<os>/q30-filelock.txt`, `filelock_versions.py`, Python 3.13.17):

| Version | macOS (arm64) | Windows |
| --- | --- | --- |
| 3.20.3 | as Linux: recheck FAIL (`path-missing; third-GOT-LOCK`), mtime FAIL | recheck PASS (`unlink-failed:PermissionError; ... same; third-refused`); file deleted on release; mtime CHANGED while held |
| 3.20.4 | as Linux: file deleted on release, foreign file REMOVED, mtime FAIL | as 3.20.3 |
| 3.29.4 | as Linux | recheck PASS; file deleted on release; mtime unchanged while held |
| 3.29.5, 4.2.0 | as Linux: file kept, mtime CHANGED (so `ftruncate` changes it on macOS too) | as 3.29.4 |
| 4.2.1, 4.2.10, 4.2.12 | all nine PASS | as 3.29.4; for 4.2.12 recheck ERROR "the waiter never reached the lock call" (probe) |

On Windows `foreign_file` printed SKIP everywhere ("cannot unlink a held lock file here: PermissionError"), and
`timeout`, `same_process` (`singleton=False; second-object-refused; same-object-reentrant(counter=2);
other-thread-object-refused`), `death` and `creates` passed for every version. The 4.2.12 ERROR is the probe's: 4.2.12
renamed the module helper `_lock_fd_nonblocking` to `lock_fd_nonblocking`
([4.2.12 `_windows.py` line 256](https://github.com/tox-dev/filelock/blob/f80f6a8d09315ad314a388523b1e470d1f08c986/src/filelock/_windows.py#L256)),
so the gate patched `msvcrt.locking`, which is never called. The probe now patches either name (still 9 of 9 on
Linux with 4.2.12). CI run 2 with the fixed probe: `recheck windows : PASS (filelock 4.2.12) - unlink-failed:PermissionError;
waiter's file vs path: same; third-refused`, the process form the same, the other checks as for 4.2.10.

### 2. Rich

**`on_broken_pipe`, where and since when.** `inspect.getsource(Console.on_broken_pipe)` per installed version: absent
in 12.6.0, 13.0.0, 13.2.0, 13.3.0, 13.3.1, 13.4.0 and 13.7.0; present and identical in 13.8.0, 13.9.4, 14.0.0, 14.3.4,
15.0.0 (`self.quiet = True`, `os.dup2(devnull, sys.stdout.fileno())`, `raise SystemExit(1)`). It is called from one place,
the `except BrokenPipeError` around `_write_buffer` in `Console._check_buffer`:
[13.8.0 `console.py` lines 1999 and 2025](https://github.com/Textualize/rich/blob/9ec419154102acce7363e3958bec6c261864d7fb/rich/console.py#L1999),
[15.0.0 lines 2030 and 2056](https://github.com/Textualize/rich/blob/6ac483cbea39cab124dfd3483bba70ffafb71050/rich/console.py#L2030).
The 13.8.0 changelog: "Added `Console.on_broken_pipe`" and "Fixed BrokenPipeError writing an error message", both
PR #3468.

**As real processes** (`ci/rich_pipe_probe.py`; "closed" means the read end of the pipe was closed before the child
started, so the first write fails; `| head -1` runs through `/bin/sh`):

| Case | 13.7.0 | 13.8.0, 13.9.4, 14.0.0, 14.3.4, 15.0.0 |
| --- | --- | --- |
| plain console, 3 lines, stdout closed | exit 120, `BrokenPipeError` left `print` | exit 1, `SystemExit(1)`, fd 1 on the null device |
| plain console, 200,000 lines `\| head -1` | exit 120 | exit 1, fd 1 on the null device |
| subclass whose `on_broken_pipe` raises `BrokenPipeError`, stdout closed / `\| head -1` | 141 (the error reaches the caller) | 141 |
| stderr console, stderr closed, stdout open | exit 120 | exit 120; `SystemExit(1)` was raised and **fd 1** was pointed at the null device |
| stderr console subclass, stderr closed | 141 | 141 |
| Typer 0.29.1 `--help`, stdout closed | (not installable: Typer needs `rich>=13.8.0`) | exit 1, fd 1 on the null device |
| Typer 0.29.1 unknown option, stderr closed | | exit 120 (`SystemExit(1)`, fd 1 to the null device) |

The 120 is the interpreter's own code when its final flush of a stream fails; F10's `main()` flushes both streams in
a guard and maps this case to 141 (`reader_gone(2)`), so the design already covers it, but the reason is that Rich
silences descriptor 1 whichever stream failed. Typer's console is the same Rich console class, so the help and usage
cases follow Rich's version, not Typer's.

**Live on the alternate screen** (`ci/rich_live_pty_probe.py`): a child draws a four-panel `Layout` through
`Live(console=Console(stderr=True), screen=True, get_renderable=..., refresh_per_second=10, redirect_stdout=False,
redirect_stderr=False)` on a pty of 100 by 30 with `TERM=xterm-256color` and no `COLUMNS` or `LINES`; it never updates
the display from outside for 1.5 s, sets the phase `Finished`, calls `refresh()` and `stop()`, then prints a line to
stdout. The parent reads the pty until `EIO`, cuts at `ESC[?1049h` and the last `ESC[?1049l`, and feeds the middle to
pyte in 512-byte pieces:

```
rich-live-pty linux : PASS (rich 13.8.0 | 13.9.4 | 14.0.0 | 14.3.4 | 15.0.0, pyte 0.8.2, Python 3.13.5) - enter/leave
  written; four titles on one screen: True; distinct ticks drawn by the refresh thread: 12..14; last frame has
  Finished: True; colours seen by pyte: ['brightgreen', 'green', 'red']; ellipsis kept: True; text after leave: True
```

`Live.stop` refreshes only when not on the alternate screen in all five versions (`if not self._alt_screen and ...`
in `Live.stop`, [13.8.0 `live.py` line 134](https://github.com/Textualize/rich/blob/9ec419154102acce7363e3958bec6c261864d7fb/rich/live.py#L134)).
A first version of the probe changed the view after the last `refresh()` and before `stop()`; once in six runs the
refresh thread drew that change first. That is the expected race of a refresh thread and is why O4's `finish`
refreshes before `close`.

**`select.poll`** (`ci/select_poll_probe.py`, standard library), Linux, Python 3.11 and 3.13:

```
reader alive: POLLOUT / no-events: none; reader closed: POLLOUT|POLLERR / POLLERR;
reader process exited: POLLOUT|POLLERR / POLLERR; full pipe, reader alive: none / none;
null device: POLLOUT; closed fd: POLLNVAL
```

("no-events" registers the descriptor with an empty mask: only `POLLERR`, `POLLHUP` and `POLLNVAL` can come back.) So
"`POLLERR` or `POLLHUP`" marks a gone reader on Linux and never a slow one; `POLLNVAL` marks a descriptor that is not
open, which F10's `reader_gone` must treat as false.

CI run 1 (`ci-run-1/<os>/q30-poll.txt`):

```
select-poll macos : PASS - reader alive: POLLOUT / no-events: none; reader closed: POLLHUP / none;
  reader process exited: POLLHUP / none; full pipe, reader alive: none / none; null device: POLLNVAL; closed fd: POLLNVAL
select-poll linux : PASS - (as on this machine)
select-poll windows : SKIP - select.poll does not exist on this platform (reader_gone is false)
```

On macOS a gone reader shows only when the descriptor is registered for an event (here `POLLOUT`); with an empty
mask `poll` returns nothing. The null device gives `POLLNVAL` on macOS (macOS `poll` does not support character
devices), which the "ignore `POLLNVAL`" rule already handles.

**Rich on macOS and Windows** (`ci-run-1/<os>/q30-rich.txt`, Rich 13.8.0, 13.9.4, 14.3.4, 15.0.0, Typer 0.29.1):

- macOS: every case as on Linux (plain console exit 1 with fd 1 on the null device, subclass 141, `| head -1` 1 and
  141, Typer `--help` closed 1); the stderr-closed cases exit 1, as on the ubuntu runner; `rich-live-pty` PASS for all
  four versions.
- Windows, a pipe whose read end was closed before the child started:

```
rich-plain-closed-stdout windows : DIFFERENT (rich 13.8.0 .. 15.0.0) - exit 1; OSError
rich-subclass-closed-stdout windows : DIFFERENT - on_broken_pipe raising BrokenPipeError: exit 1; (no note)
rich-subclass-closed-stderr windows : DIFFERENT - exit 1; (no note)
rich-typer-help-closed windows : DIFFERENT (typer 0.29.1) - exit 1; OSError: [Errno 22] Invalid argument
rich-typer-usage-closed-stderr windows : INFO - exit 1; OSError: [Errno 22] Invalid argument
rich-live-pty windows : SKIP - no pty module
```

  "(no note)" means the child's `except BrokenPipeError` never ran: the `OSError` left the program with a traceback.
  (The probe's `fd1-null` test is not meaningful on Windows, where `st_ino` of the null device and of a pipe can both
  be 0.) The ubuntu runner's results equal this machine's except the stderr-closed exit code noted above.
- Windows, CI run 2 (`windows_pipe_probe.py`, the child catches what the write raises and prints it):

```
pipe-error-closed-print windows : 3 lines, reader closed before start: NOTE OSError errno=22 winerror=None is-BrokenPipeError=False
pipe-error-reader-exits-print windows : 200000 lines, reader reads one line and exits: NOTE OSError errno=22 winerror=None is-BrokenPipeError=False
pipe-error-closed-rich windows (rich 13.9.4) : NOTE OSError errno=22 winerror=None is-BrokenPipeError=False
pipe-error-reader-exits-rich windows (rich 13.9.4) : NOTE OSError errno=22 winerror=None is-BrokenPipeError=False
```

  On Linux the same script gives `BrokenPipeError errno=32` for print and, for Rich, `on_broken_pipe called` first.
  `winerror` is None because the write goes through the C runtime's `write`, which reports only `EINVAL`; the Windows
  error code (232, `ERROR_NO_DATA`, expected) is not exposed.

### 3. pyte

See the Live run above: pyte 0.8.2 (the newest release) decodes UTF-8, cursor
moves, erase sequences and SGR colours as Rich writes them for `xterm-256color`. Bold green comes back as
`brightgreen`, which a check on colour names must allow for. Not tried: resizing the pty while the layout is up,
256-colour and true-colour styles beyond the three used.

### 4. coverage and real processes

`coverage-project/`: a package `mypkg` whose `__main__` has one function per way of ending; the tests start it as a
child with `python -m mypkg <mode>`; `pyproject.toml` has `branch = true`, `parallel = true`,
`patch = ["subprocess"]`, `source = ["mypkg"]`.

```
uv run --no-project -p 3.13 --with pytest==9.2.0 --with pytest-cov==7.1.0 --with coverage==7.17.3 \
    pytest -q -p no:cacheprovider --cov --cov-report=term-missing
src/mypkg/__main__.py      34      5      2      1    83%   26, 30-31, 35-36, 50->exit
7 passed
```

Lines 30 and 31 are the child killed by an unhandled SIGTERM, 35 and 36 the child that calls `os._exit(3)`: lost, as
expected. Line 26 is the `time.sleep` during which the handled signal landed (line 15, the same in the SIGINT case,
was missed with 7.10.6 and 7.10.7 and counted with 7.17.3); every other line of the 130, 143 and pty children is
counted. Without `patch` the report has no `mypkg` lines at all. With coverage 7.10.0 or 7.9.2 the run cannot be
resolved: pytest-cov 7.1.0 requires `coverage[toml]>=7.10.6`. The fake (`tests/fakes/java.py`, outside `source`),
started directly and from the child, with and without `mypkg` importable: its stderr was empty every time. The two
coverage warnings in the run ("Module mypkg was never imported", "No data was collected") came from the pytest process
itself, which never imported `mypkg`; tlaup's in-process tests import `tlaup`, so they will not appear there.

### 5. pytest-bdd

`pytest-bdd-project/`: one scenario with a doc string under a Given, `When I run "first"`, a Given, a second When, and
two Then steps; the doc string has an indented line with quotes.

```
pytest-bdd 9.0.1, pytest 9.2.0 (Python 3.11 and 3.13, -W error):  1 passed;  DOCSTRING: 'line one\n  indented "quoted"'
pytest-bdd 9.0.0 with pytest 9.2.0:  AttributeError: 'FixtureManager' object has no attribute '_arg2fixturedefs'
pytest-bdd 9.0.0 with pytest 9.0.2 and 9.1.0:  1 passed
pytest-bdd 7.3.0 / 8.0.0 / 8.1.0 with pytest 9.2.0:  the same AttributeError
pytest-bdd 7.3.0 / 8.1.0 with pytest <9:  1 passed (7.3.0 hands the doc string over as part of the step text)
```

### 6. responses and pytest-socket

`responses-project/tests/test_resp.py`, run with `--disable-socket -W error`:

```
HEADER Content-Length: 10
STREAM RAISED: requests.exceptions.ChunkedEncodingError | ('Connection broken: IncompleteRead(3 bytes read, 7 more expected)', ...) | got b''
CONTENT RAISED: requests.exceptions.ChunkedEncodingError | ('Connection broken: IncompleteRead(3 bytes read, 7 more expected)', ...)
RAW READ: no error, len 3
MOCKED OK under --disable-socket
UNREGISTERED: ConnectionError Connection refused by Responses - the call doesn't match any registered mock.
REAL BLOCKED: builtins.UserWarning | A test tried to use socket.getaddrinfo.        (pytest-socket 0.8.1, -W error)
REAL BLOCKED: pytest_socket.SocketBlockedError | A test tried to use socket.getaddrinfo.   (0.8.1 without -W error)
REAL BLOCKED: pytest_socket.SocketBlockedError | A test tried to use socket.socket.        (0.6.0, 0.7.0)
```

The same for responses 0.23.3, 0.24.1, 0.25.0, 0.25.8 and 0.26.3 (requests 2.34.2, urllib3 2.8.0). A body given as a
`requests.exceptions.ConnectionError` instance raises it, which is what `GitHub is unreachable` needs.

### 7. Pydantic

`pydantic_probe.py` builds the F1/F3 settings model and checks ten features (defaults for every section, strings from
the environment coerced, error list with `loc`/`msg`/`type`/`input`, host lower-casing, unknown keys found through
`model_fields`, the project-file mark, one key validated alone, JSON dump, frozen models, unknown keys ignored):

```
Python 3.11.15: pydantic 2.0, 2.1.1, 2.3.0, 2.4.2, 2.5.3, 2.6.4, 2.7.4, 2.8.2, 2.9.2, 2.10.6, 2.11.10, 2.12.5, 2.14.3: ALL PASS
Python 3.13.5 (wheels only): 2.6.4, 2.7.4: no wheel; 2.8.2 .. 2.12.5: ALL PASS
Python 3.14.3 (wheels only): 2.6.4 .. 2.11.10: no wheel; 2.12.0, 2.12.5: ALL PASS
<repo> unit tests (207) with pydantic 2.8.0 and 2.8.2 on Python 3.13: all pass
```

Without `--no-build`, pydantic 2.5.3 on Python 3.13 tries to build pydantic-core 2.14.6 from source and fails
(`ForwardRef._evaluate() missing 1 required keyword-only argument`). The error `loc` of a union field holds the
member's tag (`tlc.workers.constrained-int`, `tlc.workers.literal['auto']`) in every version, so the message builder of
F1 must name the key from the field part of `loc`, not the whole tuple.

## Implications for the roadmap

**Lower bounds proposed for `pyproject.toml`:**

| Dependency | Proposed | Reason |
| --- | --- | --- |
| `filelock` | `>=4.2.1,<5` | First version with every R6 behaviour on Linux and macOS (CI run 1); on Windows every version tried behaves the same way for R6, so the bound is set by Unix. 3.20.4 to 3.29.4 must not be allowed even though they have the second look (the release-time unlink breaks mutual exclusion); 3.29.5 to 4.2.0 break the one-hour rule. Revisit if the macOS or Windows run disagrees. |
| `rich` | `>=13.8.0`, cap removed (`<16` if a cap is wanted) | `on_broken_pipe` exists from 13.8.0 and is unchanged to 15.0.0; the pipe cases and the Live/pyte cases pass on 13.8.0, 13.9.4, 14.0.0, 14.3.4 and 15.0.0 on Linux. |
| `pydantic` | `>=2.5.3,<3` | The model works from 2.0; 2.5.3 is Typer 0.29.1's own floor, so lower is never installable. On 3.13 and 3.14 the resolver can only pick 2.8 and 2.12 or later anyway. If a lowest-versions CI job runs on 3.13 or newer, it needs `>=2.8` there (or a marker), since 2.5.3 does not build. |
| `coverage` (dev) | `>=7.10.6` | `patch = ["subprocess"]` works from 7.10; pytest-cov 7.1.0 needs 7.10.6. |
| `pytest-bdd` (dev) | `>=9.0.1,<10` | The only version that runs on pytest 9.2; it reaches into pytest's private `FixtureManager`, so the newest-dependencies job (30 I3) is what catches the next break. |
| `responses` (dev) | `>=0.23.3,<1` | Everything relied on holds from 0.23.3 (oldest tried). |
| `pytest-socket` (dev) | `>=0.8.1,<1` | Newest; 0.6 and 0.7 behave the same for the design. |
| `pyte` (dev) | `>=0.8.2,<1` | The only version tried. |

**For R6 and the specs:**

- The second look is the behaviour of 3.20.4 and later, but the version bound must also exclude the release-time
  unlink of 3.20.4 to 3.29.4: a library that unlinks the name when it releases removes the lock file of whoever took
  the lock after tlaup removed its own. That is a third behaviour the `RunFolders` spec does not model (it has
  `Recheck` only). Either add it as a variant that the bound rules out, or state in specs/README that the library is
  assumed not to touch the name on release; the unit test under R6 Tests should get the `foreign_file` case beside
  the second-look case, so a version with the unlink fails it.
- R6's "the modification time, which creating the file sets and taking or releasing the lock does not change (tried)"
  holds from 4.2.1 only; with older versions a sweep that takes a folderless lock file's lock refreshes its age, so the
  file is never an hour old and is never removed (a leak, not a safety problem). The 59/61-minute unit test catches
  it.
- R6's "a second lock object on the same file in one process is refused like any other" holds for every version
  tried, but only with a finite wait: since at least 3.29.6 (the changelog names 3.24.0 and 3.29.7) a second object in the **same thread** waiting with no
  timeout raises `RuntimeError("Deadlock ...")`. The step functions and the stateful test must always pass a finite
  `wait` (R6 already does: five seconds or one attempt), and `take_lock` should not map that `RuntimeError` to
  "busy".
- Lock objects are thread-local by default: a step function must take and release a lock in one thread, and the
  stateful test must not hand lock objects between threads.
- macOS behaves as Linux in every check (CI run 1), so R6 and the specs need nothing macOS-specific.
- On Windows (CI run 1) a held lock file cannot be unlinked (`PermissionError`) and the library deletes it on release,
  in every version tried. So R6's end step there is: the removal under the lock fails (R6 already ignores deletion
  errors), then the library removes the file as it releases. Consequences for R6: the "lock files left behind" and
  "a folderless lock file is removed after an hour" rules have almost nothing to do on Windows (a sweep's own take
  leaves no file either); the K1-1 instant between removal and release does not exist; and the second look is never
  needed. A release-time removal on Windows cannot remove another holder's file, because that holder keeps it open
  without delete sharing. The R6 unit test of the second look is meaningful on Linux and macOS only; on Windows it
  should assert that the removal under the lock fails and the property still holds, or be skipped with that reason.
  The `RunFolders` spec models the Unix behaviour; Windows is a stricter case of it (an unlink that is refused while
  any process holds the file), which the formal check did not model and which needs no change to the protocol.

**For F10, O4 and the tests:**

- F10's three-part closed-pipe handling rests on behaviour stable from Rich 13.8.0 to 15.0.0 on Linux and macOS; the
  cap can go. Add to F10's facts that a stderr console's closed pipe also silences descriptor 1, never 2, so the
  guarded final flush (and `reader_gone(2)`) is what turns such a run's 1 or 120 into 141.
- `reader_gone`: register the descriptor for `POLLOUT` (macOS reports nothing for an empty mask) and treat `POLLERR`
  or `POLLHUP` as "gone", `POLLNVAL` as "not a pipe we can judge" (false). Linux reports `POLLERR`, macOS `POLLHUP`.
- **Windows breaks F10's closed-pipe design** (CI run 1). A write to a pipe whose reader has gone raises
  `OSError(EINVAL)`, not `BrokenPipeError`, so: Rich never calls `on_broken_pipe` and tlaup's subclass is bypassed;
  Typer's help leaves with an `OSError`; `mapped`'s `OSError` branch, whose error numbers do not include `EINVAL`,
  would report an internal error (5), and `main()`'s `except OSError` gives 5; `reader_gone` is always false. The
  design has to decide what a closed pipe on Windows is: either accept 5 there and say so in X1 (the 141 code is a
  POSIX convention), or treat an `OSError` with `EINVAL` on a stream that is a pipe (`GetFileType` is
  `FILE_TYPE_PIPE`) as a closed pipe and give 141 or 1. CI run 2 settles the facts for that choice: the error is the
  same whether the reader left before or during the output, and `winerror` is None, so the test can only be "`OSError`
  with `errno == EINVAL`, no file name, and the stream's descriptor is a pipe" (`stat.S_ISFIFO(os.fstat(fd).st_mode)`,
  or `GetFileType` through `ctypes`). `EINVAL` from a write to a pipe has no other common cause, so the test is narrow
  enough. Rich's own console (Typer's help) raises that `OSError` out of `print` too, so `main()`'s `except OSError`
  needs the same test. The closed-pipe scenarios of X1 then need a Windows expectation or a skip with the reason.
- O4's pyte steps work as written on Linux and macOS; the fallback is not needed. Windows has no pty, as T5 says. A colour check must accept `brightgreen` for
  bold green.
- T10 works as written. Add `sigterm = true` under `[tool.coverage.run]` only if a test ever lets a child die of an
  unhandled SIGTERM; tlaup's own SIGTERM path exits 143 through Python and is counted.
- T5: doc strings use the `docstring` argument; the "`<command>` was run" fallback for two runs is not needed.
- T4/T6: the short-body row raises `requests.exceptions.ChunkedEncodingError` (from `iter_content` and `.content`);
  the downloader must map it to `DownloadVerificationError`. Code that reads `response.raw` directly sees no error and
  must compare the byte count itself. Under `filterwarnings = error`, an unrecorded request fails with pytest-socket's
  `UserWarning` raised as an exception, which a blind `except Exception` in tlaup would catch; the one allowed blind
  except (F10) reports it as an internal error, so the test still fails, with a less obvious message.

## Open follow-ups

- CI runs 1 and 2 answered every macOS and Windows part of this question; no further CI run is needed for it. The
  scripts are in `<tmp>/ci/q30/` (copies under `ci/` in the fixtures folder) and run from the `ci` folder.
- Open for the design, not for research: what exit code a closed pipe gives on Windows (see Implications, F10).
- `stat.S_ISFIFO` on a Windows pipe descriptor was not checked (Python's `fstat` reports pipes as `S_IFIFO` on
  Windows by its documentation); the work package that builds the Windows branch tests it there.
- Resizing a pty while the layout is up (O4) was not tried.
- Whether `filelock` 4.2.1's `fallback_to_soft` (a soft lock where the file system has no `flock`, 12 V11's network
  file system risk) changes any R6 behaviour was not tried.

## Date checked

2026-11-18 (all Linux runs on this machine) and 2026-11-19 UTC (CI runs 1 and 2); package versions as on PyPI that day, newest: filelock 4.2.12, Rich 15.0.0, pyte 0.8.2,
pytest-bdd 9.0.1, responses 0.26.3, pytest-socket 0.8.1; pydantic as locked, 2.14.3).
