# `app`

A tiny app.

**Usage**:

```console
$ app [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `-V, --version`: Show version.
* `--help`: Show this message and exit.

See the manual for more.

**Commands**:

* `lines`: Print N lines through the Rich console.
* `boom`: Raise RuntimeError.
* `interrupt`: Raise KeyboardInterrupt.
* `abort`: Raise typer.Abort.
* `eof`: Raise EOFError.
* `exit`: Exit through typer.Exit.
* `badparam`: Raise typer.BadParameter.
* `prompt`: typer.prompt on stdin at end of input.
* `spin`: Print lines without end (for SIGINT).
* `wait`: Sleep (for SIGINT).
* `tool`: Tool group.

## `app lines`

Print N lines through the Rich console.

**Usage**:

```console
$ app lines [OPTIONS]
```

**Options**:

* `--n INTEGER`: How many lines.  [env var: APP_N; default: 3]
* `--shell [bash|zsh]`: A shell.  [default: bash]
* `--help`: Show this message and exit.

## `app boom`

Raise RuntimeError.

**Usage**:

```console
$ app boom [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `app interrupt`

Raise KeyboardInterrupt.

**Usage**:

```console
$ app interrupt [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `app abort`

Raise typer.Abort.

**Usage**:

```console
$ app abort [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `app eof`

Raise EOFError.

**Usage**:

```console
$ app eof [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `app exit`

Exit through typer.Exit.

**Usage**:

```console
$ app exit [OPTIONS] [CODE]
```

**Arguments**:

* `[CODE]`: [default: 1]

**Options**:

* `--help`: Show this message and exit.

## `app badparam`

Raise typer.BadParameter.

**Usage**:

```console
$ app badparam [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `app prompt`

typer.prompt on stdin at end of input.

**Usage**:

```console
$ app prompt [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `app spin`

Print lines without end (for SIGINT).

**Usage**:

```console
$ app spin [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `app wait`

Sleep (for SIGINT).

**Usage**:

```console
$ app wait [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `app tool`

Tool group.

**Usage**:

```console
$ app tool [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `pin`: Pin a build.

### `app tool pin`

Pin a build. &#x27;nosuch&#x27; raises a domain error (3).

**Usage**:

```console
$ app tool pin [OPTIONS] BUILD
```

**Arguments**:

* `BUILD`: A build.  [required]

**Options**:

* `--help`: Show this message and exit.
