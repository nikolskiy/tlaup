---- MODULE Assum ----
EXTENDS Naturals
VARIABLE x
ASSUME 1 = 2
Init == x = 0
Next == x' = x
Spec == Init /\ [][Next]_x
====
