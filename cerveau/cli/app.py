import typer
from cerveau.cli.gh_cmd import gh_app
from cerveau.cli.sys_cmd import sys_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(gh_app, name="gh")
app.add_typer(sys_app, name="sys")

