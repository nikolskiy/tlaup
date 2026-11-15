---- MODULE ParAlias ----
EXTENDS Naturals
VARIABLES x, y
Init == x = 0 /\ y = 0
Inc(n) == /\ x' = x + n /\ y' = y
Dec == /\ y' = y + 1 /\ x' = x
Next == (\E n \in 1..2: Inc(n)) \/ Dec
Spec == Init /\ [][Next]_<<x,y>>
Safe == x + y < 3
Alias == [x |-> x, sum |-> x + y, label |-> "al"]
====
