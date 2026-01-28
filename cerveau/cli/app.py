# cerveau/cerveau/cli/app.py

from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

import psutil
import typer
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from cerveau.cli.gh_cmd import gh_app
from cerveau.cli.sys_cmd import sys_app

console = Console()

# IMPORTANT:
# - Avant: no_args_is_help=True => affiche l'aide si aucun argument
# - Maintenant: no_args_is_help=False + callback invoke_without_command=True => dashboard par défaut
app = typer.Typer(no_args_is_help=False)

# Sous-commandes existantes
app.add_typer(gh_app, name="gh")
app.add_typer(sys_app, name="sys")


# -----------------------------
# Helpers
# -----------------------------
def _sh(cmd: str, cwd: Path | None = None) -> None:
    subprocess.run(["bash", "-lc", cmd], cwd=str(cwd) if cwd else None, check=False)


def _xopen(path: Path) -> None:
    subprocess.run(["xdg-open", str(path)], check=False)


def _exists_icon(p: Path) -> str:
    return "✅" if p.exists() else "❌"


def _git_branch(path: Path) -> str:
    if not path.exists():
        return "-"
    p = subprocess.run(
        ["bash", "-lc", "git rev-parse --abbrev-ref HEAD 2>/dev/null || echo -"],
        cwd=str(path),
        text=True,
        capture_output=True,
        check=False,
    )
    return (p.stdout or "-").strip()


# -----------------------------
# Vince Dashboard (Rich Layout)
# -----------------------------
def _vince_tui() -> None:
    home = Path.home()
    root = home / "Prakash"
    projects = root / "projets"
    learn = root / "apprentissage"

    caissa = projects / "caissa"
    caissa_web = projects / "caissa-web"
    next_app = learn / "next.js" / "apprentissage"

    ActionFn = Callable[[], None]
    actions: dict[str, tuple[str, ActionFn]] = {
        "1": ("📁 Open Caïssa", lambda: _xopen(caissa)),
        "2": ("📁 Open Caïssa-Web", lambda: _xopen(caissa_web)),
        "3": ("📁 Open Next.js apprentissage", lambda: _xopen(next_app)),
        "4": ("▶ Run Next.js apprentissage (dev)", lambda: _sh("npm run dev", cwd=next_app)),
        "5": ("▶ Run Caïssa-Web (dev)", lambda: _sh("npm run dev", cwd=caissa_web)),
        "6": ("⚙ Open kitty.conf", lambda: _xopen(home / ".config" / "kitty" / "kitty.conf")),
        "q": ("✖ Quit", lambda: None),
    }

    def _render() -> None:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(home))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        host = platform.node()

        venv = os.environ.get("VIRTUAL_ENV")
        venv_name = Path(venv).name if venv else "-"

        # --- Left: Actions
        t_actions = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
        t_actions.add_column("Key", style="bold", width=4)
        t_actions.add_column("Action")
        for k, (label, _) in actions.items():
            t_actions.add_row(k, label)

        left = Panel(
            Layout(Align.left(t_actions)),
            title="🎛️  Actions",
            subtitle="Tape 1–6 (ou q)",
            padding=(1, 2),
        )

        # --- Right top: System
        t_sys = Table(show_header=False, box=None, pad_edge=False)
        t_sys.add_column("k", style="bold", width=12)
        t_sys.add_column("v")

        t_sys.add_row("Host", host)
        t_sys.add_row("Time", now)
        t_sys.add_row("CPU", f"{cpu:.0f}%")
        t_sys.add_row("RAM", f"{mem.percent:.0f}%  ({mem.used // (1024**3)}G / {mem.total // (1024**3)}G)")
        t_sys.add_row("Disk(Home)", f"{disk.percent:.0f}%")
        t_sys.add_row("Venv", venv_name)

        right_top = Panel(t_sys, title="🧠  System", padding=(1, 2))

        # --- Right bottom: Projects
        t_proj = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
        t_proj.add_column("Project", style="bold")
        t_proj.add_column("Path")
        t_proj.add_column("OK", justify="center", width=4)
        t_proj.add_column("Git", justify="center", width=10)

        t_proj.add_row("Caïssa", str(caissa), _exists_icon(caissa), _git_branch(caissa))
        t_proj.add_row("Caïssa-Web", str(caissa_web), _exists_icon(caissa_web), _git_branch(caissa_web))
        t_proj.add_row("Next.js apprentissage", str(next_app), _exists_icon(next_app), _git_branch(next_app))

        right_bottom = Panel(t_proj, title="📦  Projects", padding=(1, 2))

        # --- Layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=2),
        )
        layout["right"].split_column(
            Layout(name="right_top", size=10),
            Layout(name="right_bottom", ratio=1),
        )

        header = Panel(
            Align.center(Text("VINCE — CERVEAU DASHBOARD", style="bold")),
            padding=(0, 2),
        )
        footer = Panel(
            Align.center(Text("q = quit • 1–6 = action • prochaine étape: ports / services / Verkal 🖤", style="")),
            padding=(0, 2),
        )

        layout["header"].update(header)
        layout["left"].update(left)
        layout["right_top"].update(right_top)
        layout["right_bottom"].update(right_bottom)
        layout["footer"].update(footer)

        console.clear()
        console.print(layout)

    # Loop
    while True:
        _render()
        key = Prompt.ask("Action", default="q").strip()
        if key not in actions:
            continue
        if key == "q":
            return
        actions[key][1]()


# -----------------------------
# Typer entrypoints
# -----------------------------
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """
    Cerveau CLI.
    Sans sous-commande: lance le dashboard Vince.
    """
    if ctx.invoked_subcommand is None:
        _vince_tui()


@app.command()
def vince() -> None:
    """Interface TUI Vince (dashboard)."""
    _vince_tui()

