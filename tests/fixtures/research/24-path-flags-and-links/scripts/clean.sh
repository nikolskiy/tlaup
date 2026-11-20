#!/bin/bash
: "${TMP_ROOT:?set TMP_ROOT to the scratch root that holds jars/ and q24/}"
# remove everything the experiments created, keep the layout
cd $TMP_ROOT/q24/t || exit 1
find . -type f \( -name '*.dump' -o -name '*.dot' -o -name '*.json' -o -name '*.out' -o -name '*_TTrace_*' -o -name '*.bin' -o -name 'rel*' \) -delete
rm -rf work/sub work/dumps work/te; rm -f real/proj/SpecTE.*; find . -type d \( -name states -o -name 'md*' -o -name 'te*' -o -name 'relmeta' \) -prune -exec rm -rf {} +
