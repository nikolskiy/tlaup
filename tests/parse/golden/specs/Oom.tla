---- MODULE Oom ----
EXTENDS Naturals
VARIABLE x
Init == x = [i \in 1..100000000 |-> i]
Next == x' = x
Spec == Init /\ [][Next]_x
====
