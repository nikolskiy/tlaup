---- MODULE Boom ----
EXTENDS Naturals
VARIABLE x
Boom(n) == n
Init == x = 0
Next == x' = Boom(x + 1)
Spec == Init /\ [][Next]_x
====
