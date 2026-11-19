"""Hypothesis profiles for the stateful tests (design 01 T7): fixed and reproducible in CI."""

import os

try:
    from hypothesis import HealthCheck, settings
except ImportError:  # the test modules skip themselves when hypothesis is not installed
    pass
else:
    quiet = [HealthCheck.too_slow, HealthCheck.filter_too_much]
    common = {"deadline": None, "suppress_health_check": quiet, "database": None}  # no example database (T7)
    settings.register_profile("ci", derandomize=True, max_examples=200, **common)
    settings.register_profile("dev", max_examples=50, **common)
    settings.load_profile("ci" if os.environ.get("CI") else "dev")
