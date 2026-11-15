Question 12 captures (SANY, PlusCal translator, REPL), checked 2026-11-14 with Java 25.0.5.
Jars: v1.7.4 (tag v1.7.4) and v1.8.0 (tag v1.8.0). The "rolling" release asset has the same sha256 as v1.8.0 today (jar-sha256.txt).
<version>/inputs: the .tla files used. <version>/outputs: one file per run; first line is the command, last line is [exit=N].
run.sh and pc.sh are the helper scripts (the paths in outputs are from the scratch folder they ran in).
<version>/pcal-results: files left in the work folder after each PlusCal run (shows .old, .cfg, AST.tla).
Not captured: sany-d-interactive (SANY -d with stdin at EOF loops forever, printing the prompt; reached 143 MB, deleted).
