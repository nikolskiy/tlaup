---- MODULE Esc ----
EXTENDS Naturals
VARIABLE x
Init == x = [s |-> "a<b>&c='d' é 日本 \"q\" \\ \t", t |-> {<<1,2>>}]
Next == x' = x
Spec == Init /\ [][Next]_x
Bad == x.t # {<<1,2>>}
====
