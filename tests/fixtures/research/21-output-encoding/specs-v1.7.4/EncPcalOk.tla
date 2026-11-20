---- MODULE EncPcalOk ----
\* before the algorithm: café 日語文
EXTENDS Naturals, TLC
(* --algorithm Enc
variables x = "ascii";
begin
  \* inside the algorithm: café 日語文
  A: print "ascii only"; \* trailing café
  B: x := "b";
end algorithm *)
\* after the algorithm: café 日語文
====
