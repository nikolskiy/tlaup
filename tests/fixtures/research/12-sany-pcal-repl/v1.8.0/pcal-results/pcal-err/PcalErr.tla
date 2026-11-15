---- MODULE PcalErr ----
EXTENDS Naturals
(*--algorithm PcalErr
variable x = 0;
begin
  A: x := x + ;
end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "c0e8dfa5" /\ chksum(tla) = "b331fac5")
VARIABLES pc, x

vars == << pc, x >>

Init == (* Global variables *)
        /\ x = 0
        /\ pc = "A"

A == /\ pc = "A"
     /\ x' = x +
     /\ pc' = "Done"

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == pc = "Done" /\ UNCHANGED vars

Next == A
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(pc = "Done")

\* END TRANSLATION 
====
