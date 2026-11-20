---- MODULE Long ----
EXTENDS Naturals, FiniteSets
VARIABLES x, y
Slow(v) == Cardinality({i \in 1..200000 : i % 7 = v % 7}) > 0
Init == x = 0 /\ y = 0
Next == \/ x < 320 /\ Slow(x) /\ x' = x + 1 /\ UNCHANGED y
        \/ y < 320 /\ Slow(y) /\ y' = y + 1 /\ UNCHANGED x
Spec == Init /\ [][Next]_<<x, y>>
Inv == x + y < 10000
====
