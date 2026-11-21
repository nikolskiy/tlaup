#!/usr/bin/env bash
# Check every spec in this folder with TLC and compare each result with the first line of
# its .cfg ("\* expect: ok" or "\* expect: violated <Property>").
#
#   TLA2TOOLS=<path to a released tla2tools.jar> ./check.sh [name-pattern]
#
# Needs Java 11 or newer.  TLC's state files go to states.*/ here, which is ignored by git
# and removed after each run.  The full set took 3 h 41 min on twelve cores on 2026-11-21;
# four configs take most of it, 41 to 65 minutes each: RunFolders,
# RunFolders-one-process-three-ids, RunFolders-windows and RunFolders-no-hour-rule.  A pattern
# such as "Signals" or "RunFolders-no" runs the configs whose file name contains it.
set -u
cd "$(dirname "$0")"
: "${TLA2TOOLS:?set TLA2TOOLS to the path of tla2tools.jar}"
pattern="${1:-}"
failed=0
for cfg in *.cfg variants/*.cfg; do
    case "$cfg" in *"$pattern"*) ;; *) continue ;; esac
    base="$(basename "$cfg" .cfg)"
    spec="${base%%-*}"
    expect="$(head -n 1 "$cfg" | sed 's/^\\\* expect: //')"
    meta="$(mktemp -d states.XXXXXX)"
    started=$SECONDS
    out="$(java -XX:+UseParallelGC -cp "$TLA2TOOLS" tlc2.TLC -workers auto -noGenerateSpecTE \
        -metadir "$meta" -config "$cfg" "$spec.tla" 2>&1)"
    took=$((SECONDS - started))
    rm -rf "$meta"
    if printf '%s\n' "$out" | grep -q 'No error has been found'; then
        got="ok"
    else
        got="violated $(printf '%s\n' "$out" | sed -n 's/^Error: .*[Pp]roperty \([A-Za-z]*\) .*violated.*/\1/p; s/^Error: Invariant \([A-Za-z]*\) is violated.*/\1/p' | head -n 1)"
    fi
    states="$(printf '%s\n' "$out" | sed -n 's/^\([0-9]*\) states generated, \([0-9]*\) distinct states found.*/\2/p' | tail -n 1)"
    if [ "$got" = "$expect" ]; then mark="as expected"; else mark="NOT AS EXPECTED (expected: $expect)"; failed=1; fi
    printf '%-46s %-40s %12s distinct states %5ss  %s\n' "$cfg" "$got" "${states:-?}" "$took" "$mark"
done
exit $failed
