# Mimics setup-java's Temurin query (pages of 20, version range [1.0,100.0], ga) and reports Java 11 for one arch.
import json, sys, urllib.request, re
arch = sys.argv[1]
url = ("https://api.adoptium.net/v3/assets/version/%5B1.0,100.0%5D?project=jdk&vendor=adoptium&heap_size=normal"
       f"&sort_method=DEFAULT&sort_order=DESC&os=mac&architecture={arch}&image_type=jdk&release_type=ga&jvm_impl=hotspot&page_size=20&page=0")
n = 0; found = []
while url and n < 50:
    n += 1
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-check"}))
    link = r.headers.get("Link", "")
    d = json.load(r)
    found += [(x["version_data"]["semver"], x["binaries"][0]["package"]["name"]) for x in d if x["version_data"]["major"] == 11 and x["binaries"]]
    m = re.search(r'<([^>]+)>;\s*rel="next"', link)
    url = m.group(1) if m else None
print(arch, "pages read:", n, "java 11 builds:", len(found), "newest:", found[:1])
