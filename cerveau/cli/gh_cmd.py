import typer
from rich import print
from cerveau.gh.client import GitHubClient
from cerveau.gh.views import print_repos

gh_app = typer.Typer(no_args_is_help=True)

@gh_app.command("repos")
def repos(owner: str = typer.Option(None, help="Owner/org (default from config)"),
          limit: int = typer.Option(30, help="Max repos")):
    c = GitHubClient()
    data = c.list_repos(owner=owner, limit=limit)
    print_repos(data)

@gh_app.command("repo")
def repo(full_name: str = typer.Argument(..., help="ex: prakasch/caissa")):
    c = GitHubClient()
    info = c.get_repo(full_name)
    print(info)

