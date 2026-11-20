#!/bin/bash
# Records the GitHub responses of research 29. Unauthenticated curl (no token), run from this folder.
# Rate limit: the last loop sends requests until the 60/hour allowance is used up and keeps the first non-200 answer.
H='Accept: application/vnd.github+json'; V='X-GitHub-Api-Version: 2022-11-28'
get() { curl -sS -A "tlaup-research/0" -H "$H" -H "$V" -D "$2.headers" -o "$2.body" "$1"; }
mkdir -p tags-paged releases-paged rate-limited
get "https://api.github.com/repos/tlaplus/tlaplus/tags?per_page=30" tags-paged/page1
get "https://api.github.com/repos/tlaplus/tlaplus/tags?per_page=30&page=2" tags-paged/page2
get "https://api.github.com/repos/tlaplus/tlaplus/releases?per_page=10" releases-paged/page1
get "https://api.github.com/repos/tlaplus/tlaplus/releases?per_page=10&page=2" releases-paged/page2
for n in $(seq 1 70); do
  code=$(curl -sS -A "tlaup-research/0" -H "$H" -H "$V" -D rate-limited/response.headers -o rate-limited/response.body -w '%{http_code}' "https://api.github.com/repos/tlaplus/tlaplus/releases/latest")
  [ "$code" != 200 ] && break
done
# afterwards by hand: the releases bodies were cut to the fields tlaup reads; the IP address in the 403 body became <ip>.
