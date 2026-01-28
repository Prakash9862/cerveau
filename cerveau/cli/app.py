# cerveau/cerveau/cli/app.py

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

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
# - no_args_is_help=False + callback invoke_without_command=True => dashboard par défaut
app = typer.Typer(no_args_is_help=False)
app.add_typer(gh_app, name="gh")
app.add_typer(sys_app, name="sys")


# -----------------------------
# Helpers (shell / os)
# -----------------------------
def _sh(cmd: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", cmd],
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )


def _run(cmd: str, cwd: Path | None = None) -> None:
    subprocess.run(
        ["bash", "-lc", cmd],
        cwd=str(cwd) if cwd else None,
        check=False,
    )


def _xopen(path: Path) -> None:
    subprocess.run(["xdg-open", str(path)], check=False)


def _exists_icon(ok: bool) -> str:
    return "✅" if ok else "❌"


def _bool_icon(ok: bool) -> str:
    return "✔" if ok else "·"


def _short_path(p: Path, max_len: int = 36) -> str:
    s = str(p)
    if len(s) <= max_len:
        return s
    return "…" + s[-(max_len - 1) :]


def _safe_read_text(p: Path, max_bytes: int = 50_000) -> str:
    try:
        data = p.read_bytes()
        if len(data) > max_bytes:
            data = data[:max_bytes]
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _git_is_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _git_branch(path: Path) -> str:
    if not _git_is_repo(path):
        return "-"
    out = _sh("git rev-parse --abbrev-ref HEAD 2>/dev/null || echo -", cwd=path).stdout.strip()
    return out or "-"


def _git_last_commit_relative(path: Path) -> str:
    """
    Ex: '2 days ago', '3 hours ago', '-' if not a repo or no commits.
    """
    if not _git_is_repo(path):
        return "-"
    out = _sh("git log -1 --pretty=%cr 2>/dev/null || echo -", cwd=path).stdout.strip()
    return out or "-"


def _detect_python_project(path: Path) -> bool:
    # Python project signals
    return any(
        (path / f).exists()
        for f in (
            "pyproject.toml",
            "requirements.txt",
            "setup.py",
            "Pipfile",
        )
    )


def _detect_node_project(path: Path) -> bool:
    return (path / "package.json").exists()


def _detect_obsidian(path: Path) -> bool:
    # Obsidian vault signal
    return (path / ".obsidian").exists()


def _is_dir_candidate(p: Path) -> bool:
    # Ignore obvious noise
    if not p.is_dir():
        return False
    name = p.name
    if name.startswith(".") and name not in (".obsidian",):
        return False
    if name in ("node_modules", "__pycache__", ".venv", "dist", "build", ".cache"):
        return False
    return True


# -----------------------------
# Workspace scan (truth layer)
# -----------------------------
@dataclass(frozen=True)
class WorkspaceItem:
    name: str
    path: Path
    is_git: bool
    is_python: bool
    is_node: bool
    is_obsidian: bool
    branch: str
    last_commit: str


def scan_workspace(root: Path) -> list[WorkspaceItem]:
    """
    Scan only the direct children of `root` (one level).
    This keeps it fast, predictable, and avoids crawling the whole disk.
    """
    if not root.exists():
        return []

    items: list[WorkspaceItem] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not _is_dir_candidate(child):
            continue

        is_git = _git_is_repo(child)
        is_python = _detect_python_project(child)
        is_node = _detect_node_project(child)
        is_obsidian = _detect_obsidian(child)

        branch = _git_branch(child) if is_git else "-"
        last_commit = _git_last_commit_relative(child) if is_git else "-"

        items.append(
            WorkspaceItem(
                name=child.name,
                path=child,
                is_git=is_git,
                is_python=is_python,
                is_node=is_node,
                is_obsidian=is_obsidian,
                branch=branch,
                last_commit=last_commit,
            )
        )
    return items


