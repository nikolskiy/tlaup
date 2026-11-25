---- MODULE Big ----
EXTENDS Naturals
VARIABLES a, b, c
Init == a = 0 /\ b = 0 /\ c = 0
Next == \/ a < 130 /\ a' = a + 1 /\ UNCHANGED <<b, c>>
        \/ b < 130 /\ b' = b + 1 /\ UNCHANGED <<a, c>>
        \/ c < 130 /\ c' = c + 1 /\ UNCHANGED <<a, b>>
Spec == Init /\ [][Next]_<<a, b, c>>
====
