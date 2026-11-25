"""Record real GitHub answers for ``tests/recordings/github/`` (design 01 T4).

A developer tool, not run in CI. It sends no token and only unauthenticated requests to ``api.github.com``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import requests

API = "https://api.github.com/repos/tlaplus/tlaplus"
TAGS = ("rolling", "v1.8.0", "v1.7.4")
SITUATIONS = ("releases", "releases-paged", "rate-limited")
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "tests" / "recordings" / "github"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "tlaup-recorder/0",
}
TIMEOUT = 30
RELEASE_FIELDS = ("id", "tag_name", "name", "draft", "prerelease", "created_at", "published_at", "url", "html_url")
ASSET_FIELDS = (
    "id",
    "name",
    "size",
    "digest",
    "content_type",
    "state",
    "created_at",
    "updated_at",
    "browser_download_url",
)
_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')


def trim_release(release: dict[str, Any]) -> dict[str, Any]:
    """The fields tlaup reads, in the design's order."""
    trimmed = {key: release[key] for key in RELEASE_FIELDS if key in release}
    trimmed["assets"] = [{key: asset[key] for key in ASSET_FIELDS if key in asset} for asset in release["assets"]]
    return trimmed


def hide_ips(text: str) -> str:
    return _IP.sub("<ip>", text)


def status_and_headers(response: requests.Response) -> str:
    """The status line and every header as sent: lower-case names, one ``name: value`` per line, no cookies."""
    version = "1.1" if response.raw.version == 11 else "1.0"
    lines = [f"HTTP/{version} {response.status_code} {response.reason or ''}".rstrip()]
    lines += [f"{name.lower()}: {value}" for name, value in response.headers.items() if name.lower() != "set-cookie"]
    return hide_ips("\n".join(lines)) + "\n"


def fetch(url: str) -> requests.Response:
    """One unauthenticated request; the environment's tokens are never read."""
    print(f"GET {url}")
    return requests.get(url, headers=HEADERS, timeout=TIMEOUT)


def write_answer(folder: Path, name: str, response: requests.Response, *, trim: str | None) -> None:
    if trim is None:
        body = response.text
    else:
        data = response.json()
        data = [trim_release(r) for r in data] if trim == "list" else trim_release(data)
        body = json.dumps(data, indent=1)
    (folder / f"{name}.headers").write_text(status_and_headers(response), encoding="utf-8", newline="\n")
    (folder / f"{name}.body").write_text(hide_ips(body).rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def write_toml(folder: Path, answers: list[tuple[str, str]], *, whole_host: bool = False) -> None:
    text = ""
    for url, file in answers:
        text += f'[[answer]]\nmethod = "GET"\nurl = "{url}"\nfile = "{file}"\n'
        if whole_host:
            text += 'scope = "host"\n'
        text += "\n"
    (folder / "requests.toml").write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def record_releases(out: Path) -> None:
    folder = out / "releases"
    folder.mkdir(parents=True, exist_ok=True)
    answers = []
    response = fetch(f"{API}/releases?per_page=100")
    response.raise_for_status()
    write_answer(folder, "list", response, trim="list")
    answers.append((f"{API}/releases", "list"))
    for tag in TAGS:
        response = fetch(f"{API}/releases/tags/{tag}")
        response.raise_for_status()
        write_answer(folder, f"tag-{tag}", response, trim="one")
        answers.append((f"{API}/releases/tags/{tag}", f"tag-{tag}"))
    write_toml(folder, answers)


def record_releases_paged(out: Path) -> None:
    folder = out / "releases-paged"
    folder.mkdir(parents=True, exist_ok=True)
    answers = []
    url: str | None = f"{API}/releases?per_page=10"
    page = 0
    while url:
        page += 1
        response = fetch(url)
        response.raise_for_status()
        write_answer(folder, f"page{page}", response, trim="list")
        answers.append((f"{API}/releases" if page == 1 else url, f"page{page}"))
        match = _NEXT.search(response.headers.get("link", ""))
        url = match.group(1) if match else None
    write_toml(folder, answers)


def record_rate_limited(out: Path) -> None:
    """Spends the unauthenticated allowance: requests until the first answer that is not 200."""
    folder = out / "rate-limited"
    folder.mkdir(parents=True, exist_ok=True)
    url = f"{API}/releases/latest"
    for _ in range(70):
        response = fetch(url)
        if response.status_code != requests.codes.ok:
            write_answer(folder, "response", response, trim=None)
            write_toml(folder, [(url, "response")], whole_host=True)
            return
    sys.exit("the allowance was not used up after 70 requests")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "situations", nargs="+", choices=SITUATIONS, help="what to record; rate-limited spends the allowance"
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="output folder (default: tests/recordings/github)"
    )
    args = parser.parse_args(argv)
    recorders = {
        "releases": record_releases,
        "releases-paged": record_releases_paged,
        "rate-limited": record_rate_limited,
    }
    for situation in args.situations:
        recorders[situation](args.out)
        print(f"wrote {args.out / situation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
