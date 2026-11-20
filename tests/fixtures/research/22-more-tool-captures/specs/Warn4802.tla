---- MODULE Warn4802 ----
EXTENDS Naturals
VARIABLE x
R == [a |-> 1, a |-> 2]
Init == x = 0
Next == x < 2 /\ x' = x + 1
Spec == Init /\ [][Next]_x
====
