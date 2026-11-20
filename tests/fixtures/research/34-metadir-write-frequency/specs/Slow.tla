---- MODULE Slow ----
\* Few states, each expensive: TLC works all the time but finds a new state
\* only every minute or so.
EXTENDS Naturals, FiniteSets
CONSTANTS K, R
VARIABLE x
Init == x = 0
Expensive(n) == \A r \in 1..R : Cardinality({i * j + n + r : i \in 1..K, j \in 1..K}) > 0
Next == x < 1000 /\ Expensive(x) /\ x' = x + 1
====
