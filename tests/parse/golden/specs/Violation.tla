---- MODULE Violation ----
EXTENDS Naturals, Sequences, FiniteSets
VARIABLES store, log, n
Init == /\ store = [k \in {"alpha", "beta", "gamma"} |-> {}]
        /\ log = <<>>
        /\ n = 0
Add(k, v) == /\ store' = [store EXCEPT ![k] = @ \cup {v}]
             /\ log' = Append(log, [op |-> "add", key |-> k, val |-> v, note |-> "a deliberately long note to force the value to wrap across several lines"])
             /\ n' = n + 1
Next == \E k \in {"alpha", "beta", "gamma"}, v \in 1..2 : n < 5 /\ Add(k, v)
Spec == Init /\ [][Next]_<<store, log, n>>
Small == n < 3
====
