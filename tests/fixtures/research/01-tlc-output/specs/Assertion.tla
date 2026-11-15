---- MODULE Assertion ----
EXTENDS Naturals, TLC
VARIABLE x
Init == x = 0
Next == /\ Assert(x < 2, "x grew too large")
        /\ x' = x + 1
Spec == Init /\ [][Next]_x
====
