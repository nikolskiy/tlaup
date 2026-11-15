---- MODULE PcalProc ----
EXTENDS Naturals
(*--algorithm PcalProc
variable x = 0;
process p \in 1..2
begin
  A: x := x + 1;
end process;
end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "565103a9" /\ chksum(tla) = "68b4e6e8")
VARIABLES pc, x

vars == << pc, x >>

ProcSet == (1..2)

Init == (* Global variables *)
        /\ x = 0
        /\ pc = [self \in ProcSet |-> "A"]

A(self) == /\ pc[self] = "A"
           /\ x' = x + 1
           /\ pc' = [pc EXCEPT ![self] = "Done"]

p(self) == A(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == (\E self \in 1..2: p(self))
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ \A self \in 1..2 : WF_vars(p(self))

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 
====
