---- MODULE Level ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Bad == x' + 1
Next == Init' /\ [](x = 1)'
Q == Init'
CONSTANT C
ASSUME C' = 1
====
