---- MODULE EncPcalBad ----
EXTENDS Naturals, TLC
(* --algorithm Enc
variables x = "café 日本語 😀";
begin
  A: x := "café" +;
  B: goto Zé;
end algorithm *)
====
