from rich.table import Table
from rich.console import Console

def print_repos(repos):
    t = Table(title="GitHub Repos")
    t.add_column("Name", style="bold")
    t.add_column("Private")
    t.add_column("Stars", justify="right")
    t.add_column("Updated")
    t.add_column("Default branch")
    for r in repos:
        t.add_row(
            r.get("full_name",""),
            str(r.get("private", False)),
            str(r.get("stargazers_count", 0)),
            (r.get("updated_at","") or "")[:19],
            r.get("default_branch",""),
        )
    Console().print(t)

