---- MODULE SemErr ----
EXTENDS Naturals
VARIABLE x
Init == x = y
Next == x' = x + 1 + Foo(2)
====
