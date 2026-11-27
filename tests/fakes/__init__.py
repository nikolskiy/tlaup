"""Fake ``java``, ``javac``, ``git`` and editor for the tests (design 01 T4).

The four fakes (``java.py``, ``javac.py``, ``git.py``, ``editor.py``) run as their own processes
through launchers; ``control.py`` writes the launchers and holds the ``Fakes`` object the
``fakes`` fixture returns.
"""
