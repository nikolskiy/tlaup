------------------------------ MODULE ToolStore ------------------------------
(***************************************************************************)
(* K2 of docs/design/03-run-stages-and-specs.md: the tools store of        *)
(* docs/design/12-tools-and-downloads.md (V1, V3, V4, V5, V11, V12).       *)
(* Several tlaup processes install, upgrade, uninstall and pin under the   *)
(* store lock, download outside it into their own folder under .tmp/, and  *)
(* read the pin and a jar without any lock.  A process can be killed at    *)
(* any step, and upstream can publish a new build of a name at any moment. *)
(*                                                                         *)
(* A build is a name and a version of its bytes: <<name, v>>.  The store's *)
(* folder names (ids) are not modelled: an id stands for one build.        *)
(*                                                                         *)
(* What the model is, what it leaves out, its bounds and its results are   *)
(* in README.md beside this file.                                          *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS
    Procs,           \* tlaup processes
    Names,           \* names a build is installed as ("rolling", "v1.8.0")
    MaxVer,          \* upstream publishes versions 1..MaxVer of each name's bytes
    MaxKills,        \* how many times a tlaup is killed with SIGKILL
    ReadUnderLock,   \* TRUE: what a mutation decides on (the pin, whether a build is
                     \* installed) is read again once the store lock is held (finding K2-1)
    UnpinFirst       \* TRUE: uninstall clears the pin before it removes the pinned build
                     \* (finding K2-2, the option not taken: decision D50 keeps FALSE)

ASSUME /\ MaxVer \in Nat \ {0} /\ MaxKills \in Nat
       /\ ReadUnderLock \in BOOLEAN /\ UnpinFirst \in BOOLEAN

Builds == Names \X (1..MaxVer)
None == <<"none", 0>>
NoProc == "none"

VARIABLES
    published,   \* per name: the version upstream publishes now
    copies,      \* per build: how many folders of the store hold it (0 or 1 if NoDuplicate holds)
    pin,         \* the pinned build, or None
    storeLock,   \* the process holding <cache>/tool/.lock, or NoProc
    tmpd,        \* per process: its download folder under .tmp/ and that folder's lock
    tmpo,        \* per process: the folder of a build on its way out, and its lock
    left,        \* folders under .tmp/ whose owner was killed
    pc,          \* where each process is in its command
    loc,         \* what each process remembers while its command runs:
                 \*   cmd      the command
                 \*   nm       the name an install or upgrade was asked for
                 \*   bld      the build the command works on (downloaded, or named)
                 \*   old      upgrade: the installed build that was compared with upstream
                 \*   seenPin  the pin as the command read it before it took the lock
                 \*   removed  uninstall: the build was removed
                 \*   rd       a reader: the pin it read
    kills,
    killedInLock \* a tlaup was killed while it held the store lock (ghost)

vars == <<published, copies, pin, storeLock, tmpd, tmpo, left, pc, loc, kills, killedInLock>>

NoTmp == [lock |-> FALSE, st |-> "none"]
\* tmpd.st: "none" no folder; "partial" a download in progress; "ready" a verified jar and
\* its build.json.  tmpo.st: "none" or "out", a removed build being deleted.
NoLoc == [cmd |-> "none", nm |-> "none", bld |-> None, old |-> None, seenPin |-> None,
          removed |-> FALSE, rd |-> None]

Installed(b) == copies[b] > 0
InstalledOf(n) == {b \in Builds : b[1] = n /\ Installed(b)}
Newest(n) == CHOOSE b \in InstalledOf(n) : \A c \in InstalledOf(n) : c[2] <= b[2]
Current(n) == <<n, published[n]>>

TypeOK ==
    /\ published \in [Names -> 1..MaxVer]
    /\ copies \in [Builds -> 0..2]
    /\ pin \in Builds \cup {None}
    /\ storeLock \in Procs \cup {NoProc}
    /\ tmpd \in [Procs -> [lock : BOOLEAN, st : {"none", "partial", "ready"}]]
    /\ tmpo \in [Procs -> [lock : BOOLEAN, st : {"none", "out"}]]
    /\ left \in 0..(2 * MaxKills)
    /\ pc \in [Procs -> {"idle", "tLock", "tMkdir", "dl", "sLock", "locked", "added", "rm",
                         "rmDel", "unpin", "sUnlock", "tUnlock", "rCheck", "rOpen"}]
    /\ loc \in [Procs -> [cmd : {"none", "install", "upgrade", "uninstall", "pin", "read"},
                          nm : Names \cup {"none"}, bld : Builds \cup {None},
                          old : Builds \cup {None}, seenPin : Builds \cup {None},
                          removed : BOOLEAN, rd : Builds \cup {None}]]
    /\ kills \in 0..MaxKills
    /\ killedInLock \in BOOLEAN

Init ==
    /\ published = [n \in Names |-> 1]
    /\ copies = [b \in Builds |-> 0]
    /\ pin = None
    /\ storeLock = NoProc
    /\ tmpd = [p \in Procs |-> NoTmp]
    /\ tmpo = [p \in Procs |-> NoTmp]
    /\ left = 0
    /\ pc = [p \in Procs |-> "idle"]
    /\ loc = [p \in Procs |-> NoLoc]
    /\ kills = 0
    /\ killedInLock = FALSE

Goto(p, where) == pc' = [pc EXCEPT ![p] = where]
\* The command is over: the process forgets what it remembered.
Done(p) == pc' = [pc EXCEPT ![p] = "idle"] /\ loc' = [loc EXCEPT ![p] = NoLoc]

-----------------------------------------------------------------------------
(* Commands start without the lock: they look at the store and at GitHub.  *)

\* `tool install NAME` (V12).  What upstream publishes is already installed: nothing is
\* downloaded, and the command goes on to pin it if nothing is pinned.
StartInstall(p, n) ==
    /\ pc[p] = "idle"
    /\ loc' = [loc EXCEPT ![p] = [NoLoc EXCEPT !.cmd = "install", !.nm = n, !.seenPin = pin,
                                               !.bld = IF Installed(Current(n)) THEN Current(n) ELSE None]]
    /\ Goto(p, IF Installed(Current(n)) THEN "sLock" ELSE "tLock")
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpd, tmpo, left, kills, killedInLock>>

