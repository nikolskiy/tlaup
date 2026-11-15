---- MODULE spec ----
EXTENDS Naturals, TLC, Ovr
VARIABLE x
Init == x = Add2(1, 2)
Next == x' = x
Inv == PrintT(<<"Inv sees", x, Add2(10, 20)>>)
====
