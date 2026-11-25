# 19. Layered settings

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

Settings are read in layers (packaged defaults, the user file, the environment, command-line values), validated once against the first wave's schema, with where each value came from and a warning for unknown and removed keys; no file is written by reading; `write_user_setting` is the one writer. The old commands, still on `main` until their switch, read the new settings through one entry point so that they type-check, and the settings F3 removes no longer exist anywhere.

## Covers

- Roadmap items ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)):
  - "Layered configuration (decision D10): packaged defaults, user file, environment, flags; the project file joins the chain in milestone 3. Every section has defaults, so an old or trimmed file still loads. No file is written until the user changes a setting." (line 267), in full apart from the command that writes (`config set`, [44](44-config-commands.md)).
  - "Unknown config keys are silently ignored, so a typo has no effect and no warning." (line 207).
  - "Remove settings nothing reads (`workspace.root`, `workspace.spec_dir`, the unread `tla.community_modules` block, `save_config`) and the comment describing behaviour that no longer exists. ..." (line 269), in full: the settings, the hard-coded names, the stale comment, `module_path` and `module_lib_path` left as they are at run time (the design's departure; that `module_lib_path` is no longer on the compile classpath is [30](30-module-build.md)'s, decision D61).
  - "`config` commands work when the file is broken, and a broken file gives a readable validation message instead of a traceback." (line 268), in part: the readable message (`ConfigInvalid` with the file, line and column or the key). The commands are [44](44-config-commands.md); that no traceback is shown is [17](17-error-handler.md)'s handler.
