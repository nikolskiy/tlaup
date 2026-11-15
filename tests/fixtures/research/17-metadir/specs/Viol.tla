---- MODULE Viol ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x' = x + 1 /\ x < 10
Spec == Init /\ [][Next]_x
Inv == x < 4
====
