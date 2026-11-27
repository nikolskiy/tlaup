# Research 29: real GitHub recordings and CI facts

Made on 2026-11-19 (UTC) from one Linux machine with `curl` and no token. `record.sh` is the command list; the two
`.sh`/`.py` helpers produced `actions.txt` and the Adoptium numbers quoted in
`docs/research/29-ci-facts-and-recordings.md`.

| Folder | Request | Notes |
| --- | --- | --- |
| `tags-paged/page1`, `page2` | `GET /repos/tlaplus/tlaplus/tags?per_page=30` and `&page=2` | Full headers (status line first) and full bodies, stored pretty-printed (the same JSON as sent; `content-length` counts the compact form) so the secrets scan can skip the commit-hash lines. 30 tags on page 1; 4 pages exist (`rel="last"`). |
| `releases-paged/page1`, `page2` | `GET /repos/tlaplus/tlaplus/releases?per_page=10` and `&page=2` | Full headers. Bodies are cut to the fields tlaup reads (release: id, tag_name, name, draft, prerelease, created_at, published_at, url, html_url; assets: id, name, size, digest, content_type, state, browser_download_url), so `content-length` and `etag` no longer match the body. 10 + 7 releases. |
| `rate-limited/response` | `GET /repos/tlaplus/tlaplus/releases/latest` as request 61 within the hour | A real 403: `x-ratelimit-remaining: 0`, `x-ratelimit-reset`, no `retry-after`. The IP address in the body is replaced by `<ip>`. |

`date` and `x-ratelimit-reset` are real values of that day; a test that serves these files must not depend on them
being current. Headers are stored as sent over HTTP/2: lower-case names, one `name: value` per line.

Moved on 2026-11-25 (package 05): `releases-paged/` and `rate-limited/` went with `git mv` to `tests/recordings/github/`, so their rows above describe files that are no longer here. `releases-paged` was recorded again in place with the assets' `created_at` and `updated_at`; `rate-limited` is unchanged. `tags-paged/` stays: the client never calls the tags endpoint.
