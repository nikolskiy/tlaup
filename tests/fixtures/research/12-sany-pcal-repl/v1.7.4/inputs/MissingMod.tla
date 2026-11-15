---- MODULE MissingMod ----
EXTENDS Naturals, NoSuchModule
VARIABLE x
Init == x = 0
====
