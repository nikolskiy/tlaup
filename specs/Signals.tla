------------------------------- MODULE Signals -------------------------------
(***************************************************************************)
(* K3 of docs/design/03-run-stages-and-specs.md: the signal handling of    *)
(* the Java launcher (docs/design/20-groundwork.md G3) as the runner uses  *)
(* it (docs/design/11-runner.md R2).  One tlaup process enters             *)
(* signals_held, starts one child, waits for it, prints the summary and    *)
(* leaves.  Signals arrive at any moment.                                  *)
(*                                                                         *)
(* Revised 2026-11-20 for decisions D51 and D52: tlaup can die at any      *)
(* moment (SIGKILL, a crash), and the lifeline agent then ends the child;  *)
(* in a parsed run a first signal that arrives while TLC writes a          *)
(* checkpoint waits until the checkpoint is written.                       *)
(*                                                                         *)
(* What the model is, what it leaves out, its bounds and its results are   *)
(* in README.md beside this file.                                          *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS
    MaxSignals,      \* how many signals arrive in one behaviour
    Defer,           \* TRUE: a first signal waits for a checkpoint being written (D52)
    Lifeline         \* TRUE: the lifeline agent ends the child once tlaup is gone (D51)

ASSUME MaxSignals \in Nat /\ Defer \in BOOLEAN /\ Lifeline \in BOOLEAN

Recorded == {"int", "term", "hup"}      \* the signals G3 records and acts on
Sigs == Recorded \cup {"quit"}          \* SIGQUIT gets a handler that does nothing
None == "none"

VARIABLES
    phase,           \* where the launcher is; see Phases
    ignored,         \* the signals that were ignored when tlaup started (nohup, a background job)
    leave,           \* leave_interrupt: SIGINT is the child's business (tlaup repl)
    stubborn,        \* the child ignores SIGTERM and never ends by itself
    parsed,          \* a parsed run: tlaup reads TLC's messages (not --raw, not the REPL)
    chkpt,           \* the parser has seen TLC start a checkpoint (2195) and not end it (2196)
    handlers,        \* the signals that have a tlaup handler now
    first,           \* Signals.first
    count,           \* Signals.count
    child,           \* "none", "running", "exited"
    childIgnores,    \* the signals the child was started ignoring
    termSent,        \* terminate() was called on the child
    killSent,        \* kill() was called on the child
    failing,         \* an exception is leaving the process loop (a closed pipe, a parser error)
    stoppedBy,       \* ProcessOutcome.stopped_by, taken when the launcher sees the child gone
    code,            \* what tlaup exits with: "own" (the tool's code) or a signal's
    arrived,         \* signals that have arrived so far
    firstBeforeExit, \* ghost: a signal was recorded before the child exited
    firstAtCheck,    \* ghost: a signal was recorded when the run function looked
    diedIn           \* ghost: the phase in which Python's default handler ended tlaup

vars == <<phase, ignored, leave, stubborn, parsed, chkpt, handlers, first, count, child,
          childIgnores, termSent, killSent, failing, stoppedBy, code, arrived, firstBeforeExit,
          firstAtCheck, diedIn>>

\* The variables the original steps leave alone; they are UNCHANGED in each of them.
new == <<parsed, chkpt>>

\* before    signals_held not entered yet
\* held      handlers installed; the run folder is being made; no child
\* checked   the run function saw Signals.first unset and is about to call Popen
\* spawning  Popen has started the child and has not returned it to the launcher yet
\* attached  the child is attached to Signals; the process loop runs
\* reaped    the launcher has seen the child gone (or started nothing); the outcome is fixed
\* summary   reporter.finish has printed; the run folder is settled
\* left      signals_held has restored the previous handlers
\* exited    tlaup has exited with `code`
\* died      Python's default handler ended tlaup
\* killed    tlaup was killed with SIGKILL, or crashed, and ran no code of its own (D51)
Phases == {"before", "held", "checked", "spawning", "attached", "reaped", "summary",
           "left", "exited", "died", "killed"}
Held == {"held", "checked", "spawning", "attached", "reaped", "summary"}
Gone == {"exited", "died", "killed"}

TypeOK ==
    /\ phase \in Phases
    /\ ignored \subseteq Sigs
    /\ leave \in BOOLEAN /\ stubborn \in BOOLEAN
    /\ parsed \in BOOLEAN /\ chkpt \in BOOLEAN
    /\ handlers \subseteq Sigs
    /\ first \in Recorded \cup {None}
    /\ count \in 0..MaxSignals
    /\ child \in {"none", "running", "exited"}
    /\ childIgnores \subseteq Sigs
    /\ termSent \in BOOLEAN /\ killSent \in BOOLEAN /\ failing \in BOOLEAN
    /\ stoppedBy \in Recorded \cup {None}
    /\ code \in Recorded \cup {None, "own"}
    /\ arrived \in 0..MaxSignals
    /\ firstBeforeExit \in BOOLEAN /\ firstAtCheck \in BOOLEAN
    /\ diedIn \in Phases \cup {None}

Init ==
    /\ phase = "before"
    /\ ignored \in SUBSET Sigs
    /\ leave \in BOOLEAN
    /\ stubborn \in BOOLEAN
    /\ parsed \in (IF leave THEN {FALSE} ELSE BOOLEAN)     \* the REPL is never parsed
    /\ chkpt = FALSE
    /\ handlers = {}
    /\ first = None /\ count = 0
    /\ child = "none" /\ childIgnores = {}
    /\ termSent = FALSE /\ killSent = FALSE /\ failing = FALSE
    /\ stoppedBy = None /\ code = None
    /\ arrived = 0
    /\ firstBeforeExit = FALSE /\ firstAtCheck = FALSE
    /\ diedIn = None

-----------------------------------------------------------------------------
(* The launcher and the runner's frame.                                    *)

\* signals_held: a handler for every signal that is not ignored already.
Enter ==
    /\ phase = "before"
    /\ handlers' = Sigs \ ignored
    /\ phase' = "held"
    /\ UNCHANGED <<new, ignored, leave, stubborn, first, count, child, childIgnores, termSent,
                   killSent, failing, stoppedBy, code, arrived, firstBeforeExit, firstAtCheck, diedIn>>

\* The run function looks at Signals.first immediately before starting the child.  If it is
\* set, nothing is started and the run ends with that signal's code.
Check ==
    /\ phase = "held"
    /\ firstAtCheck' = (first # None)
    /\ IF first # None
       THEN /\ stoppedBy' = first
            /\ phase' = "reaped"
       ELSE /\ phase' = "checked"
            /\ UNCHANGED stoppedBy
    /\ UNCHANGED <<new, ignored, leave, stubborn, handlers, first, count, child, childIgnores,
                   termSent, killSent, failing, code, arrived, firstBeforeExit, diedIn>>

\* Popen.  The child inherits "ignored" for the signals tlaup left ignored; a signal with a
\* Python handler is back at its default in the child.
Spawn ==
    /\ phase = "checked"
    /\ child' = "running"
    /\ childIgnores' = ignored
    /\ phase' = "spawning"
    /\ UNCHANGED <<new, ignored, leave, stubborn, handlers, first, count, termSent, killSent,
                   failing, stoppedBy, code, arrived, firstBeforeExit, firstAtCheck, diedIn>>

\* The child is attached to Signals.  A signal that landed while Popen was returning is
\* seen now and treated as a first signal: terminate().
Attach ==
    /\ phase = "spawning"
    /\ termSent' = (first # None)
    /\ phase' = "attached"
    /\ UNCHANGED <<new, ignored, leave, stubborn, handlers, first, count, child, childIgnores,
                   killSent, failing, stoppedBy, code, arrived, firstBeforeExit, firstAtCheck, diedIn>>

\* on_stdout or on_stderr raises.  The finally round the loop stops the child: terminate().
LoopFails ==
    /\ phase = "attached"
    /\ ~failing
    /\ failing' = TRUE
    /\ termSent' = TRUE
    /\ UNCHANGED <<new, phase, ignored, leave, stubborn, handlers, first, count, child, childIgnores,
                   killSent, stoppedBy, code, arrived, firstBeforeExit, firstAtCheck, diedIn>>

\* The grace period runs out: kill().  The clock runs from the moment terminate() was sent:
\* for a first signal, when it was sent on to the child (Signals.first_at), which for a
\* signal held during a checkpoint is when the checkpoint was written, not when the signal
\* arrived; for the finally, from the terminate() it sent.  Hence termSent below.
GraceKill ==
    /\ phase = "attached"
    /\ child = "running"
    /\ termSent
    /\ ~killSent
    /\ killSent' = TRUE
    /\ UNCHANGED <<new, phase, ignored, leave, stubborn, handlers, first, count, child, childIgnores,
                   termSent, failing, stoppedBy, code, arrived, firstBeforeExit, firstAtCheck, diedIn>>

\* The launcher sees the child gone: both pipes closed and wait() returned.  The outcome is
\* fixed here: stopped_by is Signals.first as it is now.
Reap ==
    /\ phase = "attached"
    /\ child = "exited"
    /\ stoppedBy' = first
    /\ phase' = "reaped"
    /\ UNCHANGED <<new, ignored, leave, stubborn, handlers, first, count, child, childIgnores,
                   termSent, killSent, failing, code, arrived, firstBeforeExit, firstAtCheck, diedIn>>

Summary ==
    /\ phase = "reaped"
    /\ phase' = "summary"
    /\ UNCHANGED <<new, ignored, leave, stubborn, handlers, first, count, child, childIgnores,
                   termSent, killSent, failing, stoppedBy, code, arrived, firstBeforeExit,
                   firstAtCheck, diedIn>>

Leave ==
    /\ phase = "summary"
    /\ handlers' = {}
    /\ phase' = "left"
    /\ UNCHANGED <<new, ignored, leave, stubborn, first, count, child, childIgnores, termSent,
                   killSent, failing, stoppedBy, code, arrived, firstBeforeExit, firstAtCheck, diedIn>>

Exit ==
    /\ phase = "left"
    /\ code' = IF stoppedBy # None THEN stoppedBy ELSE "own"
    /\ phase' = "exited"
    /\ UNCHANGED <<new, ignored, leave, stubborn, handlers, first, count, child, childIgnores,
                   termSent, killSent, failing, stoppedBy, arrived, firstBeforeExit,
                   firstAtCheck, diedIn>>

-----------------------------------------------------------------------------
(* The child and the signals.                                              *)

\* The child ends: by itself, after terminate(), after a signal the terminal sent it too,
\* or after kill().  A stubborn child ends only after kill().
ChildExit ==
    /\ child = "running"
    /\ stubborn => killSent
    /\ child' = "exited"
    /\ firstBeforeExit' = (first # None)
    /\ UNCHANGED <<new, phase, ignored, leave, stubborn, handlers, first, count, childIgnores,
                   termSent, killSent, failing, stoppedBy, code, arrived, firstAtCheck, diedIn>>

\* The handler of G3: record, and act on the child if one is attached.  With Defer, a first
\* signal that arrives while the parser has seen a checkpoint start and not end is recorded
\* and held: it reaches the child when the checkpoint is written (CheckpointEnd).  A second
\* signal kills at once, as before (D52).
Acts(s) == s \in Recorded /\ ~(s = "int" /\ leave)
Deferring == Defer /\ chkpt

Signal(s) ==
    /\ arrived < MaxSignals
    /\ phase \notin Gone
    /\ arrived' = arrived + 1
    /\ IF s \in handlers
       THEN IF Acts(s)
            THEN /\ first' = IF first = None THEN s ELSE first
                 /\ count' = count + 1
                 /\ IF phase = "attached"
                    THEN /\ termSent' = (termSent \/ (count = 0 /\ ~Deferring))
                         /\ killSent' = (killSent \/ count > 0)
                    ELSE UNCHANGED <<termSent, killSent>>
                 /\ UNCHANGED <<phase, diedIn>>
            ELSE \* SIGQUIT, and a SIGINT that is left to the child: the handler does nothing
                 UNCHANGED <<phase, first, count, termSent, killSent, diedIn>>
       ELSE IF s \in ignored
            THEN UNCHANGED <<phase, first, count, termSent, killSent, diedIn>>
            ELSE \* no handler and not ignored: Python's default handler ends tlaup
                 /\ diedIn' = phase
                 /\ phase' = "died"
                 /\ UNCHANGED <<first, count, termSent, killSent>>
    /\ UNCHANGED <<new, ignored, leave, stubborn, handlers, child, childIgnores, failing,
                   stoppedBy, code, firstBeforeExit, firstAtCheck>>

\* The parser reads TLC's 2195 ("Checkpointing of run"), and later 2196 ("Checkpointing
\* completed").  Only a parsed run sees them; tlaup reads nothing in a raw run.  A first
\* signal held meanwhile is sent on at 2196: terminate().
CheckpointBegin ==
    /\ phase = "attached"
    /\ parsed /\ ~chkpt
    /\ child = "running"
    /\ chkpt' = TRUE
    /\ UNCHANGED <<phase, ignored, leave, stubborn, parsed, handlers, first, count, child,
                   childIgnores, termSent, killSent, failing, stoppedBy, code, arrived,
                   firstBeforeExit, firstAtCheck, diedIn>>

CheckpointEnd ==
    /\ phase = "attached"
    /\ chkpt
    /\ chkpt' = FALSE
    /\ termSent' = (termSent \/ first # None)
    /\ UNCHANGED <<phase, ignored, leave, stubborn, parsed, handlers, first, count, child,
                   childIgnores, killSent, failing, stoppedBy, code, arrived, firstBeforeExit,
                   firstAtCheck, diedIn>>

\* SIGKILL of tlaup, or a crash, at any moment: no handler runs, nothing is printed, the
\* child is not told (D51).
TlaupDies ==
    /\ phase \notin Gone
    /\ phase' = "killed"
    /\ UNCHANGED <<new, ignored, leave, stubborn, handlers, first, count, child, childIgnores,
                   termSent, killSent, failing, stoppedBy, code, arrived, firstBeforeExit,
                   firstAtCheck, diedIn>>

\* The lifeline agent in the JVM sees tlaup gone and stops the JVM, within about two
\* seconds, whatever signals the child ignores (research 35).
LifelineEnds ==
    /\ Lifeline
    /\ phase = "killed"
    /\ child = "running"
    /\ child' = "exited"
    /\ firstBeforeExit' = (first # None)
    /\ UNCHANGED <<new, phase, ignored, leave, stubborn, handlers, first, count, childIgnores,
                   termSent, killSent, failing, stoppedBy, code, arrived, firstAtCheck, diedIn>>

Launcher == Enter \/ Check \/ Spawn \/ Attach \/ GraceKill \/ Reap \/ Summary \/ Leave \/ Exit

Next == Launcher \/ LoopFails \/ ChildExit \/ (\E s \in Sigs : Signal(s))
        \/ CheckpointBegin \/ CheckpointEnd \/ TlaupDies \/ LifelineEnds

Spec == Init /\ [][Next]_vars

\* For Stops and ChildEndsWithTlaup: the launcher's own steps are taken, a child that may end
\* does end, a checkpoint that was started is written in the end, and the lifeline acts.
FairSpec == Spec /\ WF_vars(Launcher) /\ WF_vars(ChildExit) /\ WF_vars(CheckpointEnd)
                 /\ (Lifeline => WF_vars(LifelineEnds))

-----------------------------------------------------------------------------
(* Properties (03, K3).                                                    *)

\* Between entering and leaving signals_held, no signal reaches Python's default handler.
NoDefaultHandler == diedIn \notin Held

\* When tlaup exits, the child has exited.  A tlaup that is killed runs no code; for it see
\* ChildEndsWithTlaup.
ChildNeverOrphaned == phase \in {"exited", "died"} => child # "running"

\* When tlaup is killed, the child ends in the end: the lifeline (D51).  Before D51 the spec
\* left the SIGKILL of tlaup out.
ChildEndsWithTlaup == (phase = "killed") ~> (child # "running")

\* The exit code is the first signal's if it arrived before the child exited, otherwise the
\* run's own.  As 03 words it, it does not hold: tlaup cannot see a signal that arrives
\* after the child has ended and before the launcher has noticed (finding K3-1).
ExitCode ==
    phase = "exited" =>
        code = IF firstBeforeExit \/ firstAtCheck THEN first ELSE "own"

\* What does hold.  A signal that came before the child ended is never lost:
SignalNeverLost ==
    (phase = "exited" /\ (firstBeforeExit \/ firstAtCheck)) => code = first
\* and the code is a signal's exactly when one was recorded by the time the launcher saw
\* the child gone, so a signal during the summary changes nothing.
ExitCodeAsSeen ==
    phase = "exited" => code = IF stoppedBy # None THEN stoppedBy ELSE "own"
LateSignalChangesNothing ==
    [][(phase \in {"reaped", "summary", "left"}) => UNCHANGED stoppedBy]_vars

\* A signal ignored at entry has no handler, changes nothing, and is ignored by the child.
IgnoredStaysIgnored ==
    /\ handlers \cap ignored = {}
    /\ child # "none" => childIgnores = ignored
IgnoredChangesNothing ==
    [][\A s \in ignored : Signal(s) => UNCHANGED <<phase, first, count, termSent, killSent>>]_vars

\* If a signal was recorded before the start, no child is started.  As 03 words it, it does
\* not hold: a signal can land after the run function has looked and before Popen
\* (finding K3-2).
NothingStartsAfterSignal == [][Spawn => first = None]_vars

\* What does hold.  A signal seen by the look starts nothing:
NothingStartsAfterSeenSignal == firstAtCheck => child = "none"
\* and one that lands later reaches the child as soon as it is attached, or, while a
\* checkpoint is being written in a parsed run, once it is written or at the second signal.
SignalReachesChild ==
    (phase = "attached" /\ first # None /\ child = "running" /\ ~Deferring)
        => (termSent \/ killSent)

\* A first signal does not stop the child while it writes a checkpoint (D52).  It does not
\* hold without the deferral (Signals-no-deferral).
FirstSignalWaitsForCheckpoint ==
    [][\A s \in Sigs : (Signal(s) /\ phase = "attached" /\ chkpt /\ count = 0)
            => UNCHANGED termSent]_vars

\* A second signal that is acted on while the child is attached kills it.
SecondSignalKills ==
    [][\A s \in Sigs : (Signal(s) /\ phase = "attached" /\ s \in handlers /\ Acts(s) /\ count > 0)
            => killSent']_vars

\* A SIGINT left to the child and a SIGQUIT are never recorded.
LeftAloneNotRecorded ==
    [][\A s \in Sigs : (Signal(s) /\ ~Acts(s)) => UNCHANGED <<first, count, termSent, killSent>>]_vars

\* Once a signal is recorded, tlaup exits (or is past its handlers), whatever the child does.
Stops == (first # None /\ phase \in Held) ~> (phase \in Gone)

=============================================================================
