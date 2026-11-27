---- MODULE PcalStaleAlg ----
EXTENDS Naturals
(*--algorithm PcalStaleAlg
variable x = 0;
begin
  A: x := x + 2;
  B: x := x + 1;
end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "d9081052" /\ chksum(tla) = "25bac779")
VARIABLES pc, x

vars == << pc, x >>

Init == (* Global variables *)
        /\ x = 0
        /\ pc = "A"

A == /\ pc = "A"
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
