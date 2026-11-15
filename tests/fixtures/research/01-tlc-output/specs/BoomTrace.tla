---- MODULE BoomTrace ----
EXTENDS Naturals
VARIABLE x
BoomTrace(n) == n
Init == x = 0
Next == x' = BoomTrace(x + 1)
Spec == Init /\ [][Next]_x
====
