---- MODULE Inner ----
EXTENDS Naturals
VARIABLE z
Bump(k) == z < 4 /\ z' = z + k
====
