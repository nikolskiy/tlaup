---- MODULE PrintMarker ----
EXTENDS Naturals, TLC
VARIABLE x
Init == x = 0 /\ PrintT("before @!@!@STARTMSG 2185:0 @!@!@ after")
Next == x < 2 /\ x' = x + 1 /\ PrintT("@!@!@STARTMSG 9999:1 @!@!@")
Spec == Init /\ [][Next]_x
====
