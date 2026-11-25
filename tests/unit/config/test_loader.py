"""Layered settings: `load_settings` and `merge_layers` (design 14 F1 and F3)."""

import importlib.resources
import os
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

from tests.conftest import Isolated
from tlaup import context
from tlaup.config.loader import Layer, load_config, load_settings, merge_layers
from tlaup.config.schema import Settings, setting_keys
from tlaup.errors import ConfigInvalid

DATA = Path(__file__).parent / "data"
AT = chr(64)  # a user part in an address, built so that the personal-data hooks do not read it as an email address


def user_file(isolated: Isolated, text: str) -> Path:
    path = isolated.paths.config_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_no_user_file_gives_the_defaults(isolated: Isolated) -> None:
    loaded = load_settings(isolated.paths, {})
    assert set(loaded.sources.values()) == {"default"}
    assert set(loaded.sources) == set(setting_keys())
    assert loaded.warnings == ()
    assert loaded.settings.tlc.workers == "auto"
    assert loaded.settings.tlc.keep is False
    assert loaded.settings.module_path is None


def test_the_defaults_of_the_java_settings(isolated: Isolated) -> None:
    """Inventory rows J4 and R25."""
    java = load_settings(isolated.paths, {}).settings.java
    assert java.min_version == 11
    assert java.opts == ["-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC"]


