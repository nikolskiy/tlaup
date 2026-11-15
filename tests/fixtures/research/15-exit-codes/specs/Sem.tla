---- MODULE Sem ----
EXTENDS Naturals
VARIABLE x
Init == x = y
Next == x' = x
Spec == Init /\ [][Next]_x
====
