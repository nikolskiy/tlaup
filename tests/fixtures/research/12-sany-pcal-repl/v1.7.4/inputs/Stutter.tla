---- MODULE Stutter ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x' = x + 1
Spec == Init /\ [][Next]_x
P == []<>(x = 3)
Q == [](x = 1)
====
