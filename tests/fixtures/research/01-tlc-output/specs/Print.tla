---- MODULE Print ----
EXTENDS Naturals, TLC
VARIABLE x
Init == x = 0 /\ PrintT("init-print")
Next == x < 3 /\ x' = x + 1 /\ PrintT(<<"step", x>>)
Spec == Init /\ [][Next]_x
Inv == x < 2 \/ Print("inv-print", TRUE)
Bad == x < 3
====
