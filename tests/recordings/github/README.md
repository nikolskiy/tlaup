# GitHub recordings

Real answers of `api.github.com` for `tlaplus/tlaplus`, served by the `github` fixture (`tests/github.py`, `tests/conftest.py`). One folder per situation, each with a `requests.toml` that says which request every recorded answer serves. A `.headers` file holds the status line, then one lower-case `name: value` per line; a `.body` file holds the JSON with an indent of one space. `scripts/record_github.py` records them again (`uv run python scripts/record_github.py releases releases-paged`); it sends no token.

`date` and `x-ratelimit-reset` are the values of the recording day; no test may depend on them being current. The fixture does not serve `content-length`, `content-encoding` and `transfer-encoding`: the bodies are trimmed and decoded, so the recorded values are wrong for them. `etag` no longer matches the trimmed body either.

Bodies are trimmed to what tlaup reads. Release: `id`, `tag_name`, `name`, `draft`, `prerelease`, `created_at`, `published_at`, `url`, `html_url`, `assets`. Asset: `id`, `name`, `size`, `digest`, `content_type`, `state`, `created_at`, `updated_at`, `browser_download_url`. The fixture rewrites `size` and `digest` of the `tla2tools.jar` asset of `rolling`, `v1.8.0` and `v1.7.4` to the small jar it serves (a `null` digest stays `null`); the files hold what GitHub sent.

| Folder | Asked | When | Notes |
| --- | --- | --- | --- |
| `releases/` | `GET /releases?per_page=100` (`list`), and `GET /releases/tags/<tag>` for `rolling`, `v1.8.0` and `v1.7.4` (`tag-<tag>`) | 2026-11-25 (UTC) | 17 releases on one page; no `link` header. Recorded again, so every asset has `updated_at`. |
| `releases-paged/` | `GET /releases?per_page=10` (`page1`), then the address of its `rel="next"` link (`page2`) | 2026-11-25 (UTC) | 10 + 7 releases. The first request to `/releases` gets page 1 whatever its query; page 2 is served at the address of page 1's `link` header. Moved from research 29 and recorded again in place. |
| `rate-limited/` | `GET /releases/latest` as the 61st request within the hour | 2026-11-19 (UTC) | A real 403 (`x-ratelimit-remaining: 0`, `x-ratelimit-reset`, no `retry-after`), moved from research 29 unchanged, with `<ip>` in the body for an IP address. Served for every request to `api.github.com` (`scope = "host"` in `requests.toml`). |

The jar manifests the small jars are built from are in `tests/unit/data/manifests/`.
