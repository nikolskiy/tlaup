# TLA+ specs of the design

Three small TLA+ specs of the parts of the tlaup design where several processes change shared state in steps that can interleave, checked with TLC before any of it is built (roadmap decision D46; the plan is [design 03, part 2](../docs/design/03-run-stages-and-specs.md#part-2-tla-specs-of-the-design)). They are not part of the product and nothing imports them.

Written and checked on 2026-11-18 by one agent. Not reviewed by a fresh agent yet. Each spec models a design section as it was written on that day, not as it could be designed; where a spec found the section wrong or silent, the fix is in the section, marked "formal check". The maintainer walked through the results the same day and settled two of the three points left open (decisions D49 and D50); the run-folder configs were switched to D49 and checked again (below).

| Spec | Models | Design section |
| --- | --- | --- |
| `RunFolders.tla` | Run folders under `<cache>/runs/` and their lock files: start, sweep, `cache clean`, `-recover`, a killed tlaup. | [11 R6](../docs/design/11-runner.md#r6-run-folders) |
| `ToolStore.tla` | The tools store: install, upgrade, uninstall and pin under the store lock, downloads outside it, readers with no lock, `.tmp/` cleanup. | [12 V1, V3, V4, V11, V12](../docs/design/12-tools-and-downloads.md#v1-version-store) |
| `Signals.tla` | The launcher's signal handling round one child. | [20 G3](../docs/design/20-groundwork.md#g3-java-launcher), [11 R2](../docs/design/11-runner.md#r2-signals) |

## Checking them

```bash
TLA2TOOLS=<path to tla2tools.jar> ./check.sh
```

`check.sh` runs TLC on every `.cfg` here and under `variants/`, and compares the result with the first line of the `.cfg`, which says what TLC should report: `ok`, or the property that is violated. A pattern runs a part: `./check.sh Signals`. One config by hand:

```bash
java -cp <path to tla2tools.jar> tlc2.TLC -workers auto -config variants/RunFolders-no-recheck.cfg RunFolders.tla
```

It needs Java 11 or newer and a released `tla2tools.jar`; the tlaup these specs describe does not exist yet. TLC's state files go to `states*/` beside the specs, which `.gitignore` covers.

The results below are from one run of `check.sh` on 2026-11-18: TLC 2026.05.26.235334 (rev 4ba7d88; the jar published under the tag `v1.8.0` on 2026-05-26, SHA-256 `237332bd…2a4fb`), OpenJDK 25.0.5, Linux, 12 cores, `-workers auto`, breadth-first. All 27 configs came out as their first line expects, in 24 minutes for the whole set. After decision D49 the 14 run-folder configs were checked again the same day with the same TLC, Java and machine, and all came out as expected again; the run-folder table has the numbers of that second run, with the times `check.sh` measured. One run-folder config, `checkpoint-spared`, was removed then: it was the option D49 chose, and so the same as `RunFolders.cfg`. That leaves 26 configs. The times in the tables are wall-clock on a machine that was doing other work, measured between one result and the next; for the ToolStore and Signals main configs they are TLC's own figure from an earlier run of the same files that day with six and four workers. Take them as an order of magnitude. Not checked: any other TLC build or Java version.

A spec has three kinds of config. The one named after it is the design as written, with every property that should hold. A variant with `expect: ok` is the design under another answer to an open question, or with an option the maintainer did not take. A variant with `expect: violated` shows that a property does not hold, on purpose: a finding, the reach of a risk the design accepts, or a first wording of a property that said too much. TLC stops at the first violation, so those state counts are not sizes and change a little from run to run.

## Findings

Every counterexample, and a few things found while writing the models, with what became of each. "Fixed" means the design section now says it; nothing here changed a decision or what a user sees outside a race between two tlaups.

| # | Finding | Found by | What became of it |
| --- | --- | --- | --- |
| K1-1 | Between removing a lock file and releasing its lock, a second process can already hold the lock of a new file under the same name. `LockExclusive` as 03 first worded it is false in that instant. The design is safe because nothing is done under the lock after the removal. | TLC, `RunFolders-until-release` | Fixed: R6 "End" says that removing the lock file is the last step under the lock; 03's property is reworded. |
| K1-2 | Removing a lock file while holding its lock is safe only if the lock library looks at the file again after it has the lock. Without that, a process ends up holding a lock on a file that is no longer at the name; with three processes two hold "the lock" of one name; and a run folder is deleted under a live TLC when an hour passes during a start, when a deletion fails, or when there is no one-hour rule. | TLC, the `RunFolders-no-recheck-*` and `three-no-recheck` variants | Fixed: R6 Risks states the second look as part of the protocol, and a unit test pins it. Which `filelock` versions have it is still question 30; the locked one does. |
| K1-3 | `-recover` into the folder of a tlaup that was killed, while its TLC still runs, gets the free lock and starts a second TLC on the same checkpoint. | TLC, `RunFolders-orphan-recover` | Waits on question 35, with K1-5 (R6, Risks): the maintainer prefers making TLC end with tlaup. |
| K1-4 | `cache clean` without `--all` removes a folder that was never settled and holds a checkpoint; the sweep treats the same folder as kept for 30 days. | TLC, `RunFolders-checkpoint-clean` | Fixed by the maintainer's choice (decision D49): `cache clean` uses the sweep's rule. `RunFolders.cfg` has `CleanSparesCheckpoint` on and checks `CheckpointSurvives`. |
| K1-5 | The sweep counts an unsettled folder's age from the start of the run. For a long run it removes the folder at the first sweep after the kill, not "a day later" as the accepted risk said. | Reading the rule while modelling. An earlier, larger model that kept ages as state gave the trace; the committed model lets each sweep choose the age it finds, so TLC does not show it. | The risk's sentence is corrected. Changing the rule waits on question 35, with 34 as a fall-back (R6, Risks). |
| K1-6 | `KeptSurvives` as 03 first worded it forgot that a run which resumes from a kept folder and finishes deletes it. | Writing the property | Fixed: 03's property is reworded. |
| K1-7 | Taking an entry's lock creates its lock file. A sweep that listed an entry just before its run ended leaves a new, empty lock file, which the one-hour rule removes later. | Writing the model; `NothingLeft` confirms it is removed | Fixed: R6 says so. No change of behaviour. |
| K2-1 | The design did not say where a mutation reads what it decides on. Read before the lock: a second install replaces the first one's pin; an uninstall leaves the pin on the build it removed; `pin` writes a build that was removed meanwhile. No kill is needed for any of them. | TLC, the `ToolStore-stale-pin-*` variants | Fixed: V1, "What a mutation decides on is read under the lock"; V3, V4 and V12 point to it. |
| K2-2 | An uninstall killed between removing the pinned build and clearing the pin leaves a pin that names a removed build. | TLC, `ToolStore-kill-dangling-pin` | Accepted by the maintainer (decision D50): the order stays, and V3 documents the state. 03's `PinConsistent` keeps its exception. |
| K2-3 | A build removed between the preflight's look and Java opening the jar: Java fails with its own message and exit code 1. `ReaderOutcome` as 03 worded it has no such ending. | TLC, `ToolStore-reader-gone` | Fixed as a statement: V1 says what happens, 03's property is reworded. Closing it is a possible change, named in V1; nobody asked for it. |
| K2-4 | Nobody removed the lock file of a `.tmp/` folder, and the cleanup looked at folders only. | Writing the model | Fixed: V11, "The lock file of a temporary folder". Not modelled; see ToolStore, "Leaves out". |
| K2-5 | An install that finds its build installed downloads nothing. If another tlaup removes the build before the install holds the lock, the install pins a build that is gone. | The stateful test, on the throwaway model. The first version of the spec added the build back in that case and so could not show it; the corrected spec does, `ToolStore-stale-install-found`. | Fixed: V1 and V12. The install starts again. |
| K3-1 | "The exit code is the first signal's if it arrived before the child exited" cannot be built: a signal that arrives after the child has ended and before the launcher has noticed looks the same to tlaup. | TLC, `Signals-exit-code` | Fixed: G3's table and 03's `ExitCode` say "recorded by the time the launcher saw the child gone". |
| K3-2 | "If a signal was recorded before the start, no child is started" is false for a signal between the look and `Popen`. The design already handles it (the child is stopped when attached). | TLC, `Signals-start-after-signal` | Fixed: G3's table says it in so many words, and that the child is attached before `Signals.first` is looked at; 03's property is reworded. |

### What the maintainer chose

Each was written into its design section with the options and their costs, and the maintainer chose on 2026-11-18, walking through these results.

1. **`cache clean` and the checkpoint of a killed run** (K1-4, [R6](../docs/design/11-runner.md#r6-run-folders), constant `CleanSparesCheckpoint`): spared unless `--all` is given (decision D49). The configs now have the constant on, except `checkpoint-clean`, which shows the option not taken.
2. **What a SIGKILL of tlaup reaches** (K1-3 and K1-5, [R6, Risks](../docs/design/11-runner.md#r6-run-folders)): not chosen yet. The maintainer added a fourth option, making TLC end with tlaup, and prefers it; question 35 asks whether it can be done. Accepting the risk, counting ages from the last write (question 34) and letting the lock outlive tlaup (question 33) remain. The design keeps the first until then. The fourth option is not modelled: with it, a kill would end TLC too, which the spec's `Kill` action could be changed to do once question 35 says it is possible.
3. **The order of the two steps of uninstall** (K2-2, [V3](../docs/design/12-tools-and-downloads.md#v3-uninstall), constant `UnpinFirst`): the order stays, and the dangling pin after a kill is accepted (decision D50). `unpin-first` shows the option not taken.

Settled at the same time, from the agent's report on this work ([feedback](../docs/feedback/2026-11-18-tla-tools-as-an-agent.md), point 5): `tlaup tlc --no-keep`, and no kept folder for a run stopped with no intent to resume (decision D48). Neither the spec nor the stateful test models it; see RunFolders, "Leaves out".

### Questions added to the investigation list

33 (can a run's lock outlive a killed tlaup?) and 34 (how often does TLC write under its `-metadir` folder?), both for the second point above. The maintainer added 35 (can TLC be made to end with tlaup, on Linux, macOS and Windows?) for the same point. Two older questions touch this work, and neither was waited for:

- **Question 30**, the earliest `filelock` that looks again at a lock file unlinked under it. `RunFolders` has the constant `Recheck` and was checked both ways; every result below says which it assumes.
- **Question 25**, whether TLC writes checkpoints without `-checkpoint`. `RunFolders` lets TLC write a checkpoint at any moment or never, so its results hold for either answer.

## RunFolders

**Models.** Two or three tlaup processes. A run is the steps of R6 "Start" one at a time: create the lock file; take its lock (an open and a flock, apart); for `-recover`, take the recovered folder's lock; make the folder; write `run.json`; sweep. Then TLC, which may write a checkpoint at any moment or never; settle; and the end, where the folder is kept and released, or deleted with its lock file and released, first the run's own and then the recovered one. A sweep and `cache clean`, with and without `--all`, list the entries and visit each: open its lock file, try the lock once, look and act, release. Any step of a start can fail, a lock wait can time out, and a tlaup can be killed anywhere: its locks are released and its TLC runs on. A lock file ages past one hour at any moment.

Names and files are apart, as the plan asked: a lock is on a file, a lock file is opened by name and created when it is not there, and an unlink removes whatever file is at the name. That is the behaviour of `open`, `flock` and `unlink`, and of the lock library as read from the source of `filelock` 4.2.10.

**Leaves out.**

- Ages of folders are not state. Each visit of a sweep chooses what it finds: young, over a day, over 30 days. That lets every order of ageing happen, and more (a folder can look old and then young); it hides K1-5.
- "Delete the folder, remove the lock file" is one step. A deletion can fail and leave the folder; it cannot remove half of it.
- A run with the user's own `-metadir`; a folder made by a command pasted from `--show-command` (a folder with no `run.json` exists in the model only between two steps of a start, or after a kill there).
- What is inside a folder beyond "has `run.json`", "is kept", "has a checkpoint". The note and the resume command.
- Windows, where an open file cannot be deleted and the lock is not `flock`.
- More than one SIGKILL in a behaviour.
- `--no-keep` (decision D48). A run with it settles as a run that finished does, and its folder, found unsettled after a kill, is treated as one with no checkpoint; both are paths the model already has, so the properties cover it. Its own rules are unit tests in R6.

**Properties.** `NoDeleteUnderTLC`, `OneTLCPerFolder`, `KeptSurvives`, `LockExclusive` and `NothingLeft`, as [03 lists them](../docs/design/03-run-stages-and-specs.md#k1-run-folders). Added: `HeldIsCurrent` (a held lock is on the file at the name), `LiveRunLocked` (a live run that has made its folder holds a current lock on it), `CheckpointSurvives` (K1-4), and the versions without their exception, which are expected to fail: `NoDeleteUnderOrphanTLC`, `OneTLCPerFolderAfterKill`, `LockExclusiveUntilRelease`. `KeptSurvives` says that only a sweep that finds the folder over 30 days old, `cache clean --all`, or the end of a run that resumed from it removes a kept folder; since ages are chosen by the sweep, "not before 30 days" is true by the sweep's rule and not by the check.

**The two questions.**

1. *Can a process that opened the old file and one that creates the new one both believe they hold the lock?* With `Recheck` (the lock library looks at the link count of the file it locked, and tries again if it is zero): no, in every config checked. Without it: yes (`three-no-recheck`), and with two processes one of them holds a lock on a file that is no longer at the name (`no-recheck-stale`).
2. *Does the one-hour rule close the gap between creating a lock file and locking it?* With `Recheck` the gap is closed without the rule: `no-hour-rule` passes with the rule switched off, because a start whose lock file is removed under it creates a new one and locks that. Without `Recheck` the rule is what closes it: `no-recheck` passes, `no-recheck-no-hour-rule` fails, and so does `no-recheck-stall`, where the rule is on and an hour passes while a run is between its steps.

**Results.** Constants not named are those of `RunFolders.cfg`: two processes that may each do everything, two run ids, six lock files at once, one SIGKILL, `Recheck`, `HourRule`, `Stall` (an hour can pass during a start or a visit), `DeleteMayFail` and `CleanSparesCheckpoint` on (the last since decision D49).

| Config | What differs | Expect | Result | Distinct states | Time |
| --- | --- | --- | --- | --- | --- |
| `RunFolders` | R6 as written, with a lock library that re-checks (the locked filelock 4.2.10), and `cache clean` sparing a resumable checkpoint (decision D49). Two processes that may each do everything, two run ids, one SIGKILL. | holds | as expected | 16,567,759 | 7 min 8 s |
| `checkpoint-clean` | Finding K1-4, the option not taken (decision D49): `cache clean` without --all removes the checkpoint of a killed run. | `CheckpointSurvives` fails | as expected | 26,458 | 3 s |
| `liveness` | NothingLeft under FairSpec.  No symmetry (it is not sound for liveness); deletions succeed. | holds | as expected | 3,585 | 10 s |
| `no-hour-rule` | With a lock library that re-checks, the one-hour rule is not what keeps runs safe. | holds | as expected | 12,736,296 | 4 min 55 s |
| `no-recheck-delete-fails` | No re-check, and a folder deletion fails. | `NoDeleteUnderTLC` fails | as expected | 733,936 | 13 s |
| `no-recheck-no-hour-rule` | No re-check and no one-hour rule: the rule is what closes the gap then. | `NoDeleteUnderTLC` fails | as expected | 136,416 | 4 s |
| `no-recheck-stale` | No re-check: a sweep ends up holding a lock on a file that is no longer at the name. | `HeldIsCurrent` fails | as expected | 4,971 | 1 s |
| `no-recheck-stall` | No re-check, and an hour passes during a start. | `NoDeleteUnderTLC` fails | as expected | 251,258 | 5 s |
| `no-recheck` | Question 30, the other answer: no re-check.  Nothing stalls for an hour, no deletion fails. The lock invariants are left out here: RunFolders-no-recheck-stale.cfg shows they do not hold. | holds | as expected | 2,414,757 | 44 s |
| `orphan-delete` | The risk R6 accepts: a folder deleted under the TLC of a killed tlaup. | `NoDeleteUnderOrphanTLC` fails | as expected | 15,039 | 3 s |
| `orphan-recover` | Finding K1-3: -recover into the folder of a killed tlaup whose TLC still runs. | `OneTLCPerFolderAfterKill` fails | as expected | 274,921 | 5 s |
| `three-no-recheck` | No re-check: two lock objects both hold the lock of one name (needs three processes). | `LockExclusive` fails | as expected | 11,254 | 2 s |
| `three` | Three processes, one of which starts runs; one run id; nobody is killed. | holds | as expected | 682,909 | 15 s |
| `until-release` | Finding K1-1: two lock objects between an unlink and the release that follows it. | `LockExclusiveUntilRelease` fails | as expected | 3,452 | 1 s |

`liveness` checks `NothingLeft` under `FairSpec`: every step of a command is taken in the end, a lock that keeps becoming free is taken, a sweep finds each folder old enough in the end, lock files age, and sweeps keep coming. Its model is small on purpose: one process that starts runs, one that sweeps and cleans, one run id, no symmetry. A model with two run ids (1.3 million states) was tried and stopped after 35 minutes inside the liveness check, with no answer.

## ToolStore

**Models.** Two or three tlaup processes and an upstream that publishes new bytes under a name at any moment. Install: look at upstream and the store, lock a `.tmp/` folder, make it, download, take the store lock, add (or find the same name and bytes there and discard), pin if nothing is pinned, release. Upgrade: the same, then move the pin if it named the build that was compared, and remove that build. Uninstall: take the lock, rename the build into `.tmp/`, delete it there, clear the pin if it named it. Pin. A reader: read the pin, look the build up, then Java opens the jar, with no lock. Any command can give up at the download or at a busy lock, and a tlaup can be killed anywhere, which leaves its `.tmp/` folders for the next mutation's cleanup.

`ReadUnderLock` chooses where a mutation reads what it decides on: under the lock, which is the fixed design, or before it, which the first wording allowed (K2-1). `UnpinFirst` is the option of K2-2 the maintainer did not take (decision D50).

**Leaves out.**

- Folder names. A build is a name and a version of its bytes, and an id stands for exactly one build; the `-2` suffix rule and two names that give one id text are not modelled. So "a reader never opens another build than the pin named" is true here by construction, and `NoDuplicate` only says that no action adds a second copy.
- The lock files under `.tmp/` as files. A `.tmp/` folder is locked or not; whether removing such a lock file is safe is the question `RunFolders` answers, and V11 now uses its rule (K2-4).
- `--force` and repair in place, `tool list`, the lookup cache, everything about the network except "what upstream publishes now".
- Half-written folders. `NoPartialBuild` says that only the two renames change what is in the store; that each is one rename is the design's claim, not something TLC can see.
- More than one SIGKILL in a behaviour.

**Properties.** `PinConsistent`, `NoPartialBuild`, `ReaderOutcome`, `NoDuplicate`, `TmpOwnerSafe` and `PinNeverMovesSilently`, as [03 lists them](../docs/design/03-run-stages-and-specs.md#k2-tools-store). Added: `PinWritesInstalled` and `InstallPinsInstalled` (what is pinned is installed at that moment), `TmpLockedWhileThere`, `ReaderChecked`, and `PinConsistentAfterKill`, which is `PinConsistent` without its exception.

**Results.** Constants not named are those of `ToolStore.cfg`: two processes, two names, two versions of each name's bytes, one SIGKILL, `ReadUnderLock` on, `UnpinFirst` off.

| Config | What differs | Expect | Result | Distinct states | Time |
| --- | --- | --- | --- | --- | --- |
| `ToolStore` | V1, V3, V4, V11 and V12 with the fix of finding K2-1: what a mutation decides on is read under the lock. Two processes, two names, two versions of each name's bytes, one SIGKILL. | holds | as expected | 4,575,854 | 49 s |
| `kill-dangling-pin` | Finding K2-2: an uninstall killed between removing the pinned build and clearing the pin. | `PinConsistentAfterKill` fails | as expected | 9,105 | 1 s |
| `reader-gone` | Finding K2-3: the build is removed between the preflight's check and Java opening the jar. | `ReaderOutcome` fails | as expected | 11,180 | 1 s |
| `stale-install-found` | Finding K2-5: an install finds its build installed, another tlaup removes it, the install pins it.  Nobody is killed. | `InstallPinsInstalled` fails | as expected | 16,251 | 2 s |
| `stale-pin-dangles` | Finding K2-1: an uninstall that saw no pin before it took the lock removes the build an install has just pinned.  Nobody is killed. | `PinConsistent` fails | as expected | 4,751 | 1 s |
| `stale-pin-missing` | Finding K2-1: `pin` finds a build, another tlaup removes it, `pin` writes it.  Nobody is killed. | `PinWritesInstalled` fails | as expected | 12,099 | 1 s |
| `stale-pin-moves` | Finding K2-1: two installs both see that nothing is pinned; the second replaces the first one's pin. | `PinNeverMovesSilently` fails | as expected | 17,368 | 2 s |
| `three` | Three processes, one name, two versions, one SIGKILL. | holds | as expected | 2,940,014 | 48 s |
| `unpin-first` | Finding K2-2, the option not taken (decision D50): the pin is cleared before the pinned build is removed. | holds | as expected | 3,445,878 | 34 s |

## Signals

**Models.** One tlaup process: it enters `signals_held`, looks at `Signals.first`, starts the child, attaches it, waits, sees it gone, prints the summary, leaves and exits. Up to three signals arrive at any of those moments, each SIGINT, SIGTERM, SIGHUP or SIGQUIT. Chosen at the start, in every combination: which of the four were ignored when tlaup started; whether SIGINT is left to the child (`tlaup repl`); whether the child ends by itself or only when killed. The process loop can fail (a closed pipe), and the grace period can run out.

**Leaves out.**

- Installing the handlers is one step, and so is restoring them. A signal between two `signal.signal` calls is not modelled.
- What the terminal does: a Ctrl-C that reaches the child as well is the child ending at a moment of its own.
- The reader threads, the queue, output. A main thread blocked in a write (the risk G3 names).
- SIGKILL of tlaup; more than one child; Windows.

**Properties.** `NoDefaultHandler`, `ChildNeverOrphaned`, `ExitCode`, `IgnoredStaysIgnored` and `NothingStartsAfterSignal`, as [03 lists them](../docs/design/03-run-stages-and-specs.md#k3-signals). `ExitCode` and `NothingStartsAfterSignal` do not hold as first worded (K3-1, K3-2); what holds in their place is `SignalNeverLost`, `ExitCodeAsSeen`, `LateSignalChangesNothing`, `NothingStartsAfterSeenSignal` and `SignalReachesChild`. Added: `SecondSignalKills`, `LeftAloneNotRecorded`, `IgnoredChangesNothing`, and one liveness property, `Stops`: once a signal is recorded, tlaup exits, whatever the child does. `NoDefaultHandler` is true by the shape of the model, since entering installs every handler in one step.

**Results.**

| Config | What differs | Expect | Result | Distinct states | Time |
| --- | --- | --- | --- | --- | --- |
| `Signals` | G3 and R2 as written.  Three signals, each of four kinds, at any moment; every set of signals ignored at entry; with and without leave_interrupt; a child that ends by itself and one that must be killed. | holds | as expected | 29,160 | 1 s |
| `exit-code` | Finding K3-1: a signal after the child has ended and before the launcher has seen it. | `ExitCode` fails | as expected | 15,351 | 1 s |
| `start-after-signal` | Finding K3-2: a signal after the run function has looked and before Popen. | `NothingStartsAfterSignal` fails | as expected | 1,295 | 1 s |

The check found no flaw in G3 or R2. Not a finding, but worth knowing: two signals that both land before the child is attached count as one for the child, which gets `terminate()` and not `kill()`; the grace period bounds the wait.

## The stateful tests

`tests/stateful/` has one Hypothesis `RuleBasedStateMachine` per spec, as [03 describes](../docs/design/03-run-stages-and-specs.md#specs-and-their-tests). They call the step functions named in [11 R6](../docs/design/11-runner.md#r6-run-folders), [12 V1](../docs/design/12-tools-and-downloads.md#v1-version-store) and [20 G3](../docs/design/20-groundwork.md#g3-java-launcher), which do not exist yet, so those tests carry the `pending` marker, which `pyproject.toml` registers and deselects.

| File | The machine | Checks, on real files, locks, handlers and a real child |
| --- | --- | --- |
| `test_run_folders.py` | Three processes, each with its own step objects and so its own locks; every action of `RunFolders` as a rule; an injected clock; lock-file age set with `os.utime`. | `NoDeleteUnderTLC`, `OneTLCPerFolder`, `KeptSurvives`, `CheckpointSurvives` (added with decision D49: `cache clean` without `--all` leaves a folder that has a `run.json` and a checkpoint), `LockExclusive`, `HeldIsCurrent`, `LiveRunLocked`; that a lock attempt succeeds exactly when no other lock object holds the lock; that settle keeps exactly when the run did not finish and a checkpoint is there. |
| `test_tool_store.py` | Two processes, each with its own store object; every action of `ToolStore` as a rule; upstream is a table of the test's own. Four plain tests replay the counterexamples of K2-1 and K2-5 step by step. | `PinConsistent`, `PinNeverMovesSilently`, `PinWritesInstalled`, `InstallPinsInstalled`, `NoPartialBuild`, `NoDuplicate`, `TmpOwnerSafe`, `ReaderOutcome` (the jar a reader opens has the SHA-256 of the build the pin named). |
| `test_signals.py` | The test process is the tlaup of the spec: it enters `signals_held`, runs a real child a step at a time, and sends itself real signals between the steps; the grace period runs on an injected clock. | `NoDefaultHandler`, `ChildNeverOrphaned`, `ExitCodeAsSeen`, `SignalNeverLost`, `LateSignalChangesNothing`, `IgnoredStaysIgnored` (the child's own dispositions are read from `/proc`), `NothingStartsAfterSeenSignal`, `SignalReachesChild`, and that `Signals.first` and `count` are what the model says after every step. |

Each file also has a plain test with a second Python process. For the two that use locks it confirms that a lock object in the test process is refused, and refuses, exactly as another process is. For the signals it confirms that a signal from outside is recorded as one the process sends itself, and that the handler has run when `os.kill` returns.

**Run against a throwaway model: yes.** Each machine was also run against a small model of its step functions kept beside it (`reference_rundirs.py`, `reference_store.py`, `reference_launcher.py`): real `filelock` locks, real files, real signal handlers and a real child, with none of the product round them. Those runs are the tests named `..._reference_model`; they are not `pending`. All pass with the 200 examples of the CI profile, which took about 95, 75 and 26 seconds for the three machines on a machine that was also running TLC; with the 50 of the development profile, about 10, 14 and 3 seconds. The work package that builds the real code deletes the throwaway model with its tests.

**The machines were tried on broken models.** A machine that cannot fail proves nothing, so each throwaway model was broken on purpose in several ways, one at a time, and the machine run with 200 examples: twenty-two broken models in all, each tried twice, with shrinking switched off. The signals machine caught all seven of its own both times. The run-folder machine caught six of seven, then four of seven: it always finds a lock that is not held or not taken, and it missed at least once a kept folder removed too early by the sweep, by `cache clean` or at the end of a resumed run, each of which is a rule of one step that R6's unit tests cover with an injected clock. The store machine caught four of eight both times: it finds a cleanup that ignores locks, a removal that is not a rename, and an upgrade that moves the pin or removes a build it should not; both times it missed the four mistakes of reading before the lock (K2-1 and K2-5), although earlier runs of the same machine had caught two of them, and one such run is how K2-5 was found. The four replay tests catch those four every time (tried). The broken models and these runs were scratch work and are not in the repository. The first version of the machines caught under half of the broken models. What changed that: a start-up phase that leaves earlier runs or installs behind, made with the same step functions; one kill per example, as in the specs' models; a stubborn child that notes the SIGTERM it gets; and, for the signals, drawing the phase before which no signal arrives. What it shows about the limits: a race that needs one command to wait while another takes four steps is found by chance or not at all. That is why the counterexamples of K2-1 and K2-5 are also plain tests that replay their steps. After decision D49 the run-folder machine and its throwaway model were changed to the new `cache clean` rule and run again: it passes with the 200 examples of the CI profile (77 seconds). With the old rule put back in the throwaway model, the new check caught it in one of two runs of 50 examples; it was not tried with 200.

**How to run them today.** `hypothesis` is not a development dependency yet; the first testing work package adds it ([01 T10](../docs/design/01-testing.md#t10-coverage-policy-and-pytest-settings)). Until then `uv run poe test` skips the three files, and this runs them without changing the project:

```bash
uv run --with hypothesis pytest tests/stateful --no-cov
```

Adding `-m pending` runs the tests for the real code, which fail at the import until it is built.

## What was not checked

- The specs say what one agent understood of the design, and no second reader has compared them with the sections. K2-5 shows the kind of gap that leaves: the first store spec was wrong in the design's favour, and TLC was content.
- The bounds: two processes for most results (three for two configs with one run id), two run ids, two names with two versions each, one SIGKILL, three signals. A flaw that needs more is not found. Three processes with two run ids were not run.
- Liveness for the run folders in the small model only.
- Anything inside one step: the two system calls of a rename, a folder half deleted, a handler half installed.
- Windows and macOS. Network file systems, where `flock` may not hold.
- The stateful tests against real code: there is none. Whether a machine catches a mistake in the real step functions is known only from the broken throwaway models.
- The step functions' signatures were not tried against the rest of the design beyond reading it; a worker may find that one needs another argument.
