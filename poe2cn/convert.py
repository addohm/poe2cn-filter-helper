"""Drive conversion of input sources -> output files (used by the CLI and the web UI)."""
from __future__ import annotations
import shutil
from pathlib import Path

from . import core


def convert_sources(cfg: dict, U: core.Universe, class_rows: list[dict],
                    keys=None, copy_to_game: bool = True) -> tuple[list[dict], list[dict]]:
    input_folder = Path(cfg["inputFolder"])
    output_folder = Path(cfg["outputFolder"])
    game_folder = Path(cfg["gameFolder"])
    suffix = cfg.get("outputSuffix", "_cn")

    sources = core.enumerate_sources(input_folder, suffix)
    items = [s for s in sources if s["kind"] != "ziperr"]
    if keys is not None:
        wanted = set(keys)
        items = [s for s in items if s["key"] in wanted]

    results = []
    for src in items:
        raw = core.read_source_bytes(input_folder, src)
        text, rep = core.convert_filter(raw, U)
        out_dir = output_folder / (src["out_subdir"] or "")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / src["out_name"]
        out_path.write_bytes(text.encode("utf-8"))  # UTF-8, no BOM, CRLF preserved from source
        out_bytes = out_path.read_bytes()
        v = core.validate_filter(out_bytes, U)
        cm = core.validate_classes(out_bytes, class_rows)
        ok = not v["exact"] and not v["substring"]
        copied = None
        if copy_to_game:
            try:
                game_folder.mkdir(parents=True, exist_ok=True)
                dst = game_folder / src["game_name"]
                shutil.copyfile(out_path, dst)
                copied = str(dst)
            except Exception as e:
                copied = "copy failed: " + str(e)
        results.append({"src": src, "report": rep, "validate": v,
                        "classMiss": cm, "ok": ok, "copied": copied, "outPath": str(out_path)})
    return sources, results