\* `tool upgrade NAME` (V4): compare the newest installed build of the name with upstream.
StartUpgrade(p, n) ==
    /\ pc[p] = "idle"
    /\ InstalledOf(n) # {}
    /\ Newest(n) # Current(n)
    /\ loc' = [loc EXCEPT ![p] = [NoLoc EXCEPT !.cmd = "upgrade", !.nm = n, !.seenPin = pin,
                                               !.old = Newest(n)]]
    /\ Goto(p, "tLock")
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpd, tmpo, left, kills, killedInLock>>

\* `tool uninstall BUILD` (V3) and `tool pin BUILD` (V4): the build is found first.
StartUninstall(p, b) ==
    /\ pc[p] = "idle"
    /\ Installed(b)
    /\ loc' = [loc EXCEPT ![p] = [NoLoc EXCEPT !.cmd = "uninstall", !.bld = b, !.seenPin = pin]]
    /\ Goto(p, "sLock")
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpd, tmpo, left, kills, killedInLock>>

StartPin(p, b) ==
    /\ pc[p] = "idle"
    /\ Installed(b)
    /\ loc' = [loc EXCEPT ![p] = [NoLoc EXCEPT !.cmd = "pin", !.bld = b]]
    /\ Goto(p, "sLock")
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpd, tmpo, left, kills, killedInLock>>

-----------------------------------------------------------------------------
(* The download, outside the store lock (V5, V11).                         *)

\* The folder's lock file is created and its lock taken before the folder is made.
TmpLock(p) ==
    /\ pc[p] = "tLock"
    /\ tmpd' = [tmpd EXCEPT ![p].lock = TRUE]
    /\ Goto(p, "tMkdir")
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpo, left, loc, kills, killedInLock>>

TmpMkdir(p) ==
    /\ pc[p] = "tMkdir"
    /\ tmpd' = [tmpd EXCEPT ![p].st = "partial"]
    /\ Goto(p, "dl")
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpo, left, loc, kills, killedInLock>>

\* The jar that arrives is what upstream publishes at that moment.
Download(p) ==
    /\ pc[p] = "dl"
    /\ tmpd' = [tmpd EXCEPT ![p].st = "ready"]
    /\ loc' = [loc EXCEPT ![p].bld = Current(loc[p].nm)]
    /\ Goto(p, "sLock")
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpo, left, kills, killedInLock>>

\* A failed download, or a store lock that cannot be had in 60 seconds (StoreLocked): the
\* folder is deleted, then its lock released.
GiveUp(p) ==
    /\ \/ pc[p] = "dl"
       \/ pc[p] = "sLock" /\ storeLock # NoProc
    /\ tmpd' = [tmpd EXCEPT ![p].st = "none"]
    /\ IF tmpd[p].lock THEN Goto(p, "tUnlock") /\ UNCHANGED loc ELSE Done(p)
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpo, left, kills, killedInLock>>

