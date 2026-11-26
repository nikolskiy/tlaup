"""The `config` commands' helpers (design 14 F1): the text of a value, and `show` read back."""

import os

import pytest
import yaml
from typer.testing import CliRunner

import tlaup.cli
from tests.conftest import Isolated
from tlaup.cmd.config import format_value
from tlaup.config.loader import load_settings


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("auto", "auto"),
        (4, "4"),
        (1.0, "1.0"),
        (True, "true"),
        (None, "null"),
        (["ghe.example.com"], "[ghe.example.com]"),
    ],
)
def test_a_value_is_written_as_config_set_reads_it(value: object, text: str) -> None:
    assert format_value(value) == text
    assert yaml.safe_load(text) == value


def test_show_loads_back_to_the_settings_in_effect(isolated: Isolated) -> None:
    isolated.paths.config_file.parent.mkdir(parents=True)
    isolated.paths.config_file.write_text("tlc:\n  workers: 4\nmodule_path: 'a: b'\n", encoding="utf-8")
    result = CliRunner().invoke(tlaup.cli.app, ["config", "show"])
    assert result.exit_code == 0
    shown = yaml.safe_load(result.stdout)
    assert shown == load_settings(isolated.paths, os.environ).settings.model_dump()
    assert shown["tlc"]["workers"] == 4
    assert shown["module_path"] == "a: b"
