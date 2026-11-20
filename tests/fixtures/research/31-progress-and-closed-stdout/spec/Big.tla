---- MODULE Big ----
EXTENDS Naturals
VARIABLES a, b, c, d
Init == a = 0 /\ b = 0 /\ c = 0 /\ d = 0
Next == \/ a < 120 /\ a' = a + 1 /\ UNCHANGED <<b, c, d>>
        \/ b < 120 /\ b' = b + 1 /\ UNCHANGED <<a, c, d>>
        \/ c < 120 /\ c' = c + 1 /\ UNCHANGED <<a, b, d>>
        \/ d < 120 /\ d' = d + 1 /\ UNCHANGED <<a, b, c>>
Spec == Init /\ [][Next]_<<a, b, c, d>>
====
