\* For test_runner.py::test_cfg_rows (design 11 R4): copied to every place of research 16's and research 24's trees.
\* Each cfg there sets C to its own path in the tree, and the spec prints C, so the test sees which cfg TLC read.
---- MODULE Spec ----
EXTENDS TLC
CONSTANT C
VARIABLE x
ASSUME PrintT(C)
Init == x = 0
Next == UNCHANGED x
====
