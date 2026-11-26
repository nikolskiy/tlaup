"""The three sources of the JVM options and their order (design 13 J1)."""

import pytest

from tlaup.errors import UsageError
from tlaup.java.opts import jvm_options

DEFAULTS = ("-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC")


def test_the_three_sources_combine_in_order() -> None:
    options = jvm_options(DEFAULTS, {"TLAUP_JAVA_OPTS": "-Xmx2g -Xss4m"}, ["-Xss8m", "-Xmx2g"])
    assert options == (*DEFAULTS, "-Xmx2g", "-Xss4m", "-Xss8m", "-Xmx2g")  # nothing de-duplicated


def test_no_variable_and_no_flags_is_the_setting() -> None:
    assert jvm_options(DEFAULTS, {}, []) == DEFAULTS
    assert jvm_options([], {"TLAUP_JAVA_OPTS": ""}, []) == ()


def test_a_quoted_value_in_the_variable_is_one_option() -> None:
    options = jvm_options([], {"TLAUP_JAVA_OPTS": '-Xmx2g -Dx="a b"'}, [])
    assert options == ("-Xmx2g", "-Dx=a b")


def test_a_flag_is_one_option_as_given() -> None:
    assert jvm_options([], {}, ['-Dx="a b"', "-Dy=c d"]) == ('-Dx="a b"', "-Dy=c d")


@pytest.mark.parametrize("value", ['-Dx="a b', "-Dx='a", "-Dx=a\\"])
def test_an_unbalanced_quote_is_a_usage_error_naming_the_variable(value: str) -> None:
    with pytest.raises(UsageError) as caught:
        jvm_options(DEFAULTS, {"TLAUP_JAVA_OPTS": value}, [])
    assert "TLAUP_JAVA_OPTS" in caught.value.message
    assert caught.value.exit_code == 2


def test_java_opts_changes_nothing() -> None:
    assert jvm_options(DEFAULTS, {"JAVA_OPTS": "-Xmx1g"}, []) == DEFAULTS
    assert jvm_options(DEFAULTS, {"JAVA_OPTS": "-Xmx1g", "TLAUP_JAVA_OPTS": "-Xss8m"}, []) == (*DEFAULTS, "-Xss8m")
