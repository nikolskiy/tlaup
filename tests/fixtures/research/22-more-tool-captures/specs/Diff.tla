---- MODULE Diff ----
EXTENDS Naturals
VARIABLES a, b, c
Init == a = 0 /\ b = 0 /\ c = [i \in 1..3 |-> 0]
Next == \/ a < 5 /\ a' = a + 1 /\ UNCHANGED <<b, c>>
        \/ b < 5 /\ b' = b + 1 /\ c' = [c EXCEPT ![2] = @ + 1] /\ UNCHANGED a
Spec == Init /\ [][Next]_<<a, b, c>>
Inv == a + b < 4
====
