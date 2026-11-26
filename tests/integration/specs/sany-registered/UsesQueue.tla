\* For test_tools.py::test_sany_streams_and_modules: a spec that extends QueueUtils, a module of the registered
\* QueueModule example, which SANY must find through the module's folder (design 21 S1, research 27).
---- MODULE UsesQueue ----
EXTENDS QueueUtils
VARIABLE x
Init == x = 0
====
