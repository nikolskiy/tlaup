Captured 2026-11-14/15 from api.github.com (authenticated via gh, same data as unauthenticated).
- releases-all.trimmed.json: `GET /repos/tlaplus/tlaplus/releases?per_page=100`, all pages concatenated in API order (17 items); kept fields: tag_name, name, draft, prerelease, created_at, published_at, target_commitish, updated_at, assets (name, size, browser_download_url). Dropped: body, author, reactions, urls.
- tags-all.trimmed.json: `GET /repos/tlaplus/tlaplus/tags?per_page=100`, both pages concatenated in API order (114 items); kept name and commit sha.
- releases-latest.trimmed.json: `GET /repos/tlaplus/tlaplus/releases/latest`, trimmed.
