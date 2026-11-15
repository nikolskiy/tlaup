---- MODULE SanyError ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x' = x + undefinedThing
Spec == Init /\ [][Next]_x
====
