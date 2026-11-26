\* For test_runner.py::test_non_ascii_output (design 11 R3): a trace whose values hold é and 日, run with LC_ALL=C.
\* The invariant fails in the second state, so the trace shows both strings.
---- MODULE Accents ----
VARIABLE s
Init == s = "é"
Next == s = "é" /\ s' = "日"
Inv == s # "日"
Spec == Init /\ [][Next]_s
====
