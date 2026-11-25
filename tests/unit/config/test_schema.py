"""The schema's one-value check and its helpers (design 14 F1, F3)."""

import pytest

from tlaup.config.loader import parse_setting_text
from tlaup.config.schema import check_setting, closest_key, setting_keys
from tlaup.errors import ConfigKeyNotFound

GOOD_AND_BAD: list[tuple[str, object, object, object]] = [
    ("tool.repository", "https://ghe.example.com/repos/a/b", "https://ghe.example.com/repos/a/b", "http://x/y"),
    ("tool.token_hosts", ["Ghe.Example.com"], ["ghe.example.com"], ["https://x"]),
    ("java.min_version", 17, 17, "seventeen"),
    ("java.opts", ["-Xmx8g"], ["-Xmx8g"], "-Xmx8g"),
    ("tlc.workers", 4, 4, 0),
    ("tlc.workers", "auto", "auto", "many"),
    ("tlc.refresh_interval", 0.5, 0.5, "fast"),
    ("tlc.plain", True, True, "perhaps"),
    ("tlc.keep", False, False, [1]),
    ("module_path", "mods", "mods", ["a"]),
    ("module_path", None, None, 5),
    ("module_lib_path", "libs", "libs", {"a": 1}),
]


@pytest.mark.parametrize(("key", "value", "stored", "bad"), GOOD_AND_BAD)
def test_check_setting(key: str, value: object, stored: object, bad: object) -> None:
    assert check_setting(key, value) == stored
    with pytest.raises(ValueError, match=f"^{key}: ") as caught:
        check_setting(key, bad)
    assert not isinstance(caught.value, ConfigKeyNotFound)


def test_every_key_has_a_case() -> None:
    assert {case[0] for case in GOOD_AND_BAD} == set(setting_keys())


@pytest.mark.parametrize("key", ["no.such.key", "workspace.root", "tla.urls.tags", "tlc.java_class", "tlc", "tool"])
def test_a_key_that_is_not_a_setting(key: str) -> None:
    with pytest.raises(ConfigKeyNotFound):
        check_setting(key, 1)


def test_a_section_name_lists_its_keys() -> None:
    with pytest.raises(ConfigKeyNotFound) as caught:
        check_setting("tlc", 1)
    assert caught.value.hint is not None
    assert "tlc.workers" in caught.value.hint


def test_the_message_names_what_is_expected() -> None:
    with pytest.raises(ValueError, match=r'tlc\.workers: expected a positive integer or "auto", got "many"'):
        check_setting("tlc.workers", "many")


def test_host_names_are_lower_cased() -> None:
    assert check_setting("tool.token_hosts", ["A.Example.COM", "b.example.com"]) == ["a.example.com", "b.example.com"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("4", 4),
        ("auto", "auto"),
        ("[ghe.example.com]", ["ghe.example.com"]),
        ('["-Xmx8g", "-XX:+UseParallelGC"]', ["-Xmx8g", "-XX:+UseParallelGC"]),
        ("[]", []),
        ("true", True),
        ("null", None),
    ],
)
def test_parse_setting_text(text: str, expected: object) -> None:
    assert parse_setting_text(text) == expected


def test_parse_setting_text_refuses_python_tags_and_broken_flow() -> None:
    with pytest.raises(ValueError, match="cannot read the value"):
        parse_setting_text("[a")
    with pytest.raises(ValueError, match="cannot read the value"):
        parse_setting_text("!!python/object/apply:os.getcwd []")


def test_setting_keys_lists_the_ten_leaf_keys() -> None:
    assert setting_keys() == (
        "tool.repository",
        "tool.token_hosts",
        "java.min_version",
        "java.opts",
        "tlc.workers",
        "tlc.refresh_interval",
        "tlc.plain",
        "tlc.keep",
        "module_path",
        "module_lib_path",
    )


def test_closest_key() -> None:
    assert closest_key("tlc.worker") == "tlc.workers"
    assert closest_key("tlc.workers") == "tlc.workers"
    assert closest_key("completely.other") is None
