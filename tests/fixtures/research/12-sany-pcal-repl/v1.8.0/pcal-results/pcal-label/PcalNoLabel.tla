---- MODULE PcalNoLabel ----
EXTENDS Naturals
(*--algorithm PcalNoLabel
variable x = 0;
begin
  A: x := 1;
  x := 2;
end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "36e409d2" /\ chksum(tla) = "9dffd69c")
VARIABLES pc, x

vars == << pc, x >>

Init == (* Global variables *)
        /\ x = 0
        /\ pc = "A"

A == /\ pc = "A"
     /\ x' = 1
     /\ pc' = "Lbl_1"

Lbl_1 == /\ pc = "Lbl_1"
         /\ x' = 2
         /\ pc' = "Done"

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == pc = "Done" /\ UNCHANGED vars

Next == A \/ Lbl_1
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(pc = "Done")

\* END TRANSLATION 
====
