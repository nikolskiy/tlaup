---- MODULE Long ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x < 100000000 /\ x' = x + 1
Spec == Init /\ [][Next]_x
====
