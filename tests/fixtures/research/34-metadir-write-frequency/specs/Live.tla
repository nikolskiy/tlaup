---- MODULE Live ----
\* A liveness property over a graph of a few million states: TLC checks it
\* periodically during the search and once more at the end.
EXTENDS Naturals
VARIABLES a, b
N == 1500
Init == a = 0 /\ b = 0
Next == \/ a' = (a + 1) % N /\ b' = b
        \/ b' = (b + 1) % N /\ a' = a
Spec == Init /\ [][Next]_<<a, b>> /\ WF_<<a, b>>(Next)
Prop == []<>(a + b >= 0)
====
