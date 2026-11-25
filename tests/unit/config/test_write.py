"""`write_user_setting`, the one writer (design 14 F1)."""

import os
import stat
from pathlib import Path

import pytest
import yaml

from tests.conftest import Isolated
from tlaup.config.loader import CONFIG_HEADER, load_settings, write_user_setting
from tlaup.errors import ConfigInvalid, FileOperationError


def test_no_file_before(isolated: Isolated) -> None:
    write_user_setting(isolated.paths, "tlc.workers", 4)
    text = isolated.paths.config_file.read_text(encoding="utf-8")
    assert text.startswith(CONFIG_HEADER + "\n")
    assert yaml.safe_load(text) == {"tlc": {"workers": 4}}
    assert load_settings(isolated.paths, {}).settings.tlc.workers == 4


def test_other_keys_keep_their_values(isolated: Isolated) -> None:
    path = isolated.paths.config_file
    path.parent.mkdir(parents=True)
    path.write_text("tlc:\n  keep: true\njava:\n  min_version: 17\n", encoding="utf-8")
    write_user_setting(isolated.paths, "tlc.workers", "auto")
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {
        "tlc": {"keep": True, "workers": "auto"},
        "java": {"min_version": 17},
    }


def test_a_comment_is_lost_and_the_header_kept(isolated: Isolated) -> None:
    path = isolated.paths.config_file
    path.parent.mkdir(parents=True)
    path.write_text("# my note\ntlc:\n  keep: true  # because\n", encoding="utf-8")
    write_user_setting(isolated.paths, "tlc.plain", True)
    text = path.read_text(encoding="utf-8")
    assert "my note" not in text
    assert "because" not in text
    assert text.splitlines()[0] == CONFIG_HEADER


def test_a_list_value(isolated: Isolated) -> None:
    write_user_setting(isolated.paths, "tool.token_hosts", ["ghe.example.com", "b.example.com"])
    write_user_setting(isolated.paths, "java.opts", ["-Xmx8g", "-XX:+UseParallelGC"])
    loaded = load_settings(isolated.paths, {})
    assert loaded.settings.tool.token_hosts == ["ghe.example.com", "b.example.com"]
    assert loaded.settings.java.opts == ["-Xmx8g", "-XX:+UseParallelGC"]


def test_a_top_level_key(isolated: Isolated, tmp_path: Path) -> None:
    write_user_setting(isolated.paths, "module_path", str(tmp_path))
    assert load_settings(isolated.paths, {}).settings.module_path == str(tmp_path)


def test_a_file_that_does_not_parse_is_not_rewritten(isolated: Isolated) -> None:
    path = isolated.paths.config_file
    path.parent.mkdir(parents=True)
    broken = "tlc: [\n"
    path.write_text(broken, encoding="utf-8")
    with pytest.raises(ConfigInvalid):
        write_user_setting(isolated.paths, "tlc.workers", 2)
    assert path.read_text(encoding="utf-8") == broken


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores folder permissions")
def test_a_failed_write_leaves_the_old_file(isolated: Isolated) -> None:
    path = isolated.paths.config_file
    path.parent.mkdir(parents=True)
    path.write_bytes(b"tlc:\n  keep: true\n")
    path.parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(FileOperationError):
            write_user_setting(isolated.paths, "tlc.workers", 2)
    finally:
        path.parent.chmod(stat.S_IRWXU)
    assert path.read_bytes() == b"tlc:\n  keep: true\n"
    assert [p.name for p in path.parent.iterdir()] == ["config.yaml"]
