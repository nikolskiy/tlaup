#!/usr/bin/env bash
# Builds the test tree under $1 (default: ./work). Needs a JDK `jar` on PATH.
set -eu
W=${1:-work}; mkdir -p "$W"; cd "$W"
# keep cm/ and cm-deps/ (the downloaded CommunityModules jars, one folder each)
find . -mindepth 1 -maxdepth 1 ! -name cm ! -name cm-deps -exec rm -rf {} +
mkdir -p spec libA libB cpdir jarsrc other
mod() { # dir name where
  printf -- '---- MODULE %s ----\nWhere == "%s"\n====\n' "$2" "$3" > "$1/$2.tla"; }
mod libA OnlyInLibA libA
mod libB OnlyInLibB libB
mod cpdir OnlyInCpDir cpdir
mod jarsrc OnlyInJar jar
(cd jarsrc && jar cf ../mods.jar OnlyInJar.tla)
rm -rf jarsrc
# precedence ladder: module Dup exists in every place
mod spec Dup spec; mod libA Dup libA; mod libB Dup libB; mod cpdir Dup cpdir
mkdir j2 && mod j2 Dup jar && (cd j2 && jar cf ../dup.jar Dup.tla) && rm -rf j2
