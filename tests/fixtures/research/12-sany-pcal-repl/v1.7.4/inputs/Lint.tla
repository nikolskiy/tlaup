---- MODULE Lint ----
EXTENDS Naturals
VARIABLE x
Unused(a) == 1
Init == \E n \in Nat : x = n
Next == x' = x
====
