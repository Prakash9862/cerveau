import typer
from cerveau.sys.health import system_report
from rich import print

sys_app = typer.Typer(no_args_is_help=True)

@sys_app.command("report")
def report():
    print(system_report())

