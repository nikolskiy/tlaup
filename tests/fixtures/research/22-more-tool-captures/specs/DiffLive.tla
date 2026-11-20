---- MODULE DiffLive ----
EXTENDS Naturals
VARIABLES p, q
Init == p = 0 /\ q = "idle"
Next == /\ p' = (p + 1) % 3
        /\ q' = IF p = 2 THEN "busy" ELSE "idle"
Spec == Init /\ [][Next]_<<p, q>> /\ WF_<<p, q>>(Next)
Reach == <>(p = 5)
====
