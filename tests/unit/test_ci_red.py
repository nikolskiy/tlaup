"""A deliberately failing test for the red run of the CI check `Test`; revert it after."""

from __future__ import annotations

import os


def test_ci_red_run() -> None:
    assert os.environ.get("CI") != "true"
