---- MODULE Enc ----
EXTENDS Naturals, TLC
VARIABLE s
Names == <<"café", "日本語", "😀">>
Init == s = "café"
Next == \/ /\ s = "café" /\ s' = "日本語"
        \/ /\ s = "日本語" /\ s' = "😀"
        \/ /\ s = "😀" /\ s' = "😀"
Inv == s # "😀"
Spec == Init /\ [][Next]_s
PrintIt == Print("print: café 日本語 😀", TRUE)
====
