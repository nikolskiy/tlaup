---- MODULE EncPrint ----
EXTENDS Naturals, TLC
VARIABLE s
Init == s = 0
Next == s' = s + 1 /\ PrintT("printt: café 日本語 😀") /\ Print("print: café 日本語 😀", TRUE) /\ s < 1
Spec == Init /\ [][Next]_s
====
