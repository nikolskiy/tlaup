---- MODULE Big ----
\* A state space far too large to finish: the queue, the trace and the
\* fingerprint set keep growing for the whole run.
EXTENDS Naturals
VARIABLES a, b, c, d
N == 400
Init == a = 0 /\ b = 0 /\ c = 0 /\ d = 0
Next == \/ a < N /\ a' = a + 1 /\ UNCHANGED <<b, c, d>>
        \/ b < N /\ b' = b + 1 /\ UNCHANGED <<a, c, d>>
        \/ c' = (c + a + 1) % N /\ UNCHANGED <<a, b, d>>
        \/ d' = (d + b + 1) % N /\ UNCHANGED <<a, b, c>>
====