TmpUnlock(p) ==
    /\ pc[p] = "tUnlock"
    /\ tmpd' = [tmpd EXCEPT ![p] = NoTmp]
    /\ Done(p)
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpo, left, kills, killedInLock>>

-----------------------------------------------------------------------------
(* Under the store lock.                                                   *)

StoreLock(p) ==
    /\ pc[p] = "sLock"
    /\ storeLock = NoProc
    /\ storeLock' = p
    /\ Goto(p, "locked")
    /\ UNCHANGED <<published, copies, pin, tmpd, tmpo, left, loc, kills, killedInLock>>

\* V11: whoever holds the store lock goes through .tmp/ and removes each folder whose own
\* lock it can take, which means its owner is gone.
CleanupLeft(p) ==
    /\ pc[p] = "locked"
    /\ left > 0
    /\ left' = left - 1
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpd, tmpo, pc, loc, kills, killedInLock>>

\* The same step meeting the folder of a process that is alive.  It is enabled only when
\* that folder exists and its lock is free, which TmpLockedWhileThere says never happens.
CleanupLive(p, q) ==
    /\ pc[p] = "locked"
    /\ q # p
    /\ \/ /\ tmpd[q].st # "none" /\ ~tmpd[q].lock
          /\ tmpd' = [tmpd EXCEPT ![q].st = "none"]
          /\ UNCHANGED tmpo
       \/ /\ tmpo[q].st # "none" /\ ~tmpo[q].lock
          /\ tmpo' = [tmpo EXCEPT ![q].st = "none"]
          /\ UNCHANGED tmpd
    /\ UNCHANGED <<published, copies, pin, storeLock, left, pc, loc, kills, killedInLock>>

\* An install that found its build installed has downloaded nothing.
FoundInstalled(p) == loc[p].cmd = "install" /\ tmpd[p].st = "none"

\* store.add: a build with the same name and bytes is there, and the copy is discarded;
\* or the folder is moved into place with one rename.  Always decided under the lock (V1).
\* An install that downloaded nothing has nothing to add.
Add(p) ==
    /\ pc[p] = "locked"
    /\ loc[p].cmd \in {"install", "upgrade"}
    /\ ~(ReadUnderLock /\ FoundInstalled(p) /\ ~Installed(loc[p].bld))
    /\ copies' = IF Installed(loc[p].bld) \/ tmpd[p].st = "none"
                 THEN copies ELSE [copies EXCEPT ![loc[p].bld] = 1]
    /\ tmpd' = [tmpd EXCEPT ![p].st = "none"]
    /\ Goto(p, "added")
    /\ UNCHANGED <<published, pin, storeLock, tmpo, left, loc, kills, killedInLock>>

\* The build an install found installed has been removed by the time it holds the lock:
\* it lets the lock go and starts again, this time with a download (finding K2-5).
StartAgain(p) ==
    /\ pc[p] = "locked"
    /\ ReadUnderLock /\ FoundInstalled(p) /\ ~Installed(loc[p].bld)
    /\ storeLock' = NoProc
    /\ loc' = [loc EXCEPT ![p].bld = None]
    /\ Goto(p, "tLock")
    /\ UNCHANGED <<published, copies, pin, tmpd, tmpo, left, kills, killedInLock>>

PinNow(p) == IF ReadUnderLock THEN pin ELSE loc[p].seenPin

\* install: pin the build if nothing is pinned.  upgrade: move the pin if it named the
\* build that is replaced.
PinStep(p) ==
    /\ pc[p] = "added"
    /\ IF loc[p].cmd = "install"
       THEN /\ pin' = IF PinNow(p) = None THEN loc[p].bld ELSE pin
            /\ Goto(p, "sUnlock")
       ELSE /\ pin' = IF PinNow(p) = loc[p].old THEN loc[p].bld ELSE pin
            /\ Goto(p, "rm")
    /\ UNCHANGED <<published, copies, storeLock, tmpd, tmpo, left, loc, kills, killedInLock>>

\* The build to remove: upgrade removes the build it compared, uninstall the one named.
Outgoing(p) == IF loc[p].cmd = "upgrade" THEN loc[p].old ELSE loc[p].bld

