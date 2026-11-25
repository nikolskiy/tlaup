"""``parse_version_spec`` and ``latest_refused`` (design 02 X3)."""

from __future__ import annotations

import pytest

from tlaup.errors import UsageError
from tlaup.versioning.spec import VersionSpec, latest_refused, parse_version_spec

SHA40 = "bc1b506bdcad80bb518bf3776a9161c34ff0fc4c"
CALVER = "2026.11.15.002146"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("v1.7.4", VersionSpec("v1.7.4", None, None, None)),
        ("1.7.4", VersionSpec("1.7.4", None, None, None)),
        ("stable", VersionSpec("stable", None, None, None)),
        ("rolling", VersionSpec("rolling", None, None, None)),
        ("rolling@bc1b506", VersionSpec("rolling", "bc1b506", None, None)),
        ("v1.8.0@bc1b506", VersionSpec("v1.8.0", "bc1b506", None, None)),
        (f"v1.8.0@{SHA40}", VersionSpec("v1.8.0", SHA40, None, None)),
        (f"rolling@{CALVER}", VersionSpec("rolling", None, CALVER, None)),
        ("rolling@sha256:7e53aa636dac", VersionSpec("rolling", None, None, "7e53aa636dac")),
        ("rolling@sha256:" + "a" * 64, VersionSpec("rolling", None, None, "a" * 64)),
        ("rolling@sha256:12345678", VersionSpec("rolling", None, None, "12345678")),
        (CALVER, VersionSpec(None, None, CALVER, None)),
        (f"{CALVER}@bc1b506", VersionSpec(CALVER, "bc1b506", None, None)),
        ("stable@bc1b506", VersionSpec("stable", "bc1b506", None, None)),
        ("rolling@BC1B506", VersionSpec("rolling", "bc1b506", None, None)),
        (f"rolling@{SHA40.upper()}", VersionSpec("rolling", SHA40, None, None)),
        ("rolling@sha256:7E53AA636DAC", VersionSpec("rolling", None, None, "7e53aa636dac")),
        ("2026.11.15.02146", VersionSpec("2026.11.15.02146", None, None, None)),  # not a CalVer: a tag
        ("v1.9-rc_1", VersionSpec("v1.9-rc_1", None, None, None)),
        ("release/1.9", VersionSpec("release/1.9", None, None, None)),
        ("v1.9+build5", VersionSpec("v1.9+build5", None, None, None)),
        ("v1-x@bc1b506", VersionSpec("v1-x", "bc1b506", None, None)),
    ],
)
def test_accepted(text: str, expected: VersionSpec) -> None:
    assert parse_version_spec(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "@abc",
        "v1.7.4@",
        "rolling@xyz",
        "rolling@bc1b50",  # six digits
        f"rolling@{SHA40}0",  # forty-one digits
        "-v1",
        "-",
        "v1@bc1b506@bc1b506",
        "v1@v2@bc1b506",
        "v 1.7.4",
        "v1.7.4 ",
        " v1.7.4",
        "v1.7.4\n",
        "v1\t@bc1b506",
        "rolling@sha256:1234567",
        "rolling@sha256:1234567g",
        "rolling@sha256:",
        "rolling@sha256:" + "a" * 65,
        "@sha256:7e53aa636dac",
        "rolling@2026.11.15.02146",
        "rolling@2026.11.15.0021460",
        "rolling@bc1b506.1",
        "v1é",
    ],
)
def test_malformed_is_a_usage_error(text: str) -> None:
    with pytest.raises(UsageError) as caught:
        parse_version_spec(text)
    assert caught.value.exit_code == 2
    assert "\n" not in caught.value.message
    assert not caught.value.message.endswith(".")
    assert caught.value.hint is None or "\n" not in caught.value.hint


@pytest.mark.parametrize("text", ["latest", "latest@bc1b506"])
def test_latest_names_stable_and_rolling(text: str) -> None:
    with pytest.raises(UsageError) as caught:
        parse_version_spec(text)
    hint = caught.value.hint or ""
    assert "stable" in hint
    assert "rolling" in hint


@pytest.mark.parametrize(
    "text",
    ["https://example.org/tla2tools.jar", "http://example.org/x.jar", "ftp://example.org/x", "git@host:org/repo"],
)
def test_address_hint_says_it_is_not_supported(text: str) -> None:
    with pytest.raises(UsageError) as caught:
        parse_version_spec(text)
    hint = caught.value.hint or ""
    assert "address" in hint
    assert "rolling" not in hint


def test_plain_refusal_is_neither_latest_nor_address() -> None:
    with pytest.raises(UsageError) as caught:
        parse_version_spec("rolling@xyz")
    hint = caught.value.hint or ""
    assert "address" not in hint
    assert "latest" not in caught.value.message


def test_latest_refused_with_a_tag() -> None:
    error = latest_refused("v1.7.4")
    assert isinstance(error, UsageError)
    hint = error.hint or ""
    assert "`stable` (v1.7.4)" in hint
    assert "`rolling`" in hint


def test_latest_refused_without_a_tag_has_no_brackets() -> None:
    hint = latest_refused().hint or ""
    assert "stable" in hint
    assert "rolling" in hint
    assert "()" not in hint
    assert "(" not in hint.split("rolling")[0]
