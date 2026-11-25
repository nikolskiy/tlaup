---- MODULE PcalStaleTla ----
EXTENDS Naturals
(*--algorithm PcalStaleTla
variable x = 0;
begin
  A: x := x + 1;
  B: x := x + 1;
end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "740de904" /\ chksum(tla) = "25bac779")
VARIABLES pc, x

vars == << pc, x >>

Init == (* Global variables *)
        /\ x = 0
        /\ pc = "A"

A == /\ pc = "A" /\ TRUE
     /\ x' = x + 1
     /\ pc' = "B"

B == /\ pc = "B"
     /\ x' = x + 1
     /\ pc' = "Done"

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == pc = "Done" /\ UNCHANGED vars

Next == A \/ B
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(pc = "Done")

\* END TRANSLATION 
====
