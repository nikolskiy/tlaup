# 11. Sources for download numbers

## Question

Which sources give download and usage numbers for `tlaup` and `tlaplus-cli` without sending anything from users' machines: pypistats (API and CLI), the public BigQuery dataset, GitHub release asset counts, GitHub repository traffic? For each: what it measures, granularity, history length, whether mirrors and CI are counted or can be filtered, authentication, cost, rate limits.

## Source

- pypistats API docs, fetched 2026-11-14: https://pypistats.org/api/
- `pypistats` CLI 1.14.0, run with `uvx pypistats ...`.
- PyPI BigQuery docs: https://docs.pypi.org/api/bigquery/ ; example queries: https://packaging.python.org/en/latest/guides/analyzing-pypi-package-downloads/
- GitHub REST API via `gh api` (logged in as `nikolskiy`, which has push access).
- Repos (from `git remote -v` and `gh api`): `nikolskiy/tlaup` and `nikolskiy/tlaplus-cli`.

## Short answer

| Source | Measures | Granularity / history | Mirrors, CI | Auth, cost | Limits |
|---|---|---|---|---|---|
| pypistats API / CLI | PyPI file downloads per project | daily series, last 180 days only; recent day/week/month | Excludes known mirrors (e.g. bandersnatch) by default; `mirrors=true/false` on `overall`. No CI filter. No pip-vs-uv split in the API. | none, free | 60 requests per window per IP (header `x-ratelimit-limit: 60`); data updates once a day |
| BigQuery `bigquery-public-data.pypi.file_downloads` | one row per download request | per event, full history | Raw rows; filter on `details.installer.name`, `details.ci`, `details.system.name`, `details.python`, `country_code`. No mirror flag documented | Google Cloud project needed; first 1 TB queried per month free | BigQuery quotas; cost is bytes scanned, so always filter on `timestamp` and `file.project` |
| GitHub release asset `download_count` | downloads of release assets by URL | per asset, cumulative since upload, no dates | counts anything that fetches the asset URL, including CI and bots | `gh` login (public read works) | 5000 requests/hour authenticated |
| GitHub traffic (views, clones, referrers, paths) | page views and git clones of the repo | daily for views and clones, 14 days only; referrers and paths are a 14-day top-10 | counts bots and CI clones; `uniques` is per day | needs push access | same 5000/hour |

Verified results today: `tlaup` is not in pypistats yet (HTTP 404, the 0.8.2 upload was 2026-11-15 UTC by the PyPI timestamp). `tlaplus-cli` has 3,800 downloads with mirrors and 980 without in the last 180 days. Release asset counts are tiny (mostly 1 per asset). Traffic for `tlaup` is all zeros so far.

## Confidence

Partly verified. pypistats, GitHub asset counts and traffic were run for both repos. BigQuery was not run (no Google Cloud project, as instructed); its description comes from the PyPI and packaging.python.org docs, and the `details.ci` field and the exact free-tier terms were not re-checked against current Google pages.

## Evidence

### pypistats

