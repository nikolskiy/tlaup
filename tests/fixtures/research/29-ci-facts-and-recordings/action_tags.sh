#!/bin/bash
# usage: tags.sh owner/repo  -> latest release tag and commit sha it points to (dereferenced)
r=$1
t=$(gh api repos/$r/releases/latest --jq .tag_name)
ref=$(gh api repos/$r/git/ref/tags/$t)
type=$(echo "$ref" | python3 -I -c "import json,sys;print(json.load(sys.stdin)['object']['type'])")
sha=$(echo "$ref" | python3 -I -c "import json,sys;print(json.load(sys.stdin)['object']['sha'])")
if [ "$type" = tag ]; then sha=$(gh api repos/$r/git/tags/$sha --jq .object.sha); fi
pub=$(gh api repos/$r/releases/latest --jq .published_at)
echo "$r $t $sha (ref type $type) published $pub"
