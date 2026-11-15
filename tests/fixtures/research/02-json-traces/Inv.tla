---- MODULE Inv ----
EXTENDS Naturals, Sequences, FiniteSets
CONSTANTS A, B
VARIABLES x, rec, fn, st, sq, str, mv, tup
Init == /\ x = 0 /\ rec = [a |-> 1, b |-> "hi"] /\ fn = [i \in {1,2} |-> i*10]
        /\ st = {1,2} /\ sq = <<>> /\ str = "s\"q\n" /\ mv = A /\ tup = <<1,"a",TRUE>>
Next == /\ x < 3 /\ x' = x+1 /\ rec' = [rec EXCEPT !.a = @+1] /\ fn' = [fn EXCEPT ![1] = @+1]
        /\ st' = st \cup {x+3} /\ sq' = Append(sq, x) /\ str' = "t" /\ mv' = B /\ tup' = <<x,"a",FALSE>>
Spec == Init /\ [][Next]_<<x,rec,fn,st,sq,str,mv,tup>>
Safe == x < 3
====
