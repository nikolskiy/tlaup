---- MODULE Asrt ----
EXTENDS Naturals, TLC
VARIABLE x
Init == x = 0
Next == x < 2 /\ x' = x + 1 /\ Assert(x < 1, "boom")
Spec == Init /\ [][Next]_x
====
