# 14. Milestone 1: configuration, messages and the command-line shell

Covers milestone 1's "Configuration", "Messages and help", "Startup cost", the traceback item of "First run and failures", and the recorded problem about unknown config keys. Relies on decisions D10, D14, D20, D25, D29, D30.

## F1 Layered configuration

Roadmap: "Layered configuration (decision D10): packaged defaults, user file, environment, flags; the project file joins the chain in milestone 3. Every section has defaults, so an old or trimmed file still loads. No file is written until the user changes a setting." Also the recorded problem "Unknown config keys are silently ignored".

**Problem.** `load_config` copies the packaged YAML into the user's config folder on first use and then reads only that copy. `Settings` has required sections with no defaults, so a file missing `workspace:` or written by an older version fails with a pydantic traceback. A new default in a later release never reaches a user who already has a file. Unknown keys are dropped silently.

**Design.**

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

The list of layers is a value, not something built inside `load_settings`: milestone 3 adds the project file by putting one more `Layer` into the list between the user file and the environment, and the tests of the project-layer rule (F3) call `merge_layers` with a list they made.

Layers, lowest first; each is a plain nested dictionary and they are merged key by key (lists are replaced, not concatenated):

1. **Packaged defaults**: `tlaup/resources/default_config.yaml`, read through `importlib.resources`. Every key has a value here, so every section has defaults.
2. **User file**: `<config>/config.yaml`, if it exists. It is never created by reading.
3. **Project file**: milestone 3. `merge_layers` takes a list of layers, so this is one more entry, of kind `project`. Each key in the schema is marked as settable by a project file or not; `tool.repository` and `tool.token_hosts` are not (F3, decision D41), and the loader drops them from that layer with a warning.
4. **Environment**: `TLAUP_<SECTION>_<KEY>` in upper case (`TLAUP_TLC_WORKERS`, `TLAUP_TLC_REFRESH_INTERVAL`, `TLAUP_JAVA_MIN_VERSION`, `TLAUP_TOOL_REPOSITORY`, `TLAUP_TOOL_TOKEN_HOSTS`). A key with a list value is given as its items separated by commas, with white space around an item dropped and an empty value meaning the empty list: `TLAUP_TOOL_TOKEN_HOSTS=ghe.example.com,api.ghe.example.com`. The two settings that sit at the top level, outside any section (`module_path` and `module_lib_path`, F3), follow the same rule with no section part: `TLAUP_MODULE_PATH` and `TLAUP_MODULE_LIB_PATH` (settled with the maintainer on 2026-11-24). `java.opts` is the one list that cannot be set this way, because a Java option can contain a comma; `TLAUP_JAVA_OPTS` exists instead and adds to `java.opts` at run time rather than replacing it ([13 J1](13-modules-and-java.md#j1-java-options)).
5. **Flags**: the `overrides` argument, filled by a command from its options (`--workers`, `--refresh-interval`, `--plain`).

The merged dictionary is validated once by pydantic.

- **A broken file** raises `ConfigInvalid` (code 3) with a readable message built from the validation errors, one line each: `config.yaml: tlc.refresh_interval: expected a number, got "fast"`. The key is named from the field part of each error's `loc`, not from the whole tuple: for a field whose type is a union, Pydantic puts the member's tag in `loc` (`tlc.workers.constrained-int`, `tlc.workers.literal['auto']`), in every 2.x version (top-up, [research 30](../research/30-library-behaviours.md)). A YAML syntax error gives the file, line and column. There is no traceback (F10).
- **Read with YAML's safe loader**, as 0.8.x reads it. The packaged defaults and the user file are read with `yaml.safe_load`, so a file cannot make tlaup construct a Python object or run code: a tag such as `!!python/object/apply:...` is a YAML error like a syntax error, `ConfigInvalid` (code 3) with the file, line and column. (Stage 4 review, 2026-11-24: the safe loader was kept but not written, preserved-behaviour row C4; that the schema checks only the type, and a range is the command's, written into the bullet on the value given to `config set`, question Q16, kept as built; the environment variables of the two top-level settings, finding F4, and the output of `config show` and `config get`, finding H5, settled with the maintainer on 2026-11-24.)
- **Unknown keys** are a warning, not an error: `warning: config.yaml: unknown key "workspace" (ignored)`, with "did you mean" when a known key is within edit distance 2. Warning rather than error because the roadmap requires an old file to keep loading, and the settings removed in F3 would otherwise break every existing file. They are detected by comparing the user file's keys with the schema before validation.
- **No file is written until the user changes a setting**: only `config set` and `config edit` write ([23 C1](23-command-layout.md#c1-command-tree)).
- **What `config set` does to the file.** `write_user_setting` reads the user file as data (an empty mapping if there is none), sets the one key, and writes the whole file again with PyYAML, through a temporary file and `os.replace`. The other keys keep their values. **Comments, blank lines, key order within what PyYAML emits, and quoting style are not kept**: PyYAML, the only YAML library the project depends on, does not carry them through a load and a dump. The file tlaup writes always starts with one comment line naming the reference page, so that line survives. The help of `config set` says: "Rewrites the config file. Comments in it are not kept; use `tlaup config edit` to keep them." A file that does not parse is not rewritten: `config set` stops with the parse error (F4).
- **The value given to `config set`** is one argument, read as a YAML scalar or flow value and then validated against the schema for that key: `config set tlc.workers 4`, `config set tlc.workers auto`, `config set tool.token_hosts '[ghe.example.com]'`, `config set java.opts '["-Xmx8g", "-XX:+UseParallelGC"]'`, `config set tool.token_hosts '[]'`. A value that does not fit the key's type is a `UsageError` (code 2) naming the key and what it expects, and nothing is written: the mistake is in the command just typed, not in the installation, which is what code 3 is for ([02 X1](02-cross-cutting.md#x1-exit-codes)). The same value found in the file or in the environment is `ConfigInvalid` (code 3); the check is one function and the caller chooses the error. The schema checks the type only; a rule beyond the type, such as the range of `tlc.refresh_interval`, is the command's that uses the value and gives 2 wherever the value came from ([22 O5](22-reporters.md#o5-refresh-interval)). A key that does not exist is code 4 for `get` and `set` alike.
- **What `config show` prints** (settled with the maintainer on 2026-11-24). The settings in effect, as YAML on stdout, each leaf key with its source (`sources`, above) as a trailing comment: `workers: auto  # default`, `min_version: 17  # TLAUP_JAVA_MIN_VERSION`. The output is valid YAML, and loading it back gives the same values.
- **What `config get KEY` prints** (settled with the maintainer on 2026-11-24). The one value, in the form the value given to `config set` is read (above), so that it reads back to the same value: `auto`, `4`, `[ghe.example.com]`, `null`. `get` and `set` take leaf keys only: a section name such as `tlc` is not a key, so it is `ConfigKeyNotFound` (code 4), with a hint listing the keys of that section.
- **Loaded lazily and once**: `AppContext.settings` loads on first use ([00](00-overview.md#application-context)); `tlaup --help`, `tlaup tool path` and `tlaup config path` never load it.

**Rejected.** *pydantic-settings*: does env and file layering, but not "packaged YAML as the lowest layer" or "which layer did this value come from", and it is another dependency. *Erroring on unknown keys*: see above. *Writing a commented default file on first run* (today): the copy goes stale, and decision D10 says not to. *A round-trip YAML library (`ruamel.yaml`) so `config set` keeps comments*: a new runtime dependency for one command. *Patching the one line in the file's text*: nested keys, a key that is absent, and flow style make it a second YAML parser. *A `config unset` command*: not asked for; a key is removed with `config edit`.

**Tests.** Unit, on `load_settings` with real files in a temporary folder: no user file; a file holding one key; each layer overriding the one below, with `sources` naming the winner; a list given in the environment, with spaces and with an empty value; a file with a removed section loads with a warning; a file with a typo warns and suggests; invalid YAML and an invalid value raise `ConfigInvalid` with file and key in the message; a file holding `!!python/object/apply:os.mkdir ["<tmp>/made"]` raises `ConfigInvalid` and `<tmp>/made` does not exist afterwards; reading never creates a file. Unit, on `write_user_setting`: no file before; a file with two other keys keeps both values; a file with a comment loses the comment and keeps the header line; a list value; a write that fails leaves the old file. Unit, on `merge_layers` with hand-made lists: the order of the list decides the winner; `sources` takes its text from the winning layer's `labels`. `config.feature` (in-process): `config set tlc.workers many` exits 2 and `the file "{config}/config.yaml" does not exist` afterwards; `config set no.such.key 1` exits 4. `config.feature` (in-process): `tlaup tool path` on a fresh home leaves `the file "{config}/config.yaml" does not exist`.

**Changelog.** Changed: "Settings are read in layers: built-in defaults, then the user's config file, then environment variables, then command-line options. A config file is no longer created on first run; a file needs to hold only the settings that differ from the defaults." Added: "Each setting can be given as an environment variable `TLAUP_<SECTION>_<KEY>`." "`tlaup config set KEY VALUE` changes one setting. It rewrites the config file and does not keep comments." Fixed: "A config file written by an older version, or missing a section, caused a traceback." Changed: "Unknown keys in the config file give a warning."

**Depends on.** F2, G2. **Risks.** Merging lists by replacement means a user who sets `java.opts` loses the two default options unless they repeat them; this is the usual rule for config layers and the reference page says so. `TLAUP_JAVA_OPTS` exists for adding. A user who keeps comments in the file and then runs `config set` loses them; the help text and the changelog say so, and `config edit` is the way to keep them.

## F2 Folder overrides

Roadmap: "Environment overrides for the tool's folders (decision D25). Lands early, with the test isolation work in milestone 2."

**Design.**

```python
# tlaup/paths.py
@dataclass(frozen=True)
class AppPaths:
    config: Path; cache: Path; data: Path
    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppPaths"
    # derived, as properties:
    config_file; tools; pin; modules; runs; remote; java_cache
```

| Variable | Effect |
| --- | --- |
| `TLAUP_HOME` | Moves all three: `config = $TLAUP_HOME/config`, `cache = $TLAUP_HOME/cache`, `data = $TLAUP_HOME/data`. |
| `TLAUP_CONFIG_DIR`, `TLAUP_CACHE_DIR`, `TLAUP_DATA_DIR` | Each sets one folder and wins over `TLAUP_HOME`. |
| none | `platformdirs` with the name `tlaup` (roadmap, "Keep"). |

A value must be an absolute path, or one starting with `~`, which is expanded; a relative path is `ConfigInvalid`. `AppPaths` is the only place that knows any folder; `config/loader.py` and `versioning/paths.py` lose their path functions, and code that needs a path is given `AppPaths` or one path from it. The data folder is unused in the first wave and exists so that one variable moves everything, now and after milestone 3 moves tools and modules there.

`tlaup doctor` and `tlaup cache dir`, `config path`, `tool dir`, `module dir` print the folders in effect.

**Tests.** Unit: each variable alone and in combination; a relative value; the fallback, with `platformdirs` asked through `XDG_*` set to a temporary folder. The isolation fixture's own test ([01 T2](01-testing.md#t2-isolation)) writes through every derived path.

**Changelog.** Added: "`TLAUP_HOME` moves all of tlaup's folders; `TLAUP_CONFIG_DIR`, `TLAUP_CACHE_DIR` and `TLAUP_DATA_DIR` move one each."

**Depends on.** Nothing; second in the order of work.

## F3 Settings that go and settings that stay

Roadmap: "Remove settings nothing reads (`workspace.root`, `workspace.spec_dir`, the unread `tla.community_modules` block, `save_config`) and the comment describing behaviour that no longer exists. For each hard-coded value that config appears to control (`"spec"`, `"modules"`, `"classes"`, `"lib"`, the TLC and overrides class names), either read the setting or remove it. Decide whether `module_path` and `module_lib_path` ... are documented or folded into the project file."

**Design.** The settings file after the first wave:

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

| Setting | Decision | Reason |
| --- | --- | --- |
| `workspace.root`, `workspace.spec_dir` | Removed. | Nothing reads them. |
| `workspace.modules_dir`, `workspace.classes_dir` | Removed; the names `spec`, `modules`, `classes`, `lib` are constants in `tlaup/project/core.py`. | They are read, but a user-wide setting for a per-project folder name has no use; the code already falls back to the literal names, and `lib` was never configurable. A per-project layout belongs in the project file (milestone 3). |
| `tlc.java_class` | Removed; the main classes are the table `ENTRY_POINTS` ([00](00-overview.md#the-run-pipeline)). | No reason to run another class as TLC. |
| `tlc.overrides_class` | Removed. | Its one use was as a default written into the service file, which M3 stops writing. |
| `tla.urls.tags`, `tla.urls.releases`, `tla.urls.per_page` | Replaced by `tool.repository`. | Pagination follows `Link` headers and per-tag lookups need a base address, not two list addresses ([12 V7](12-tools-and-downloads.md#v7-github-client)). The page size is always 100. |
| `tool.token_hosts` | New (decision D41). A list of host names, default empty. | The GitHub token is sent to `api.github.com` and to the hosts listed here, and nowhere else ([12 V7](12-tools-and-downloads.md#v7-github-client)). It exists for a GitHub Enterprise host named in `tool.repository`. Each entry is a bare host name, lower-cased; an entry with a scheme, a path, a port or a wildcard is `ConfigInvalid` when it comes from the file or the environment, and a usage error when it is typed to `config set` (F1). |
| `tla.community_modules` | Removed. | Nothing reads it. Milestone 3 designs community modules. |
| `tlc.workers` | New. | [11 R8](11-runner.md#r8-passthrough-and-workers). |
| `tlc.refresh_interval` | Stays; now has an effect. | [22 O5](22-reporters.md#o5-refresh-interval). |
| `tlc.plain` | New, default false; the default of `tlc --plain`. | Plain output on a terminal as a habit ([22 O4](22-reporters.md#o4-live-display)). |
| `tlc.keep` | New (top-up, D53), default false; the default of `tlc --keep`, also `TLAUP_TLC_KEEP`. | Keeping the checkpoint of an interrupted run as a habit, for someone who runs long models ([11 R6](11-runner.md#r6-run-folders)). |
| `java.min_version`, `java.opts` | Stay. | |
| `module_path`, `module_lib_path` | Stay as they are, undocumented, in the first wave. | The roadmap asks to decide, in this item, between documenting them and folding them into the project file. The project file does not exist yet, so the decision is deferred to milestone 3's design note. This is a departure from the roadmap, which the README lists. Until then both act at run time as in 0.8.x, in the places [13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder) gives them in the classpath. One thing changes: `module_lib_path` is run time only, and is no longer on the compile classpath of `module add`, which holds the build's jar and the module's own `lib/*.jar` alone (decision D61; the changelog line is M2's). A relative `module_path` or `module_lib_path` is read against the working folder, as in 0.8.x (inventory row C6). |

**Two settings a project file can never set** (decision D41): `tool.repository` and `tool.token_hosts`. They are read from the packaged defaults, the user's file and the environment only. Both decide where requests and the token go, and a project file arrives with a cloned repository. The schema marks them, so the rule is in place before milestone 3 adds the project layer ([40](40-later-milestones.md#milestone-3-reproducibility)).

Also deleted: `save_config` (replaced by `write_user_setting`, F1), `workspace_root`, `ensure_config`, the stale comment in the default file.

**What an existing user sees.** Release 0.8.2 copies the full default file into the config folder on first use (`ensure_config`, `config/loader.py`), so every existing user has a file holding every removed setting. Unknown keys only warn (F1), so the file keeps loading. To keep that to one line, the loader knows the removed names and reports them together:

```
warning: config.yaml: 4 settings are no longer used (workspace, tla, tlc.java_class, tlc.overrides_class); run `tlaup config edit` and delete them
```

One line per load, whatever the number of removed names, a removed section counting once. A key that is neither known nor on the removed list gets its own warning, as F1 says. The list of removed names is deleted from the code in the release after 0.9.0 is superseded; from then on they are ordinary unknown keys.

**Tests.** Unit: the default file validates; the 0.8.2 default file, kept as a test data file, loads and produces exactly the one warning above; a file with one removed key inside a kept section (`tlc.java_class`) is reported in the same line; `tool.token_hosts` with a scheme or a path is `ConfigInvalid`; a layer marked as a project layer that sets `tool.repository` or `tool.token_hosts` has the key dropped with a warning (the layer kind exists in the loader from the first wave, so this is testable before the project file is). Feature (in-process): `tool.repository` set to another `https` address is the host the requests go to.

**Changelog.** Breaking: "Config settings removed: `workspace.root`, `workspace.spec_dir`, `workspace.modules_dir`, `workspace.classes_dir` (the folder names `spec`, `modules`, `classes` and `lib` are fixed), `tlc.java_class`, `tlc.overrides_class`, `tla.community_modules`. `tla.urls.tags`, `tla.urls.releases` and `tla.urls.per_page` are replaced by `tool.repository`. A config file that still has them loads with one warning on every command; earlier versions wrote all of them into the file, so delete the file or remove those lines with `tlaup config edit`." Added: "`tool.token_hosts` lists extra hosts that may receive the GitHub token."

**Risks.** Someone relies on a renamed modules folder; the warning names the key and the changelog says what is fixed. (Stage 4 review, 2026-11-24: the YAML block named the section `tools:` and lacked `tlc.keep`, clerical; "nothing changes" for `module_lib_path` no longer held once the compile classpath became narrow, finding B8, decision D61; the relative-path rule covers `module_lib_path` too, finding E9.)

## F4 Config commands with a broken file

Roadmap: "`config` commands work when the file is broken, and a broken file gives a readable validation message instead of a traceback."

**Problem.** The root callback calls `load_config()` for every command (`cli.py:46`), so with a broken file even `tlaup config edit` fails with a traceback.

**Design** (decision D42). Nothing loads settings in the root callback. With a broken file, the two commands that let the user fix it work, and nothing pretends the file was read:

| Command | With a file that does not parse, or holds an invalid value |
| --- | --- |
| `config path` | Prints the path. Never reads the file. |
| `config edit` | Opens the file (F5). |
| `config show` | Exits 3 with the error of F1: the file, the line and column for a YAML error, or the key for an invalid value. Nothing on stdout. |
| `config get KEY` | The same. |
| `config set KEY VALUE` | The same; nothing is written. A file that does not parse cannot be rewritten without losing what is in it, and a file with one invalid value is still a file the user has to look at. |

The error carries the hint `tlaup config edit`. Every other command that needs settings raises the same `ConfigInvalid`.

This reads the roadmap's "`config` commands work when the file is broken" as: the commands needed to repair the file work, and the others fail cleanly with the reason. D42 settled it; `show` and `get` do not fall back to defaults, because their output would then describe settings that are not in effect.

**Rejected.** `show` and `get` printing defaults and environment values with a warning: exit 0 with output that ignores the user's file. `config set` repairing a file with an invalid value in another key: it would rewrite a file it could only partly validate, and with a YAML error it cannot read the file at all.

**Tests.** `tlc_run.feature` (the new `tlc` command's, since the config commands land before it): with a broken file, `tlaup tlc Spec` exits 3, names the key and prints no traceback. `config.feature` (in-process): with `the config file contains:` invalid YAML, and separately a wrong type, each of the five commands behaves as in the table, with no traceback; for `set`, `the config file is unchanged`; after the fake editor fixes the file, `config show` exits 0. (Stage 4 review, 2026-11-24: the `tlaup tlc Spec` scenario moved to the `tlc` command's feature, since under D62 no old command is tested in between.)

**Changelog.** Fixed: "With a broken config file every command, including `tlaup config edit`, failed with a traceback. `config path` and `config edit` now work with a broken file; other commands stop with the file, the line and the reason."

**Depends on.** F1, C1.

## F5 config edit

Roadmap: "`config edit`: accept `$VISUAL` and `$EDITOR` values with arguments such as `code --wait`, have a default that exists on the platform, and validate the file after editing."

**Problem.** The editor value is passed whole to `shutil.which`, so `code --wait` is "not found"; the default is `vim`; `$VISUAL` is not read; the editor is a positional argument.

**Design.**

1. The editor command is `$VISUAL`, else `$EDITOR`, else the first of these found on `PATH`: on Windows `notepad`; elsewhere `sensible-editor`, `nano`, `vi`. None found: `NotSetUp` with the hint to set `EDITOR`. A `$VISUAL` or `$EDITOR` whose first word is not on `PATH` is `NotSetUp` too (code 3), naming the program and the variable.
2. The value is split with `shlex.split`; the first word is looked up with `shutil.which`; the file path is appended as the last argument.
3. If the file does not exist it is created first holding one line: the comment naming the reference page that every file written by tlaup starts with (F1). The defaults are not copied in as commented-out lines: `config set` would drop them at the next change (F1), and `tlaup config show` prints every default with its source.
4. The editor is run without a shell and waited for. A non-zero exit is `Failed` (code 5).
5. Afterwards the file is validated with the loader. Problems are printed as in F1 and the command exits 3; the file is left as the user saved it. A file still holding only that one line is removed again, so that opening the editor and quitting does not create a file (D10).

The positional `EDITOR` argument is removed ([23 C1](23-command-layout.md#c1-command-tree)).

**Tests.** `config.feature` with the fake editor: `EDITOR="editor --wait"` runs it with `--wait` and the path; `VISUAL` wins over `EDITOR`; an edit that writes a wrong value exits 3 and names the key; quitting without changes leaves no file; the editor exiting 1 gives code 5; an `EDITOR` that names a program not on `PATH` exits 3 and names it (inventory row O10). (Stage 4 review, 2026-11-24: an editor not on `PATH` is `NotSetUp`; F5 was silent on it.)

**Changelog.** Fixed: "`tlaup config edit` failed for an editor given with arguments (`EDITOR='code --wait'`) and on machines without vim." Changed: "It reads `$VISUAL` before `$EDITOR` and checks the file after editing." Breaking: "The editor can no longer be given as an argument; set `VISUAL` or `EDITOR`."

## F6 Messages

Roadmap: "Route every message through the one UI helper; there are 21 hand-written error prints and a warning printed to stdout in `tools list`." Relies on D30.

**Design.** `tlaup/ui.py` owns the only two consoles.

```python
class _PipeConsole(Console):         # rich.console.Console; the only console class tlaup builds
    def on_broken_pipe(self) -> None:
        raise BrokenPipeError        # Rich's own version points stdout at the null device and exits 1 (F10)

class Ui:
    def __init__(self, stdout: TextIO, stderr: TextIO, stdin: TextIO, *, color: ColorPolicy,
                 env: Mapping[str, str], interactive: bool | None = None,
                 terminal: bool | None = None, size: tuple[int, int] | None = None): ...
    @classmethod
    def for_process(cls) -> "Ui"                # the real three streams and os.environ; needs no settings, raises nothing
    out: Console                 # results; a _PipeConsole on stdout
    err: Console                 # everything else; a _PipeConsole on stderr
    def error(self, message: str, *, hint: str | None = None, details: str | None = None) -> None
    def warning(self, message: str) -> None
    def note(self, message: str) -> None        # what tlaup did: "Pinned v1.7.4@5a47802"
    def result(self, renderable) -> None        # to stdout
    def ask(self, question: str, *, choices, default) -> str      # prompt on stderr, answer from stdin
    def is_interactive(self) -> bool            # the argument if given; else stdin and stderr are both terminals
```

**Both consoles are `_PipeConsole`s**, and so is any console a reporter needs: reporters take `ui.out` and `ui.err` and build none of their own ([22 O1](22-reporters.md#o1-reporter-interface)). That is what makes a closed pipe exit 141 instead of Rich's 1 (F10, tried).

**`ask` is the only place that reads an answer.** It writes the question to stderr and reads one line from the `stdin` stream it was given, with `readline`. It uses none of Typer's or Rich's prompt functions. Typer's raise `typer.Abort` at end of input (tried: `typer.prompt` and `typer.confirm` with stdin at its end print "Aborted." and exit 1 in a bare app), and the mapping of F10 turns `typer.Abort` into 130, the code for Ctrl-C; and they read from the process's real stdin, which a test cannot hand in. An empty read is end of input (stdin closed, Ctrl-D) and raises `CannotAsk` (code 3). A line holding only a newline takes the default. An answer that is not one of the choices is asked again. Ctrl-C while it waits is a `KeyboardInterrupt` and exits 130 ([02 X1](02-cross-cutting.md#x1-exit-codes)).

`is_interactive` requires both streams because the question is written to stderr and the answer read from stdin; a command that would ask and finds it false raises `CannotAsk`, or a usage error naming the option that answers the question, or takes its documented non-interactive path. While a run's reporter is between `start` and `close`, nothing else prints through `ui`, so the layout is not torn ([22 O1](22-reporters.md#o1-reporter-interface)); a line of tlaup's own that the run must show meanwhile, such as the waiting line while a first signal is held during a checkpoint, goes through `Reporter.notice` instead ([22 O1](22-reporters.md#o1-reporter-interface) says where it is shown; [11 R2](11-runner.md#r2-signals)). (Stage 4 review, 2026-11-24: the waiting line went through `ui` while the reporter was up, question Q12.)

**One seam for tests: the constructor.** A test that needs a prompt answered builds the `Ui` itself, on in-memory streams, with the answers in `stdin` and `interactive=True`, and calls the function under test with it; nothing is patched. `Ui.for_process()` never passes the three test arguments, so in a real process no stream is ever treated as a terminal when it is not one. A test of the live layout needs more than answers: `terminal=True` and `size=(100, 30)` are passed to both consoles as Rich's public `force_terminal`, `width` and `height`, and the test sets `TERM=xterm-256color` with `monkeypatch`, because Rich reads `TERM` from the process's environment and the isolation fixture's `TERM=dumb` would switch the layout off (the third check found that under `TERM=dumb` Rich's live display writes no frames at all; [22 O6](22-reporters.md#o6-snapshot-tests)). Rich has no public constructor argument for the environment in the locked 13.9.4 (the reviewer's probe set the private `_environ`), and tlaup does not use a private one for the sake of a test: `monkeypatch` alone is enough (tried in memory on the locked Rich: one enter, one leave and four frames, against none under `dumb`). That is plain pytest, and it is how a prompt followed by a download is tested, since a real process cannot be served recordings. A prompt that needs no network (`uninstall` asking which build, `pin` asking which build) is also a feature scenario run as a real process on a pty, where the answers are typed ([01 T5](01-testing.md#t5-feature-files-and-steps)). In-process feature scenarios never answer a prompt: under `CliRunner` the streams are not terminals, so `is_interactive()` is false and the command takes its non-interactive path.

Format, on stderr:

```
error: no version pinned
hint: run `tlaup tool pin v1.7.4`
warning: config.yaml: unknown key "workspace" (ignored)
```

- Lower-case prefixes, no symbols. `error:` red, `warning:` yellow, `hint:` cyan, when the stream is a terminal and `NO_COLOR` is unset. The symbols `✖ ⚠ ✔` go: they are what cannot be encoded on some terminals (the milestone 4 point about glyphs), and the prefix carries the meaning without them.
- One line per message; `details` follow, indented by two spaces.
- A successful action prints a `note` on stderr, without a "Success:" prefix. "Successfully installed" after "already installed" goes; the line is `v1.7.4@5a47802 is already installed (use --force to download it again)`.
- Text from outside tlaup is never treated as markup ([10 P11](10-parser.md#p11-tlc-text-and-rich-markup)).
- `NO_COLOR` is honoured by both consoles (roadmap: the helper ignores it today). The `--color`, `--quiet` and `--verbose` options are milestone 4; `ColorPolicy` and the methods above are where they attach.

All 21 hand-written prints and every `typer.echo(..., err=True)` become `raise SomeError(...)` (printed by the handler, F10) or a `ui` call. The `T20` lint rule ([30 I8](30-ci-and-release.md#i8-lint-rules)) forbids `print` in `src/`; a second check forbids `typer.echo` and `Console(` outside `ui.py` and the reporters.

**Rejected.** The `logging` module for user messages: levels and handlers for what is a dozen calls. Keeping the symbols with an ASCII fallback: two renderings to test for no information.

**Tests.** Feature assertions on stream and content throughout. A unit test renders each kind of message through `Ui` built on `StringIO` streams, with colour off and on, against expected files. With `NO_COLOR=1` and a forced terminal the output has no escape sequences. Unit, `ask` on in-memory streams: a valid answer; an invalid one and then a valid one asks twice; an empty line gives the default; an empty read raises `CannotAsk`; the question is on stderr and nothing is on stdout. Unit: `is_interactive()` is false on in-memory streams and true with `interactive=True`. A real-pty scenario covers the worked-out case: `tool uninstall rolling` with two builds asks on a pty, and with stderr redirected to a file it does not ask ([12 V3](12-tools-and-downloads.md#v3-uninstall)). Unit: a `_PipeConsole` writing to a file object whose `write` raises `BrokenPipeError` lets the error out.

**Changelog.** Changed: "Messages have the form `error: ...`, `warning: ...`, `hint: ...` on stderr, without symbols." Fixed: "`NO_COLOR` is honoured everywhere." "A warning from `tool list` went to stdout."

**Depends on.** G2. **Risks.** Scripts that matched `Error:` with a capital; the changelog entry covers it.

## F7 Help text

Roadmap: "Help text (raised list): ..." (eleven points).

**Design.** Each point is a change to a help string or to the command's declaration; the review reads the generated CLI reference ([23 C5](23-command-layout.md#c5-help-and-the-cli-reference)), not assertions on wording.

| Point | Text or change |
| --- | --- |
| What `upgrade` means | "Replace an installed version with the newest build of the same name. Rolling builds are rebuilt often; this fetches the current one. It does not move to a different version: use `install` for that." |
| `install` with no version; first install is pinned | "With no VERSION, asks whether to install `stable` or `rolling`. The first build installed is pinned." |
| `module` wording | "Manage your own TLA+ modules, with optional Java operator overrides." |
| The layout `module add` expects | A long description: `modules/*.tla`, `modules/tlc2/overrides/*.java` or `tlc2/overrides/*.java`, `lib/*.jar`; the folder's name becomes the module's name; an existing module of that name is replaced. |
| `SPEC` | "A TLA+ spec: a name (`Spec`), a file (`Spec.tla`) or a path. `spec/Spec.tla` is tried too." |
| `--raw` | "Print TLC's own output unchanged, with no parsing or formatting." |
| Scope of `--yes` | "Answer every question of this command with yes." |
| `tool path VERSION` | Gets a help string. |
| "TLC" where the toolset is meant | "TLA+ tools" in every `tool` help string. |
| One summary line | The package summary in `pyproject.toml` is the one source; the root help reads it from the metadata. |
| Root help order | Three panels: Run (`tlc`, `sany`, `pcal`, `repl`), Manage (`tool`, `module`, `config`, `cache`), Maintenance (`doctor`, `completion`). |
| Examples | `tlc`, `tool install`, `module add` and `sany` get an epilog with two or three example commands. |

**Tests.** The generated reference is an expected file; CI fails when it drifts ([23 C5](23-command-layout.md#c5-help-and-the-cli-reference)). No test asserts a help sentence.

**Changelog.** Changed: "Help text rewritten for `tool`, `module` and `tlc`; root help is grouped." (Stage 4 review, 2026-11-24: the command names made singular, as decision D47 has them; clerical.)

**Depends on.** C1.

## F8 Wording

Roadmap: "Wording: one word for a stopped run ('canceled' and 'stopped' are both used); module timestamps with a time zone; the typos listed in the report."

**Design.**

- A run ended by a signal is **interrupted**: the status value, the summary line ("Interrupted after 02:13."), the live layout's key hint ("Ctrl-C to interrupt"). "canceled" and "stopped" go; `CheckState.Stopped` becomes `Status.INTERRUPTED` ([10 P3](10-parser.md#p3-result-model)).
- Module build times are stored in UTC with `Z` and shown as `2026-11-15 10:00 UTC` ([13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder)).
- Typos: the comment in `java/inspector.py` ("might minimal output") and its reference to a document that does not exist are removed with the rewrite of that file (J2). The two changelog typos (0.7.0 "copy subfolders", 0.5.0 "now parsed") are corrected here, in the pull request that does the rest of this item: two one-word edits to `CHANGELOG.md`. They are not handed to the documentation track's changelog item, whose text says to leave the rest of the history alone.

**Tests.** Through the reporter's expected files; `modules.feature` checks the list shows `UTC`.

**Changelog.** Changed: "A run stopped with Ctrl-C is called 'interrupted' everywhere." "`module list` shows build times in UTC."

## F9 Startup cost

Roadmap: "Skip the `git rev-parse` call on normal installs; load heavy libraries (requests, Rich progress, pydantic schema) only in the commands that need them; set up the OS trust store where the network is used, not as a side effect of importing the package. `tlaup --help` took about a third of a second when measured."

**Problem.** `tlaup/__init__.py` and the top-level imports of the command modules pull in `requests`, `rich.progress`, the settings schema and the trust-store setup for every command. `--version` starts `git rev-parse` every time (`get_app_version` calls `get_git_commit_hash` before it decides whether the install is a development one, `versioning/app_version.py`); only the use of the answer depends on the install.

**Design.**

- `tlaup/__init__.py` holds nothing but the docstring.
- Command modules import only `typer`, `tlaup.errors` and `tlaup.context` at the top. Everything else is imported inside the command function. This is the one place function-level imports are the rule, and the lint configuration says so: ruff's `PLC0415` (an import outside the top level, in the `PL` group, active on the locked ruff 0.17.5) flags them, so `pyproject.toml` carries the per-file ignores `"src/tlaup/cmd/**" = ["PLC0415"]` and `"src/tlaup/cli.py" = ["PLC0415"]`, with a comment naming this section. It is in place before the first command module written this way, so that no command needs a `noqa` of its own.
- **One exception: the completion module.** `tlaup/cmd/completion.py` ([23 C3](23-command-layout.md#c3-completion)) is imported at the top of `tlaup/cli.py`, which registers the `completion` command, and at the top of the command modules that name its completers in `autocompletion=`, since a completer is named when the command is declared. Keeping it out would save nothing worth having: Typer loads its own completion modules on `import typer` (tried on the locked 0.29.1), so what is added is tlaup's one small module, which imports nothing on the list of the tests below at its top level; its completers import what they need in their own bodies. Completion is still off unless asked: Typer's shell registry stays empty until `completion_init()` runs, and `main()` calls that only when `_TLAUP_COMPLETE` is set (C3).
- `truststore.inject_into_ssl()` is called in `GitHubClient.__init__`.
- Settings load lazily (F1), so the settings schema (`tlaup.config.schema`) and `yaml` are imported only by commands that read a setting. **pydantic itself is not on the list of things kept out.** The roadmap names "pydantic schema"; on the locked Typer 0.29.1, Typer imports `pydantic` when any command runs (tried: `pydantic` is absent from `sys.modules` after `import typer` and after `--help`, and present after a command with no pydantic use of its own ran). So tlaup can keep its own schema module from loading, and cannot keep pydantic from loading. What that costs was not measured.
- `get_app_version`: the version is the package metadata's. The commit suffix is added only when `is_editable_install()` is true, and only then is `git` started, with a 2-second timeout.

**Tests.** A test starts `python -c "import tlaup.cli, sys; print(sorted(m for m in ('requests','yaml','truststore','rich.progress','rich.live','tlaup.config.schema','tlaup.versioning.github') if m in sys.modules))"` and asserts the list is empty. A second, also in a fresh interpreter, does the same after running `tlaup tool dir` in-process, a command that needs neither settings nor the network. `pydantic` is not in the list, for the reason above. A third, also in a fresh interpreter, shows that completion is off unless asked: after `import tlaup.cli`, Typer's shell registry (`typer._click.shell_completion._available_shells`) is empty, and after `completion_init()` it holds `bash`, `zsh` and `fish`; the name is private, so the Typer contract tests (F10) check that it exists. `test_app_version` with the fake `git`: a normal install does not start `git` (the fake's log is empty). No test measures time.

**Changelog.** Changed: "`tlaup --help` and other commands that need neither the network nor the config start faster." Fixed: "`tlaup --version` started `git` on every call."

**Risks.** A later change adds a top-level import and nobody notices; the test above is the guard. (Stage 4 review, 2026-11-24: ruff's `PLC0415` flags the rule and the per-file ignore had no home, finding D2; the completion module cannot be kept out of an ordinary start, since Typer loads its own on import, and is now an exception, finding D1.)

## F10 No tracebacks

Roadmap: "No tracebacks for users: missing Java, missing jar with `--raw` or `--show-command`, a broken config, an unreadable pin file. Turn off Typer's decorated crash reports, add one top-level handler that prints a one-line error, and add `--debug` to show the full traceback."

**Problem.** Besides the four cases above: the first version of this design caught exceptions in `main()` around `app(standalone_mode=False)` and named Click's exception classes. The stage 3 review found that this does not work on the Typer the project locks, and the facts below were then tried.

**Facts (tried on the locked Typer 0.29.1; top-up: [research 23](../research/23-typer-versions.md) ran the same checks on thirteen Typer versions from 0.22.0 to 0.29.2, with the results below).** Typer carries its own copy of Click as the private package `typer._click`; `click` is not installed and `import click` fails. That holds from Typer 0.26.0; before it Typer depends on a separate Click, and with a Click older than 8.2.1 a bare group exits 0. `typer.TyperException` is public from 0.27.2 only. From 0.27.2 every version gave the codes below, the 141 through a closed pipe and the 130 on a real SIGINT exactly as 0.29.1 did, which is why the lower bound is `typer>=0.27.2` ([30 B2](30-ci-and-release.md#b2-build-fixes)). Typer's public names include `typer.Exit`, `typer.Abort`, `typer.BadParameter` and `typer.TyperException`, which is a base class of every usage error Typer raises. In Typer's own entry code, in this order: an `EOFError` becomes "Aborted." and exit 1; a `KeyboardInterrupt` becomes exit 130; a usage error is printed in Typer's form and exits 2; an `OSError` with `EPIPE` exits 1. An exception raised by a command and caught nowhere else leaves through `sys.excepthook`. A test runner that calls the app (`typer.testing.CliRunner`) sees only what happens inside the app, so a mapping done in `main()` around it is invisible to in-process tests: a domain error showed exit 1 there.

A root group class with its own `invoke` was then tried, with these results: a domain error raised in a nested `tools` subcommand gave exit 3 under `CliRunner` and as a real process; `KeyboardInterrupt` in a command gave 130; a missing argument, an unknown command, an unknown option and a `typer.BadParameter` gave 2 in Typer's form; an unexpected `RuntimeError` gave 5 with one line, and with the traceback when debugging was on.

**The closed pipe, tried again after the second check of this design.** The first probe printed with plain `print` and gave 141. tlaup prints through Rich consoles (F6), and there the result was 1: Rich 13.9.4 catches `BrokenPipeError` inside `Console.print`, calls the console's `on_broken_pipe`, and that method points `sys.stdout`'s file descriptor at the null device and raises `SystemExit(1)`. Rich documents the method as the place to change this. Tried on the locked Rich 13.9.4 and Typer 0.29.1, as real processes on Linux:

- A console subclass whose `on_broken_pipe` raises `BrokenPipeError` instead: the error reaches the root group, and a command printing through it into `| head -1` gave 141.
- Typer prints help and its usage errors through a console of its own, so those still left as `SystemExit(1)`: `--help | head -1` gave 1.
- With the check in `main()` below, these all gave 141: `--help | head -1`; a subcommand's `--help | head -1`; no arguments `| head -1`; an unknown option with `2>&1 | head -1`; and `--help`, an unknown option with `2>&1`, and a three-line command printing through the subclass, each with a reader that had closed its end before tlaup wrote anything. `--help | cat` gave 0 and an unknown option with nothing closed gave 2.
- Without the flush in `main()`'s `finally`, an unknown option with stderr on a closed pipe once gave 120, which is the interpreter's own code for a failed flush at exit.
- An unknown option with stdout already on the null device and stderr on a closed pipe gave 1 with the null-device check alone, because descriptor 1 does not change; with the second check below (the reader of a stream is gone) it gave 141.

**Tried again after the third check**, with a small app built from the code below, as real processes on Linux with the same two versions:

- A domain error and an internal error with stderr's reader gone, with stdout open, on the same dead pipe, and on the null device: all 141 with no traceback (they gave 1 before `reported` existed). A domain error with only stdout's reader gone: 3, with its message on stderr.
- Onto `/dev/full`: a command's output and `--help` gave 5 with `error: cannot write output: No space left on device` on stderr; an unknown option with stderr there gave 5; a domain error with stderr there kept its 3. Before, these gave 120 or an internal-error line.
- A command printing without end into a pipe whose reader was alive and not reading, then SIGINT: exit 130 within a fifth of a second, with stdout alone and with both streams on that pipe.
- Two calls of `main()` in one process, the first a command exiting 1 through `typer.Exit`, the second `--help` into a pipe with no reader: the second gave 141.
- Unchanged: help at three levels, no arguments, `--version`, a three-line command and a 200,000-line command into a dead or early-leaving reader, and an unknown option with either or both streams dead, all 141; a command exiting 1, 12 or 0 through `typer.Exit` with its readers gone kept its code; a reader that waited a second and then read everything gave 0.

**Errors outside `invoke`, tried.** The root's own options are parsed in the group's `make_context`, before `invoke`. An exception raised there by an eager option callback (`--version`) left as a traceback and exit 1 (tried without the wrapper). With the same mapping wrapped around `make_context`, a `RuntimeError` in the callback gave 5 with one line, a domain error 3, a `BrokenPipeError` 141; usage errors stayed 2 in Typer's form, and an error raised by the root callback was mapped as before.

**Design.** The mapping lives inside the app, in the root group, around both steps Typer takes there: building the context (`make_context`, where the root's options are parsed and eager callbacks run) and running (`invoke`).

```python
# tlaup/cli.py
@contextmanager
def mapped(*, ctx: typer.Context | None = None, args: Sequence[str] = ()) -> Iterator[None]:
    try:
        yield
    except typer.Exit:
        own_exit.seen = True                    # an exit a command asked for, the wrapped tool's code among them
        raise
    except (typer.TyperException, KeyboardInterrupt):
        raise                                   # Typer's own: usage errors (2), Ctrl-C (130)
    except typer.Abort:
        raise typer.Exit(130) from None         # Ctrl-C at a prompt that is not Ui.ask; tlaup has none
    except TlaupError as e:                     # error:, hint:, details, then the exception's notes; see below
        raise typer.Exit(reported(e.exit_code, report, e, ctx, args)) from None
    except BrokenPipeError as e:
        silence(sys.stdout)
        print_notes(e, ctx)                     # to stderr; nothing else is printed for a closed pipe
        raise typer.Exit(141) from None
    except EOFError:
        error = CannotAsk("the input ended while tlaup was waiting for an answer")
        raise typer.Exit(reported(3, report, error, ctx, args)) from None
    except OSError as e:
        if closed_pipe_on_windows(e):           # top-up, D57: Windows reports a closed pipe as EINVAL
            silence(sys.stdout)
            print_notes(e, ctx)
            raise typer.Exit(141) from None
        if e.filename is None and e.errno in WRITE_ERRNOS:      # a write to a stream that is already open failed
            silence(sys.stdout)
            error = Failed(f"cannot write output: {e.strerror}")
            raise typer.Exit(reported(5, report, error, ctx, args)) from None
        raise typer.Exit(reported(5, report_internal_error, e, ctx, args)) from None
    except Exception as e:                      # the one allowed blind except (30 I8)
        raise typer.Exit(reported(5, report_internal_error, e, ctx, args)) from None

def reported(code: int, report_it, *args) -> int:
    """Print the error; if stderr itself cannot be written, say nothing more and keep a sensible code."""
    try:
        report_it(*args)
    except BrokenPipeError:                     # stderr is the pipe that closed
        silence(sys.stderr)
        return 141
    except OSError:                             # stderr is on a full disk; the error's own code stands
        silence(sys.stderr)
    return code

WRITE_ERRNOS = {errno.ENOSPC, errno.EDQUOT, errno.EFBIG, errno.EIO}

def closed_pipe_on_windows(e: OSError) -> bool:
    """An OSError(EINVAL) with no file name from a write, while stdout or stderr is a pipe: on Windows
    that is how a closed pipe shows (research 30); nowhere else is it treated so."""
    return (os.name == "nt" and e.errno == errno.EINVAL and e.filename is None
            and (is_pipe(1) or is_pipe(2)))         # stat.S_ISFIFO(os.fstat(fd).st_mode), guarded

class TlaupGroup(TyperGroup):                      # typer.core.TyperGroup
    def make_context(self, info_name, args, parent=None, **extra):
        with mapped(args=args):                     # no context yet
            return super().make_context(info_name, args, parent=parent, **extra)

    def invoke(self, ctx: typer.Context) -> Any:
        with mapped(ctx=ctx):
            return super().invoke(ctx)

app = typer.Typer(cls=TlaupGroup, name="tlaup", add_completion=False, no_args_is_help=True,
                  pretty_exceptions_enable=False)

def main() -> None:                                 # the console script, and tlaup/__main__.py
    own_exit.seen = False                           # main() may be called twice in one process
    stdout_was_null = is_null_device(1)
    code = 0
    try:
        app(prog_name="tlaup")                      # always leaves by SystemExit
    except SystemExit as leaving:
        code = exit_code_of(leaving)                # None is 0, an int is itself
        if code == 1 and not own_exit.seen and (            # never a 1 that a command asked for
            (is_null_device(1) and not stdout_was_null)     # Rich's own closed-pipe handling ran
            or reader_gone(1) or reader_gone(2)             # a stream is a pipe nobody reads
        ):
            code = 141
    except BrokenPipeError:                         # Typer's own printing, outside the group
        code = 141
    except OSError as e:                            # the same, on a full disk: its message could not be written
        code = 141 if closed_pipe_on_windows(e) else 5
    if code in (129, 130, 143):                     # stopped by a signal: do not wait for a reader
        silence(sys.stdout)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except BrokenPipeError:
            silence(stream)
            code = code or 141
        except OSError as e:                        # a full disk under a redirect, or Windows' closed pipe
            silence(stream)
            code = code or (141 if closed_pipe_on_windows(e) else 5)
    sys.exit(code)
```

- **Everything goes through the root group.** Subcommands and nested groups are invoked from inside the root's `invoke`, and so is the root callback, so one mapping covers them all. The root's `make_context` is wrapped too, so an error in the eager `--version` callback, or anything else raised while the root's options are parsed, is mapped the same way. Usage errors Typer raises there pass through untouched and are printed by Typer, which is the wanted result (exit 2).
- **`report(error, ctx, args)`** prints through a `Ui`: `error: <message>`, then `hint:` if the error has one, then its details, then the exception's notes. **Notes** are Python's own: text attached with `exception.add_note(...)`, which every exception has from Python 3.11 on, read from `__notes__` and printed one per line on stderr ([20 G2](20-groundwork.md#g2-domain-errors)). The one use in the first wave is the run frame, which adds "Checkpoint kept: ..." and the command to resume when a run folder with a checkpoint was kept while an error passes through it ([11 R6](11-runner.md#r6-run-folders)). The error can be of any class, so the notes are printed in all three branches: after the `error:` line and hint of a `TlaupError`, after those of an internal error, and alone for a closed pipe, where stderr may still be read although stdout is not. Printing them is guarded: if stderr is the pipe that closed, the second `BrokenPipeError` is swallowed and the code is still 141. **Reporting itself is guarded the same way** (`reported`): `report` and `report_internal_error` print through tlaup's own console, so with stderr on a closed pipe they raise `BrokenPipeError` from inside the `except` branch, where nothing above would catch it. The third check of this design found that path exiting 1 with a traceback (`tlaup --debug tool pin nosuch 2>&1 | head -1` is a realistic form). `reported` silences stderr and makes the code 141; if stderr is on a full disk instead, it silences stderr and the error keeps its own code. `report` needs a `Ui` even when the application context was never built, for example when `TLAUP_HOME` is a relative path and `AppPaths.from_env` raises in the root callback. So it takes `ctx.obj.ui` when there is one and otherwise `Ui.for_process()` (F6), which needs no settings and no paths. The eager `--version` callback prints through `Ui.for_process()` for the same reason: it runs before the root callback has built anything.
- **The closed pipe has three parts** ([02 X1](02-cross-cutting.md#x1-exit-codes), rule 8).
  1. tlaup's consoles are built from a subclass whose `on_broken_pipe` raises `BrokenPipeError` (F6). The error travels up to `mapped`, whose branch points stdout at the null device and exits 141.
  2. Help and Typer's usage errors are printed by Typer through a console tlaup does not own; Rich handles the closed pipe there itself and raises `SystemExit(1)`. A `SystemExit` passes through `mapped` (it is not an `Exception`), so `main()` looks at every 1 that leaves the app. It is turned into 141 when descriptor 1 is the null device now and was not when `main()` started (Rich's handling points it there), or when stdout or stderr is a pipe whose reader is gone (`reader_gone(fd)`: the descriptor is registered with `select.poll` for `POLLOUT`, and `POLLERR` or `POLLHUP` in the answer means the reader is gone; `POLLNVAL` means it is not a pipe that can be judged, and gives false, as does a platform without `poll`). Top-up ([research 30](../research/30-library-behaviours.md)): Linux reports `POLLERR`, macOS `POLLHUP` alone, and macOS reports nothing at all for a descriptor registered with an empty mask, which is why `POLLOUT` is asked for; a full pipe whose reader is alive reports neither. Also from research 30: a stderr console on a closed stderr points descriptor 1 at the null device, never descriptor 2, so the final flush and `reader_gone(2)` are what turn such a run's 1 or 120 into 141. The same `reader_gone(1)` lets a raw run stop TLC when its stdout's reader goes ([11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are), D58). The second test is what catches a closed stderr while stdout was on the null device from the start. A 1 can also be the wrapped tool's own code, passed through as `typer.Exit(1)` (TLC rejecting a flag, [02 X1](02-cross-cutting.md#x1-exit-codes) rules 1 and 2), and that one must stay 1 even when the reader has gone. So `mapped` notes every `typer.Exit` that passes through it (`own_exit.seen`, a module-level flag), and `main()` leaves the code alone when one was seen. Rich's `SystemExit(1)` is not a `typer.Exit` and is never noted. Tried with a small app after this was written: a command that exits 1 or 12 through `typer.Exit`, with its reader gone on stdout or on both streams, kept its code; help, a subcommand's help and an unknown option with the reader gone still gave 141.
  3. `main()` flushes both streams itself inside a guard and then exits with the code it holds, so the interpreter's own flush at exit cannot fail and turn the code into 120. A closed pipe found only at this flush makes a 0 into 141 and leaves any other code alone.
- **A full disk** (`tlaup tlc Spec > out.txt` on a full file system; tried with `/dev/full`) is not a closed pipe and is code 5. Where the write fails decides who sees it: inside a command it is an `OSError` with no file name and one of four error numbers (no space, quota, file too large, input/output error), which `mapped` reports as `error: cannot write output: <reason>` instead of as an internal error; in Typer's own printing outside the group it reaches `main()`, which sets 5; at the final flush it makes a 0 into 5 and leaves any other code alone. An `OSError` of any other kind that reaches the root is still an internal error: domain code wraps its own ([20 G2](20-groundwork.md#g2-domain-errors)).
- **After a signal the final flush does not wait.** When the code is 129, 130 or 143, `main()` points stdout at the null device before flushing. Without that, a Ctrl-C while the reader is alive but not reading (`tlaup tool list | less`, with the pipe full) left tlaup blocked in the flush until the reader read or quit (found by the third check). What was still in Python's buffer for stdout is dropped; the consoles flush after every print, so that is at most part of one print.
- **The body of `main()` is a function of the app**, `run_app(app)`, which `main()` calls with tlaup's own; the code above shows it inline. A test can then start a child Python that runs it on a small app, which is how the signal and two-calls cases below are tested without a hidden command in tlaup.
- **`own_exit.seen` is reset at the top of `main()`**, since any `typer.Exit` sets it, a successful `--help` among them, and `main()` can be called more than once in a process. In-process tests call `app`, not `main()`, and never read the flag.
- **`main()` is otherwise only the call.** `src/tlaup/__main__.py` is added and calls `main()`, so `python -m tlaup` works; the real-process tests start tlaup that way ([01 T5](01-testing.md#t5-feature-files-and-steps)). `prog_name` is fixed so that usage lines and the completion variable (`_TLAUP_COMPLETE`, [23 C3](23-command-layout.md#c3-completion)) do not depend on how the program was started. `main()` also switches Typer's completion on when that variable is set (C3). In-process tests call `app`, not `main()`, and see every code except those `main()` sets (141 for Typer's own printing, and 141 or 5 at the final flush); those are tested as real processes.
- **No command.** `tlaup` alone and a group alone print that level's help on stdout and exit 2, which is Typer's behaviour with `no_args_is_help` (tried: help on stdout, nothing on stderr, exit 2 for the root and for a nested group). It is kept and written into [02 X1](02-cross-cutting.md#x1-exit-codes), rule 7. Making it exit 0 is possible with a callback on the root and on each of the four groups; it was not done, because an incomplete command line is a usage error in the tools this one is modelled on.
- **Usage errors.** Typer's stay in Typer's form ([02 X1](02-cross-cutting.md#x1-exit-codes), rule 7). tlaup's own `UsageError` is a `TlaupError`, not a subclass of Typer's, and is printed as one `error:` line.
- **`report_internal_error`** prints `error: internal error: <ExceptionType>: <message>` and `hint: run it again as "tlaup --debug ..." or with TLAUP_DEBUG=1, and report it at <issues address>`.
- **`--debug`** is an option of the root command, so it goes before the subcommand: `tlaup --debug tool install rolling`. After the subcommand Typer answers "No such option" (tried). `TLAUP_DEBUG=1` does the same from the environment and needs no position, which is why the hint names both. With either, the handler prints the full traceback after the one-line message, for a `TlaupError` and for an internal error. Every line the handler prints under debug, the one-line message and the traceback, passes through the debug filter `redact(text, os.environ)` of [12 V7](12-tools-and-downloads.md#v7-github-client), which the handler imports without the cost F9 keeps out. (Stage 4 review, 2026-11-24: the filter had no home or signature, question Q6; the command name in the realistic form above made singular, clerical; the contract tests below check the shell registry that F9's test reads, finding D1.) The handler does not read the flag from the application context, because the failure may have happened while the context was being built: it reads `ctx.params` when a context exists, the environment always, and, when the failure was in `make_context` and no context exists yet, whether `--debug` stands among the arguments before the first word that does not start with `-`.
- **`silence(stream)`** points the stream's file descriptor at the null device (`os.dup2`), so a later flush does not raise a second broken-pipe error. Guarded for a stream that has no file descriptor (the in-process runner).
- **A prompt that hits end of input** is `CannotAsk` (3), raised by `Ui.ask` itself (F6), which reads the answer with `readline` and uses none of Typer's or Rich's prompts. The `EOFError` branch above is the net for a read that did not go through `Ui`; without it Typer would exit 1, which tlaup never returns ([02 X1](02-cross-cutting.md#x1-exit-codes), rule 1).
- **Signals during a run** are the launcher's ([20 G3](20-groundwork.md#g3-java-launcher), [11 R2](11-runner.md#r2-signals)); this handler sees only what is left: a `KeyboardInterrupt` outside a run, which Typer turns into 130.
- An unreadable pin file is an `OSError` inside the store; the store turns it into `FileOperationError` naming the file.

The four cases the roadmap lists are each a `TlaupError` raised by the preflight ([11 R11](11-runner.md#r11-preflight)) or the loader (F1).

**The versions this rests on** (top-up). Research 23 ran every check above on thirteen Typer versions from 0.22.0 to 0.29.2, each with the locked Rich 13.9.4 and with the lowest Rich it accepts, under `CliRunner` and as real processes: from 0.27.2 on, every result equals 0.29.1's. Research 30 found `Console.on_broken_pipe` from Rich 13.8.0 and its body unchanged up to 15.0.0, and every closed-pipe case above gave the same codes on 13.8.0, 13.9.4, 14.0.0, 14.3.4 and 15.0.0, on Linux and macOS; Rich 13.7 has no such method and the process exits 120. So the bounds are `typer>=0.27.2,<1.0.0` and `rich>=13.8.0` with no upper cap ([30 B2](30-ci-and-release.md#b2-build-fixes)). Python 3.11, 3.12 and 3.14 were not run; the newest-dependencies job covers the drift. Of the `| head -1` forms listed above, those whose output is shorter than the pipe's buffer are racy (the reader may close before or after tlaup writes); the form that is tested is the reader that has closed before tlaup writes anything ([01 T5](01-testing.md#t5-feature-files-and-steps)).

**A closed pipe on Windows** (decision D57, top-up; research 30, two CI runs). On Windows a write to a pipe whose reader has gone raises `OSError` with `errno` 22 (`EINVAL`) and no `winerror`, not `BrokenPipeError`, in every Rich version, whether the reader left before the output or during it. Rich never calls `on_broken_pipe` then, Typer's help leaves with that `OSError`, `select.poll` does not exist, and as first designed every case exited 1 with a traceback. tlaup treats an `OSError` with `errno == EINVAL`, no file name, raised while stdout or stderr is a pipe, as a closed pipe on Windows (`closed_pipe_on_windows` above), in `mapped`, in `main()` and at the final flush: no message, 141, as on Linux and macOS. Why 141 and not 5, which F10's general rule for a failed write would give: `tlaup tool list | more` closed early is not a failure, F10 promises no traceback, and one code for one situation on every system keeps scripts portable. `EINVAL` from a write to a pipe has no other common cause, so the test is narrow; it is not applied on other systems. `stat.S_ISFIFO` on a Windows pipe descriptor follows Python's documentation and was not tried; the work package that builds this checks it on Windows by hand. D15 means no Windows CI, so the tests are unit tests with the error injected.

**Rejected.** *A handler in `main()` around `app(standalone_mode=False)`* (the first design): in-process tests cannot see the codes; `Exit` is returned rather than raised in that mode; Typer has already turned a broken pipe into exit 1 before control returns. *Importing Click's classes from `typer._click`*: a private path, when `typer.TyperException` is public and enough. *Setting `sys.excepthook`*: runs after the interpreter has decided the exit code is 1. *Catching in each command*: forty places instead of one.

**Tests.** `errors.feature` (in-process, where not marked): each of the four listed cases exits with its code and `stderr` has no line starting `Traceback`; with `--debug` before the command, and separately with `TLAUP_DEBUG=1`, the same case has one; `--debug` after the subcommand exits 2. The internal-error path is tested by a unit test that builds a small app with `cls=TlaupGroup` and a command that raises `RuntimeError`, run through `CliRunner`: code 5 and the one-line message; the same with a command that raises `EOFError`: code 3. No hidden test-only command is added to tlaup. The same small app with an eager option callback that raises `RuntimeError`, a `TlaupError` and `BrokenPipeError` in turn: 5, the error's code, 141. In-process: `TLAUP_HOME=relative/path tlaup tool dir` exits 3 with one `error:` line, which is the case of an error before the application context exists. A unit test of `report`: an error with a hint, details and two notes added with `add_note` prints them in that order; the small app with a command that adds a note to a `BrokenPipeError` and raises it exits 141 with the note alone on stderr. Real process: `tlaup tlc Spec` with a fake `java` that prints 100,000 lines, its stdout piped into a reader that exits after one line, gives 141 and no `Traceback` on stderr (the scenario of [11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are)); the closed-pipe, full-disk and interrupted-flush scenarios of [02 X1](02-cross-cutting.md#x1-exit-codes) (a short table, help, and a usage error twice), which are what covers `main()`; `python -m tlaup --version` equals the console script's output. A unit test asserts that no module under `src/tlaup` imports `click` or any Typer module whose name starts with an underscore, apart from `tlaup/cmd/completion.py` ([23 C3](23-command-layout.md#c3-completion)). Unit (top-up, D57): with the platform given as Windows and a pipe as stdout, a command whose print raises `OSError(errno.EINVAL, ...)` exits 141 with nothing printed; the same error on Linux, or with stdout a file, is code 5; `reader_gone` on a stand-in poll answer of `POLLERR`, `POLLHUP`, `POLLOUT` alone and `POLLNVAL` gives true, true, false, false.

**Contract tests of Typer.** Added at the stage 3 sign-off, 2026-11-18. One file, `tests/unit/test_typer_contract.py`, in the default suite, checks each Typer name tlaup relies on by its shape, so that a Typer upgrade which renames or reshapes one fails with that name in the message instead of somewhere inside a command:

- Public: `typer.Exit`, `typer.Abort`, `typer.BadParameter` and `typer.TyperException` exist, and the error Typer raises for an unknown option is a `TyperException`; `typer.core.TyperGroup` has `make_context(info_name, args, parent=None, **extra)` and `invoke(ctx)`, checked with `inspect.signature`.
- Private, for completion ([23 C3](23-command-layout.md#c3-completion)): `typer._completion_classes.completion_init` can be called with no argument; `typer._completion_shared.get_completion_script` accepts the keyword arguments `prog_name`, `complete_var` and `shell`; the script it returns names `COMP_WORDS`, `COMP_CWORD` and `complete_bash` for bash, `_TYPER_COMPLETE_ARGS` and `complete_zsh` for zsh, and `_TYPER_COMPLETE_ARGS`, `_TYPER_COMPLETE_FISH_ACTION` and `complete_fish` for fish; `typer._click.shell_completion._available_shells` is a dictionary, which F9's test reads.

What those names do is tested by the scenarios and unit tests above and in C3; this file only says which name broke. It runs on the locked Typer in every job and on the newest Typer in the newest-dependencies job ([30 I3](30-ci-and-release.md#i3-newest-dependencies-job)). A pull request that changes the root group or `tlaup/cmd/completion.py` because of a Typer change updates the matching check in the same pull request. Not chosen at the sign-off: a separate adapter layer around Typer, since the private names already sit in one module and the overridden methods in the root group; depending on `click` directly, which does not help, since Typer uses its own copy.

**Changelog.** Fixed: "Several failures printed a Python traceback. tlaup now prints one `error:` line; `tlaup --debug ...` or `TLAUP_DEBUG=1` shows the traceback." Added: "`--debug`, and `python -m tlaup`."

**Depends on.** G2, F6. **Risks.** The handler subclasses `typer.core.TyperGroup`, overrides two of its methods, and relies on the order in which Typer handles exceptions; a Typer release can change any of these. Part 2 of the closed-pipe handling relies on what Rich does in a console tlaup does not own; if a Rich release stops pointing stdout at the null device, the reader test still applies, and if it stops raising `SystemExit(1)` the scenario for help into a closed pipe fails and says so. The guard is the version bound ([30 B2](30-ci-and-release.md#b2-build-fixes)), the contract tests and the unit tests above, and the newest-dependencies job ([30 I3](30-ci-and-release.md#i3-newest-dependencies-job)), which runs them against each new Typer.

## F11 Error messages

Roadmap: "Error messages (raised list): list the locations searched when a spec is not found; 'did you mean v1.8.0' for a version typed without the `v`; say when GitHub rate-limited the request and how to give a token; add the next command to 'no pinned version' errors; drop 'Successfully installed' after 'already installed' and mention `--force`; show the classpath when `javac` fails."

Each is designed where its error is raised; this table is the checklist.

| Point | Where |
| --- | --- |
| Locations searched for a spec | `SpecNotFound.details` ([11 R5](11-runner.md#r5-spec-names)); likewise for a cfg (R4). |
| A version typed without `v` | No longer an error: `1.8.0` finds `v1.8.0` ([02 X3](02-cross-cutting.md#x3-version-syntax)). For a name that matches nothing, `VersionNotFound` suggests the closest tag. |
| Rate limit and token | `RateLimited` ([12 V7](12-tools-and-downloads.md#v7-github-client)). |
| Next command for "no pinned version" | `NoPinnedBuild`, `NoToolsInstalled`, `PinnedBuildMissing` hints ([11 R11](11-runner.md#r11-preflight)). |
| "Already installed" | F6. |
| Classpath when `javac` fails | `ModuleBuildError.details` ([13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder)). |

**Tests.** One scenario each in `errors.feature`, asserting the fact that matters (a path from the searched list appears; the hint names `tlaup tool pin`; the word `GITHUB_TOKEN` appears), not the sentence.

**Changelog.** Changed: "Error messages name what was searched and the command to run next."
