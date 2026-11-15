---- MODULE LiveStutter ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x' = (x + 1) % 3
Spec == Init /\ [][Next]_x
Reach == <>(x = 2)
====
