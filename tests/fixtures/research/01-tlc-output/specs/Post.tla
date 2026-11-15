---- MODULE Post ----
EXTENDS Naturals, TLC
VARIABLE x
Init == x = 0
Next == x < 2 /\ x' = x + 1
Spec == Init /\ [][Next]_x
Done == x = 2 \/ TRUE
Post == TLCGet("distinct") = 99
====
