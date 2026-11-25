"""The debug filter (design 12 V7): no token and no query string reaches what ``--debug`` prints.

Imports neither ``requests`` nor the GitHub client, so the root handler can call it at no cost (14 F9).
"""

import re
from collections.abc import Mapping

TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN")
# An address runs from its scheme to white space or a quote character.
_ADDRESS = re.compile(r"https?://[^\s'\"]*", re.IGNORECASE)


def _cut(match: re.Match[str]) -> str:
    return match.group(0).split("?", 1)[0]


def redact(text: str, env: Mapping[str, str]) -> str:
    """``text`` with the values of GH_TOKEN and GITHUB_TOKEN as ``***`` and every address cut at its ``?``.

    An unset or empty variable replaces nothing. No state: the tokens are read from ``env`` on every call.
    """
    values = {env.get(name) or "" for name in TOKEN_VARIABLES} - {""}
    for value in sorted(values, key=len, reverse=True):  # the longer first: one value may hold the other
        text = text.replace(value, "***")
    return _ADDRESS.sub(_cut, text)
