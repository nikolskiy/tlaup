---- MODULE NextEval ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x' = 1 \div x
Spec == Init /\ [][Next]_x
====
