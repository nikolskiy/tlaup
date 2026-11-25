"""The `tool` group (design 23 C1, decision D47): each command registered here, by name."""

import typer

from tlaup.cmd.tool import current, install, pin, uninstall, upgrade
from tlaup.cmd.tool import dir as dir_cmd
from tlaup.cmd.tool import list as list_cmd
from tlaup.cmd.tool import path as path_cmd

app = typer.Typer(name="tool", help="Install, pin and remove TLA+ tools builds (tla2tools.jar).", no_args_is_help=True)

app.command(name="list", help=list_cmd.HELP)(list_cmd.list_command)
app.command(name="install", help=install.HELP)(install.install_command)
app.command(name="upgrade", help=upgrade.HELP)(upgrade.upgrade_command)
app.command(name="uninstall", help=uninstall.HELP)(uninstall.uninstall_command)
app.command(name="pin", help=pin.HELP)(pin.pin_command)
app.command(name="current", help=current.HELP)(current.current_command)
app.command(name="path", help=path_cmd.HELP)(path_cmd.path_command)
app.command(name="dir", help=dir_cmd.HELP)(dir_cmd.dir_command)
