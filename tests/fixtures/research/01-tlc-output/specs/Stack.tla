---- MODULE Stack ----
EXTENDS Naturals
VARIABLE x
RECURSIVE Rec(_)
Rec(n) == Rec(n + 1) + 1
Init == x = 0
Next == x' = Rec(x)
Spec == Init /\ [][Next]_x
====