- Design sections:
  - [14 F1](../design/14-config-and-cli.md#f1-layered-configuration): `LoadedSettings`, `Layer`, `read_layers`, `merge_layers`, `load_settings`, `write_user_setting`, the environment layer, the broken-file messages, unknown keys, the value check shared with `config set`; its unit tests. Not here: `config set` itself and the two in-process `config.feature` scenarios (44).
  - [14 F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay): the schema, the packaged `default_config.yaml`, the removed names and their one-line warning, the two keys a project layer may not set, the deletions; its unit tests. Not here: the feature "`tool.repository` set to another `https` address is the host the requests go to" ([29](29-tool-commands.md)a, the first command that makes requests), and the Added entry for `tool.token_hosts` (29a).
  - [00, application context](../design/00-overview.md#application-context): `AppContext.settings`, loaded on first use.
- The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md): rows C2 (the packaged defaults read through `importlib.resources`), C4 (the safe loader), J4 (the minimum Java version defaults to 11), R25 (the default JVM options) and the environment half of C6 (`TLAUP_MODULE_PATH`, `TLAUP_MODULE_LIB_PATH`), whose owner this package is.

## Depends on

- [02](02-errors-and-paths.md): `AppPaths` (`config_file`), `ConfigInvalid`, `ConfigKeyNotFound`, `FileOperationError`; `tlaup/context.py`.
- [03](03-test-foundation.md): the isolation fixture (its `TLAUP_HOME` and its `TLAUP_TOOL_REPOSITORY` closed port, which the old `tools` commands read from this package on), `tmp_path`-based tests; no old test is left (03b).
- [16](16-ui-messages.md): `Ui.warning`, to print the loader's warnings when the context first loads settings. **Added to the draft** by stage 4: the warnings must be printed in the form F6 and F1 show, and the context is where settings are first loaded.

## Files

Creates:

- `tests/unit/config/test_loader.py`, `tests/unit/config/test_schema.py`, `tests/unit/config/test_write.py`.
- `tests/unit/config/data/config-0.8.2.yaml`: today's `src/tlaup/resources/default_config.yaml`, copied byte for byte before it is rewritten (F3: "the 0.8.2 default file, kept as a test data file").

Changes (rewritten):

- `src/tlaup/config/schema.py`: the first wave's schema (Interfaces). The old `TlaUrls`, `TlaConfig`, `WorkspaceConfig`, `TlcConfig`, `JavaConfig` and its `JAVA_OPTS` validator go.
- `src/tlaup/config/loader.py`: the layered loader and the writer. `save_config`, `ensure_config`, `workspace_root` and `_default_config_content` are deleted (F3). The defaults layer reads `default_config.yaml` as `_default_config_content` does today, through `importlib.resources.files("tlaup.resources")` (inventory row C2). The old path helpers `config_dir`, `config_path` and `cache_dir` stay with the bodies package 02 gave them, for their old callers; each goes with its last caller: `config_dir()` with `config_path()`, its only caller, in [44](44-config-commands.md), and `cache_dir()` in [39](39-tlc-command.md), which deletes the last of `versioning/paths.py`, its last caller once 04 has removed the legacy fallbacks (finding F2 of the [second review](review-2026-11-24.md)). `load_config()` stays as the old commands' entry point (see Context).
- `src/tlaup/resources/default_config.yaml`: the defaults below, every key with a value, no comments describing behaviour.
- `src/tlaup/context.py`: `AppContext.settings`, loaded on first use. 02's `reset()` does not clear `load_config`'s `lru_cache` (02, Context), so there is no line to remove. Nothing else calls `load_config.cache_clear()`: the old tests that did (`tests/unit/cmd/test_modules.py`, `tests/unit/test_config_suite.py`, finding B1) went in 03b, and the one call in `src/`, in `save_config`, goes with that function.

Changes (the old readers of removed keys, one or two lines each; see "The old readers"):

- `src/tlaup/project/core.py`: the constants `SPEC_DIR = "spec"`, `MODULES_DIR = "modules"`, `CLASSES_DIR = "classes"`, `LIB_DIR = "lib"`, with exactly the names [32](32-spec-resolution.md) gives them.
- `src/tlaup/cmd/tlc.py`, `src/tlaup/tlc/runner.py`: `find_project_root(..., modules_dir=MODULES_DIR, classes_dir=CLASSES_DIR)`; in `runner.py` the main class `tlc2.TLC` as a module constant.
- `src/tlaup/java/classpath.py`: the three `self.config.workspace.*` reads become `MODULES_DIR`, `CLASSES_DIR` and `LIB_DIR`.
- `src/tlaup/cmd/modules/add.py`: `config.tlc.overrides_class` becomes the literal `tlc2.overrides.TLCOverrides` as a module constant.
- `src/tlaup/versioning/api.py`: a helper giving the old two addresses and page size from `tool.repository`; `src/tlaup/cmd/tools/list.py`, `install.py`, `upgrade.py`, `meta/sync.py` call it instead of reading `config.tla.urls`.
- `tests/unit/test_context.py` (02's new test): not changed. Its two assertions on the old loader (`config_dir()` and `cache_dir()` follow `TLAUP_HOME`) stay, because both functions stay here with 02's bodies; each assertion goes in the pull request that deletes its function ([44](44-config-commands.md) the `config_dir` one, [39](39-tlc-command.md) the `cache_dir` one).
- `CHANGELOG.md`: see Changelog.

Deletes: nothing beyond the functions named above. The old tests of the loader and the schema (`tests/unit/test_config.py`, `test_settings.py`, `test_config_suite.py`, the `base_settings` fixture) went in 03b ([01 T11](../design/01-testing.md#t11-the-existing-tests), decision D62).

Not changed: `src/tlaup/cli.py` (the `load_config()` call in the root callback is removed by [17](17-error-handler.md)).

Shared with packages of the same group: `src/tlaup/project/core.py`, `src/tlaup/cmd/tlc.py` and `src/tlaup/tlc/runner.py` with [32](32-spec-resolution.md): the same three call lines and the four constants, written identically in both, so whichever lands second keeps the other's form. `src/tlaup/context.py` with 16 and 17, one field or function each. `CHANGELOG.md`.

## Interfaces

Provides, from [14 F1](../design/14-config-and-cli.md#f1-layered-configuration) (copied):

```python
# tlaup/config/loader.py
@dataclass(frozen=True)
class LoadedSettings:
    settings: Settings
    sources: dict[str, str]          # "tlc.workers" -> "default" | "user file" | "TLAUP_TLC_WORKERS" | "--workers"
    warnings: tuple[str, ...]        # unknown and removed keys

@dataclass(frozen=True)
class Layer:
    kind: str                        # "defaults", "user", "project", "env" or "flags"
    data: Mapping[str, object]       # nested, as read
    labels: Mapping[str, str]        # dotted key -> what `sources` shows for it: "user file", "TLAUP_TLC_WORKERS", "--workers"

def read_layers(paths: AppPaths, env: Mapping[str, str], overrides: Mapping[str, object] = {}) -> list[Layer]
    # the four layers of the first wave, lowest first; raises ConfigInvalid for a file that does not parse
def merge_layers(layers: Sequence[Layer]) -> LoadedSettings
    # merges, drops what a "project" layer may not set (F3), warns about unknown keys, validates once
def load_settings(paths: AppPaths, env: Mapping[str, str], overrides: Mapping[str, object] = {}) -> LoadedSettings
    # merge_layers(read_layers(...)); what every command calls
def write_user_setting(paths: AppPaths, key: str, value: object) -> None      # the one writer; used by `config set`
```

**Written by stage 4**, from what F1 and F3 say in words:

```python
# tlaup/config/schema.py
class ToolSettings(BaseModel):   repository: str;  token_hosts: list[str]     # neither settable by a project layer
class JavaSettings(BaseModel):   min_version: int; opts: list[str]
class TlcSettings(BaseModel):    workers: PositiveInt | Literal["auto"]; refresh_interval: float; plain: bool; keep: bool
class Settings(BaseModel):
    tool: ToolSettings; java: JavaSettings; tlc: TlcSettings
    module_path: str | None; module_lib_path: str | None

REMOVED: tuple[str, ...] = ("workspace", "tla", "tlc.java_class", "tlc.overrides_class")   # in this order (see Context)
def setting_keys() -> tuple[str, ...]                 # every dotted leaf key, from the schema; also for completion (47)
def closest_key(key: str) -> str | None               # a known key within edit distance 2, for "did you mean"
def check_setting(key: str, value: object) -> object
    # validates one value for one key and returns it as stored (host names lower-cased);
    # unknown key: ConfigKeyNotFound (4); a value that does not fit: ValueError naming the key and what it expects.
    # The one check of F1: `config set` turns the ValueError into UsageError (2), the loader into ConfigInvalid (3).

# tlaup/config/loader.py
CONFIG_HEADER: str     # the comment line every file tlaup writes starts with; names the configuration reference page
def parse_setting_text(text: str) -> object           # one command-line argument read as a YAML scalar or flow value (config set)
def load_config() -> Settings                         # for the old commands only (see Context); goes with its last caller

# tlaup/context.py
AppContext.settings: Settings    # load_settings(paths, env) on first use; each warning printed once through ui.warning
```

The packaged defaults, F3's block with the section name of D47 and the key F3's table adds (`tlc.keep`, top-up):

```yaml
tool:
  repository: https://api.github.com/repos/tlaplus/tlaplus
  token_hosts: []
java:
  min_version: 11
  opts: ["-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC"]
tlc:
  workers: auto
  refresh_interval: 1.0
  plain: false
  keep: false
module_path: null
module_lib_path: null
```

Consumes: `AppPaths`, `ConfigInvalid`, `ConfigKeyNotFound`, `FileOperationError`, `AppContext` (02); `Ui.warning` (16).

Used later by: the config commands (44), the tool commands (29: `tool.repository`, `tool.token_hosts`), the preflight and the `tlc` command (33, 39: `java.*`, `tlc.workers`, `tlc.keep`, `module_path`, `module_lib_path`), the run folders (35: `tlc.keep`), the reporter (38, 40: `tlc.plain`, `tlc.refresh_interval`), `doctor` (46), completion (47: `setting_keys`). [24](24-github-client.md) does not import this package: the commands pass it the address and the hosts.

## Tests that must pass

Plain pytest, real files in a temporary folder, `AppPaths` from the isolation fixture, the environment as a dictionary argument ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests): pure functions given real files).

`tests/unit/config/test_loader.py`, on `load_settings` (F1's list, and F3's). The rows of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) this package owns are C2, C4, J4, R25 and C6's environment half; each test below that holds one is marked with it (findings F1 and G1 of the [second review](review-2026-11-24.md)):

- No user file: the defaults, every `sources` entry `"default"`, no warnings.
- J4 and R25, the defaults' values: with no user file and no `TLAUP_` setting variable, `settings.java.min_version == 11` and `settings.java.opts == ["-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC"]`. That these options reach the Java command line is [33](33-tlc-invocation.md)'s.
- A file holding one key: that key from `"user file"`, the rest defaults.
- Each layer overriding the one below: default, then user file, then `TLAUP_TLC_WORKERS`, then the `overrides` argument; `sources` names the winner each time (`"TLAUP_TLC_WORKERS"`, `"--workers"`).
- A list in the environment: `TLAUP_TOOL_TOKEN_HOSTS=ghe.example.com, api.ghe.example.com` gives two hosts with the spaces dropped; an empty value gives the empty list.
- `TLAUP_JAVA_OPTS` set: `java.opts` is unchanged and its source stays `"default"` (it is not part of this layer, [13 J1](../design/13-modules-and-java.md#j1-java-options)).
- `TLAUP_TLC_KEEP=false` over a file with `tlc.keep: true` gives false.
- A file with a removed section loads, with the one combined warning.
- A file with a typo (`tlc.worker`) warns and suggests `tlc.workers`.
- Invalid YAML raises `ConfigInvalid` naming the file and giving line and column; an invalid value (`tlc.refresh_interval: fast`) raises `ConfigInvalid` naming the file and the key; an invalid value from the environment names the variable. No traceback text in the message.
- A union-typed key with a bad value (`tlc.workers: 0`, `tlc.workers: many`) names `tlc.workers`, not Pydantic's tagged location.
- Reading never creates a file or a folder.
- C4, the safe loader ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration)): a user file holding `!!python/object/apply:os.mkdir ["<tmp>/made"]` (the path a folder under `tmp_path`) raises `ConfigInvalid` naming the file, and `<tmp>/made` does not exist afterwards. The same for the packaged-defaults reader is not needed: it reads a file in the wheel, through the same function.
- C6, the environment half that is this package's (the names settled with the maintainer on 2026-11-24, [14 F1](../design/14-config-and-cli.md#f1-layered-configuration)): `TLAUP_MODULE_PATH=<a folder>` gives `module_path` that folder with the source `"TLAUP_MODULE_PATH"`, and `TLAUP_MODULE_LIB_PATH` the same for `module_lib_path`. The rest of C6 (the logged Java command) is [33](33-tlc-invocation.md)'s.
- F3 and C2: the packaged default file validates, read the way the loader reads it, through `importlib.resources.files("tlaup.resources")` (not a path built from `__file__`), so the test fails if the file is not reachable as a package resource; `config-0.8.2.yaml` loads and gives exactly `config.yaml: 4 settings are no longer used (workspace, tla, tlc.java_class, tlc.overrides_class); run `tlaup config edit` and delete them` (the text of the warning, without the `warning:` prefix that `Ui` adds), and no other warning; a file with `tlc.java_class` alone inside a kept section is reported in the same kind of line, counting 1; `tool.token_hosts` with a scheme, a path, a port or a wildcard is `ConfigInvalid`; `tool.repository` with `http`, a user part, a query string, a fragment, a backslash or white space is `ConfigInvalid`.

`tests/unit/config/test_loader.py`, on `merge_layers` with hand-made lists: the order of the list decides the winner; `sources` takes its text from the winning layer's `labels`; a layer of kind `"project"` that sets `tool.repository` or `tool.token_hosts` has the key dropped with a warning, and the value and source stay those of the layer below.

`tests/unit/config/test_write.py`, on `write_user_setting`: no file before (the folder and the file are created; the file starts with `CONFIG_HEADER`); a file with two other keys keeps both values; a file with a comment loses the comment and keeps the header line; a list value; a write that fails (the config folder made read-only, skipped with the reason under root) leaves the old file byte for byte and raises `FileOperationError`; a file that does not parse is not rewritten (`ConfigInvalid`).

`tests/unit/config/test_schema.py`: `check_setting` for each key with a good and a bad value; an unknown key is `ConfigKeyNotFound`; a removed key (`workspace.root`) is `ConfigKeyNotFound`; host names come back lower-cased; `parse_setting_text` on `4`, `auto`, `'[ghe.example.com]'`, `'["-Xmx8g", "-XX:+UseParallelGC"]'`, `'[]'`; `setting_keys()` lists the ten leaf keys of the defaults; `closest_key("tlc.worker") == "tlc.workers"`.

Not tested here: `load_config()`, which only hands the old commands the context's settings (see Context) and goes with them.

F1's `config.feature` scenarios are not here: the two on `config set` are [44](44-config-commands.md)'s, and "`tlaup tool path` on a fresh home leaves `the file "{config}/config.yaml" does not exist`" is [29](29-tool-commands.md)b's, which builds `tool path` (findings B5, D3). F3's in-process scenario on `tool.repository` is 29a's. No stateful test applies.

## Changelog

Under `## [Unreleased]`, word for word. These describe what every command sees from this package on: the old commands read the new loader.

From [14 F1](../design/14-config-and-cli.md#f1-layered-configuration):

- Changed: "Settings are read in layers: built-in defaults, then the user's config file, then environment variables, then command-line options. A config file is no longer created on first run; a file needs to hold only the settings that differ from the defaults."
- Added: "Each setting can be given as an environment variable `TLAUP_<SECTION>_<KEY>`."
- Fixed: "A config file written by an older version, or missing a section, caused a traceback."
- Changed: "Unknown keys in the config file give a warning."

From [14 F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay):

- Breaking: "Config settings removed: `workspace.root`, `workspace.spec_dir`, `workspace.modules_dir`, `workspace.classes_dir` (the folder names `spec`, `modules`, `classes` and `lib` are fixed), `tlc.java_class`, `tlc.overrides_class`, `tla.community_modules`. `tla.urls.tags`, `tla.urls.releases` and `tla.urls.per_page` are replaced by `tool.repository`. A config file that still has them loads with one warning on every command; earlier versions wrote all of them into the file, so delete the file or remove those lines with `tlaup config edit`."

Not here: F1's "`tlaup config set KEY VALUE` changes one setting ..." ([44](44-config-commands.md)); F3's "`tool.token_hosts` lists extra hosts that may receive the GitHub token." ([29](29-tool-commands.md)a, where the token is first sent, and which has it in its Added list); the Breaking entry on the compile classpath, which names `module_lib_path` ([13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder), written by [31](31-module-commands.md)).

## Context for the worker

**Decisions this rests on.** D10 (layers; nothing is written until the user changes a setting). D14 (no migration of old files: removed keys warn and are ignored). D41 (`tool.repository` and `tool.token_hosts` are never taken from a project layer). D47 (the section is `tool`, the variables `TLAUP_TOOL_...`). D20 via [13 J1](../design/13-modules-and-java.md#j1-java-options) (`TLAUP_JAVA_OPTS` adds at run time and is not part of the environment layer). D25 (all paths from `AppPaths`). The design agent's decisions: unknown keys warn, not fail; `config set` takes one YAML value and loses comments.

**The old readers, and the edit each needs.** The new schema and loader are complete here; no removed key survives in the schema. The old code read five removed keys, and it stays on `main` until each command's switch, so it must still type-check (`main` need only be green between packages; nothing promises the old commands keep their behaviour, decision D62). None of the keys ever held a value a user could usefully change, which is why F3 removes them, so each old reader gets the value as a constant, which is also the final design for the folder names. This is not a shim in D14's sense: nothing a user names stays readable.

| Removed key | Old reader today | After this package | Last old reader deleted by |
| --- | --- | --- | --- |
| `workspace.modules_dir`, `workspace.classes_dir` | `cmd/tlc.py` (two calls of `find_project_root` today, one of them in `_show_diagnostic_info`; one if [04](04-delete-dead-code.md) has merged first and deleted that function), `tlc/runner.py` (two), `java/classpath.py` (three reads) | `MODULES_DIR`, `CLASSES_DIR`, `LIB_DIR` from `tlaup/project/core.py` (the final form, F3; shared with 32) | none needed: the constants are the design |
| `workspace.root`, `workspace.spec_dir` | `workspace_root()` (no caller) | deleted | here |
| `tlc.java_class` | `tlc/runner.py` (the run and the `-version` call) | the constant `tlc2.TLC` in `runner.py` | [39](39-tlc-command.md), which deletes `runner.py`; the new code has the constant of 33 and later `ENTRY_POINTS` (41) |
| `tlc.overrides_class` | `cmd/modules/add.py` (the service file default) | the constant `tlc2.overrides.TLCOverrides` in `add.py` | [31](31-module-commands.md), which replaces `module add` and stops writing the service file (M3) |
| `tla.urls.tags`, `.releases`, `.per_page` | `cmd/tools/list.py`, `install.py`, `upgrade.py`, `meta/sync.py`, through `fetch_remote_versions` | a helper in the old `versioning/api.py` returns `(f"{repository}/tags", f"{repository}/releases", 30)` from `tool.repository`, trailing slash removed; 30 is today's page size, kept so the old code behaves as today | [29](29-tool-commands.md), which deletes `api.py` and the old `tools` commands |
| `tla.community_modules` | none | gone | here |

Two more points about the old code:

- **`load_config()` stays as the old commands' one entry point**, one line: it returns `get_context().settings`. Today's `JAVA_OPTS` validator is not carried over: the new schema must not read the environment ([13 J1](../design/13-modules-and-java.md#j1-java-options) deletes it), and nothing has to keep the old `tlc` reading `JAVA_OPTS` until [39](39-tlc-command.md) (D62). So from here the old `tlc` ignores `JAVA_OPTS`; J1's Breaking entry that says so is still [39](39-tlc-command.md)'s, which brings `TLAUP_JAVA_OPTS`, and 39 has no `JAVA_OPTS` branch to remove (finding C10 of the review). New code never calls `load_config()`; it reads `ctx.settings`. The function goes with its last caller: the old `tools` commands (29), `modules` commands (31), `config edit` (44), `tlc` and the runner (39), `check-java` (46 or 48).
- **The old `tools` commands now take their addresses from `tool.repository`.** Under the isolation fixture that is a closed local port, so an old command that tries the network by mistake fails at once instead of reaching GitHub.

**Merging and validation** (F1).

- Each layer is a nested dictionary; merged key by key; a list is replaced, never concatenated. Validated once, after merging. Every key has a value in the packaged defaults, so the schema's fields need no defaults of their own, and the packaged YAML is the one source of them; the test that the default file validates is what keeps them complete. Do not repeat the defaults in the models.
- Unknown keys are found by comparing the user file's keys with the schema before validation, and removed before it; so are the removed names. Unknown keys warn as `config.yaml: unknown key "tlc.worker" (ignored); did you mean "tlc.workers"?` (`Ui` adds the `warning:` prefix). The exact wording after "(ignored)" is stage 4's; the test asserts the key and the suggestion, not the sentence.
- Removed names give one line per load whatever their number, a removed section counting once, in the order of `REMOVED` (that order gives F3's example line exactly: `workspace, tla, tlc.java_class, tlc.overrides_class`). A key both unknown and removed is reported as removed only. F3 says the removed list is deleted in the release after 0.9.0 is superseded; not now.
- F1's example `unknown key "workspace"` was written before F3's combined line; under F3 `workspace` is a removed name and appears only in the combined line.
- **Error messages.** One line per problem: `config.yaml: tlc.refresh_interval: expected a number, got "fast"`. The key is built from the field part of each Pydantic error's `loc`: for a union (`tlc.workers`) Pydantic puts the member's tag in `loc` (`tlc.workers.constrained-int`, `tlc.workers.literal['auto']`), in every 2.x version, so stop at the first part that is not a field. A YAML syntax error gives the file, line and column (PyYAML's mark, counted from 0; add 1). The file is named as F1's examples name it; `ConfigInvalid`'s `hint` is `tlaup config edit` for the file ([14 F4](../design/14-config-and-cli.md#f4-config-commands-with-a-broken-file)). A value from the environment is named by its variable and gets no edit hint.

**The environment layer** (F1).

- `TLAUP_<SECTION>_<KEY>` in upper case, for every leaf key of the schema except `java.opts`. Read only the names that map to a known key; any other `TLAUP_` variable (`TLAUP_HOME`, `TLAUP_DEBUG`, `TLAUP_AUTO_INSTALL`, `TLAUP_JAVA_OPTS`, the test variables) is not this layer's and gets no warning.
- **The two top-level keys** `module_path` and `module_lib_path` have no section. "Each setting" ([F1's Added entry](../design/14-config-and-cli.md#f1-layered-configuration)) joins the dotted key's parts with `_`: `TLAUP_MODULE_PATH`, `TLAUP_MODULE_LIB_PATH`. Settled with the maintainer on 2026-11-24 and written into [14 F1](../design/14-config-and-cli.md#f1-layered-configuration) (findings F4 and G6 of the [second review](review-2026-11-24.md)); C6's environment half.
- A list key's value is its items separated by commas, white space around an item dropped, an empty value the empty list; empty items between commas are dropped. A scalar is passed as text and left to Pydantic's lax parsing (`"4"` for an integer, `"false"` for a boolean).
- The label of an environment value is the variable's name.

**The flags layer.** The `overrides` argument maps dotted keys to values. F1 gives no way to pass the option's name for `sources`; stage 4's rule: the label is `--` and the key's last part with `_` written as `-` (`tlc.refresh_interval` is `--refresh-interval`). The first wave's commands may pass options in their request instead ([33](33-tlc-invocation.md) does for `--workers` and `--keep`); the layer exists for whoever uses it and for `config show`'s sources.

**The project layer** does not exist yet, but the kind does: `merge_layers` drops `tool.repository` and `tool.token_hosts` from a layer of kind `"project"`, with a warning naming the key. Mark the two fields in the schema (for example in `json_schema_extra`) so the rule reads the schema, not a second list.

**`tool.repository` and `tool.token_hosts` checks.** `token_hosts`: each entry a bare host name, lower-cased on the way in; a scheme, a path, a port or a wildcard is invalid. `repository`: `https`, no user part, no query string, no fragment, no backslash, no white space or control character ([12 V7](../design/12-tools-and-downloads.md#v7-github-client)). The schema checks the string with the standard library; it must not import `requests` ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)). The client ([24](24-github-client.md)) checks the address `requests` prepares as well; both checks are wanted.

**`tlc.refresh_interval`'s range** (question Q16, settled: kept as built). The schema checks the type only; a rule beyond the type, such as the range of `tlc.refresh_interval` (below 0.1 or above 60), is the command's that uses the value and gives 2 wherever the value came from ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration), [22 O5](../design/22-reporters.md#o5-refresh-interval)). So here it is only a number; the range is [40](40-live-display.md)'s.

**`write_user_setting`** reads the user file as data (an empty mapping if there is none), sets the one key, and writes the whole file with PyYAML (`sort_keys=False`), starting with `CONFIG_HEADER`, through a temporary file in the same folder and `os.replace`. Comments, blank lines and quoting are not kept (PyYAML cannot carry them). A file that does not parse is not rewritten. It does not validate the value: the caller has already called `check_setting`, and `config set` first loads the whole file so that a file with an invalid value elsewhere is refused (F4).

**`CONFIG_HEADER`** names the configuration reference page, which the documentation track writes ("Reference pages: configuration"); it does not exist yet. Write it as one constant naming the page's planned address on GitHub (`docs/reference/` beside the generated `cli.md` of [23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference)), so the documentation track can change one line. This is a reading of the design, not confirmed: the index lists it under "Readings the packages build on".

**Loading lazily.** `AppContext` is a frozen dataclass; give it a lazily computed `settings` (a `functools.cached_property` works on a frozen dataclass without `slots`). A broken file raises `ConfigInvalid` each time `settings` is asked for, so a command that needs settings stops cleanly; a command that does not ask never reads the file (`tlaup --help`, `tool path`, `config path`). The context imports the loader inside that property, so importing `tlaup.context` loads neither the schema nor `yaml` (F9; [49](49-startup-cost.md) tests it). Warnings are printed once, through `ui.warning`, when settings are first loaded.

**Traps.**

- `LoadedSettings` is frozen; the models may keep Pydantic's default.
- A test of `merge_layers` and `load_settings` passes `env` as a dictionary; a test that goes through the context sets variables with `monkeypatch.setenv` and resets the context.
- The isolation fixture sets `TLAUP_TOOL_REPOSITORY` for every test, so `sources["tool.repository"]` is `"TLAUP_TOOL_REPOSITORY"` in any test that passes the real environment. Tests of `sources` pass their own `env`.
- Do not add a setting for `TLAUP_JAVA_OPTS`, `TLAUP_AUTO_INSTALL` or `TLAUP_DEBUG`: they are switches read by their own code.

**State of `main` when this starts.** Release 0.8.x commands; `errors.py`, `paths.py`, `context.py` with `config_dir()` and `cache_dir()` in the loader routed to `AppPaths` (02); the isolation fixture, and no old test (03b); `Ui` (16). The old loader copies the packaged defaults to the user's folder on first use and is cached with `lru_cache`. [32](32-spec-resolution.md) may be merged already, in which case the folder-name constants and the `find_project_root` calls are in place; keep them.

## Done when

- The modules and the defaults file are as above; `mypy` strict passes.
- The tests above pass.
- `grep` finds no `workspace`, `tla.urls`, `java_class` or `overrides_class` in `src/` outside the `REMOVED` list and the two constants named above.
- On a fresh `TLAUP_HOME`, `uv run tlaup tools dir` leaves no `config.yaml` (tried by hand once and said in the pull request; [29](29-tool-commands.md)b adds the scenario with `tool path`).
- The changelog entries are written.
- The pull request names inventory rows C2, C4, J4, R25 and C6's environment half, each with its test.
- `uv run poe lint` and `uv run poe test` pass; CI is green.

## Out of scope

- `config path`, `show`, `get`, `set`, `edit` and `config.feature`: [44](44-config-commands.md).
- `TLAUP_JAVA_OPTS` and `--java-opt`: [33](33-tlc-invocation.md), [39](39-tlc-command.md).
- The GitHub client's use of `tool.repository` and `tool.token_hosts`: [24](24-github-client.md), with the values passed by [29](29-tool-commands.md).
- The project file: milestone 3.
- Documenting `module_path` and `module_lib_path`: deferred to milestone 3 (F3's departure, listed in the design README).
- The configuration reference page: the documentation track.

## Risks

- From F1: merging lists by replacement means a user who sets `java.opts` loses the two default options unless they repeat them; the reference page says so, and `TLAUP_JAVA_OPTS` exists for adding. A user who keeps comments in the file and runs `config set` loses them.
- From F3: someone relies on a renamed modules folder; the warning names the key and the changelog says what is fixed.
- From the cut: `load_config()` lives until its last caller goes (39, or 46 or 48 for `check-java`); 48's tree check and `grep load_config` catch one left behind. The old `tlc` ignores `JAVA_OPTS` from here until 39 (accepted under D62; nothing is released in between).
- From the cut: the old `tools` commands take addresses derived from `tool.repository` from here on; a user who had changed `tla.urls` in their file loses that change at once. Nothing is released in between (D6), and the Breaking entry says so.
