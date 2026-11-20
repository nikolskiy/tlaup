---- MODULE Slow ----
EXTENDS Naturals, FiniteSets
VARIABLE x
Init == x = 0
Next == /\ x < 4000
        /\ Cardinality({i \in 1..400000 : i % 7 = x % 7}) > 0
        /\ x' = x + 1
Spec == Init /\ [][Next]_x
Inv == x < 10000
====
