"""The module steps of design 01 T5 that package 31 owns, as helpers over the registry and the fake sources.

``given.py`` and ``then.py`` wrap these. The registry is read and written through ``Registry`` and
``build_module`` only, with the scenario's injected clock (the one the store steps use).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from tests.fakes._fakelib import FAKES_DIR
from tests.steps import _store
from tests.steps._scenario import Scenario, fail
from tlaup.errors import TlaupError
from tlaup.modules.build import build_module
from tlaup.modules.registry import Registry

SOURCES = FAKES_DIR / "module-src"
JAVAC_ERRORS = FAKES_DIR / "javac-errors"
COLUMN = "module"


def registry(scenario: Scenario) -> Registry:
    """The registry as a step sees it, with the scenario's clock."""
    return Registry(_store.paths().modules, now=_store.state(scenario).clock.now)


def module_source(scenario: Scenario, name: str) -> None:
    """``a module source "<name>" from the fake sources``: the folder is copied into the current folder."""
    source = SOURCES / name
    if not source.is_dir():
        fail(f"no fake module source {name}: {source} does not exist")
    shutil.copytree(source, Path.cwd() / name)
    scenario.write_javac()  # the fake javac answers with its script, which this scenario will want


def registered(scenario: Scenario, name: str) -> None:
    """``the module "<name>" is registered``: a module of one ``.tla`` file, through ``build_module``.

    It has no Java sources, so a build, a javac and the registry's lock are all it needs and none is asked for:
    the files are what a real add of such a module leaves, and no fake is started.
    """
    clock = _store.state(scenario).clock
    source = scenario.folder / "registered" / name
    (source / "modules").mkdir(parents=True)
    (source / "modules" / f"{name}.tla").write_text(f"---- MODULE {name} ----\n====\n", encoding="utf-8")

    def unwanted() -> None:
        fail("a registered module of .tla files only asked for a build or a javac")

    try:
        build_module(
            source,
            registry=registry(scenario),
            get_build=unwanted,  # type: ignore[arg-type]
            get_javac=unwanted,  # type: ignore[arg-type]
            release=11,
            now=clock.now,
        )
    except TlaupError as error:
        fail(f'the module "{name}" could not be registered: {error.message}')
    clock.advance(60)


def javac_fails(scenario: Scenario, recording: str) -> None:
    """``javac fails with "<recording>"``: the fake prints ``tests/fakes/javac-errors/<recording>.txt`` and exits 1."""
    if not (JAVAC_ERRORS / f"{recording}.txt").is_file():
        fail(f"no recorded javac error {recording}: {JAVAC_ERRORS / (recording + '.txt')} does not exist")
    scenario.javac_settings["fail_with"] = f"{recording}.txt"
    scenario.write_javac()


def check_registered(scenario: Scenario, datatable: list[list[str]]) -> None:
    """``the registered modules are:``: one column, headed ``module``, the names in ``Registry.list()`` order."""
    if not datatable or [cell.strip() for cell in datatable[0]] != [COLUMN]:
        fail(f'"the registered modules are:" takes a table of one column headed "{COLUMN}"')
    wanted = [row[0].strip() for row in datatable[1:]]
    actual = [module.name for module in registry(scenario).list()]
    if actual != wanted:
        fail(f"the registered modules are {actual}, not {wanted}")