# -----------------------------
# Vince Dashboard (Rich Layout)
# -----------------------------
def _vince_tui() -> None:
    home = Path.home()
    workspace_root = home / "Prakash"  # ✅ source de vérité (scan)

    # Cache scan per loop (cheap anyway, but keep it tidy)
    selected_index = 0

    ActionFn = Callable[[], None]

    def _render(items: list[WorkspaceItem]) -> None:
        nonlocal selected_index

        # System metrics
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(home))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        host = platform.node()
        venv = os.environ.get("VIRTUAL_ENV")
        venv_name = Path(venv).name if venv else "-"

        # Clamp selection
        if items:
            selected_index = max(0, min(selected_index, len(items) - 1))
        else:
            selected_index = 0

        # Summary
        count_dirs = len(items)
        count_git = sum(1 for it in items if it.is_git)
        count_py = sum(1 for it in items if it.is_python)
        count_node = sum(1 for it in items if it.is_node)
        count_obs = sum(1 for it in items if it.is_obsidian)

        # Selected item
        selected = items[selected_index] if items else None

        # --- LEFT: Actions (brain-friendly, but still practical)
        # We keep actions minimal & generic; they operate on the selected item.
        actions: dict[str, tuple[str, ActionFn]] = {
            "j": ("↓ Select next", lambda: _select_delta(+1, items)),
            "k": ("↑ Select prev", lambda: _select_delta(-1, items)),
            "o": ("📁 Open folder", lambda: _open_selected(selected)),
            "g": ("🌿 Git status (quick)", lambda: _git_status(selected)),
            "n": ("▶ npm dev (if Node)", lambda: _npm_dev(selected)),
            "p": ("🐍 python setup (if Python)", lambda: _python_setup(selected)),
            "r": ("🔄 Refresh", lambda: None),
            "q": ("✖ Quit", lambda: None),
        }

        t_actions = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
        t_actions.add_column("Key", style="bold", width=4)
        t_actions.add_column("Action")
        for k, (label, _) in actions.items():
            t_actions.add_row(k, label)

        left = Panel(
            t_actions,
            title="🎛️  Actions",
            subtitle="j/k = naviguer • o = ouvrir • q = quitter",
            padding=(1, 2),
        )

        # --- RIGHT TOP: System
        t_sys = Table(show_header=False, box=None, pad_edge=False)
        t_sys.add_column("k", style="bold", width=14)
        t_sys.add_column("v")

        t_sys.add_row("Host", host)
        t_sys.add_row("Time", now)
        t_sys.add_row("Workspace", str(workspace_root))
        t_sys.add_row("CPU", f"{cpu:.0f}%")
        t_sys.add_row("RAM", f"{mem.percent:.0f}%  ({mem.used // (1024**3)}G / {mem.total // (1024**3)}G)")
        t_sys.add_row("Disk(Home)", f"{disk.percent:.0f}%")
        t_sys.add_row("Venv", venv_name)

        right_top = Panel(t_sys, title="🧠  System", padding=(1, 2))

        # --- RIGHT BOTTOM: Workspace (scan)
        t_ws = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
        t_ws.add_column(" ", width=2)
        t_ws.add_column("Name", style="bold")
        t_ws.add_column("Git", justify="center", width=3)
        t_ws.add_column("Py", justify="center", width=3)
        t_ws.add_column("Node", justify="center", width=4)
        t_ws.add_column("Obs", justify="center", width=4)
        t_ws.add_column("Branch", justify="center", width=8)
        t_ws.add_column("Last", justify="center", width=12)
        t_ws.add_column("Path")

        for idx, it in enumerate(items[:30]):  # keep it readable; we can add paging later
            marker = "▶" if idx == selected_index else " "
            t_ws.add_row(
                marker,
                it.name,
                _bool_icon(it.is_git),
                _bool_icon(it.is_python),
                _bool_icon(it.is_node),
                _bool_icon(it.is_obsidian),
                it.branch,
                it.last_commit,
                _short_path(it.path, 40),
            )

        ws_title = f"📦  ÉCOSYSTÈME (scan) — dirs:{count_dirs} git:{count_git} py:{count_py} node:{count_node} obs:{count_obs}"
        ws_sub = "Sélection: j/k • Actions: o/g/n/p • (affiche 30 max)"
        right_bottom = Panel(t_ws, title=ws_title, subtitle=ws_sub, padding=(1, 2))

        # --- Footer: selected details
        if selected:
            footer_text = Text.assemble(
                ("Selected: ", "bold"),
                (selected.name, "bold"),
                ("  |  ", ""),
                ("Path: ", "bold"),
                (str(selected.path), ""),
            )
        else:
            footer_text = Text("No items found in ~/Prakash", style="bold")

        footer = Panel(Align.left(footer_text), padding=(0, 2))

        # --- Header
        header = Panel(
            Align.center(Text("VINCE — CERVEAU DASHBOARD", style="bold")),
            padding=(0, 2),
        )

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

        layout["header"].update(header)
        layout["left"].update(left)
        layout["right_top"].update(right_top)
        layout["right_bottom"].update(right_bottom)
        layout["footer"].update(footer)

        console.clear()
        console.print(layout)

        return actions

    # --- action helpers (need access to selection)
    def _select_delta(delta: int, items: list[WorkspaceItem]) -> None:
        nonlocal selected_index
        if not items:
            return
        selected_index = (selected_index + delta) % len(items)

    def _open_selected(it: WorkspaceItem | None) -> None:
        if not it:
            return
        _xopen(it.path)

    def _git_status(it: WorkspaceItem | None) -> None:
        if not it or not it.is_git:
            return
        # quick status in a terminal pager-like way
        _run("git status --porcelain=v1 && echo '---' && git status", cwd=it.path)
        # after command ends, dashboard will refresh next loop

    def _npm_dev(it: WorkspaceItem | None) -> None:
        if not it or not it.is_node:
            return
        # Prefer package-lock/pnpm-lock? keep simple
        _run("npm install && npm run dev", cwd=it.path)

    def _python_setup(it: WorkspaceItem | None) -> None:
        if not it or not it.is_python:
            return
        # Minimal "professional" bootstrap: venv + pip upgrade + install if requirements exists
        # We do NOT assume poetry. We do not destroy existing venv.
        venv_dir = it.path / ".venv"
        if not venv_dir.exists():
            _run("python -m venv .venv", cwd=it.path)
        cmd = """
        source .venv/bin/activate
        python -m pip install -U pip
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
        if [ -f pyproject.toml ]; then echo "pyproject.toml detected (poetry/pip-tools possible)"; fi
        """
        _run(cmd, cwd=it.path)

    # --- loop
    while True:
        items = scan_workspace(workspace_root)
        actions = _render(items)
        key = Prompt.ask("Action", default="q").strip()

        if key not in actions:
            continue
        if key == "q":
            return

        # Run action
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

