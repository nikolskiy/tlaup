"""Domain errors. The class attribute `exit_code` is the whole mapping to exit codes."""

from typing import ClassVar


class TlaupError(Exception):
    """Base of tlaup's own errors.

    `message` is one line with no trailing full stop and no "Error:" prefix; `hint` is one line that names the
    next command; `details` is optional longer text.
    """

    exit_code: ClassVar[int]

    def __init__(self, message: str, *, hint: str | None = None, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.details = details


class UsageError(TlaupError):
    exit_code = 2


class NotSetUp(TlaupError):  # noqa: N818
    exit_code = 3


class NotFound(TlaupError):  # noqa: N818
    exit_code = 4


class Failed(TlaupError):  # noqa: N818
    exit_code = 5


class NoToolsInstalled(NotSetUp):
    pass


class NoPinnedBuild(NotSetUp):
    pass


class PinnedBuildMissing(NotSetUp):
    pass


class JavaNotFound(NotSetUp):
    pass


class JavaTooOld(NotSetUp):
    pass


class JavacNotFound(NotSetUp):
    pass


class ConfigInvalid(NotSetUp):
    pass


class ToolNotInBuild(NotSetUp):
    pass


class CannotAsk(NotSetUp):
    pass


class SpecNotFound(NotFound):
    pass


class CfgNotFound(NotFound):
    pass


class VersionNotFound(NotFound):
    pass


class ModuleNotFound(NotFound):
    pass


class PathNotFound(NotFound):
    pass


class ConfigKeyNotFound(NotFound):
    pass


class NetworkError(Failed):
    pass


class RateLimited(Failed):
    pass


class RemoteDataError(Failed):
    pass


class DownloadVerificationError(Failed):
    pass


class ModuleBuildError(Failed):
    pass


class StoreLocked(Failed):
    pass


class FileOperationError(Failed):
    pass


class ToolStartError(Failed):
    pass


class InternalError(Failed):
    pass


class AmbiguousVersion(UsageError):  # noqa: N818
    pass


class InvalidName(UsageError):  # noqa: N818
    pass


class ConflictingOptions(UsageError):  # noqa: N818
    pass
