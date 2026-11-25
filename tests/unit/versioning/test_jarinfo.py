"""``read_jar`` on the recorded manifests packed into small jars (design 12 V5)."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from tests.jars import make_tools_jar
from tlaup.errors import DownloadVerificationError
from tlaup.versioning.jarinfo import read_jar

MANIFESTS = Path(__file__).resolve().parents[1] / "data" / "manifests"
ROLLING = MANIFESTS / "rolling.MANIFEST.MF"
V174 = MANIFESTS / "v1.7.4.MANIFEST.MF"
ROLLING_COMMIT = "bc1b506bdcad80bb518bf3776a9161c34ff0fc4c"
V174_COMMIT = "5a47802b5c391f59ecdd44117981f4ff8c0656ba"


def test_v174(tmp_path: Path) -> None:
    info = read_jar(make_tools_jar(tmp_path / "a.jar", V174))
    assert info.commit == V174_COMMIT
    assert info.built_at is None
    assert info.calver is None
    assert info.capabilities == frozenset()


def test_rolling(tmp_path: Path) -> None:
    info = read_jar(make_tools_jar(tmp_path / "a.jar", ROLLING))
    assert info.commit == ROLLING_COMMIT
    assert info.built_at == "2026-11-15T00:21:46.50Z"
    assert info.calver == "2026.11.15.002146"
    assert info.capabilities == {"calver", "overrides_property", "no_generate_spec_te"}


def test_rolling_with_repl(tmp_path: Path) -> None:
    info = read_jar(make_tools_jar(tmp_path / "a.jar", ROLLING, repl=True))
    assert info.capabilities == {"repl", "calver", "overrides_property", "no_generate_spec_te"}


def test_repl_alone(tmp_path: Path) -> None:
    info = read_jar(make_tools_jar(tmp_path / "a.jar", V174, repl=True))
    assert info.capabilities == {"repl"}


def test_wrapped_commit_line_and_crlf_give_the_same_commit(tmp_path: Path) -> None:
    text = ROLLING.read_text()
    line = f"X-Git-Revision: {ROLLING_COMMIT}"
    assert line in text
    wrapped = text.replace(line, f"{line[:30]}\n {line[30:]}")
    assert wrapped != text
    crlf = text.replace("\n", "\r\n")
    wrapped_crlf = wrapped.replace("\n", "\r\n")
    for name, data in [("w", wrapped), ("c", crlf), ("wc", wrapped_crlf)]:
        info = read_jar(make_tools_jar(tmp_path / f"{name}.jar", data.encode()))
        assert info.commit == ROLLING_COMMIT, name
        assert info.calver == "2026.11.15.002146", name


def test_upper_case_commit_is_lower_cased(tmp_path: Path) -> None:
    data = f"Manifest-Version: 1.0\nX-Git-Revision: {ROLLING_COMMIT.upper()}\n".encode()
    assert read_jar(make_tools_jar(tmp_path / "a.jar", data)).commit == ROLLING_COMMIT


def test_manifest_without_revision_has_no_commit(tmp_path: Path) -> None:
    lines = [x for x in ROLLING.read_text().splitlines() if not x.startswith("X-Git-Revision")]
    info = read_jar(make_tools_jar(tmp_path / "a.jar", "\n".join(lines).encode() + b"\n"))
    assert info.commit is None
    assert info.calver == "2026.11.15.002146"


@pytest.mark.parametrize("value", ["", "bc1b506", "not-a-commit", ROLLING_COMMIT + "0", "g" * 40])
def test_malformed_revision_is_no_commit(tmp_path: Path, value: str) -> None:
    data = f"Manifest-Version: 1.0\nX-Git-Revision: {value}\n".encode()
    assert read_jar(make_tools_jar(tmp_path / "a.jar", data)).commit is None


def test_unreadable_build_time_is_no_build_time(tmp_path: Path) -> None:
    data = b"Manifest-Version: 1.0\nBuild-TimeStamp: yesterday\n"
    info = read_jar(make_tools_jar(tmp_path / "a.jar", data))
    assert info.built_at is None
    assert info.calver is None
    assert info.capabilities == frozenset()


def test_build_time_with_an_offset_is_written_in_utc(tmp_path: Path) -> None:
    data = b"Manifest-Version: 1.0\nBuild-TimeStamp: 2026-11-15T02:21:46.99+02:00\n"
    assert read_jar(make_tools_jar(tmp_path / "a.jar", data)).calver == "2026.11.15.002146"


def test_sha256_and_size_are_the_files(tmp_path: Path) -> None:
    jar = make_tools_jar(tmp_path / "a.jar", ROLLING)
    info = read_jar(jar)
    assert info.sha256 == hashlib.sha256(jar.read_bytes()).hexdigest()
    assert info.size == jar.stat().st_size


def test_a_class_file_of_a_few_bytes_of_text_is_accepted(tmp_path: Path) -> None:
    jar = tmp_path / "a.jar"
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
        z.writestr("tlc2/TLC.class", "not a class")
    assert read_jar(jar).commit is None


def test_zip_without_manifest(tmp_path: Path) -> None:
    jar = tmp_path / "a.jar"
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("tlc2/TLC.class", b"x")
    with pytest.raises(DownloadVerificationError):
        read_jar(jar)


def test_zip_without_tlc_class(tmp_path: Path) -> None:
    jar = tmp_path / "a.jar"
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("META-INF/MANIFEST.MF", ROLLING.read_bytes())
        z.writestr("tlc2/REPL.class", b"x")
    with pytest.raises(DownloadVerificationError):
        read_jar(jar)


def test_text_file(tmp_path: Path) -> None:
    path = tmp_path / "a.jar"
    path.write_text("<html>Not found</html>")
    with pytest.raises(DownloadVerificationError):
        read_jar(path)


def test_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "a.jar"
    path.write_bytes(b"")
    with pytest.raises(DownloadVerificationError):
        read_jar(path)


def test_zip_cut_to_half(tmp_path: Path) -> None:
    jar = make_tools_jar(tmp_path / "a.jar", ROLLING)
    data = jar.read_bytes()
    jar.write_bytes(data[: len(data) // 2])
    with pytest.raises(DownloadVerificationError):
        read_jar(jar)


def test_damaged_entry(tmp_path: Path) -> None:
    jar = tmp_path / "a.jar"
    with zipfile.ZipFile(jar, "w", zipfile.ZIP_STORED) as z:
        z.writestr("META-INF/MANIFEST.MF", ROLLING.read_bytes())
        z.writestr("tlc2/TLC.class", b"A" * 200)
    data = bytearray(jar.read_bytes())
    at = data.index(b"A" * 200)
    data[at + 50] = ord("B")
    jar.write_bytes(bytes(data))
    with pytest.raises(DownloadVerificationError):
        read_jar(jar)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DownloadVerificationError):
        read_jar(tmp_path / "nothing.jar")


def test_a_folder(tmp_path: Path) -> None:
    with pytest.raises(DownloadVerificationError):
        read_jar(tmp_path)


@pytest.mark.parametrize(
    "stamp", ["0001-01-01T00:00:00+02:00", "9999-12-31T23:59:59-05:00", "0999-05-05T00:00:00Z", "2026-13-45T00:00:00Z"]
)
def test_out_of_range_build_time_is_no_build_time(tmp_path: Path, stamp: str) -> None:
    data = f"Manifest-Version: 1.0\nBuild-TimeStamp: {stamp}\n".encode()
    info = read_jar(make_tools_jar(tmp_path / "a.jar", data))
    assert info.built_at is None
    assert info.calver is None
    assert info.capabilities == frozenset()
