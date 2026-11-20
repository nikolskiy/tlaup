"""Question 30: a settings model shaped like design 14 F1/F3, checked on one pydantic version.

    uv run --no-project -p 3.11 --with pydantic==<v> python pydantic_probe.py
Prints PASS/FAIL per feature and a summary line.
"""

from __future__ import annotations

import sys
from typing import Annotated, Any, Literal, Union

import pydantic
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

results: list[tuple[str, bool, str]] = []


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:  # noqa: BLE001
        ok, detail = False, f"{e.__class__.__name__}: {e}"
    results.append((name, ok, detail))


PROJECT_FORBIDDEN = {"project": False}


class ToolSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    repository: Annotated[str, Field(json_schema_extra=PROJECT_FORBIDDEN)] = "https://api.github.com/repos/tlaplus/tlaplus"
    token_hosts: Annotated[tuple[str, ...], Field(json_schema_extra=PROJECT_FORBIDDEN)] = ()

    @field_validator("token_hosts", mode="before")
    @classmethod
    def _hosts(cls, v: Any) -> Any:
        if isinstance(v, (list, tuple)):
            out = []
            for h in v:
                if not isinstance(h, str) or any(c in h for c in ":/*") or not h.strip():
                    raise ValueError(f"not a bare host name: {h!r}")
                out.append(h.strip().lower())
            return tuple(out)
        return v


class JavaSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    min_version: Annotated[int, Field(ge=8)] = 11
    opts: tuple[str, ...] = ("-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC")


class TlcSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    workers: Union[Literal["auto"], Annotated[int, Field(gt=0)]] = "auto"
    refresh_interval: Annotated[float, Field(gt=0)] = 1.0
    plain: bool = False


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    tool: ToolSettings = Field(default_factory=ToolSettings)
    java: JavaSettings = Field(default_factory=JavaSettings)
    tlc: TlcSettings = Field(default_factory=TlcSettings)
    module_path: str | None = None
    module_lib_path: str | None = None


def t_defaults():
    s = Settings.model_validate({})
    return s.tlc.workers == "auto" and s.java.min_version == 11 and s.tool.token_hosts == (), repr(s.tlc)


def t_env_strings():
    s = Settings.model_validate({"tlc": {"workers": "4", "refresh_interval": "0.5", "plain": "true"},
                                 "java": {"min_version": "17"}})
    return (s.tlc.workers == 4 and s.tlc.refresh_interval == 0.5 and s.tlc.plain is True and s.java.min_version == 17,
            repr(s.tlc))


def t_errors():
    try:
        Settings.model_validate({"tlc": {"refresh_interval": "fast", "workers": 0}, "tool": {"token_hosts": ["https://x"]}})
    except ValidationError as e:
        errs = e.errors()
        locs = sorted(".".join(str(p) for p in er["loc"]) for er in errs)
        has = all(k in errs[0] for k in ("loc", "msg", "type", "input"))
        want = {"tlc.refresh_interval", "tool.token_hosts"}
        ok = has and want <= {".".join(str(p) for p in er["loc"][:2]) for er in errs}
        return ok, f"{locs}; first: {errs[0]['msg']!r} input={errs[0]['input']!r}"
    return False, "no error"


def t_hosts_lower():
    s = Settings.model_validate({"tool": {"token_hosts": ["GHE.Example.com"]}})
    return s.tool.token_hosts == ("ghe.example.com",), repr(s.tool.token_hosts)


def t_unknown_keys_by_fields():
    names = set(Settings.model_fields) | {f"tlc.{k}" for k in TlcSettings.model_fields}
    # Walk nested models through model_fields annotations
    sub = Settings.model_fields["tlc"].annotation
    return "workers" in sub.model_fields and "tool" in Settings.model_fields, f"{sorted(names)[:4]}..."


def t_project_marker():
    f = ToolSettings.model_fields["token_hosts"]
    return f.json_schema_extra == PROJECT_FORBIDDEN, repr(f.json_schema_extra)


def t_single_key():
    ann = TlcSettings.model_fields["workers"].annotation
    meta = TlcSettings.model_fields["workers"].metadata
    ta = TypeAdapter(ann)
    a = ta.validate_python("auto")
    b = ta.validate_python(4)
    try:
        ta.validate_python("many")
        c = "accepted"
    except ValidationError:
        c = "refused"
    # Validate via a one-field copy instead: model_validate on a partial nested dict
    try:
        TlcSettings.model_validate({"workers": 0})
        d = "accepted-0"
    except ValidationError:
        d = "refused-0"
    return a == "auto" and b == 4 and c == "refused" and d == "refused-0", f"{a},{b},{c},{d}, metadata={meta}"


def t_dump():
    s = Settings.model_validate({"tlc": {"workers": 2}})
    d = s.model_dump(mode="json")
    return d["tlc"]["workers"] == 2 and d["java"]["opts"][0].startswith("-XX"), str(d["tlc"])


def t_frozen():
    s = Settings.model_validate({})
    try:
        s.tlc.plain = True  # type: ignore[misc]
        return False, "mutated"
    except ValidationError as e:
        return True, e.errors()[0]["type"]
    except TypeError as e:
        return True, f"TypeError {e}"


def t_extra_ignored():
    s = Settings.model_validate({"workspace": {"root": "x"}, "tlc": {"java_class": "y"}})
    return not hasattr(s, "workspace"), "ignored"


for name, fn in list(globals().items()):
    if name.startswith("t_"):
        check(name[2:], fn)

bad = [r for r in results if not r[1]]
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'} {n}: {d}")
print(f"SUMMARY pydantic {pydantic.VERSION} python {sys.version.split()[0]}: {'ALL PASS' if not bad else 'FAIL ' + ','.join(b[0] for b in bad)}")
