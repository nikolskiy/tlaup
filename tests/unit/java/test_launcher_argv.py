"""`JavaInvocation.argv()`: the lifeline, the encoding options and the order of the rest (design 20 G3, D51, D56)."""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest

from tlaup.java.launcher import ENCODING_OPTIONS, LIFELINE_JAR, JavaInvocation

ENCODINGS = ["-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8"]
MAIN_CLASSES = ["tlc2.TLC", "tla2sany.SANY", "pcal.trans", "tlc2.REPL"]


def invocation(main_class: str = "tlc2.TLC", **changes: object) -> JavaInvocation:
    inv = JavaInvocation(
        java=Path("/opt/jdk/bin/java"),
        jvm_options=("-Xmx2g", "-Dfile.encoding=ISO-8859-1"),
        system_properties=(("tlc2.tool.fp.FPSet.impl", "tlc2.tool.fp.OffHeapDiskFPSet"), ("a", "b=c")),
        classpath=(Path("/lib/tla2tools.jar"), Path("/project/classes")),
        main_class=main_class,
        args=("-workers", "auto", "Spec.tla"),
    )
    return dataclasses.replace(inv, **changes)  # type: ignore[arg-type]


def test_the_encoding_options_are_the_three_of_d56() -> None:
    assert list(ENCODING_OPTIONS) == ENCODINGS


@pytest.mark.parametrize("main_class", MAIN_CLASSES)
def test_the_order_of_the_arguments(main_class: str) -> None:
    classpath = os.pathsep.join(["/lib/tla2tools.jar", "/project/classes"])
    assert invocation(main_class).argv() == [
        "/opt/jdk/bin/java",
        f"-javaagent:{LIFELINE_JAR}=pid={os.getpid()}",
        *ENCODINGS,
        "-Xmx2g",
        "-Dfile.encoding=ISO-8859-1",
        "-Dtlc2.tool.fp.FPSet.impl=tlc2.tool.fp.OffHeapDiskFPSet",
        "-Da=b=c",
        "-cp",
        classpath,
        main_class,
        "-workers",
        "auto",
        "Spec.tla",
    ]


def test_the_lifeline_names_the_absolute_jar_and_this_process() -> None:
    agent = invocation().argv()[1]
    jar, _, pid = agent.removeprefix("-javaagent:").rpartition("=pid=")
    assert Path(jar).is_absolute()
    assert Path(jar).name == "lifeline.jar"
    assert Path(jar).is_file()  # package data beside the launcher (06)
    assert pid == str(os.getpid())


def test_a_users_encoding_option_comes_after_tlaups_own() -> None:
    argv = invocation().argv()
    assert argv.index("-Dfile.encoding=ISO-8859-1") > argv.index("-Dfile.encoding=UTF-8")


@pytest.mark.parametrize("main_class", MAIN_CLASSES)
def test_without_the_lifeline_the_agent_goes_and_the_encodings_stay(main_class: str) -> None:
    with_it = invocation(main_class).argv()
    without = invocation(main_class, lifeline=False).argv()
    assert not any(arg.startswith("-javaagent:") for arg in without)
    assert without == [with_it[0], *with_it[2:]]
    assert without[1:4] == ENCODINGS


def test_an_empty_classpath_leaves_cp_out() -> None:
    argv = invocation(classpath=()).argv()
    assert "-cp" not in argv
    assert argv[-4:] == ["tlc2.TLC", "-workers", "auto", "Spec.tla"]
