\* For test_signals.py: the spec that runs until stopped. An unbounded counter: TLC never ends by itself, and one
\* new state per step grows memory slowly, so it is still running when the test signals or kills tlaup.
---- MODULE Forever ----
EXTENDS Naturals
VARIABLE n
Init == n = 0
Next == n' = n + 1
Spec == Init /\ [][Next]_n
====
