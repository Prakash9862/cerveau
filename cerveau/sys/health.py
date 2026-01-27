import os, platform, shutil, psutil, time
from pathlib import Path
import yaml

def load_config():
    p = Path("~/.config/cerveau/config.yaml").expanduser()
    return yaml.safe_load(p.read_text())

def system_report():
    cfg = load_config()
    min_free = float(cfg["system"]["min_disk_free_gb"])
    warn_load = float(cfg["system"]["warn_load_1m"])

    vm = psutil.virtual_memory()
    du = shutil.disk_usage("/")

    load1, load5, load15 = os.getloadavg()

    out = {
        "os": f"{platform.system()} {platform.release()}",
        "host": platform.node(),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cpu": {
            "cores_logical": psutil.cpu_count(),
            "load": {"1m": load1, "5m": load5, "15m": load15},
            "warn_load_1m": warn_load,
            "status": "WARN" if load1 > warn_load else "OK",
        },
        "ram": {
            "total_gb": round(vm.total/1e9, 2),
            "used_gb": round(vm.used/1e9, 2),
            "percent": vm.percent,
        },
        "disk_root": {
            "total_gb": round(du.total/1e9, 2),
            "free_gb": round(du.free/1e9, 2),
            "min_free_gb": min_free,
            "status": "WARN" if (du.free/1e9) < min_free else "OK",
        },
    }
    return out

