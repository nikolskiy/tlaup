"""The JVM options of a run (design 13 J1): the setting, then TLAUP_JAVA_OPTS, then each --java-opt.

Under `java/` so that the other tools (package 41) can import it without importing `tlc/`. `JAVA_OPTS` is not read
(decision D20).
"""

import shlex
from collections.abc import Mapping, Sequence

from tlaup.errors import UsageError

ENV_VARIABLE = "TLAUP_JAVA_OPTS"


def jvm_options(setting: Sequence[str], env: Mapping[str, str], flags: Sequence[str]) -> tuple[str, ...]:
    """The setting `java.opts`, then `TLAUP_JAVA_OPTS` split as a shell would, then each flag as given.

    Nothing is de-duplicated: for a repeated option the JVM decides, and the later one usually wins.
    Raises UsageError, naming the variable, for an unbalanced quote in it.
    """
    try:
        from_env = shlex.split(env.get(ENV_VARIABLE, ""))
    except ValueError as error:  # shlex's "No closing quotation" and "No escaped character"
        message = f"{ENV_VARIABLE} cannot be split into options: {error}"
        raise UsageError(message, hint=f"check the quotes in {ENV_VARIABLE}") from error
    return (*setting, *from_env, *flags)