\* store.remove, first half: one rename takes the build's folder out of the store into
\* .tmp/, under a lock of its own.  A build that is no longer there is not removed.
RenameOut(p) ==
    /\ \/ pc[p] = "rm"
       \/ pc[p] = "locked" /\ loc[p].cmd = "uninstall" /\ ~UnpinFirst
    /\ LET b == Outgoing(p)
           there == Installed(b) /\ (loc[p].cmd = "upgrade" => b # loc[p].bld)
       IN /\ copies' = IF there THEN [copies EXCEPT ![b] = @ - 1] ELSE copies
          /\ tmpo' = IF there THEN [tmpo EXCEPT ![p] = [lock |-> TRUE, st |-> "out"]] ELSE tmpo
          /\ loc' = [loc EXCEPT ![p].removed = there]
    /\ Goto(p, "rmDel")
    /\ UNCHANGED <<published, pin, storeLock, tmpd, left, kills, killedInLock>>

\* store.remove, second half: the folder is deleted in .tmp/ and its lock released.
DeleteOut(p) ==
    /\ pc[p] = "rmDel"
    /\ tmpo' = [tmpo EXCEPT ![p] = NoTmp]
    /\ Goto(p, IF loc[p].cmd = "uninstall" /\ ~UnpinFirst THEN "unpin" ELSE "sUnlock")
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpd, left, loc, kills, killedInLock>>

\* uninstall: clear the pin if the pinned build is the one removed (V3, step 2).
ClearPin(p) ==
    /\ \/ pc[p] = "unpin"
       \/ pc[p] = "locked" /\ loc[p].cmd = "uninstall" /\ UnpinFirst
    /\ LET goes == IF UnpinFirst THEN Installed(loc[p].bld) ELSE loc[p].removed
       IN pin' = IF goes /\ PinNow(p) = loc[p].bld THEN None ELSE pin
    /\ Goto(p, IF UnpinFirst THEN "rm" ELSE "sUnlock")
    /\ UNCHANGED <<published, copies, storeLock, tmpd, tmpo, left, loc, kills, killedInLock>>

\* pin: write the pin.  With ReadUnderLock the build is looked up again first.
WritePin(p) ==
    /\ pc[p] = "locked"
    /\ loc[p].cmd = "pin"
    /\ pin' = IF ReadUnderLock /\ ~Installed(loc[p].bld) THEN pin ELSE loc[p].bld
    /\ Goto(p, "sUnlock")
    /\ UNCHANGED <<published, copies, storeLock, tmpd, tmpo, left, loc, kills, killedInLock>>

StoreUnlock(p) ==
    /\ pc[p] = "sUnlock"
    /\ storeLock' = NoProc
    /\ IF tmpd[p].lock THEN Goto(p, "tUnlock") /\ UNCHANGED loc ELSE Done(p)
    /\ UNCHANGED <<published, copies, pin, tmpd, tmpo, left, kills, killedInLock>>

-----------------------------------------------------------------------------
(* A reader: the preflight of a run, `tool path`.  No lock (V1).           *)

\* With no pin the reader ends at once (NoPinnedBuild, or the first-run prompt).
ReadPin(p) ==
    /\ pc[p] = "idle"
    /\ pin # None
    /\ loc' = [loc EXCEPT ![p] = [NoLoc EXCEPT !.cmd = "read", !.rd = pin]]
    /\ Goto(p, "rCheck")
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpd, tmpo, left, kills, killedInLock>>

\* pinned(): the pin names a build that is in builds(), or PinnedBuildMissing.
ReadCheck(p) ==
    /\ pc[p] = "rCheck"
    /\ IF Installed(loc[p].rd) THEN Goto(p, "rOpen") /\ UNCHANGED loc ELSE Done(p)
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpd, tmpo, left, kills, killedInLock>>

\* Java opens the jar.  If the build was removed after the check, Java, not tlaup, reports
\* that it cannot load its main class (finding K2-3).
ReadOpen(p) ==
    /\ pc[p] = "rOpen"
    /\ Done(p)
    /\ UNCHANGED <<published, copies, pin, storeLock, tmpd, tmpo, left, kills, killedInLock>>

-----------------------------------------------------------------------------
(* The environment.                                                        *)

\* SIGKILL: the operating system releases the process's locks; its folders under .tmp/ stay.
Kill(p) ==
    /\ pc[p] # "idle"
    /\ kills < MaxKills
    /\ kills' = kills + 1
    /\ killedInLock' = (killedInLock \/ storeLock = p)
    /\ storeLock' = IF storeLock = p THEN NoProc ELSE storeLock
    /\ left' = left + (IF tmpd[p].st # "none" THEN 1 ELSE 0) + (IF tmpo[p].st # "none" THEN 1 ELSE 0)
    /\ tmpd' = [tmpd EXCEPT ![p] = NoTmp]
    /\ tmpo' = [tmpo EXCEPT ![p] = NoTmp]
    /\ Done(p)
    /\ UNCHANGED <<published, copies, pin>>

\* Upstream replaces the asset of a moving tag.
Publish(n) ==
    /\ published[n] < MaxVer
    /\ published' = [published EXCEPT ![n] = @ + 1]
    /\ UNCHANGED <<copies, pin, storeLock, tmpd, tmpo, left, pc, loc, kills, killedInLock>>

Next ==
    \/ \E p \in Procs :
        \/ (\E n \in Names : StartInstall(p, n) \/ StartUpgrade(p, n))
        \/ (\E b \in Builds : StartUninstall(p, b) \/ StartPin(p, b))
        \/ TmpLock(p) \/ TmpMkdir(p) \/ Download(p) \/ GiveUp(p) \/ TmpUnlock(p)
        \/ StoreLock(p) \/ CleanupLeft(p) \/ (\E q \in Procs : CleanupLive(p, q))
        \/ Add(p) \/ StartAgain(p) \/ PinStep(p) \/ RenameOut(p) \/ DeleteOut(p) \/ ClearPin(p) \/ WritePin(p)
        \/ StoreUnlock(p)
        \/ ReadPin(p) \/ ReadCheck(p) \/ ReadOpen(p)
        \/ Kill(p)
    \/ \E n \in Names : Publish(n)

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
(* Properties (03, K2).                                                    *)

\* Whenever the store lock is free, the pin is absent or names an installed build, unless
\* a tlaup was killed while it held the lock.
PinConsistent ==
    (storeLock = NoProc /\ ~killedInLock) => (pin = None \/ Installed(pin))

\* The same without the exception.  As V3 orders the steps it does not hold (finding K2-2).
PinConsistentAfterKill == storeLock = NoProc => (pin = None \/ Installed(pin))

\* A reader never sees a half-moved or half-deleted build: every folder that is not a whole
\* build is under .tmp/.  In this model that is so by the shape of Add and RenameOut, each
\* one rename; the property only says that nothing else changes the store's folders.
NoPartialBuild ==
    [][\A b \in Builds : copies'[b] # copies[b] => \E p \in Procs : Add(p) \/ RenameOut(p)]_vars

\* A reader ends with a jar it opened or with PinnedBuildMissing: when Java opens the jar,
\* the build is there.  It does not hold (finding K2-3).  That the jar it opens is the build
\* the pin named when it read it is so because an id stands for one build.
ReaderOutcome == [][\A p \in Procs : ReadOpen(p) => Installed(loc[p].rd)]_vars

\* What does hold: the build was there when pinned() looked.
ReaderChecked == \A p \in Procs : pc[p] = "rOpen" => loc[p].rd # None

\* No two installed builds have the same name and bytes.
NoDuplicate == \A b \in Builds : copies[b] <= 1

\* A folder under .tmp/ whose owner is alive is never removed by a cleanup, because
\* while it exists its lock is held.
TmpOwnerSafe == [][\A p, q \in Procs : ~CleanupLive(p, q)]_vars
TmpLockedWhileThere ==
    \A p \in Procs : (tmpd[p].st # "none" => tmpd[p].lock) /\ (tmpo[p].st # "none" => tmpo[p].lock)

\* The pin changes only by `pin`, by uninstall of the pinned build (to absent), by upgrade
\* of the pinned build, or by the first install.
PinNeverMovesSilently ==
    [][pin' # pin =>
        \E p \in Procs :
            \/ WritePin(p)
            \/ ClearPin(p) /\ pin = loc[p].bld /\ pin' = None
            \/ PinStep(p) /\ loc[p].cmd = "upgrade" /\ pin = loc[p].old /\ pin' = loc[p].bld
            \/ PinStep(p) /\ loc[p].cmd = "install" /\ pin = None /\ pin' = loc[p].bld]_vars

\* What `pin` pins is installed at that moment, and so is what an install pins.
PinWritesInstalled ==
    [][\A p \in Procs : (WritePin(p) /\ pin' # pin) => Installed(pin')]_vars
InstallPinsInstalled ==
    [][\A p \in Procs : (PinStep(p) /\ pin' # pin) => Installed(pin')]_vars

Symmetry == Permutations(Procs)

=============================================================================
