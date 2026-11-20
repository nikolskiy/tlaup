---- MODULE EncPcal ----
EXTENDS Naturals, TLC, Sequences
(* --algorithm Enc
variables x = "café 日本語 😀";
begin
  A: print "pcal: café 日本語 😀";
  B: x := "😀";
end algorithm *)
====