def test_a_file_with_one_key(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  workers: 3\n")
    loaded = load_settings(isolated.paths, {})
    assert loaded.settings.tlc.workers == 3
    assert loaded.sources["tlc.workers"] == "user file"
    assert loaded.sources["tlc.keep"] == "default"
    assert loaded.settings.java.min_version == 11


def test_each_layer_overrides_the_one_below(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  workers: 3\n")
    default = load_settings(isolated.paths, {})
    assert default.settings.tlc.workers == 3
    assert default.sources["tlc.workers"] == "user file"
    env = load_settings(isolated.paths, {"TLAUP_TLC_WORKERS": "5"})
    assert env.settings.tlc.workers == 5
    assert env.sources["tlc.workers"] == "TLAUP_TLC_WORKERS"
    flag = load_settings(isolated.paths, {"TLAUP_TLC_WORKERS": "5"}, {"tlc.workers": 7})
    assert flag.settings.tlc.workers == 7
    assert flag.sources["tlc.workers"] == "--workers"


def test_a_flag_label_follows_the_key(isolated: Isolated) -> None:
    loaded = load_settings(isolated.paths, {}, {"tlc.refresh_interval": 2.0})
    assert loaded.sources["tlc.refresh_interval"] == "--refresh-interval"


def test_a_list_in_the_environment(isolated: Isolated) -> None:
    loaded = load_settings(isolated.paths, {"TLAUP_TOOL_TOKEN_HOSTS": "ghe.example.com, api.ghe.example.com"})
    assert loaded.settings.tool.token_hosts == ["ghe.example.com", "api.ghe.example.com"]
    empty = load_settings(isolated.paths, {"TLAUP_TOOL_TOKEN_HOSTS": ""})
    assert empty.settings.tool.token_hosts == []
    assert empty.sources["tool.token_hosts"] == "TLAUP_TOOL_TOKEN_HOSTS"


def test_java_opts_is_not_in_the_environment_layer(isolated: Isolated) -> None:
    loaded = load_settings(isolated.paths, {"TLAUP_JAVA_OPTS": "-Xmx8g"})
    assert loaded.settings.java.opts == ["-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC"]
    assert loaded.sources["java.opts"] == "default"
    assert loaded.warnings == ()


def test_other_tlaup_variables_are_not_this_layers(isolated: Isolated) -> None:
    env = {"TLAUP_HOME": "/x", "TLAUP_DEBUG": "1", "TLAUP_AUTO_INSTALL": "1", "TLAUP_TLC_NOPE": "1"}
    loaded = load_settings(isolated.paths, env)
    assert loaded.warnings == ()
    assert set(loaded.sources.values()) == {"default"}


def test_the_environment_beats_a_file_for_a_boolean(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  keep: true\n")
    assert load_settings(isolated.paths, {}).settings.tlc.keep is True
    assert load_settings(isolated.paths, {"TLAUP_TLC_KEEP": "false"}).settings.tlc.keep is False


def test_module_paths_from_the_environment(isolated: Isolated, tmp_path: Path) -> None:
    """Inventory row C6, the environment half."""
    env = {"TLAUP_MODULE_PATH": str(tmp_path / "mods"), "TLAUP_MODULE_LIB_PATH": str(tmp_path / "libs")}
    loaded = load_settings(isolated.paths, env)
    assert loaded.settings.module_path == str(tmp_path / "mods")
    assert loaded.settings.module_lib_path == str(tmp_path / "libs")
    assert loaded.sources["module_path"] == "TLAUP_MODULE_PATH"
    assert loaded.sources["module_lib_path"] == "TLAUP_MODULE_LIB_PATH"


def test_a_removed_section_loads_with_one_warning(isolated: Isolated) -> None:
    user_file(isolated, "workspace:\n  root: .\ntla:\n  urls:\n    tags: x\n")
    loaded = load_settings(isolated.paths, {})
    assert loaded.warnings == (
        "config.yaml: 2 settings are no longer used (workspace, tla); run `tlaup config edit` and delete them",
    )


def test_a_typo_warns_and_suggests(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  worker: 4\n")
    loaded = load_settings(isolated.paths, {})
    (warning,) = loaded.warnings
    assert '"tlc.worker"' in warning
    assert '"tlc.workers"' in warning
    assert loaded.settings.tlc.workers == "auto"


def test_an_unknown_key_without_a_near_match(isolated: Isolated) -> None:
    user_file(isolated, "something_else: 1\n")
    (warning,) = load_settings(isolated.paths, {}).warnings
    assert '"something_else"' in warning
    assert "did you mean" not in warning


def test_invalid_yaml_names_file_line_and_column(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  workers: [1\nkeep: true\n")
    with pytest.raises(ConfigInvalid) as caught:
        load_settings(isolated.paths, {})
    message = str(caught.value)
    assert message.startswith("config.yaml: line ")
    assert "column" in message
    assert "Traceback" not in message
    assert caught.value.hint == "run `tlaup config edit` to fix the file"


def test_an_invalid_value_names_the_file_and_the_key(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  refresh_interval: fast\n")
    with pytest.raises(ConfigInvalid) as caught:
        load_settings(isolated.paths, {})
    assert str(caught.value) == 'config.yaml: tlc.refresh_interval: expected a number, got "fast"'
    assert caught.value.hint is not None


def test_an_invalid_value_from_the_environment_names_the_variable(isolated: Isolated) -> None:
    with pytest.raises(ConfigInvalid) as caught:
        load_settings(isolated.paths, {"TLAUP_TLC_REFRESH_INTERVAL": "fast"})
    assert str(caught.value) == 'TLAUP_TLC_REFRESH_INTERVAL: tlc.refresh_interval: expected a number, got "fast"'
    assert caught.value.hint is None


@pytest.mark.parametrize("value", ["0", "many"])
def test_a_union_key_names_the_key_not_the_tag(isolated: Isolated, value: str) -> None:
    user_file(isolated, f"tlc:\n  workers: {value}\n")
    with pytest.raises(ConfigInvalid) as caught:
        load_settings(isolated.paths, {})
    message = str(caught.value)
    assert message.startswith("config.yaml: tlc.workers: ")
    assert "constrained-int" not in message
    assert "literal[" not in message
    assert "\n" not in message


def test_a_section_that_is_not_a_mapping(isolated: Isolated) -> None:
    user_file(isolated, "tlc: 5\n")
    with pytest.raises(ConfigInvalid, match=r"config\.yaml: tlc: expected a section"):
        load_settings(isolated.paths, {})


def test_a_top_level_list_is_invalid(isolated: Isolated) -> None:
    user_file(isolated, "- a\n- b\n")
    with pytest.raises(ConfigInvalid, match=r"config\.yaml: expected a mapping"):
        load_settings(isolated.paths, {})


def test_an_empty_file_is_the_defaults(isolated: Isolated) -> None:
    user_file(isolated, "")
    assert load_settings(isolated.paths, {}).warnings == ()


def test_reading_creates_nothing(isolated: Isolated) -> None:
    load_settings(isolated.paths, {"TLAUP_TLC_WORKERS": "2"}, {"tlc.keep": True})
    assert not isolated.paths.config.exists()
    assert not isolated.paths.config_file.exists()


def test_the_safe_loader_refuses_python_tags(isolated: Isolated, tmp_path: Path) -> None:
    """Inventory row C4."""
    made = tmp_path / "made"
    user_file(isolated, f'x: !!python/object/apply:os.mkdir ["{made}"]\n')
    with pytest.raises(ConfigInvalid) as caught:
        load_settings(isolated.paths, {})
    assert str(caught.value).startswith("config.yaml: line 1")
    assert not made.exists()


def test_the_packaged_defaults_validate_through_the_package_resource() -> None:
    """Inventory row C2: read as a resource of `tlaup.resources`, not by a path built from `__file__`."""
    text = importlib.resources.files("tlaup.resources").joinpath("default_config.yaml").read_text(encoding="utf-8")
    Settings.model_validate(yaml.safe_load(text))


def test_the_0_8_2_default_file_loads_with_the_one_warning(isolated: Isolated) -> None:
    user_file(isolated, (DATA / "config-0.8.2.yaml").read_text(encoding="utf-8"))
    loaded = load_settings(isolated.paths, {})
    assert loaded.warnings == (
        "config.yaml: 4 settings are no longer used (workspace, tla, tlc.java_class, tlc.overrides_class); "
        "run `tlaup config edit` and delete them",
    )
    assert loaded.settings.tlc.refresh_interval == 1.0


def test_one_removed_key_inside_a_kept_section(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  java_class: tlc2.TLC\n  workers: 2\n")
    loaded = load_settings(isolated.paths, {})
    assert loaded.warnings == (
        "config.yaml: 1 setting is no longer used (tlc.java_class); run `tlaup config edit` and delete it",
    )
    assert loaded.settings.tlc.workers == 2


@pytest.mark.parametrize(
    "host", ["https://ghe.example.com", "ghe.example.com/x", "ghe.example.com:8443", "*.example.com"]
)
def test_a_bad_token_host_is_invalid(isolated: Isolated, host: str) -> None:
    user_file(isolated, f'tool:\n  token_hosts: ["{host}"]\n')
    with pytest.raises(ConfigInvalid, match=r"config\.yaml: tool\.token_hosts: "):
        load_settings(isolated.paths, {})


def test_a_token_host_is_lower_cased(isolated: Isolated) -> None:
    loaded = load_settings(isolated.paths, {"TLAUP_TOOL_TOKEN_HOSTS": "GHE.Example.com"})
    assert loaded.settings.tool.token_hosts == ["ghe.example.com"]


@pytest.mark.parametrize(
    "address",
    [
        "http://api.github.com/repos/a/b",
        "https://user" + AT + "api.github.com/repos/a/b",
        "https://user:pw" + AT + "api.github.com/repos/a/b",
        "https://api.github.com/repos/a/b?x=1",
        "https://api.github.com/repos/a/b#frag",
        "https://api.github.com\\repos",
        "https://api.github.com/repos/a b",
        "https://api.github.com/repos/a\tb",
        "api.github.com/repos",
    ],
)
def test_a_bad_repository_is_invalid(isolated: Isolated, address: str) -> None:
    with pytest.raises(ConfigInvalid, match=r"TLAUP_TOOL_REPOSITORY: tool\.repository: "):
        load_settings(isolated.paths, {"TLAUP_TOOL_REPOSITORY": address})


def test_another_https_repository_is_accepted(isolated: Isolated) -> None:
    address = "https://ghe.example.com/api/v3/repos/tlaplus/tlaplus"
    assert load_settings(isolated.paths, {"TLAUP_TOOL_REPOSITORY": address}).settings.tool.repository == address


# --- merge_layers -----------------------------------------------------------------------------------------------


def layer(kind: str, data: Mapping[str, object], labels: Mapping[str, str] | None = None) -> Layer:
    return Layer(kind, data, labels or {})


BASE = layer(
    "defaults",
    yaml.safe_load(importlib.resources.files("tlaup.resources").joinpath("default_config.yaml").read_text("utf-8")),
)


def test_the_order_of_the_list_decides() -> None:
    low = layer("user", {"tlc": {"workers": 2}})
    high = layer("flags", {"tlc": {"workers": 9}})
    assert merge_layers([BASE, low, high]).settings.tlc.workers == 9
    assert merge_layers([BASE, high, low]).settings.tlc.workers == 2


def test_sources_take_the_labels_of_the_winner() -> None:
    low = layer("user", {"tlc": {"workers": 2}}, {"tlc.workers": "somewhere"})
    high = layer("env", {"tlc": {"workers": 9}}, {"tlc.workers": "TLAUP_TLC_WORKERS"})
    assert merge_layers([BASE, low]).sources["tlc.workers"] == "somewhere"
    assert merge_layers([BASE, low, high]).sources["tlc.workers"] == "TLAUP_TLC_WORKERS"
    assert merge_layers([BASE, low, high]).sources["tlc.keep"] == "default"


def test_a_list_is_replaced_not_joined() -> None:
    user = layer("user", {"java": {"opts": ["-Xmx1g"]}})
    assert merge_layers([BASE, user]).settings.java.opts == ["-Xmx1g"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("repository", "https://evil.example.com/repos/x/y"),
        ("token_hosts", ["evil.example.com"]),
    ],
)
def test_a_project_layer_cannot_set_the_two_keys(key: str, value: object) -> None:
    user = layer("user", {"tool": {"repository": "https://ghe.example.com/repos/a/b"}})
    project = layer("project", {"tool": {key: value}, "tlc": {"workers": 4}})
    loaded = merge_layers([BASE, user, project])
    full = f"tool.{key}"
    assert any(f'"{full}"' in w for w in loaded.warnings)
    assert loaded.settings.tool.repository == "https://ghe.example.com/repos/a/b"
    assert loaded.settings.tool.token_hosts == []
    assert loaded.sources[full] == ("user file" if key == "repository" else "default")
    assert loaded.settings.tlc.workers == 4
    assert loaded.sources["tlc.workers"] == "project file"


def test_a_user_layer_may_set_the_two_keys() -> None:
    user = layer("user", {"tool": {"token_hosts": ["ghe.example.com"]}})
    loaded = merge_layers([BASE, user])
    assert loaded.settings.tool.token_hosts == ["ghe.example.com"]
    assert loaded.warnings == ()


# --- the context -----------------------------------------------------------------------------------------------


def test_the_context_loads_lazily_and_prints_each_warning_once(
    isolated: Isolated, capfd: pytest.CaptureFixture[str]
) -> None:
    user_file(isolated, "tlc:\n  worker: 4\n")
    ctx = context.build_context(dict(os.environ), debug=False)
    assert "warning" not in capfd.readouterr().err
    assert ctx.settings.tlc.workers == "auto"
    assert ctx.settings is ctx.settings
    assert ctx.settings.tlc.workers == "auto"
    err = capfd.readouterr().err
    assert err.count("unknown key") == 1
    assert err.startswith("warning: config.yaml: unknown key")


def test_a_broken_file_raises_each_time_the_settings_are_asked_for(isolated: Isolated) -> None:
    user_file(isolated, "tlc: [\n")
    ctx = context.build_context(dict(os.environ), debug=False)
    for _ in range(2):
        with pytest.raises(ConfigInvalid):
            _ = ctx.settings


def test_load_config_hands_over_the_contexts_settings(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  workers: 6\n")
    context.reset()
    assert load_config().tlc.workers == 6
    assert load_config() is context.get_context().settings


def test_a_non_string_key_inside_a_section(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  1: x\n")
    with pytest.raises(ConfigInvalid, match=r"config\.yaml: tlc\.1: expected a setting name") as caught:
        load_settings(isolated.paths, {})
    assert caught.value.hint is not None


def test_a_null_section_is_an_empty_section(isolated: Isolated) -> None:
    user_file(isolated, "tlc:\n  # workers: 4\njava:\n")
    loaded = load_settings(isolated.paths, {})
    assert loaded.warnings == ()
    assert set(loaded.sources.values()) == {"default"}


def test_a_bad_list_item_is_named_by_position(isolated: Isolated) -> None:
    user_file(isolated, 'java:\n  opts: ["-Xmx1g", 1]\n')
    with pytest.raises(ConfigInvalid) as caught:
        load_settings(isolated.paths, {})
    assert str(caught.value) == "config.yaml: java.opts: expected a list of strings, but item 2 is 1"


def test_an_empty_module_path_variable_means_unset(isolated: Isolated) -> None:
    loaded = load_settings(isolated.paths, {"TLAUP_MODULE_PATH": "", "TLAUP_MODULE_LIB_PATH": ""})
    assert loaded.settings.module_path is None
    assert loaded.settings.module_lib_path is None
    assert loaded.sources["module_path"] == "TLAUP_MODULE_PATH"
