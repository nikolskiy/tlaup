---- MODULE Success ----
EXTENDS Naturals
VARIABLES x, y
TypeOK == x \in 0..3 /\ y \in 0..3
Init == x = 0 /\ y = 0
Next == \/ x < 3 /\ x' = x + 1 /\ y' = y
        \/ y < 3 /\ y' = y + 1 /\ x' = x
        \/ x = 3 /\ y = 3 /\ UNCHANGED <<x, y>>
Spec == Init /\ [][Next]_<<x, y>>
Inv == x + y <= 6
====
