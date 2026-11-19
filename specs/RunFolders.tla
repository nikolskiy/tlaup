----------------------------- MODULE RunFolders -----------------------------
(***************************************************************************)
(* K1 of docs/design/03-run-stages-and-specs.md: the run folders under     *)
(* <cache>/runs/ and their lock files, as docs/design/11-runner.md R6      *)
(* designs them.  Several tlaup processes start runs, sweep, clean the     *)
(* cache, resume into another run's folder with -recover, and are killed.  *)
(*                                                                         *)
(* A lock belongs to a file, not to its name.  The spec therefore keeps    *)
(* names (lockFile) and files (Inodes) apart: removing a lock file and     *)
(* creating one under the same name gives a second lock.                   *)
(*                                                                         *)
(* What the model is, what it leaves out, its bounds and its results are   *)
(* in README.md beside this file.                                          *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS
    Procs,                 \* tlaup processes
    Runners,               \* the processes that may start runs
    Cleaners,              \* the processes that may sweep alone and run `cache clean`
    RunIds,                \* run ids; each names one folder and one lock file
    Inodes,                \* lock files that can exist at once, a set of numbers from 1
    MaxKills,              \* how many times a tlaup is killed with SIGKILL
    Recheck,               \* TRUE: after it gets the lock, the lock library checks that the
                           \* file it locked is still linked (filelock 4.2.10 does; question 30)
    HourRule,              \* TRUE: a lock file with no folder is removed only when over an hour old
    Stall,                 \* TRUE: an hour can pass while a process is in the middle of a start
                           \* or of a visit (a suspended machine)
    DeleteMayFail,         \* TRUE: deleting a folder can fail and leave it (R6, "Errors while
                           \* deleting are ignored")
    CleanSparesCheckpoint  \* TRUE: `cache clean` without --all leaves an unsettled folder
                           \* that holds a checkpoint, as the sweep does (finding K1-4;
                           \* decision D49 chose TRUE)

ASSUME /\ Runners \subseteq Procs /\ Cleaners \subseteq Procs
       /\ Recheck \in BOOLEAN /\ HourRule \in BOOLEAN /\ Stall \in BOOLEAN
       /\ DeleteMayFail \in BOOLEAN /\ CleanSparesCheckpoint \in BOOLEAN
       /\ MaxKills \in Nat

VARIABLES
    pc,        \* where each process is in its command
    cur,       \* the run id of the run a process is in, or NoRun
    mode,      \* what the process is doing: "run", "sweep", "clean", "cleanAll"
    snap,      \* entries of runs/ a sweep or clean has listed and not visited yet
    vis,       \* the entry being visited
    keptD,     \* what settle decided: the folder is kept
    used,      \* run ids already given out; an id is never used twice
    target,    \* per run: the run folder its -recover names, or NoRun
    tlc,       \* per run: its TLC process: "none", "live", "orphan" (its tlaup was killed), "done"
    folder,    \* per run id: the run folder
    lockFile,  \* per run id: the file at <id>.lock, or 0
    lockOld,   \* per run id: that file is more than an hour old
    holder,    \* per file: the lock object that holds its flock, or NoHandle
    hnd,       \* per lock object: closed, open on a file, holding it, or holding it after
               \* removing the name ("gone")
    kills      \* tlaups killed so far

procVars == <<pc, cur, mode, snap, vis, keptD>>
runVars  == <<used, target, tlc>>
lockVars == <<lockFile, lockOld, holder, hnd>>
vars == <<pc, cur, mode, snap, vis, keptD, used, target, tlc, folder,
          lockFile, lockOld, holder, hnd, kills>>

NoRun == "none"
Roles == {"own", "rec", "vis"}      \* a process's lock objects: its run, the recovered run, a visit
Handles == Procs \X Roles
NoHandle == <<"none", "none">>
Own(p) == <<p, "own">>
Rec(p) == <<p, "rec">>
Vis(p) == <<p, "vis">>

Closed == [st |-> "closed", name |-> NoRun, ino |-> 0]
NoFolder == [ex |-> FALSE, json |-> "none", chk |-> FALSE]
\* folder.json: "none" no run.json; "started" written at the start, never settled as kept;
\*              "kept" settled with "kept": true and a fresh "ended".
\* A folder's age is not kept as state.  The sweep is the only reader of it, and each visit
\* chooses what it finds: 0 young, 1 older than a day, 2 older than 30 days.

PCs == {"idle", "lock", "lock2", "rlock", "rlock2", "mkdir", "json",
        "visit", "visit2", "visit3", "visit4", "tlc", "settle",
        "eOwn", "eOwnRel", "eRec", "eRecRel"}

TypeOK ==
    /\ pc \in [Procs -> PCs]
    /\ cur \in [Procs -> RunIds \cup {NoRun}]
    /\ mode \in [Procs -> {"run", "sweep", "clean", "cleanAll"}]
    /\ snap \in [Procs -> SUBSET RunIds]
    /\ vis \in [Procs -> RunIds \cup {NoRun}]
    /\ keptD \in [Procs -> BOOLEAN]
    /\ used \subseteq RunIds
    /\ target \in [RunIds -> RunIds \cup {NoRun}]
    /\ tlc \in [RunIds -> {"none", "live", "orphan", "done"}]
    /\ folder \in [RunIds -> [ex : BOOLEAN, json : {"none", "started", "kept"}, chk : BOOLEAN]]
    /\ lockFile \in [RunIds -> Inodes \cup {0}]
    /\ lockOld \in [RunIds -> BOOLEAN]
    /\ holder \in [Inodes -> Handles \cup {NoHandle}]
    /\ hnd \in [Handles -> [st : {"closed", "open", "held", "gone"},
                            name : RunIds \cup {NoRun}, ino : Inodes \cup {0}]]
    /\ kills \in 0..MaxKills

Init ==
    /\ pc = [p \in Procs |-> "idle"]
    /\ cur = [p \in Procs |-> NoRun]
    /\ mode = [p \in Procs |-> "run"]
    /\ snap = [p \in Procs |-> {}]
    /\ vis = [p \in Procs |-> NoRun]
    /\ keptD = [p \in Procs |-> FALSE]
    /\ used = {}
    /\ target = [r \in RunIds |-> NoRun]
    /\ tlc = [r \in RunIds |-> "none"]
    /\ folder = [r \in RunIds |-> NoFolder]
    /\ lockFile = [r \in RunIds |-> 0]
    /\ lockOld = [r \in RunIds |-> FALSE]
    /\ holder = [i \in Inodes |-> NoHandle]
    /\ hnd = [h \in Handles |-> Closed]
    /\ kills = 0

-----------------------------------------------------------------------------
(* Files and locks, as open(2), flock(2) and unlink(2) behave.             *)

Referenced(i) == (\E n \in RunIds : lockFile[n] = i) \/ (\E h \in Handles : hnd[h].ino = i)
FreeInodes == {i \in Inodes : ~Referenced(i)}
NewInode == CHOOSE i \in FreeInodes : \A j \in FreeInodes : i <= j

\* One attempt of the lock library starts by opening the lock file, creating it when it is
\* not there (O_CREAT).  Creating sets the file's time; opening does not (no O_TRUNC).
OpenLock(h, n) ==
    /\ hnd[h].st = "closed"
    /\ IF lockFile[n] = 0
       THEN /\ FreeInodes # {}
            /\ lockFile' = [lockFile EXCEPT ![n] = NewInode]
            /\ lockOld' = [lockOld EXCEPT ![n] = FALSE]
            /\ hnd' = [hnd EXCEPT ![h] = [st |-> "open", name |-> n, ino |-> NewInode]]
       ELSE /\ hnd' = [hnd EXCEPT ![h] = [st |-> "open", name |-> n, ino |-> lockFile[n]]]
            /\ UNCHANGED <<lockFile, lockOld>>
    /\ UNCHANGED holder

\* The attempt goes on with a non-blocking flock.  With Recheck it then looks at the link
\* count of the file it locked, and gives the lock up if the file was unlinked meanwhile.
FlockWins(h) ==
    /\ hnd[h].st = "open"
    /\ holder[hnd[h].ino] = NoHandle
    /\ Recheck => lockFile[hnd[h].name] = hnd[h].ino

FlockOK(h) ==
    /\ FlockWins(h)
    /\ holder' = [holder EXCEPT ![hnd[h].ino] = h]
    /\ hnd' = [hnd EXCEPT ![h].st = "held"]
    /\ UNCHANGED <<lockFile, lockOld>>

FlockFail(h) ==
    /\ hnd[h].st = "open"
    /\ ~FlockWins(h)
    /\ hnd' = [hnd EXCEPT ![h] = Closed]
    /\ UNCHANGED <<lockFile, lockOld, holder>>

Release(h) ==
    /\ hnd[h].st \in {"held", "gone"}
    /\ holder' = [holder EXCEPT ![hnd[h].ino] = NoHandle]
    /\ hnd' = [hnd EXCEPT ![h] = Closed]
    /\ UNCHANGED <<lockFile, lockOld>>

\* "Delete the folder, remove the lock file while the lock is held", in one step.  Deleting
\* either removes the folder or, with DeleteMayFail, leaves it.  unlink(2) takes a name: it
\* removes whatever file is at the name now, which is the caller's own only if the caller's
\* lock is on that file.  `del` and `unl` say which of the two is done.
Remove(h, del, unl) ==
    /\ hnd[h].st = "held"
    /\ \E ok \in (IF DeleteMayFail THEN BOOLEAN ELSE {TRUE}) :
         LET n == hnd[h].name
             gone == ~folder[n].ex \/ (del /\ ok)
             unlink == unl[gone]
         IN /\ folder' = IF del /\ ok THEN [folder EXCEPT ![n] = NoFolder] ELSE folder
            /\ lockFile' = IF unlink THEN [lockFile EXCEPT ![n] = 0] ELSE lockFile
            /\ lockOld' = IF unlink THEN [lockOld EXCEPT ![n] = FALSE] ELSE lockOld
            /\ hnd' = IF unlink THEN [hnd EXCEPT ![h].st = "gone"] ELSE hnd
    /\ UNCHANGED holder

Always == [b \in BOOLEAN |-> TRUE]
Never == [b \in BOOLEAN |-> FALSE]
IfGone == [b \in BOOLEAN |-> b]

-----------------------------------------------------------------------------
(* Start (R6, "Start"): create the lock file, take its lock, take the      *)
(* recovered folder's lock, make the folder, write run.json, sweep.        *)

CreateLockFile(p, r, t) ==
    /\ pc[p] = "idle"
    /\ p \in Runners
    /\ r \notin used
    /\ t = NoRun \/ (t \in RunIds /\ t # r /\ folder[t].ex)   \* -recover PATH inside runs/<t>/
    /\ lockFile[r] = 0
    /\ FreeInodes # {}
    /\ lockFile' = [lockFile EXCEPT ![r] = NewInode]
    /\ lockOld' = [lockOld EXCEPT ![r] = FALSE]
    /\ used' = used \cup {r}
    /\ target' = [target EXCEPT ![r] = t]
    /\ cur' = [cur EXCEPT ![p] = r]
    /\ mode' = [mode EXCEPT ![p] = "run"]
    /\ pc' = [pc EXCEPT ![p] = "lock"]
    /\ UNCHANGED <<snap, vis, keptD, tlc, folder, holder, hnd, kills>>

TakeLockOpen(p) ==
    /\ pc[p] = "lock"
    /\ OpenLock(Own(p), cur[p])
    /\ pc' = [pc EXCEPT ![p] = "lock2"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, folder, kills>>

TakeLockOK(p) ==
    /\ pc[p] = "lock2"
    /\ FlockOK(Own(p))
    /\ pc' = [pc EXCEPT ![p] = IF target[cur[p]] # NoRun THEN "rlock" ELSE "mkdir"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, folder, kills>>

TakeLockFail(p) ==                    \* held elsewhere, or unlinked under it: the next poll
    /\ pc[p] = "lock2"
    /\ FlockFail(Own(p))
    /\ pc' = [pc EXCEPT ![p] = "lock"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, folder, kills>>

TakeLockTimeout(p) ==                 \* five seconds are over: FileOperationError, code 5
    /\ pc[p] = "lock"
    /\ pc' = [pc EXCEPT ![p] = "idle"]
    /\ cur' = [cur EXCEPT ![p] = NoRun]
    /\ UNCHANGED <<mode, snap, vis, keptD, runVars, folder, lockVars, kills>>

TakeRecoverLockOpen(p) ==
    /\ pc[p] = "rlock"
    /\ OpenLock(Rec(p), target[cur[p]])
    /\ pc' = [pc EXCEPT ![p] = "rlock2"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, folder, kills>>

TakeRecoverLockOK(p) ==
    /\ pc[p] = "rlock2"
    /\ FlockOK(Rec(p))
    /\ pc' = [pc EXCEPT ![p] = "mkdir"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, folder, kills>>

TakeRecoverLockFail(p) ==
    /\ pc[p] = "rlock2"
    /\ FlockFail(Rec(p))
    /\ pc' = [pc EXCEPT ![p] = "rlock"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, folder, kills>>

TakeRecoverLockTimeout(p) ==          \* "the run folder is in use by another tlaup run"
    /\ pc[p] = "rlock"
    /\ pc' = [pc EXCEPT ![p] = "eOwn"]
    /\ keptD' = [keptD EXCEPT ![p] = FALSE]
    /\ UNCHANGED <<cur, mode, snap, vis, runVars, folder, lockVars, kills>>

MakeFolder(p) ==
    /\ pc[p] = "mkdir"
    /\ folder' = [folder EXCEPT ![cur[p]] = [ex |-> TRUE, json |-> "none", chk |-> FALSE]]
    /\ pc' = [pc EXCEPT ![p] = "json"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, lockVars, kills>>

SweepEntries == {n \in RunIds : folder[n].ex \/ lockFile[n] # 0}
CleanEntries == {n \in RunIds : folder[n].ex}

\* Write run.json, then list the entries of runs/ for the sweep.
WriteRunJson(p) ==
    /\ pc[p] = "json"
    /\ folder' = [folder EXCEPT ![cur[p]] = IF @.ex THEN [@ EXCEPT !.json = "started"] ELSE @]
    /\ snap' = [snap EXCEPT ![p] = {n \in RunIds : folder'[n].ex \/ lockFile[n] # 0}]
    /\ pc' = [pc EXCEPT ![p] = "visit"]
    /\ UNCHANGED <<cur, mode, vis, keptD, runVars, lockVars, kills>>

\* An error or a signal between taking the locks and starting TLC: nothing is started, the
\* folders are settled and the run ends (R2, "A signal before the child exists").
AbortStart(p) ==
    /\ \/ pc[p] \in {"mkdir", "json"}
       \/ pc[p] = "visit" /\ mode[p] = "run" /\ snap[p] = {}
    /\ pc' = [pc EXCEPT ![p] = "settle"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, folder, lockVars, kills>>

-----------------------------------------------------------------------------
(* The sweep, `cache clean` and `cache clean --all`: list the entries,     *)
(* then for each one take its lock without waiting, look, act, release.    *)

BeginSweep(p) ==                      \* the sweep of a run beyond the model's run ids
    /\ pc[p] = "idle"
    /\ p \in Cleaners
    /\ mode' = [mode EXCEPT ![p] = "sweep"]
    /\ snap' = [snap EXCEPT ![p] = SweepEntries]
    /\ pc' = [pc EXCEPT ![p] = "visit"]
    /\ UNCHANGED <<cur, vis, keptD, runVars, folder, lockVars, kills>>

BeginClean(p, all) ==
    /\ pc[p] = "idle"
    /\ p \in Cleaners
    /\ mode' = [mode EXCEPT ![p] = IF all THEN "cleanAll" ELSE "clean"]
    /\ snap' = [snap EXCEPT ![p] = CleanEntries]
    /\ pc' = [pc EXCEPT ![p] = "visit"]
    /\ UNCHANGED <<cur, vis, keptD, runVars, folder, lockVars, kills>>

VisitOpen(p, n) ==
    /\ pc[p] = "visit"
    /\ n \in snap[p]
    /\ OpenLock(Vis(p), n)
    /\ snap' = [snap EXCEPT ![p] = @ \ {n}]
    /\ vis' = [vis EXCEPT ![p] = n]
    /\ pc' = [pc EXCEPT ![p] = "visit2"]
    /\ UNCHANGED <<cur, mode, keptD, runVars, folder, kills>>

VisitLockOK(p) ==
    /\ pc[p] = "visit2"
    /\ FlockOK(Vis(p))
    /\ pc' = [pc EXCEPT ![p] = "visit3"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, folder, kills>>

VisitLockFail(p) ==                   \* a held lock: the entry is never touched
    /\ pc[p] = "visit2"
    /\ FlockFail(Vis(p))
    /\ vis' = [vis EXCEPT ![p] = NoRun]
    /\ pc' = [pc EXCEPT ![p] = "visit"]
    /\ UNCHANGED <<cur, mode, snap, keptD, runVars, folder, kills>>

\* R6, "sweep": a kept folder after 30 days; an unsettled one as kept if it holds a
\* checkpoint, else after one day; one without run.json after 30 days.
SweepRemoves(n, age) ==
    LET f == folder[n] IN
    /\ f.ex
    /\ CASE f.json = "kept" -> age = 2
         [] f.json = "started" -> IF f.chk THEN age = 2 ELSE age >= 1
         [] OTHER -> age = 2

\* R6, `cache clean`: every folder with a run.json that is not kept and, with
\* CleanSparesCheckpoint (decision D49), that is not unsettled with a checkpoint; with --all
\* every folder.
CleanRemoves(n, all) ==
    LET f == folder[n] IN
    /\ f.ex
    /\ all \/ (f.json = "started" /\ ~(CleanSparesCheckpoint /\ f.chk))

\* Holding the entry's lock: the sweep removes a folder that is old enough, and a lock file
\* whose folder is gone when the file is over an hour old.  `cache clean` removes a folder
\* and the lock file with it.
VisitAct(p, age) ==
    /\ pc[p] = "visit3"
    /\ LET n == vis[p] IN
       IF mode[p] \in {"run", "sweep"}
       THEN Remove(Vis(p), SweepRemoves(n, age),
                   IF lockFile[n] # 0 /\ (HourRule => lockOld[n]) THEN IfGone ELSE Never)
       ELSE LET del == CleanRemoves(n, mode[p] = "cleanAll")
            IN Remove(Vis(p), del, IF del THEN IfGone ELSE Never)
    /\ pc' = [pc EXCEPT ![p] = "visit4"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, kills>>

VisitRelease(p) ==
    /\ pc[p] = "visit4"
    /\ Release(Vis(p))
    /\ vis' = [vis EXCEPT ![p] = NoRun]
    /\ pc' = [pc EXCEPT ![p] = "visit"]
    /\ UNCHANGED <<cur, mode, snap, keptD, runVars, folder, kills>>

VisitDone(p) ==
    /\ pc[p] = "visit"
    /\ mode[p] # "run"
    /\ snap[p] = {}
    /\ pc' = [pc EXCEPT ![p] = "idle"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, folder, lockVars, kills>>

-----------------------------------------------------------------------------
(* The run itself, settle and the end.                                     *)

RecHeld(p) == hnd[Rec(p)].st = "held"

\* The folders the TLC of run r works in: its own, and the one -recover names.
Where(r) == IF target[r] # NoRun THEN {r, target[r]} ELSE {r}
\* The folder TLC writes its checkpoints in.
CheckpointFolder(r) == IF target[r] # NoRun THEN target[r] ELSE r
Working(f) == {r \in RunIds : tlc[r] \in {"live", "orphan"} /\ f \in Where(r)}

StartTLC(p) ==                        \* after the sweep
    /\ pc[p] = "visit"
    /\ mode[p] = "run"
    /\ snap[p] = {}
    /\ tlc' = [tlc EXCEPT ![cur[p]] = "live"]
    /\ pc' = [pc EXCEPT ![p] = "tlc"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, used, target, folder, lockVars, kills>>

\* TLC writes a checkpoint, at any moment or never (question 25 asks when; the model allows
\* both).  A TLC whose folder was deleted writes nothing: it crashes (research 17).
Checkpoint(r) ==
    /\ tlc[r] \in {"live", "orphan"}
    /\ folder[CheckpointFolder(r)].ex
    /\ ~folder[CheckpointFolder(r)].chk
    /\ folder' = [folder EXCEPT ![CheckpointFolder(r)].chk = TRUE]
    /\ UNCHANGED <<procVars, runVars, lockVars, kills>>

TLCExit(p) ==                         \* finished, violated, crashed or stopped by a signal
    /\ pc[p] = "tlc"
    /\ tlc' = [tlc EXCEPT ![cur[p]] = "done"]
    /\ pc' = [pc EXCEPT ![p] = "settle"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, used, target, folder, lockVars, kills>>

OrphanExit(r) ==
    /\ tlc[r] = "orphan"
    /\ tlc' = [tlc EXCEPT ![r] = "done"]
    /\ UNCHANGED <<procVars, used, target, folder, lockVars, kills>>

\* R6, "Settle": kept when the run did not finish and a checkpoint is there.  After
\* -recover the checkpoint is looked for in the recovered folder.
Settle(p) ==
    /\ pc[p] = "settle"
    /\ LET r == cur[p]
           f == IF RecHeld(p) THEN target[r] ELSE r
       IN \E finished \in (IF tlc[r] = "done" THEN BOOLEAN ELSE {FALSE}) :
            LET k == ~finished /\ folder[f].ex /\ folder[f].chk IN
            /\ keptD' = [keptD EXCEPT ![p] = k]
            /\ folder' = IF k THEN [folder EXCEPT ![f].json = "kept"] ELSE folder
    /\ pc' = [pc EXCEPT ![p] = "eOwn"]
    /\ UNCHANGED <<cur, mode, snap, vis, runVars, lockVars, kills>>

\* R6, "End".  The run's own folder: kept and released, or deleted, its lock file removed
\* while the lock is held, and released.  Then the same for the recovered folder.
KeepOwn(p) == keptD[p] /\ ~RecHeld(p)

EndOwn(p) ==
    /\ pc[p] = "eOwn"
    /\ IF KeepOwn(p) THEN UNCHANGED <<folder, lockVars>>
       ELSE Remove(Own(p), TRUE, Always)
    /\ pc' = [pc EXCEPT ![p] = "eOwnRel"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, kills>>

EndOwnRelease(p) ==
    /\ pc[p] = "eOwnRel"
    /\ Release(Own(p))
    /\ IF RecHeld(p)
       THEN /\ pc' = [pc EXCEPT ![p] = "eRec"]
            /\ UNCHANGED cur
       ELSE /\ pc' = [pc EXCEPT ![p] = "idle"]
            /\ cur' = [cur EXCEPT ![p] = NoRun]
    /\ UNCHANGED <<mode, snap, vis, keptD, runVars, folder, kills>>

EndRecover(p) ==
    /\ pc[p] = "eRec"
    /\ IF keptD[p] THEN UNCHANGED <<folder, lockVars>>
       ELSE Remove(Rec(p), TRUE, Always)
    /\ pc' = [pc EXCEPT ![p] = "eRecRel"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, runVars, kills>>

EndRecoverRelease(p) ==
    /\ pc[p] = "eRecRel"
    /\ Release(Rec(p))
    /\ pc' = [pc EXCEPT ![p] = "idle"]
    /\ cur' = [cur EXCEPT ![p] = NoRun]
    /\ UNCHANGED <<mode, snap, vis, keptD, runVars, folder, kills>>

-----------------------------------------------------------------------------
(* The environment: SIGKILL, and time.                                     *)

\* SIGKILL: the operating system releases the process's locks; its TLC runs on.
Kill(p) ==
    /\ pc[p] # "idle"
    /\ kills < MaxKills
    /\ kills' = kills + 1
    /\ hnd' = [h \in Handles |-> IF h[1] = p THEN Closed ELSE hnd[h]]
    /\ holder' = [i \in Inodes |-> IF holder[i][1] = p THEN NoHandle ELSE holder[i]]
    /\ tlc' = IF cur[p] # NoRun /\ tlc[cur[p]] = "live"
              THEN [tlc EXCEPT ![cur[p]] = "orphan"] ELSE tlc
    /\ pc' = [pc EXCEPT ![p] = "idle"]
    /\ cur' = [cur EXCEPT ![p] = NoRun]
    /\ snap' = [snap EXCEPT ![p] = {}]
    /\ vis' = [vis EXCEPT ![p] = NoRun]
    /\ UNCHANGED <<mode, keptD, used, target, folder, lockFile, lockOld>>

\* A process is in the middle of a start on entry n, or has its lock file open.
Busy(n) ==
    \/ \E p \in Procs : cur[p] = n /\ pc[p] \in {"lock", "lock2", "rlock", "rlock2", "mkdir"}
    \/ \E h \in Handles : hnd[h].name = n /\ hnd[h].st # "closed" /\ h[2] = "vis"

\* An hour passes for the lock file of entry n.
AgeLock(n) ==
    /\ lockFile[n] # 0
    /\ ~lockOld[n]
    /\ Stall \/ ~Busy(n)
    /\ lockOld' = [lockOld EXCEPT ![n] = TRUE]
    /\ UNCHANGED <<procVars, runVars, folder, lockFile, holder, hnd, kills>>

-----------------------------------------------------------------------------
Step(p) ==
    \/ TakeLockOpen(p) \/ TakeLockOK(p) \/ TakeLockFail(p)
    \/ TakeRecoverLockOpen(p) \/ TakeRecoverLockOK(p) \/ TakeRecoverLockFail(p)
    \/ MakeFolder(p) \/ WriteRunJson(p)
    \/ (\E n \in RunIds : VisitOpen(p, n))
    \/ VisitLockOK(p) \/ VisitLockFail(p) \/ (\E age \in 0..2 : VisitAct(p, age))
    \/ VisitRelease(p) \/ VisitDone(p)
    \/ StartTLC(p) \/ TLCExit(p) \/ Settle(p)
    \/ EndOwn(p) \/ EndOwnRelease(p) \/ EndRecover(p) \/ EndRecoverRelease(p)

Choice(p) ==
    \/ (\E r \in RunIds, t \in RunIds \cup {NoRun} : CreateLockFile(p, r, t))
    \/ BeginSweep(p) \/ (\E all \in BOOLEAN : BeginClean(p, all))
    \/ TakeLockTimeout(p) \/ TakeRecoverLockTimeout(p) \/ AbortStart(p)
    \/ Kill(p)

Next ==
    \/ \E p \in Procs : Step(p) \/ Choice(p)
    \/ \E r \in RunIds : Checkpoint(r) \/ OrphanExit(r) \/ AgeLock(r)

Spec == Init /\ [][Next]_vars

\* For NothingLeft: every step of a command is taken in the end; a lock that keeps
\* becoming free is taken in the end; a sweep finds every folder old enough in the end;
\* lock files age; and sweeps keep coming.
Fairness ==
    /\ \A p \in Procs :
        /\ WF_vars(Step(p))
        /\ SF_vars(TakeLockOK(p)) /\ SF_vars(TakeRecoverLockOK(p)) /\ SF_vars(VisitLockOK(p))
        /\ SF_vars(BeginSweep(p))
        /\ \A n \in RunIds :
              SF_vars(VisitAct(p, 2) /\ mode[p] \in {"run", "sweep"} /\ vis[p] = n)
    /\ \A r \in RunIds : WF_vars(AgeLock(r))

FairSpec == Spec /\ Fairness

-----------------------------------------------------------------------------
(* Properties (03, K1).                                                    *)

Deleted(f) == folder[f].ex /\ ~folder'[f].ex

\* No folder is deleted while a TLC whose tlaup is alive works in it.
NoDeleteUnderTLC ==
    [][\A f \in RunIds : Deleted(f) => \A r \in Working(f) : tlc[r] # "live"]_vars

\* The exception R6 accepts under "Risks", stated on its own.  It does not hold: the
\* counterexample is the reach of a SIGKILL.
NoDeleteUnderOrphanTLC ==
    [][\A f \in RunIds : Deleted(f) => \A r \in Working(f) : tlc[r] # "orphan"]_vars

\* At most one TLC writes a run folder, unless the tlaup of one of them was killed.
OneTLCPerFolder ==
    \A f \in RunIds : \A r1, r2 \in Working(f) :
        r1 # r2 => (tlc[r1] = "orphan" \/ tlc[r2] = "orphan")

\* The same without the exception.  It does not hold: also the reach of a SIGKILL.
OneTLCPerFolderAfterKill == \A f \in RunIds : Cardinality(Working(f)) <= 1

SweepOldStep(f) ==
    \E p \in Procs : VisitAct(p, 2) /\ mode[p] \in {"run", "sweep"} /\ vis[p] = f
CleanAllStep(f) == \E p \in Procs, a \in 0..2 : VisitAct(p, a) /\ mode[p] = "cleanAll" /\ vis[p] = f
RecoverEndStep(f) == \E p \in Procs : EndRecover(p) /\ target[cur[p]] = f
OwnEndStep(f) == \E p \in Procs : EndOwn(p) /\ cur[p] = f

\* A kept folder with a checkpoint is removed only by a sweep that finds it over 30 days
\* old, by `cache clean --all`, and by the end of a run that resumed from it and finished.
KeptSurvives ==
    [][\A f \in RunIds :
        (Deleted(f) /\ folder[f].json = "kept" /\ folder[f].chk)
            => (SweepOldStep(f) \/ CleanAllStep(f) \/ RecoverEndStep(f))]_vars

\* The same for every folder that holds a checkpoint, settled or not, whose own run is not
\* the one ending (finding K1-4).
CheckpointSurvives ==
    [][\A f \in RunIds :
        (Deleted(f) /\ folder[f].json # "none" /\ folder[f].chk)
            => (SweepOldStep(f) \/ CleanAllStep(f) \/ RecoverEndStep(f) \/ OwnEndStep(f))]_vars

Holding(n, states) == {h \in Handles : hnd[h].st \in states /\ hnd[h].name = n}

\* No two lock objects hold the lock of one name, counting an object until it has removed
\* the name.  After that it does nothing but release (R6, "End").
LockExclusive == \A n \in RunIds : Cardinality(Holding(n, {"held"})) <= 1

\* As 03 first worded it, counting an object until it releases.  It does not hold in the
\* instant between removing a lock file and releasing its lock (finding K1-1).
LockExclusiveUntilRelease == \A n \in RunIds : Cardinality(Holding(n, {"held", "gone"})) <= 1

\* A held lock is on the file that is at the name.
HeldIsCurrent == \A h \in Handles : hnd[h].st = "held" => lockFile[hnd[h].name] = hnd[h].ino

\* The folder of a live run that has made it is protected by a current lock.
LiveRunLocked ==
    \A p \in Procs :
        mode[p] = "run" /\ pc[p] \in {"json", "visit", "visit2", "visit3", "visit4", "tlc", "settle"}
            => hnd[Own(p)].st = "held" /\ lockFile[cur[p]] = hnd[Own(p)].ino

\* The model never runs out of files; if it did, behaviours would be cut off unseen.
PoolEnough == FreeInodes # {}

\* Processes and run ids are interchangeable.  SymAll is for models in which every process
\* may do everything; SymIds for the others.  Neither is used when checking NothingLeft.
SymAll == Permutations(Procs) \cup Permutations(RunIds)
SymIds == Permutations(RunIds)

\* Every folder and every lock file is removed in the end.
NothingLeft ==
    \A n \in RunIds : <>[](~folder[n].ex) /\ []<>(lockFile[n] = 0)

=============================================================================
