---- MODULE PcalStaleBoth ----
EXTENDS Naturals
(*--algorithm PcalStaleBoth
variable x = 0;
begin
  A: x := x + 2;
  B: x := x + 1;
end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "7bf2517e" /\ chksum(tla) = "538abadf")
VARIABLES x, pc

vars == << x, pc >>

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
