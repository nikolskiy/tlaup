---- MODULE Params ----
EXTENDS Naturals
VARIABLES x, y, z
I == INSTANCE Inner
Init == x = 0 /\ y = 0 /\ z = 0
Step(i) == x < 3 /\ x' = x + i /\ UNCHANGED <<y, z>>
Reset == x >= 2 /\ x' = 0 /\ y' = y + 1 /\ UNCHANGED z
Viaz == I!Bump(2) /\ UNCHANGED <<x, y>>
Pick == \E i \in 1..2 : Step(i)
Next == Pick \/ Reset \/ Viaz
Spec == Init /\ [][Next]_<<x, y, z>>
Inv == y < 2 /\ z < 4
InvX == x < 3
Viaq == (\E i \in 1..2 : I!Bump(i)) /\ UNCHANGED <<x, y>>
Next2 == Pick \/ Reset \/ Viaq
Spec2 == Init /\ [][Next2]_<<x, y, z>>
====
