"""The `module` group (design 23 C1, decision D47): each command registered here, by name."""

import typer

from tlaup.cmd.module import add, remove
from tlaup.cmd.module import dir as dir_cmd
from tlaup.cmd.module import list as list_cmd

app = typer.Typer(name="module", help="Add, list and remove Java operator-override modules.", no_args_is_help=True)

app.command(name="add", help=add.HELP)(add.add_command)
app.command(name="list", help=list_cmd.HELP)(list_cmd.list_command)
app.command(name="remove", help=remove.HELP)(remove.remove_command)
app.command(name="dir", help=dir_cmd.HELP)(dir_cmd.dir_command)
