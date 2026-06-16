"""Maintainer step: re-extract the 国服 item DB after a game patch.

The Oodle decompression is done by maintainer/datamine.mjs (Node + the bundled
pathofexile-dat library). This wrapper locates Node and translates paths across the
WSL↔Windows boundary, then streams the extractor's output. Only needed after a patch;
end users just use the data/*.json shipped in the repo.
"""
from __future__ import annotations
import re
import shutil
import subprocess
from pathlib import Path

from . import config as cfgmod

REPO = cfgmod.REPO
WIN_NODE = REPO / "maintainer" / "node" / "node.exe"     # bundled Windows portable node
SCRIPT = REPO / "maintainer" / "datamine.mjs"
DATA = REPO / "data"


def wsl_to_win(p: str) -> str:
    """/mnt/c/Users/x -> C:\\Users\\x.  Leaves Windows/other paths unchanged."""
    m = re.match(r"^/mnt/([a-z])/(.*)$", p or "")
    if m:
        return f"{m.group(1).upper()}:\\" + m.group(2).replace("/", "\\")
    return p


def run(force_schema: bool = False, include_intl: bool = True, log=print) -> int:
    cfg = cfgmod.load()
    linux_node = shutil.which("node")

    if linux_node:
        node, conv = linux_node, (lambda p: p)            # native Linux node: keep WSL paths
    elif WIN_NODE.exists():
        node, conv = str(WIN_NODE), wsl_to_win            # Windows portable node from WSL: translate
        log("Using bundled Windows Node via WSL interop.")
    else:
        log("ERROR: no Node found. Install Node in WSL, or keep maintainer/node/node.exe.")
        log("Datamining needs Node for Oodle decompression. (End users don't need this — the")
        log("converter uses the data/*.json already in the repo.)")
        return 1

    args = [node, conv(str(SCRIPT)), "--data", conv(str(DATA)), "--cn", conv(cfg["cnInstall"])]
    if include_intl:
        args += ["--intl", conv(cfg["intlInstall"])]
    if force_schema:
        args += ["--force-schema"]

    log(f"datamine: {cfg['cnInstall']}")
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except Exception as e:
        log(f"ERROR launching Node: {e}")
        return 1
    for line in proc.stdout:
        log(line.rstrip("\n"))
    return proc.wait()


if __name__ == "__main__":
    import sys
    sys.exit(run())
