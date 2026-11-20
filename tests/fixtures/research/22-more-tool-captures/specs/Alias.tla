---- MODULE Alias ----
EXTENDS Naturals
VARIABLES x, y
Init == x = 0 /\ y = 0
Next == x' = x + 1 /\ y' = y + 2
Spec == Init /\ [][Next]_<<x, y>>
Inv == x < 3
Alias == [x |-> x, sum |-> x + y, label |-> "step"]
====
