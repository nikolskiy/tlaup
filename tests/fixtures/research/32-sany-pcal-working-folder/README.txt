Question 32 captures: standalone SANY and pcal.trans started in the spec's folder with the bare name (mode A) versus started in
another folder with the spec as an absolute path (mode B) or as ../spec/Name.tla (mode C). Checked 2026-11-18, Java 25.0.5,
Linux x86-64.
run.py JAR JAVA OUTDIR runs every scenario in a fresh folder tree (<w>/spec, <w>/other, <w>/lib) and writes one file per
(scenario, mode): command, stdout, stderr, exit code, files created or changed, contents of small changed files. diffs.txt
holds the diff A-vs-B and A-vs-C per scenario (command lines left out). summarize.py makes sany-summary.txt (which Helper
file SANY parsed, and the exit code, per mode).
v1.7.4/ is the v1.7.4 jar; v1.8.0-rolling/ is the byte-identical v1.8.0 and rolling jar. Paths are written as <w> and <jar>.
Noise: v1.7.4 extracts standard modules to /tmp/Naturals.tla, so runs of it at the same time as other agents' runs can
print "Encountered an exception while attempt to validate /tmp/Naturals.tla"; this is not part of the question.
Java 21 (rolling) and Java 11 (v1.7.4) gave the same outputs apart from that noise (not kept).
