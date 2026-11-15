---- MODULE Val ----
EXTENDS Naturals, Integers, Sequences, TLC
CONSTANTS M, S
VARIABLE v
Init == v = [ f34 |-> [i \in {3,4} |-> i],
  fstr |-> [s \in {"a","b"} |-> 1],
  fmv |-> [m \in S |-> 1],
  fset |-> [s \in {{1},{2,3}} |-> 0],
  frec |-> (<<1,2>> :> "x" @@ <<3>> :> "y"),
  fbool |-> [b \in BOOLEAN |-> 0],
  empf |-> [i \in {} |-> 0],
  eset |-> {}, eseq |-> <<>>,
  ss |-> {{1},{2,3},{}},
  sr |-> {[a |-> 1],[a |-> 2]},
  big |-> 2147483647, neg |-> -5, huge |-> -2147483647,
  uni |-> "héllo \\ / \t", mset |-> S, mval |-> M, 
  nested |-> <<[a |-> {<<1>>,<<2>>}], "x">>,
  str1 |-> "1", fn1 |-> [i \in 1..2 |-> "a"],
  fnKeyNum |-> [i \in {1,3} |-> 1],
  recempty |-> [x \in {} |-> 1],
  setfn |-> {[i \in 1..2 |-> i]},
  tlcval |-> 1 ]
Next == v' = v
Spec == Init /\ [][Next]_v
Bad == v.big # 2147483647
====
