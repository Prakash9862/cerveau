import os, time, json, pathlib, yaml, requests

def load_config():
    p = pathlib.Path("~/.config/cerveau/config.yaml").expanduser()
    return yaml.safe_load(p.read_text())

class Cache:
    def __init__(self, cfg):
        self.dir = pathlib.Path(cfg["cache"]["dir"]).expanduser()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ttl = int(cfg["cache"]["ttl_seconds"])

    def get(self, key: str):
        f = self.dir / (key + ".json")
        if not f.exists():
            return None
        if time.time() - f.stat().st_mtime > self.ttl:
            return None
        return json.loads(f.read_text())

    def set(self, key: str, value):
        f = self.dir / (key + ".json")
        f.write_text(json.dumps(value, indent=2))

class GitHubClient:
    def __init__(self):
        self.cfg = load_config()
        env = self.cfg["github"]["token_env"]
        self.token = os.environ.get(env)
        if not self.token:
            raise RuntimeError(f"Missing {env}. Export your GitHub token.")
        self.base = "https://api.github.com"
        self.cache = Cache(self.cfg)

    def _get(self, path: str, params=None, cache_key=None):
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        r = requests.get(
            self.base + path,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            },
            params=params,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if cache_key:
            self.cache.set(cache_key, data)
        return data

    def list_repos(self, owner=None, limit=30):
        owner = owner or self.cfg["github"]["default_owner"]
        data = self._get(f"/users/{owner}/repos", params={"per_page": min(limit, 100)}, cache_key=f"repos_{owner}_{limit}")
        return data[:limit]

    def get_repo(self, full_name: str):
        return self._get(f"/repos/{full_name}", cache_key=f"repo_{full_name.replace('/','_')}")

