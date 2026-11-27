---- MODULE Act ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x < 3 /\ x' = x + 1
Spec == Init /\ [][Next]_x
Dec == [][x' < x]_x
====