API doc statements (https://pypistats.org/api/): "All download stats exclude known mirrors ... unless noted otherwise", "Time series data is retained only for 180 days", "All download data is updated once daily", "IP-based rate limiting is imposed application-wide", and a request to cache results and not fetch the same endpoint more than once a day. It also tells heavy users to use BigQuery instead.

`tlaup` (command `uvx pypistats recent tlaup`):

```
urllib3.exceptions.HTTPError: HTTP Error 404 for url: https://pypistats.org/api/packages/tlaup/recent
```

`overall`, `system`, `python_minor` for `tlaup` also fail with 404 or "No data found". PyPI itself has the project: `https://pypi.org/pypi/tlaup/json` returns 200, version 0.8.2, upload time 2026-11-15T02:24:49 (UTC, per PyPI; the shell clock says 2026-11-15 as well). The `info.downloads` field is `-1` for day, week and month: PyPI's own API gives no counts. Most likely cause of the 404 is that the project is under a day old and pypistats has not ingested it; not confirmed.

`tlaplus-cli`:

```
$ uvx pypistats recent tlaplus-cli
 last_day 1 | last_month 31 | last_week 16

$ uvx pypistats overall tlaplus-cli
 with_mirrors    100.00%  3,800
 without_mirrors  25.79%    980
 Date range: 2026-05-18 - 2026-11-14
```

So even the "exclude mirrors" default hides a lot: 3,800 with mirrors against 980 without. Roughly 3 in 4 downloads are mirror traffic. The `without_mirrors` series (`curl "https://pypistats.org/api/packages/tlaplus-cli/overall?mirrors=false"`) has 112 daily rows summing to 980. Days with no download are missing rows. Last 14 rows: 10-23 2, 10-26 1, 10-27 2, 10-28 1, 10-29 1, 11-01 1, 11-03 1, 11-04 1, 11-05 1, 11-06 1, 11-10 11, 11-11 1, 11-13 3, 11-14 1. The 11-10 spike of 11 is probably the maintainer's or CI's own testing; not confirmed.

Breakdown without mirrors (`system`, `python_minor`): system `null` 742 (75.71%), Linux 190, Darwin 43, Windows 5. Python: null 742, 3.12 134, 3.11 78, 3.14 16, 3.13 7, 3.10 2, 3.8 1. The `null` bucket (about 76%) means the client sent no User-Agent detail, which is the pattern of mirrors or non-pip tools; it is not explained in the docs. The API has no installer endpoint (`/api/packages/tlaplus-cli/installer` returns 404); the CLI offers `recent`, `overall`, `python_major`, `python_minor`, `system`. pypistats 1.14.0 CLI on Python 3.14 works with `uvx`.

Rate limit: response headers on a normal request showed `x-ratelimit-limit: 60` and `x-ratelimit-remaining` counting down (48 after earlier calls). The window length is not stated in the docs or headers I saw (there was `retry-after: 0`). A once-a-day script with a few calls is far under it.

### BigQuery (docs only, not run)

- Table `bigquery-public-data.pypi.file_downloads`, populated by Linehaul from PyPI download logs (https://docs.pypi.org/api/bigquery/). Partitioned by `timestamp`.
- The pypistats doc says "You can query up to 1TB of data FREE every month" and each month of data is under 100 GB. The packaging guide shows the `details.installer.name` filter (pip only) and warns that an unfiltered 6-month query scans over 500 GB.
- Fields used by the example queries: `file.project`, `timestamp`, `details.installer.name`, `details.python`. From my knowledge of the schema (not shown in the fetched pages): `file.version`, `file.type`, `details.ci`, `details.system.name`, `details.distro`, `country_code`, `url`. Verify with the table schema in the console before relying on `details.ci`.
- Running it needs a Google Cloud project (a free project with no billing may work using the sandbox; not verified here, and not created).
- Query that would be run (last 180 days, per day, both names, split by installer and CI; the `timestamp` filter keeps the scan small):

```sql
SELECT
  DATE(timestamp) AS day,
  file.project AS project,
  file.version AS version,
  details.installer.name AS installer,
  details.ci AS ci,
  COUNT(*) AS downloads
FROM `bigquery-public-data.pypi.file_downloads`
WHERE file.project IN ('tlaup', 'tlaplus-cli')
  AND DATE(timestamp) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY) AND CURRENT_DATE()
GROUP BY day, project, version, installer, ci
ORDER BY day DESC
```

BigQuery keeps history longer than 180 days, so it is the only source that can backfill beyond pypistats' window, but nothing exists to backfill for these projects before 2026.

### GitHub release asset counts

Command: `gh api repos/nikolskiy/<repo>/releases --jq '.[] | {tag, assets:[{name,download_count}]}'`.

- `nikolskiy/tlaup`: one release, v0.8.2 (published 2026-11-15T02:24:29Z): `tlaup-0.8.2-py3-none-any.whl` 1, `tlaup-0.8.2.tar.gz` 1, `default.gitignore` 1.
- `nikolskiy/tlaplus-cli`: 20 releases, v0.1.3 to v0.8.3. Counts are mostly 0 or 1 per asset; highest: v0.5.0 (wheel 3, sdist 5), v0.3.4 (4, 4), v0.3.2 (4, 4), v0.3.1 (4, 4), v0.8.1 (wheel 1, sdist 2). The `default.gitignore` asset has 0 to 1.
- The count is a cumulative total with no timestamps; a history needs a script that records the value each day. The very first counts of 1 per asset directly after release look like the release workflow or the maintainer's own check; not confirmed. Users installing from PyPI do not touch these assets, so this number says little about real usage.
- Rate limit seen: `gh api rate_limit` core limit 5000, 160 used at the time.

### GitHub traffic

`gh api repos/nikolskiy/<repo>/traffic/views`, `/clones`, `/popular/referrers`, `/popular/paths` all succeeded (push access works). Both views and clones return 14 daily rows (the window runs to the current day) with `count` and `uniques`. The 14-day window is GitHub's documented limit; the 14 rows returned agree with it.

- `nikolskiy/tlaup` (2026-11-02 to 2026-11-15 rows): views 0 (uniques 0), clones 0 (uniques 0), referrers `[]`, paths `[]`.
- `nikolskiy/tlaplus-cli` (2026-11-01 to 2026-11-14): views 9 total, 3 unique (11-05 1, 11-12 7 from 1 unique, 11-13 1); clones 15 total, 10 unique (daily 0 to 3, 11-14 1); referrers `aocr.org` 1, `github.com` 1; paths: overview 2, plus single views of `src/tlaplus_cli/cli.py`, `java/classpath.py`, `java/inspector.py`, `py.typed`, `ui.py` and `docs/examples`.
- Counts include bots and CI runs that clone. The numbers are small enough that one person (the 11-12 spike of 7 views by 1 unique) dominates them.
- Data is gone after 14 days; only a scheduled collector can keep a history. A GitHub Actions run with `GITHUB_TOKEN` cannot read traffic (needs push-level token with `repository` scope; not tested here).

## Implications for the roadmap

- A collector script that makes no network calls from users' machines is feasible with public sources only: pypistats (no auth) and `gh api` (maintainer's login). Nothing needs to be added to `tlaup` itself.
- pypistats and GitHub traffic both forget (180 and 14 days). If history matters, the script must be run on a schedule and append to a local file; for PyPI, BigQuery is the only way to reach past 180 days, but the projects are under a year old, so pypistats' window already covers all of `tlaplus-cli`'s life (first row 2026-05-18, 180 days).
- Raw PyPI counts overstate use: for `tlaplus-cli` only 980 of 3,800 survive the mirror filter, and about 76% of those have no system or Python data. Any report should state "without mirrors" and treat the numbers as an upper bound on installs.
- Release asset counts and traffic are too small and too noisy (maintainer and CI included) to serve as usage evidence; they are cheap to record next to the others.
- Package split: `tlaup` and `tlaplus-cli` are separate PyPI projects, so the script must query both and report them separately (the forwarding `tlaplus-cli` release will keep producing its own downloads).

## Open follow-ups

- Re-run `uvx pypistats recent tlaup` in a few days to confirm the 404 is only a new-project delay.
- Check the BigQuery table schema (is `details.ci` present, is there any mirror marker) and whether a billing-free sandbox project is enough. Needs a Google Cloud project; the maintainer must decide whether to create one.
- Find the pypistats rate-limit window (docs say only "IP-based"); the header showed 60 per unspecified window.
- Check whether a scheduled GitHub Actions job can read traffic with a fine-grained token, or whether it must run from the maintainer's machine.
- Identify what the `null` system/Python bucket is on pypistats (likely clients without a pip-style User-Agent).

## Date checked

2026-11-14 (shell clock and GitHub timestamps already show 2026-11-15 UTC for releases made late that day). pypistats CLI 1.14.0; pypistats data range 2026-05-18 to 2026-11-14.
