---- MODULE EncPrint ----
EXTENDS Naturals, TLC
VARIABLE s
Init == s = 0
Next == s' = s + 1 /\ PrintT("printt: café 日語文") /\ Print("print: café 日語文", TRUE) /\ s < 1
Spec == Init /\ [][Next]_s
====
