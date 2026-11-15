---- MODULE Small ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x < 5 /\ x' = x + 1
Spec == Init /\ [][Next]_x
Inv == x <= 5
====
