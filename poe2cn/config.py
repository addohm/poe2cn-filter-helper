"""Config load/save. Keys are camelCase to match the web UI's JSON contract.
Windows paths (C:\\...) are normalised to WSL (/mnt/c/...) on load."""
from __future__ import annotations
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO / "config.json"

DEFAULTS = {
    "cnInstall": "/mnt/c/WeGameApps/rail_apps/Path of  Exile 2(2002052)",
    "intlInstall": "/mnt/c/Program Files (x86)/Steam/steamapps/common/Path of Exile 2",
    "inputFolder": str(REPO / "filters" / "input"),
    "outputFolder": str(REPO / "filters" / "output"),
    "gameFolder": "/mnt/c/Users/addohm/Documents/My Games/Path of Exile 2",
    "outputSuffix": "_cn",
}
_PATH_KEYS = ("cnInstall", "intlInstall", "inputFolder", "outputFolder", "gameFolder")


def win_to_wsl(p: str) -> str:
    """C:\\Users\\x or C:/Users/x  ->  /mnt/c/Users/x.  Leaves WSL/POSIX paths unchanged."""
    if not p:
        return p
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", p)
    if m:
        return f"/mnt/{m.group(1).lower()}/" + m.group(2).replace("\\", "/")
    return p


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text("utf-8")))
        except Exception:
            pass
    for k in _PATH_KEYS:
        if cfg.get(k):
            cfg[k] = win_to_wsl(cfg[k])
    return cfg


def save(cfg: dict) -> dict:
    clean = {k: cfg.get(k, DEFAULTS.get(k)) for k in DEFAULTS}
    for k in _PATH_KEYS:
        if clean.get(k):
            clean[k] = win_to_wsl(clean[k])
    CONFIG_PATH.write_text(json.dumps(clean, indent=2), "utf-8")
    return clean
