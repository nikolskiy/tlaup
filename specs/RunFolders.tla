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
(* Revised 2026-11-20 for decisions D51 to D53: a killed tlaup's TLC       *)
(* inherits the run's locks where the system allows it (LockFollowsTLC)    *)
(* and always ends in the end (the lifeline agent); keeping a run folder   *)
(* is asked for per run (keep); a checkpoint can be left half written.     *)
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
    CleanSparesCheckpoint, \* TRUE: `cache clean` without --all leaves an unsettled folder
                           \* that holds a resumable checkpoint, as the sweep does (finding
                           \* K1-4; decision D49 chose TRUE)
    LockFollowsTLC,        \* TRUE: the JVM holds a duplicate of the run's lock descriptors, so
                           \* a SIGKILL of tlaup leaves the locks held until its TLC ends
                           \* (Linux and macOS, decision D51); FALSE: Windows, network file
                           \* systems, where only the lifeline ends the orphan TLC
    UnlinkOnRelease,       \* TRUE: the lock library deletes the file at the name when it
                           \* releases (filelock 3.20.4 to 3.29.4, question 30); ruled out by
                           \* the lower bound filelock>=4.2.1
    KeptMeansKeep          \* TRUE: settle writes "keep": true when it keeps a folder, and a
                           \* resume of a folder that says keep or kept is a kept run (R6, the
                           \* fix of finding FC1 of the 2026-11-20 review); FALSE: the rule before

ASSUME /\ Runners \subseteq Procs /\ Cleaners \subseteq Procs
       /\ Recheck \in BOOLEAN /\ HourRule \in BOOLEAN /\ Stall \in BOOLEAN
       /\ DeleteMayFail \in BOOLEAN /\ CleanSparesCheckpoint \in BOOLEAN
       /\ LockFollowsTLC \in BOOLEAN /\ UnlinkOnRelease \in BOOLEAN /\ KeptMeansKeep \in BOOLEAN
       /\ MaxKills \in Nat

VARIABLES
    pc,        \* where each process is in its command
    cur,       \* the run id of the run a process is in, or NoRun
    mode,      \* what the process is doing: "run", "sweep", "clean", "cleanAll"
    snap,      \* entries of runs/ a sweep or clean has listed and not visited yet
    vis,       \* the entry being visited
    keptD,     \* what settle decided: "kept"; "fin", the run finished; "drop", deleted for
               \* another reason (not asked to keep, no complete checkpoint, an abort)
    used,      \* run ids already given out; an id is never used twice
    target,    \* per run: the run folder its -recover names, or NoRun
    keep,      \* per run: started with --keep (or tlc.keep); recorded in run.json
    tlc,       \* per run: its TLC process: "none", "live", "orphan" (its tlaup was killed), "done"
    folder,    \* per run id: the run folder
    lockFile,  \* per run id: the file at <id>.lock, or 0
    lockOld,   \* per run id: that file is more than an hour old
    holder,    \* per file: the lock object that holds its flock, or NoHandle
    hnd,       \* per lock object: closed, open on a file, holding it, or holding it after
               \* removing the name ("gone")
    kills      \* tlaups killed so far

procVars == <<pc, cur, mode, snap, vis, keptD>>
runVars  == <<used, target, keep, tlc>>
lockVars == <<lockFile, lockOld, holder, hnd>>
vars == <<pc, cur, mode, snap, vis, keptD, used, target, keep, tlc, folder,
          lockFile, lockOld, holder, hnd, kills>>

NoRun == "none"
Roles == {"own", "rec", "vis"}      \* a process's lock objects: its run, the recovered run, a visit
\* The duplicates a run's TLC inherited (D51): of the run's own lock and of the recovered one.
\* They count only once the run's tlaup has been killed; until then the JVM's copy and tlaup's
\* are one lock, held by tlaup's object.
TLCRoles == {"tlc", "tlcrec"}
Handles == (Procs \X Roles) \cup (RunIds \X TLCRoles)
NoHandle == <<"none", "none">>
Own(p) == <<p, "own">>
Rec(p) == <<p, "rec">>
Vis(p) == <<p, "vis">>
TLCOwn(r) == <<r, "tlc">>
TLCRec(r) == <<r, "tlcrec">>

Closed == [st |-> "closed", name |-> NoRun, ino |-> 0]
NoFolder == [ex |-> FALSE, json |-> "none", chk |-> "no"]
\* folder.json: "none" no run.json; "started" written at the start, never settled as kept;
\*              "kept" settled with "kept": true and a fresh "ended".
\* folder.chk:  "no" no checkpoint; "tmp" TLC is writing one, or was stopped while writing
\*              one (".tmp" files are there); "ok" a complete checkpoint (queue.chkpt and
\*              vars.chkpt, no ".tmp" file; decision D52).
\* A folder's age is not kept as state.  The sweep is the only reader of it, and each visit
\* chooses what it finds: 0 young, 1 older than a day, 2 older than 30 days.  Since D53 only a
\* folder with no run.json is removed by age.

PCs == {"idle", "lock", "lock2", "rlock", "rlock2", "mkdir", "json",
        "visit", "visit2", "visit3", "visit4", "tlc", "settle",
        "eOwn", "eOwnRel", "eRec", "eRecRel"}

TypeOK ==
    /\ pc \in [Procs -> PCs]
    /\ cur \in [Procs -> RunIds \cup {NoRun}]
    /\ mode \in [Procs -> {"run", "sweep", "clean", "cleanAll"}]
    /\ snap \in [Procs -> SUBSET RunIds]
    /\ vis \in [Procs -> RunIds \cup {NoRun}]
    /\ keptD \in [Procs -> {"kept", "fin", "drop"}]
    /\ used \subseteq RunIds
    /\ target \in [RunIds -> RunIds \cup {NoRun}]
    /\ keep \in [RunIds -> BOOLEAN]
    /\ tlc \in [RunIds -> {"none", "live", "orphan", "done"}]
    /\ folder \in [RunIds -> [ex : BOOLEAN, json : {"none", "started", "kept"},
                              chk : {"no", "tmp", "ok"}]]
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
    /\ keptD = [p \in Procs |-> "drop"]
    /\ used = {}
    /\ target = [r \in RunIds |-> NoRun]
    /\ keep = [r \in RunIds |-> FALSE]
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

\* With UnlinkOnRelease the library also unlinks the name as it releases, whatever file is at
\* the name by then (filelock 3.20.4 to 3.29.4, research 30).  Only a visit's lock is a
\* filelock FileLock; a run's own and recovered locks are tlaup's own descriptors (D51), whose
\* release never unlinks.
Release(h) ==
    /\ hnd[h].st \in {"held", "gone"}
    /\ holder' = [holder EXCEPT ![hnd[h].ino] = NoHandle]
    /\ hnd' = [hnd EXCEPT ![h] = Closed]
    /\ IF UnlinkOnRelease /\ h[2] = "vis"
       THEN /\ lockFile' = [lockFile EXCEPT ![hnd[h].name] = 0]
            /\ lockOld' = [lockOld EXCEPT ![hnd[h].name] = FALSE]
       ELSE UNCHANGED <<lockFile, lockOld>>

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

\* k: the run was started with --keep.  A run that resumes from a folder whose run asked to
\* be kept is a kept run too (D53: a kept folder goes only when a resume from it finishes),
\* and so, with KeptMeansKeep, is one that resumes from a folder that was kept.
CreateLockFile(p, r, t, k) ==
    /\ pc[p] = "idle"
    /\ p \in Runners
    /\ r \notin used
    /\ t = NoRun \/ (t \in RunIds /\ t # r /\ folder[t].ex)   \* -recover PATH inside runs/<t>/
    /\ (t # NoRun /\ (keep[t] \/ (KeptMeansKeep /\ folder[t].json = "kept"))) => k
    /\ lockFile[r] = 0
    /\ FreeInodes # {}
    /\ lockFile' = [lockFile EXCEPT ![r] = NewInode]
    /\ lockOld' = [lockOld EXCEPT ![r] = FALSE]
    /\ used' = used \cup {r}
    /\ target' = [target EXCEPT ![r] = t]
    /\ keep' = [keep EXCEPT ![r] = k]
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
    /\ keptD' = [keptD EXCEPT ![p] = "drop"]
    /\ UNCHANGED <<cur, mode, snap, vis, runVars, folder, lockVars, kills>>

MakeFolder(p) ==
    /\ pc[p] = "mkdir"
    /\ folder' = [folder EXCEPT ![cur[p]] = [ex |-> TRUE, json |-> "none", chk |-> "no"]]
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

\* An unsettled folder that can be resumed: its run asked to be kept and its checkpoint is
\* complete (D52, D53).
Resumable(n) == keep[n] /\ folder[n].chk = "ok"

\* R6, "sweep" (D53): a kept folder never; an unsettled one at once, unless it is resumable;
\* one without run.json after 30 days.
SweepRemoves(n, age) ==
    LET f == folder[n] IN
    /\ f.ex
    /\ CASE f.json = "kept" -> FALSE
         [] f.json = "started" -> ~Resumable(n)
         [] OTHER -> age = 2

\* R6, `cache clean`: every folder with a run.json that is not kept and, with
\* CleanSparesCheckpoint (decision D49), that is not unsettled and resumable; with --all
\* every folder.  `cache clean <run-id>` is --all for one entry.
CleanRemoves(n, all) ==
    LET f == folder[n] IN
    /\ f.ex
    /\ all \/ (f.json = "started" /\ ~(CleanSparesCheckpoint /\ Resumable(n)))

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
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, used, target, keep, folder, lockVars, kills>>

\* TLC writes a checkpoint, at any moment or never (research 25: every 30 minutes by
\* default).  It writes ".tmp" files first and then commits them one by one; a TLC stopped in
\* between leaves "tmp", whatever stopped it (research 35).  A new checkpoint replaces a
\* complete one the same way.  A TLC whose folder was deleted writes nothing: it crashes
\* (research 17).
CheckpointBegin(r) ==
    /\ tlc[r] \in {"live", "orphan"}
    /\ folder[CheckpointFolder(r)].ex
    /\ folder[CheckpointFolder(r)].chk # "tmp"
    /\ folder' = [folder EXCEPT ![CheckpointFolder(r)].chk = "tmp"]
    /\ UNCHANGED <<procVars, runVars, lockVars, kills>>

CheckpointEnd(r) ==
    /\ tlc[r] \in {"live", "orphan"}
    /\ folder[CheckpointFolder(r)].ex
    /\ folder[CheckpointFolder(r)].chk = "tmp"
    /\ folder' = [folder EXCEPT ![CheckpointFolder(r)].chk = "ok"]
    /\ UNCHANGED <<procVars, runVars, lockVars, kills>>

TLCExit(p) ==                         \* finished, violated, crashed or stopped by a signal
    /\ pc[p] = "tlc"
    /\ tlc' = [tlc EXCEPT ![cur[p]] = "done"]
    /\ pc' = [pc EXCEPT ![p] = "settle"]
    /\ UNCHANGED <<cur, mode, snap, vis, keptD, used, target, keep, folder, lockVars, kills>>

\* The TLC of a killed tlaup ends: the lifeline agent stops the JVM (D51).  The operating
\* system then releases the lock descriptors the JVM inherited; nothing is unlinked.
OrphanExit(r) ==
    /\ tlc[r] = "orphan"
    /\ tlc' = [tlc EXCEPT ![r] = "done"]
    /\ hnd' = [h \in Handles |-> IF h \in {TLCOwn(r), TLCRec(r)} THEN Closed ELSE hnd[h]]
    /\ holder' = [i \in Inodes |->
                    IF holder[i] \in {TLCOwn(r), TLCRec(r)} THEN NoHandle ELSE holder[i]]
    /\ UNCHANGED <<procVars, used, target, keep, folder, lockFile, lockOld, kills>>

\* R6, "Settle" (D52, D53): kept when the run did not finish, it asked to be kept, and a
\* complete checkpoint is there.  After -recover the checkpoint is looked for in the
\* recovered folder.
SettledFolder(p) == IF RecHeld(p) THEN target[cur[p]] ELSE cur[p]

Settle(p) ==
    /\ pc[p] = "settle"
    /\ LET r == cur[p]
           f == SettledFolder(p)
       IN \E finished \in (IF tlc[r] = "done" THEN BOOLEAN ELSE {FALSE}) :
            LET k == ~finished /\ keep[r] /\ folder[f].ex /\ folder[f].chk = "ok" IN
            /\ keptD' = [keptD EXCEPT ![p] = IF k THEN "kept" ELSE IF finished THEN "fin" ELSE "drop"]
            /\ folder' = IF k THEN [folder EXCEPT ![f].json = "kept"] ELSE folder
            /\ keep' = IF k /\ KeptMeansKeep THEN [keep EXCEPT ![f] = TRUE] ELSE keep
    /\ pc' = [pc EXCEPT ![p] = "eOwn"]
    /\ UNCHANGED <<cur, mode, snap, vis, used, target, tlc, lockVars, kills>>

\* R6, "End".  The run's own folder: kept and released, or deleted, its lock file removed
\* while the lock is held, and released.  Then the same for the recovered folder.
KeepOwn(p) == keptD[p] = "kept" /\ ~RecHeld(p)

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
    /\ IF keptD[p] = "kept" THEN UNCHANGED <<folder, lockVars>>
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

\* SIGKILL: the operating system closes the process's descriptors; its TLC runs on until the
\* lifeline ends it (OrphanExit).  With LockFollowsTLC the TLC holds duplicates of the run's
\* own lock and of the recovered folder's lock (D51), so those locks stay held, now by the
\* TLC; every other lock of the process is released.
Kill(p) ==
    /\ pc[p] # "idle"
    /\ kills < MaxKills
    /\ kills' = kills + 1
    /\ LET r == cur[p]
           follow == LockFollowsTLC /\ r # NoRun /\ tlc[r] = "live"
       IN /\ hnd' = [h \in Handles |->
                       IF follow /\ h = TLCOwn(r) THEN hnd[Own(p)]
                       ELSE IF follow /\ h = TLCRec(r) THEN hnd[Rec(p)]
                       ELSE IF h[1] = p THEN Closed ELSE hnd[h]]
          /\ holder' = [i \in Inodes |->
                          IF follow /\ holder[i] = Own(p) THEN TLCOwn(r)
                          ELSE IF follow /\ holder[i] = Rec(p) THEN TLCRec(r)
                          ELSE IF holder[i][1] = p THEN NoHandle ELSE holder[i]]
          /\ tlc' = IF r # NoRun /\ tlc[r] = "live" THEN [tlc EXCEPT ![r] = "orphan"] ELSE tlc
    /\ pc' = [pc EXCEPT ![p] = "idle"]
    /\ cur' = [cur EXCEPT ![p] = NoRun]
    /\ snap' = [snap EXCEPT ![p] = {}]
    /\ vis' = [vis EXCEPT ![p] = NoRun]
    /\ UNCHANGED <<mode, keptD, used, target, keep, folder, lockFile, lockOld>>

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
    \/ (\E r \in RunIds, t \in RunIds \cup {NoRun}, k \in BOOLEAN : CreateLockFile(p, r, t, k))
    \/ BeginSweep(p) \/ (\E all \in BOOLEAN : BeginClean(p, all))
    \/ TakeLockTimeout(p) \/ TakeRecoverLockTimeout(p) \/ AbortStart(p)
    \/ Kill(p)

Next ==
    \/ \E p \in Procs : Step(p) \/ Choice(p)
    \/ \E r \in RunIds : CheckpointBegin(r) \/ CheckpointEnd(r) \/ OrphanExit(r) \/ AgeLock(r)

Spec == Init /\ [][Next]_vars

\* For NothingLeft: every step of a command is taken in the end; a lock that keeps
\* becoming free is taken in the end; a sweep finds every folder old enough in the end;
\* lock files age; sweeps keep coming; and the TLC of a killed tlaup ends (the lifeline, D51).
Fairness ==
    /\ \A p \in Procs :
        /\ WF_vars(Step(p))
        /\ SF_vars(TakeLockOK(p)) /\ SF_vars(TakeRecoverLockOK(p)) /\ SF_vars(VisitLockOK(p))
        /\ SF_vars(BeginSweep(p))
        /\ \A n \in RunIds :
              SF_vars(VisitAct(p, 2) /\ mode[p] \in {"run", "sweep"} /\ vis[p] = n)
    /\ \A r \in RunIds : WF_vars(AgeLock(r)) /\ WF_vars(OrphanExit(r))

FairSpec == Spec /\ Fairness

-----------------------------------------------------------------------------
(* Properties (03, K1).                                                    *)

Deleted(f) == folder[f].ex /\ ~folder'[f].ex

\* No folder is deleted while a TLC works in it, the TLC of a killed tlaup included.  Before
\* D51 this carried the exception "unless its tlaup was killed"; with LockFollowsTLC it holds
\* without it.
NoDeleteUnderTLC ==
    [][\A f \in RunIds : Deleted(f) => Working(f) = {}]_vars

\* The weaker form, with the exception, for the systems where the lock does not follow the
\* TLC (Windows, network file systems): what the lifeline alone gives.
NoDeleteUnderLiveTLC ==
    [][\A f \in RunIds : Deleted(f) => \A r \in Working(f) : tlc[r] # "live"]_vars

\* At most one TLC writes a run folder.  Before D51 this carried the same exception.
OneTLCPerFolder == \A f \in RunIds : Cardinality(Working(f)) <= 1

\* The weaker form, for the systems where the lock does not follow the TLC.
OneTLCPerFolderUnlessKilled ==
    \A f \in RunIds : \A r1, r2 \in Working(f) :
        r1 # r2 => (tlc[r1] = "orphan" \/ tlc[r2] = "orphan")

CleanAllStep(f) == \E p \in Procs, a \in 0..2 : VisitAct(p, a) /\ mode[p] = "cleanAll" /\ vis[p] = f
\* The end of a run that resumed from f and finished.
ResumeFinishedStep(f) == \E p \in Procs : EndRecover(p) /\ target[cur[p]] = f /\ keptD[p] = "fin"
OwnFinishedStep(f) == \E p \in Procs : EndOwn(p) /\ cur[p] = f /\ keptD[p] = "fin"

\* A kept folder with a complete checkpoint is removed only by `cache clean --all` (or
\* `cache clean <run-id>`, which is the same for one entry) and by the end of a run that
\* resumed from it and finished.  No sweep removes it, whatever its age (D53).
KeptSurvives ==
    [][\A f \in RunIds :
        (Deleted(f) /\ folder[f].json = "kept" /\ folder[f].chk = "ok")
            => (CleanAllStep(f) \/ ResumeFinishedStep(f))]_vars

\* The same for every folder of a run that asked to be kept and holds a complete checkpoint,
\* settled or not, unless its own run finished (finding K1-4, D49, D53).
CheckpointSurvives ==
    [][\A f \in RunIds :
        (Deleted(f) /\ folder[f].json # "none" /\ keep[f] /\ folder[f].chk = "ok")
            => (CleanAllStep(f) \/ ResumeFinishedStep(f) \/ OwnFinishedStep(f))]_vars

\* No folder is kept because of a checkpoint that is not complete (D52): settle keeps only a
\* complete one.  The sweep and `cache clean` spare an unsettled folder only by Resumable,
\* the same test.
KeptIsComplete ==
    [][\A p \in Procs : (Settle(p) /\ keptD'[p] = "kept") => folder[SettledFolder(p)].chk = "ok"]_vars

Holding(n, states) == {h \in Handles : hnd[h].st \in states /\ hnd[h].name = n}

\* No two lock objects hold the lock of one name, counting an object until it has removed
\* the name.  After that it does nothing but release (R6, "End").
LockExclusive == \A n \in RunIds : Cardinality(Holding(n, {"held"})) <= 1

\* As 03 first worded it, counting an object until it releases.  It does not hold in the
\* instant between removing a lock file and releasing its lock (finding K1-1).
LockExclusiveUntilRelease == \A n \in RunIds : Cardinality(Holding(n, {"held", "gone"})) <= 1

\* A held lock is on the file that is at the name.
HeldIsCurrent == \A h \in Handles : hnd[h].st = "held" => lockFile[hnd[h].name] = hnd[h].ino

\* The folder of a live run that has made it is protected by a current lock, and with
\* LockFollowsTLC so is the folder of a TLC whose tlaup was killed.
LiveRunLocked ==
    /\ \A p \in Procs :
        mode[p] = "run" /\ pc[p] \in {"json", "visit", "visit2", "visit3", "visit4", "tlc", "settle"}
            => hnd[Own(p)].st = "held" /\ lockFile[cur[p]] = hnd[Own(p)].ino
    /\ LockFollowsTLC =>
        \A r \in RunIds : tlc[r] = "orphan"
            => hnd[TLCOwn(r)].st = "held" /\ lockFile[r] = hnd[TLCOwn(r)].ino

\* The model never runs out of files; if it did, behaviours would be cut off unseen.
PoolEnough == FreeInodes # {}

\* Processes and run ids are interchangeable.  SymAll is for models in which every process
\* may do everything; SymIds for the others.  Neither is used when checking NothingLeft.
SymAll == Permutations(Procs) \cup Permutations(RunIds)
SymIds == Permutations(RunIds)

\* A folder that stays on purpose: kept, or unsettled and resumable (D53).  Nothing removes
\* it but the user.
StaysOnPurpose(n) ==
    folder[n].ex /\ (folder[n].json = "kept" \/ (folder[n].json = "started" /\ Resumable(n)))

\* Every other folder and lock file is removed in the end: a run that did not ask to be kept
\* leaves nothing, also when its tlaup was killed.
NothingLeft ==
    \A n \in RunIds : <>[](~folder[n].ex \/ StaysOnPurpose(n))
                      /\ []<>(lockFile[n] = 0 \/ StaysOnPurpose(n))

=============================================================================
