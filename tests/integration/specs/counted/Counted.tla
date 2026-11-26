\* For test_runner.py::test_keep_and_resume_exact: a state space whose size is known by construction, four counters
\* in 0..K, so (K + 1)^4 distinct states. Work(x) makes each step cost a set of W numbers (it depends on the state,
\* so TLC cannot compute it once), which makes a run last past its first one-minute checkpoint with few states.
\* The run time rests on how TLC evaluates Work, so a faster build or machine can finish before the first
\* checkpoint (the test then fails saying so): W in Counted.cfg is the knob to turn; K sets the count.
---- MODULE Counted ----
EXTENDS Naturals
CONSTANTS K, W
VARIABLES a, b, c, d
vars == <<a, b, c, d>>
Work(x) == x + 1 \in {i + x : i \in 1..W}
Step(x) == x < K /\ Work(x) /\ x' = x + 1
Init == a = 0 /\ b = 0 /\ c = 0 /\ d = 0
Done == a = K /\ b = K /\ c = K /\ d = K /\ UNCHANGED vars
Next == \/ Step(a) /\ UNCHANGED <<b, c, d>>
        \/ Step(b) /\ UNCHANGED <<a, c, d>>
        \/ Step(c) /\ UNCHANGED <<a, b, d>>
        \/ Step(d) /\ UNCHANGED <<a, b, c>>
        \/ Done
Spec == Init /\ [][Next]_vars
====
