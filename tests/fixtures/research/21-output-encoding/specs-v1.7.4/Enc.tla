---- MODULE Enc ----
EXTENDS Naturals, TLC
\* emoji only in a comment: 😀
VARIABLE s
Names == <<"café", "日語文">>
Init == s = "café"
Next == \/ /\ s = "café" /\ s' = "日語文"
        \/ /\ s = "日語文" /\ s' = "ø"
        \/ /\ s = "ø" /\ s' = "ø"
Inv == s # "ø"
Spec == Init /\ [][Next]_s
PrintIt == Print("print: café 日語文", TRUE)
====
