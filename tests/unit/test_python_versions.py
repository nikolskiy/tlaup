"""One rule ties the Python versions together (design 30 H3; inventory row P8).

The lowest supported version is the target, and the edges are tested: ``.python-version``, the
type checker and linter targets, ``requires-python``, the classifiers and the CI ``unit`` matrix
all agree.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
LOWEST = "3.11"
CLASSIFIER = re.compile(r"^Programming Language :: Python :: (3\.\d+)$")


def _pyproject() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _matrix_versions(workflow: dict[str, Any]) -> set[str]:
    cells = workflow["jobs"]["unit"]["strategy"]["matrix"]["include"]
    versions = [cell["python"] for cell in cells]
    for version in versions:
        assert isinstance(version, str), (
            f"a unit matrix cell in .github/workflows/test.yml has python: {version!r}, which YAML read as "
            f'{type(version).__name__}; quote the version (python: "3.10"), or 3.10 reads as 3.1'
        )
    return set(versions)


def _classifier_versions(pyproject: dict[str, Any]) -> set[str]:
    matches = (CLASSIFIER.match(item) for item in pyproject["project"]["classifiers"])
    return {m.group(1) for m in matches if m}


def _workflow() -> dict[str, Any]:
    return yaml.safe_load((ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8"))


def _lowest(versions: set[str]) -> str:
    return min(versions, key=lambda v: tuple(int(part) for part in v.split(".")))


def _compare_sets(classifiers: set[str], matrix: set[str]) -> str | None:
    if classifiers != matrix:
        return (
            f"pyproject.toml classifiers {sorted(classifiers)} and the unit matrix in "
            f".github/workflows/test.yml {sorted(matrix)} disagree"
        )
    if _lowest(classifiers) != LOWEST:
        return f"the lowest classifier/matrix version {_lowest(classifiers)} is not {LOWEST}"
    return None


def test_python_version_file_names_the_lowest_version() -> None:
    text = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    assert text == LOWEST, f".python-version says {text} but pyproject.toml's requires-python starts at {LOWEST}"


def test_tool_targets_and_requires_python_name_the_lowest_version() -> None:
    pyproject = _pyproject()
    requires = pyproject["project"]["requires-python"]
    assert requires == f">={LOWEST}", f"requires-python is {requires}, expected >={LOWEST} (inventory row P8)"
    ruff = pyproject["tool"]["ruff"]["target-version"]
    assert ruff == "py311", f"ruff target-version {ruff} and requires-python >={LOWEST} disagree"
    mypy = pyproject["tool"]["mypy"]["python_version"]
    assert mypy == LOWEST, f"mypy python_version {mypy} and requires-python >={LOWEST} disagree"


def test_classifiers_equal_the_unit_matrix() -> None:
    problem = _compare_sets(_classifier_versions(_pyproject()), _matrix_versions(_workflow()))
    assert problem is None, problem


def test_a_matrix_cell_without_a_classifier_is_reported() -> None:
    matrix = _matrix_versions(_workflow()) | {"3.13"}
    problem = _compare_sets(_classifier_versions(_pyproject()), matrix)
    assert problem is not None
    assert "disagree" in problem


def test_a_classifier_without_a_matrix_cell_is_reported() -> None:
    classifiers = _classifier_versions(_pyproject()) | {"3.13"}
    problem = _compare_sets(classifiers, _matrix_versions(_workflow()))
    assert problem is not None
    assert "disagree" in problem


def test_a_lowest_version_other_than_the_target_is_reported() -> None:
    versions = {"3.12", "3.15"}
    problem = _compare_sets(versions, versions)
    assert problem is not None
    assert "3.12" in problem
    assert LOWEST in problem


def test_an_unquoted_matrix_version_is_reported() -> None:
    workflow = yaml.safe_load("jobs: {unit: {strategy: {matrix: {include: [{python: 3.10}]}}}}")
    with pytest.raises(AssertionError, match="quote the version"):
        _matrix_versions(workflow)
