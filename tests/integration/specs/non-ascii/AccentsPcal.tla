\* For test_runner.py::test_non_ascii_output (design 11 R3): a comment with é and 日, which the PlusCal translator
\* must leave in the rewritten .tla byte for byte.
---- MODULE AccentsPcal ----
EXTENDS Naturals
\* café 日本
(* --algorithm AccentsPcal
variables x = 0;
begin
  A: x := 1; \* é and 日 inside the algorithm
end algorithm *)
====
