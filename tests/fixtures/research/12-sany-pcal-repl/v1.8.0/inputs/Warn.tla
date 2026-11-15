---- MODULE Warn ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x' = x + 1
Prop == [](x' = x + 1)
Prop2 == <>(x' = 5)
====
