---- MODULE MultiError ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x < 6 /\ x' = x + 1
Spec == Init /\ [][Next]_x
InvA == x # 2
InvB == x # 4
====
