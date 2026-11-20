# 33: Can a run's lock outlive a killed tlaup by letting the JVM inherit it?

## Question

Investigation list item 33 ([roadmap](../roadmap.md)), for option 3 of the Risks of
[11 R6](../design/11-runner.md#r6-run-folders): can the lock of a run folder be made to outlive a tlaup killed with
SIGKILL, by passing the lock's open file to the JVM? In detail: does the locked `filelock` (4.2.10) give a supported
way to reach the descriptor of a held lock, or must tlaup open and lock the file itself; does a child started with that
descriptor keep the lock after its parent is killed, so that a second attempt (by `filelock` and by a raw lock) is
refused until the child ends; do `flock` and `fcntl`/`lockf` locks differ here; do the JVM and TLC leave an inherited
descriptor alone (both jars, Java 25 and Java 11); what does `filelock`'s own release in the parent do to the child's
lock; how does this meet R6's rule that the holder removes the lock file before releasing it; and what happens on
macOS and Windows.

## Source

- `filelock` 4.2.10, installed with `uv` into a scratch environment; the installed `_unix.py`, `_descriptor.py`,
  `_api.py` and `_windows.py` are byte-identical to the tag's source (checked with `diff` against
  `gh api repos/tox-dev/filelock/contents/...?ref=<sha>`). Tag `4.2.10` is commit
  `f9e562169e2580019e3fd96e66d8e0accf57fe4a`. Pinned links:
  - `_lock_fd_nonblocking`, the `fcntl.flock(fd, LOCK_EX | LOCK_NB)` both the path lock and `lock_descriptor` use:
    [_unix.py#L48](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_unix.py#L48)
  - the re-check (`st_nlink == 0` after the flock, then try again):
    [_unix.py#L171](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_unix.py#L171)
  - `_release`, `flock(fd, LOCK_UN)` then close:
    [_unix.py#L210-L218](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_unix.py#L210-L218)
  - public `lock_descriptor` / `unlock_descriptor` (since 3.30.0), a lock on a descriptor the caller opened and owns:
    [_descriptor.py#L20](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_descriptor.py#L20)
  - public `on_acquired` hook (since 3.30.0), "invoked with the borrowed lock descriptor", which "must not close,
    unlock, or take ownership of it":
    [_api.py#L813](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_api.py#L813)
  - `__del__` force-releases a lock still held:
    [_api.py#L1438](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_api.py#L1438)
  - the `os.register_at_fork` hooks; in a forked child the descriptors filelock owns are closed:
    [_api.py#L2024](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_api.py#L2024),
    [_api.py#L2208](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_api.py#L2208)
  - Windows: `LockFileEx` on one byte at offset 0, on a handle opened `O_NOINHERIT`:
    [_windows.py#L249](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_windows.py#L249),
    [_windows.py#L464](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/src/filelock/_windows.py#L464)
  - the docs, "Native locks are advisory" and "Ownership scope per lock": a `fork` or `dup` shares the one lock;
    "unlocking, or the last shared descriptor closing or exiting, releases it for both":
    [concepts.rst#L560-L586](https://github.com/tox-dev/filelock/blob/f9e562169e2580019e3fd96e66d8e0accf57fe4a/docs/concepts.rst#L560-L586)
- Jars: v1.7.4 (`5a47802`) and 1.8.0 (rolling, `bc1b506`, CalVer 2026.11.15.002146).
- Java: OpenJDK 25.0.5, OpenJDK 21.0.13, Temurin 11.0.33+10. Python 3.14.3. Linux x86-64, 12 cores, with other
  agents' TLC runs on the machine at the same time (no timing below matters).
- Experiments: `tests/fixtures/research/33-inherited-lock/`:
  - `inherit_lock_posix.py`, the Linux and macOS check (also the CI script);
  - `inherit_lock_windows.py`, the Windows check (CI only, not run here);
  - `unlink_check.py`, the lock file removed by its holder while the child holds the lock;
  - `linux-run1.txt`, the full matrix on the three Javas; `linux-tlc-rerun.txt`, the real-TLC checks again after a
    fix in the script (below);
  - `ci-ubuntu-latest.txt`, `ci-macos-latest.txt`, `ci-windows-latest.txt`, the logs of the CI run.
- CI run: <https://github.com/nikolskiy/tlaup/actions/runs/44489200898> (branch `research/top-up-experiments`, commit
  `0d43a75`, 2026-11-19 08:37 to 08:48 UTC). Runner images: ubuntu-latest = ubuntu26 20261111.82.6 x86_64,
  macos-latest = macos26 20261112.0504.1 arm64, windows-latest = win25-vs2026 20261103.298.1 x86_64. Python 3.13.17
  and 3.13.18, uv 0.13.9, `filelock` 4.2.10. The `java` on PATH was Temurin 21: the scripts printed `21.0.13` on
  ubuntu and Windows and `21.0.13.1` on macOS (the run notes give 21.0.13.1+2 for Windows; the log is quoted here).
  Java 11 was installed on the runners but not used by these scripts.

## Short answer

- **On Linux and macOS, yes; on Windows, not with `filelock`** (the last two bullets). A `flock` lock belongs to the open file description, not to the process. A child started with the
  descriptor in `pass_fds` holds the same lock; after the parent is killed with SIGKILL a third process is refused, by
  `filelock` (timeout 0) and by a raw `flock`, until the child ends, and granted at once after. Shown with a Python
  child, a small Java program, and a real TLC run on v1.7.4 and 1.8.0 under Java 25, 21 and 11. The JVM and TLC leave
  the inherited descriptor alone: `/proc/<java>/fd` shows it open for the whole run and `/proc/<java>/fdinfo` shows
  `FLOCK ADVISORY WRITE` on it; TLC ran to its normal end and the lock was free then.
- **A POSIX record lock (`fcntl.lockf`) is not kept**: it belongs to the process, the child has the descriptor and no
  lock, and the lock is free the moment the parent dies. Only `flock` works, and `flock` is what `filelock` uses.
- **`filelock` gives the descriptor through public API, two ways**: the `on_acquired` hook hands over "the borrowed
  lock descriptor" of a `FileLock`, and `lock_descriptor(fd)` locks a descriptor tlaup opened itself. Passing the
  borrowed descriptor to a child is not what the hook's docs promise (it "must not close, unlock, or take ownership"),
  although the docs on ownership describe exactly the sharing it relies on. `lock._context.lock_file_fd` also works and
  is private.
- **A normal release in the parent ends the child's lock too.** `FileLock.release()` calls `flock(LOCK_UN)`, which
  unlocks the shared open file description: the third process was granted the lock while the child still ran. The same
  happens on a normal interpreter exit while the `FileLock` is still held, because `__del__` releases it. Only closing
  the parent's descriptor without unlocking (possible with an `os.open` plus `lock_descriptor` or `flock` lock, not
  through `FileLock`) leaves the child holding it.
- **R6's removal rule must not run while the JVM may live.** If the holder removes the lock file and then dies, the
  child still holds a lock on the nameless file, and the next `FileLock` creates a new file at the name and gets it.
  R6 already removes the file only after TLC has exited, so this holds as designed; it becomes a rule the code must keep.
- **`preexec_fn` breaks it with `FileLock`.** With `preexec_fn`, Python runs its at-fork child hooks, `filelock`'s
  hook closes the descriptors it owns, and `Popen` fails with `EBADF` for the descriptor in `pass_fds`. A raw `flock`
  descriptor, or an `os.dup` of filelock's, survives `preexec_fn`. This matters if question 35 uses `preexec_fn` for
  `PR_SET_PDEATHSIG`.
- **macOS: the same as Linux** (CI, arm64, Java 21). All 18 checks gave the Linux outcome: kept after SIGKILL with
  `filelock` and with raw `flock`, for a Python child, a Java program and real TLC on both jars; not kept with `lockf`;
  lost on `release()` and on a normal exit holding a `FileLock`; `preexec_fn` fails with `EBADF` with `FileLock`.
- **Windows: not with `filelock`.** `filelock` 4.2.10 locks one byte with `LockFileEx` (not `msvcrt.locking`), on a
  handle it opens non-inheritable. Made inheritable and passed to the child, the handle does not keep the lock: the
  moment the holder is ended (`TerminateProcess`), a third process gets the lock, by `filelock` and by
  `msvcrt.locking`, while the child (Python, Java, TLC on both jars) still runs. The same for a raw `msvcrt.locking`
  lock and for `lock_descriptor`. Byte-range locks on Windows belong to the process that took them.
  **A share-mode handle does follow the child**: a handle opened with `GENERIC_READ` and only `FILE_SHARE_READ`,
  inherited by the child, makes every open for writing fail with a sharing violation for as long as the child lives,
  also when the holder closed its own copy before it was killed. `filelock` treats that sharing violation as
  contention, so a `FileLock` of another tlaup is refused, and granted once the child has ended. So option 3 on
  Windows would need a lock of tlaup's own making, not `filelock`'s.

## Confidence

Verified on Linux (kernel 6.12, ext4 on the real disk) with `filelock` 4.2.10, both jars, Java 25, 21 and 11, and
on GitHub's ubuntu, macOS (arm64) and Windows runners with Java 21, one run each. On Windows the share-mode result has
one inconclusive line (below); the `filelock` result there is clear. Java 11 was not run on macOS or Windows. Not
tried: how a share-mode lock and a `FileLock` taken by the same tlaup meet (see Implications), network file systems (NFS emulates `flock` with
POSIX locks on Linux, which would make the inherited lock per process again), Docker bind mounts, a TLC started by
`tlaup repl`, a user's `-javaagent`.

## Evidence

### The script

`inherit_lock_posix.py` has three roles. A *holder* stands for tlaup: it takes the lock one of seven ways, starts a
child with `subprocess.Popen(child, pass_fds=(fd,), stdin=DEVNULL, stdout=<file>)` (`close_fds` stays at its default,
`True`), and then either waits to be killed or does one of: release, close its descriptor, exit normally. The
*driver* kills the holder with SIGKILL where that is the case, checks that the child still lives, runs two *try*
processes (a `FileLock(path, timeout=0)` and a raw `flock(LOCK_EX | LOCK_NB)` on a fresh `open`, plus a raw `lockf`
for the `lockf` holder), lists `/proc/<child>/fd` and `fdinfo`, waits for the child to end by itself, and tries again.

Children: `python -c "time.sleep(6)"`; `java Sleep.java 10` (the single-file source launcher, a `Thread.sleep`);
TLC on a two-variable counter, `N = 1500` (2,253,001 distinct states, 8 to 11 s with one worker here):
`java -XX:+UseParallelGC -cp <jar> tlc2.TLC -workers 1 -deadlock -metadir <work>/meta -config Long.cfg Long.tla`.

Run: `uv run --no-project --with filelock==4.2.10 python q33/inherit_lock_posix.py` from `<tmp>/ci`, with
`Q33_JAVA` set to each Java and `TLA2TOOLS_174`, `TLA2TOOLS_ROLLING` set. Each line is abridged here; the full output
is in `linux-run1.txt`.

### Results, Linux, 2026-11-18

Identical on Java 25.0.5, 21.0.13 and 11.0.33 except one line explained below.

| Check | Holder | Then | While the child lives | After it ended |
| --- | --- | --- | --- | --- |
| `py-fl-hook-kill` | `FileLock` + `on_acquired` | SIGKILL | filelock refused, flock refused; fd 4, `FLOCK ADVISORY WRITE` | both granted |
| `py-fl-private-kill` | `FileLock`, `_context.lock_file_fd` | SIGKILL | refused, refused | granted |
| `py-fl-descriptor-kill` | `os.open` + `lock_descriptor` | SIGKILL | refused, refused | granted |
| `py-flock-kill` | `os.open` + `flock` | SIGKILL | refused, refused | granted |
| `py-lockf-kill` | `os.open` + `lockf` | SIGKILL | **granted** (filelock, flock and lockf); fd 4 open, no lock listed | granted |
| `py-fl-noinherit-kill` | `FileLock`, no `pass_fds` | SIGKILL | granted; the child has no such fd | granted |
| `py-fl-preexec-kill` | `FileLock` + `on_acquired`, `preexec_fn` | | `Popen` fails: `OSError: [Errno 9] Bad file descriptor` | |
| `py-fl-dup-preexec-kill` | as above, child gets `os.dup(fd)` | SIGKILL | refused, refused; fd 5 | granted |
| `py-flock-preexec-kill` | `flock`, `preexec_fn` | SIGKILL | refused, refused | granted |
| `py-fl-hook-release` | `FileLock` | `lock.release()`, holder lives | **granted**; fd 4 open, no lock listed | granted |
| `py-flock-release` | `flock` | `flock(LOCK_UN)` | **granted** | granted |
| `py-flock-close` | `flock` | `os.close(fd)`, no unlock | refused, refused | granted |
| `py-fl-hook-exit` | `FileLock`, kept in a global | normal exit, code 0 | **granted**; no lock listed | granted |
| `py-flock-exit` | `flock` | normal exit, code 0 | refused, refused | granted |
| `java-sleep-fl-hook-kill` | `FileLock` + `on_acquired` | SIGKILL | refused, refused; fd 4 in the JVM, `FLOCK ADVISORY WRITE` | granted |
| `java-sleep-flock-kill` | `flock` | SIGKILL | refused, refused | granted |
| `tlc174-fl-hook-kill` | `FileLock` + `on_acquired` | SIGKILL | refused, refused; fd 4 in the JVM, `FLOCK ADVISORY WRITE` | granted; log ends `Finished in 08s` |
| `tlcrolling-fl-hook-kill` | `FileLock` + `on_acquired` | SIGKILL | refused, refused; same | granted; `Finished in 09s` |

`inheritable-in-holder=False` on every line: `filelock` opens its descriptor non-inheritable (Python's default since
PEP 446), so without `pass_fds` the JVM never sees it (`py-fl-noinherit-kill`).

One line differed: `tlcrolling-fl-hook-kill` on Java 11 in the first run gave "after it ended: filelock refused,
flock granted". That was the script, not the lock: the driver judged the JVM gone when `/proc/<pid>/stat` showed the
thread-group leader as a zombie, while the JVM's other threads were still exiting and still held the descriptor table.
The script now also counts `Threads:` in `/proc/<pid>/status` and waits one second after the end; the real-TLC checks
were then run twice more on Java 11 and twice on Java 25, eight of eight as in the table (`linux-tlc-rerun.txt`).

### Removing the lock file while the child holds the lock

`unlink_check.py`: the holder takes `FileLock` with the hook, starts a child with the descriptor, and either keeps the
file or removes it (still holding the lock); it is then killed with SIGKILL, and a third `FileLock(timeout=0)` tries.

```
keep: child 1504599 holds inode 8298317; path exists=True; third FileLock: refused
unlink: child 1505969 holds inode 8298074; path exists=False; third FileLock: granted (new inode 8298784, nlink 1)
```

The re-check of `filelock` does not change this: it protects a waiter from holding a lock on a file that is no longer at
the name, not a holder whose name was removed. A waiter that opened the old file before the removal is refused by the
child's lock and, once it tries again, opens the new file.

### Reading of the source

- `UnixFileLock._acquire` opens the path (`O_RDWR | O_NONBLOCK | O_NOFOLLOW`, `O_CREAT | O_EXCL` first), takes
  `flock(LOCK_EX | LOCK_NB)`, then checks `st_nlink`; the descriptor goes into `self._context.lock_file_fd`.
  `_release` is `flock(LOCK_UN)` and then `close`. There is no way through `FileLock` to give up the descriptor without
  the unlock.
- `on_acquired(fd)` runs once per physical acquisition with the lock held; the docs call the descriptor borrowed. A
  child holding a copy of it after `release()` holds no lock (the unlock is on the open file description), so nothing
  breaks for `filelock` itself; the risk is only that the hook's contract does not mention this use and a later version
  could, for example, start opening the lock with a per-process lock (`F_OFD_SETLK` would still be per description;
  `F_SETLK` would not).
- `lock_descriptor(fd, blocking=False)` is one `flock` attempt on a caller-owned descriptor, with no path handling, no
  re-check and no timeout; the caller owns `close`. It contends with `FileLock` on the same file (tried one way: a
  `FileLock` was refused while a `lock_descriptor` lock was held, `py-fl-descriptor-kill`).
- At-fork: `filelock` registers its owned descriptors and closes them in a forked child when the child runs Python's
  at-fork hooks, which `subprocess` does only when `preexec_fn` is given. Without `preexec_fn`, `_posixsubprocess`
  forks and `exec`s in C and the hooks do not run; the descriptor in `pass_fds` arrives.

### CI run, 2026-11-19 (ubuntu, macOS, Windows)

`inherit_lock_posix.py` ran on ubuntu-latest and macos-latest, `inherit_lock_windows.py` on windows-latest, each with
`uv run --no-project --with filelock==4.2.10`. On macOS the script uses `lsof` in place of `/proc` and can only say
whether the child has the lock file open, not which lock is on it.

ubuntu-latest: all 18 lines as on the Linux machine here (`ci-ubuntu-latest.txt`). macOS: all 18 lines with the same
outcome (`ci-macos-latest.txt`), the child's lock file shown `open` in every case where it was passed and `not open`
in the control. The real TLC runs were short on the runners (1 to 3 s), but each check was made while the child lived
and the end was seen.

Windows (`ci-windows-latest.txt`). The holder takes the lock, makes its handle inheritable and passes it in
`STARTUPINFO.lpAttributeList["handle_list"]`; the driver tries the lock once while the holder lives ("holder alive"),
ends the holder with `TerminateProcess`, and tries again while the child lives and after it ended. The raw attempt is
`os.open` for read/write and then `msvcrt.locking` of byte 0.

| Check | Holder alive | While the child lives | After it ended |
| --- | --- | --- | --- |
| `py-fl-hook-kill` (`FileLock`, handle inherited) | filelock refused, raw refused (lock, errno 13) | **granted**, granted | granted |
| `py-fl-descriptor-kill` (`lock_descriptor`) | refused, refused | **granted**, granted | granted |
| `py-msvcrt-kill` (`msvcrt.locking`) | refused, refused | **granted**, granted | granted |
| `py-fl-noinherit-kill` (control) | refused, refused | granted, granted | granted |
| `py-share-deny-kill` (share-mode handle) | refused, refused (open) | refused, refused (open) | granted |
| `py-share-deny-own-kill` (holder closed its copy) | refused, refused (open) | refused, refused (open) | granted |
| `java-sleep-fl-hook-kill` | refused, refused | **granted**, granted | granted |
| `java-sleep-share-deny-kill` | refused, refused | refused, refused | granted |
| `tlc174-fl-hook-kill` | refused, refused | **granted**, granted | granted; `Finished in 02s` |
| `tlc174-share-deny-kill` | refused, refused | refused, refused | granted; `Finished in 03s` |
| `tlcrolling-fl-hook-kill` | refused, refused | **granted**, granted | granted; `Finished in 02s` |
| `tlcrolling-share-deny-kill` | refused, refused | filelock refused, **raw granted** | granted; `Finished in 02s` |

The last line is "mixed": `filelock` was refused and the raw attempt, made just after it, was granted. TLC finished in
2 s, and on the runner the driver's checks start about 3 to 4 s after the child (1.5 s of waiting, one round of
attempts while the holder lives, the kill, 1 s, then the attempts, each a new Python process). The likeliest reading
is that TLC ended between the two attempts. The same check on v1.7.4 and with a Java child that sleeps 12 s gave the
clean result, and the share mode is the operating system's, not the jar's; but this line on its own does not prove it.

## Implications for the roadmap

These are for the maintainer's choice among R6's four options; nothing here changes a decision.

**Option 3 is a fall-back.** Question 35 found ways to make the JVM end with tlaup on all three systems
([35](35-jvm-ends-with-tlaup.md)), which is option 4, the one the maintainer prefers. If option 4 is taken, nothing
below is needed. It is recorded for the case that option 4 turns out not to fit (for example with the user's own Java
options), and because points 3 and 5 below also touch option 4: `preexec_fn` closes `filelock`'s descriptor.

**What option 3 would need (POSIX: Linux and macOS, the same here).**

1. The descriptor. Either the `on_acquired` hook of `FileLock` (public, but a use its docs do not cover), or tlaup's
   own `os.open` plus `filelock.lock_descriptor` (public and meant for this), with the five-second wait and the
   `st_nlink` re-check that R6 relies on (Risks, question 30) written by tlaup, since `lock_descriptor` has neither.
   The second keeps the re-check in tlaup's tests rather than in a dependency's internals, and it is the only one that
   allows point 3.
2. Both locks passed on: the run's own lock and, after `-recover` into a managed folder, the recovered folder's lock
   (`pass_fds=(own, recovered)`), so that K1-3 is closed as well as the deletion.
3. Never unlock while the JVM may live. A `FileLock` release, explicit or from `__del__` at a normal exit, unlocks the
   JVM's copy. R6's End runs after TLC has exited, so the ordinary path is fine; but every way out of `run_tlc` that
   does not wait for the child (a second signal, an error while draining, a G3 time-out, if there is one) must close the
   descriptor without unlocking, and then also not remove the lock file. With `FileLock` that cannot be done through
   its public API; with `lock_descriptor` it is `os.close`.
4. The removal rule keeps its place: the lock file is removed only by a holder that knows the JVM has exited.
5. No `preexec_fn` on the JVM's `Popen` while a `FileLock` is held, or pass an `os.dup` of its descriptor. This
   touches question 35 if it uses `PR_SET_PDEATHSIG` from `preexec_fn`.
6. The R6 sentence "a lock is released by the operating system when the process dies" becomes "when tlaup and the
   JVM it started have both ended". `tlaup cache` will list a held lock for a folder whose tlaup is gone; `run.json`
   would then be more useful with the JVM's pid next to tlaup's, so the user can stop that TLC.
7. Windows needs a second design. The `filelock` lock does not follow the handle (CI). What does follow it is a
   share-mode handle (opened for reading, sharing only reading) passed to the JVM. Other tlaups' `FileLock` attempts
   see its sharing violation as contention and wait or give up, so sweeps, `cache clean` and `-recover` would be
   refused while the JVM lives. But tlaup cannot hold that handle and its own `FileLock` on the same file. Each one
   conflicts with the other: an open that refuses to share writing fails while a handle with write access is open, and
   the reverse. Windows tlaup would therefore lock the run with the share-mode handle alone, which is a second lock
   protocol on the same file. It needs its own reasoning about the removal rule: `filelock` on Windows deletes its lock
   file on release, and no one can delete a file while a handle that does not share deletion is open. It would also
   need its own spec variant. The alternative is option 1 on Windows only. The first part, the conflict between the two
   handles, is from Windows' share-mode rules and was not run.

What it would not cover: a file system without real `flock` (NFS on Linux), where the lock is per process again.

**A second CI run is not needed for the answer.** It would be needed only if option 3 is chosen, and then for three
things:
- the Windows share-mode check on rolling with a longer TLC run (`Q33_TLC_N=4000`, about seven times the states), to
  replace the one inconclusive line;
- the two scripts with Java 11 (`Q33_JAVA` set to the Java 11 `java`) on macOS and Windows, since this run used Java 21
  only;
- on Windows, a check that a share-mode handle and a `FileLock` on the same file refuse each other in both orders, in
  one process and across two. That is the design question of point 7, and the current script does not have that check.

**What it would change in `specs/RunFolders.tla`.** Today `Kill(p)` closes every handle of `p` and frees every lock it
holds, and turns a live TLC into `"orphan"`; `OrphanExit(r)` only sets `"done"`. Under option 3:

- `Kill(p)` would close and free only the handles of `p` that its TLC does not share: a sweep's or a clean's visit
  handle, and the run's handles while no TLC was started (before `StartTLC`, or after `TLCExit`). The run's own handle
  and its recover handle, while `tlc[cur[p]] = "live"`, would pass to the orphan (a holder value for "the TLC of run
  `r`") and stay held.
- `OrphanExit(r)` would then release those handles, the way the operating system does when the JVM ends.
- The invariant that a held lock is on the file at the name (`HeldIsCurrent`) would have to hold for the orphan too;
  it should, because End is the only step that removes a lock file and it comes after `TLCExit`.
- Expected effect: `NoDeleteUnderOrphanTLC` and `OneTLCPerFolderAfterKill` hold, so the configs `orphan-delete` and
  `orphan-recover` move from "fails" to "holds", and the "unless killed" exceptions in `NoDeleteUnderTLC` and
  `OneTLCPerFolder` can go; `LiveRunLocked` can be widened to orphan TLCs. Not checked: these are predictions, for
  the coordinator to run. The model's "an abort without TLC" and "kill" paths would also need a step for point 3 if
  the design allows tlaup to leave while its TLC runs.
- On Windows the change above models the share-mode handle only if the whole Windows protocol is that handle (point
  7). The spec's "Leaves out" already excludes Windows.

## Open follow-ups

- If option 3 is chosen: the second CI run described under Implications.
- If option 3 is taken: whether to ask `filelock` upstream to document passing the `on_acquired` descriptor to a child,
  or to use `lock_descriptor` and own the re-check.
- NFS and other file systems where `flock` is emulated; whether tlaup's cache can be on one.
- Whether a `-javaagent` or the user's Java options could close inherited descriptors (none of the runs here did).

## Date checked

2026-11-18 (local time) on Linux; CI run 2026-11-19 UTC for ubuntu, macOS and Windows.
