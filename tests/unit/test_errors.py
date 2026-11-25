import pytest

from tlaup import errors
from tlaup.errors import Failed, NotFound, NotSetUp, TlaupError, UsageError

FAMILIES: dict[type[TlaupError], tuple[int, str]] = {
    NotSetUp: (
        3,
        "NoToolsInstalled NoPinnedBuild PinnedBuildMissing JavaNotFound JavaTooOld JavacNotFound ConfigInvalid "
        "ToolNotInBuild CannotAsk",
    ),
    NotFound: (4, "SpecNotFound CfgNotFound VersionNotFound ModuleNotFound PathNotFound ConfigKeyNotFound"),
    Failed: (
        5,
        "NetworkError RateLimited RemoteDataError DownloadVerificationError ModuleBuildError StoreLocked "
        "FileOperationError ToolStartError InternalError",
    ),
    UsageError: (2, "AmbiguousVersion InvalidName ConflictingOptions"),
}


def _all_subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for sub in cls.__subclasses__():
        found.add(sub)
        found |= _all_subclasses(sub)
    return found


def _family(cls: type[TlaupError]) -> type[TlaupError]:
    return next(f for f in FAMILIES if issubclass(cls, f))


def test_every_subclass_has_its_familys_exit_code() -> None:
    subclasses = _all_subclasses(TlaupError)
    assert subclasses
    for cls in subclasses:
        assert cls.exit_code in (2, 3, 4, 5), cls
        assert cls.exit_code == FAMILIES[_family(cls)][0], cls  # type: ignore[arg-type]


def test_family_codes() -> None:
    assert [c.exit_code for c in (UsageError, NotSetUp, NotFound, Failed)] == [2, 3, 4, 5]


@pytest.mark.parametrize("family", list(FAMILIES))
def test_named_subclasses_exist_in_their_family(family: type[TlaupError]) -> None:
    for name in FAMILIES[family][1].split():
        cls = getattr(errors, name)
        assert issubclass(cls, family), name
        assert "exit_code" not in vars(cls), name


def test_named_subclasses_are_exactly_the_table() -> None:
    names = {n for _, (_, ns) in FAMILIES.items() for n in ns.split()}
    assert len(names) == 27
    families = set(FAMILIES)
    assert {c.__name__ for c in _all_subclasses(TlaupError)} == names | {f.__name__ for f in families}


def test_error_keeps_message_hint_and_details() -> None:
    err = errors.SpecNotFound("no spec", hint="try x", details="searched a, b")
    assert (err.message, err.hint, err.details) == ("no spec", "try x", "searched a, b")
    assert str(err) == "no spec"


def test_hint_and_details_default_to_none() -> None:
    err = errors.NetworkError("down")
    assert err.hint is None and err.details is None
