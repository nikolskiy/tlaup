---- MODULE LevelErr ----
EXTENDS Naturals
VARIABLE x
ASSUME x = 1
Init == x = 0
Bad == x'' = 1
====
