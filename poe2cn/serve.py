"""Local web UI (stdlib http.server). Reuses poe2cn/ui.html; speaks the same JSON
API the front-end expects (camelCase). Start with: python3 -m poe2cn serve"""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import core, config as cfgmod, convert as convmod

HERE = Path(__file__).resolve().parent
DATA = cfgmod.REPO / "data"
UI = HERE / "ui.html"
META = DATA / "extract.meta.json"


def _read_json(p):
    try:
        return json.loads(Path(p).read_text("utf-8"))
    except Exception:
        return None


def _src_for_ui(s: dict) -> dict:
    return {"key": s["key"], "display": s["display"], "kind": s["kind"], "source": s.get("source", ""),
            "variant": s.get("variant", ""), "outName": s.get("out_name", ""),
            "style": s.get("style", ""), "type": s.get("type", ""), "version": s.get("version", "")}


def _res_for_ui(r: dict) -> dict:
    rep = r["report"]
    return {"input": r["src"]["display"], "output": r["src"]["out_name"],
            "linesChanged": rep["lines_changed"], "removed": rep["removed"],
            "normalized": list(rep["normalized"].keys()), "remapped": rep["remapped"],
            "droppedBlocks": rep["dropped_blocks"], "validateExactMiss": r["validate"]["exact"],
            "validateSubMiss": r["validate"]["substring"], "classMiss": r["classMiss"],
            "ok": r["ok"], "copied": r["copied"]}


def _crossover():
    U = core.load_universe()
    if U is None or not U.intl_by_name_lc:
        return {"available": False, "renames": [], "note": "Refresh database (with the international install) first."}
    intl_id_to_name = {}
    for lc, ids in U.intl_by_name_lc.items():
        for cid in ids:
            intl_id_to_name.setdefault(cid, lc)
    renames = []
    for cid, cn in U.cn_by_id.items():
        il = intl_id_to_name.get(cid)
        if il is not None and cn and il != cn.lower():
            renames.append({"id": cid, "intl": il, "cn": cn})
    return {"available": True, "renames": renames}


def _state():
    cfg = cfgmod.load()
    return {"config": cfg, "meta": _read_json(META),
            "hasDb": (DATA / "cn_baseitemtypes.json").exists(),
            "hasIntl": (DATA / "intl_baseitemtypes.json").exists(),
            "filters": [_src_for_ui(s) for s in core.enumerate_sources(Path(cfg["inputFolder"]), cfg.get("outputSuffix", "_cn"))]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj=None, raw=None, ctype="application/json"):
        body = raw if raw is not None else json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        try:
            if self.path == "/":
                return self._send(200, raw=UI.read_bytes(), ctype="text/html; charset=utf-8")
            if self.path == "/api/state":
                return self._send(200, _state())
            if self.path == "/api/crossover":
                return self._send(200, _crossover())
            self._send(404, {"error": "not found"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            if self.path == "/api/config":
                cfg = cfgmod.save({**cfgmod.load(), **self._body()})
                return self._send(200, {"config": cfg,
                                        "filters": [_src_for_ui(s) for s in core.enumerate_sources(Path(cfg["inputFolder"]), cfg.get("outputSuffix", "_cn"))]})
            if self.path == "/api/refresh-db":
                from . import datamine
                b = self._body()
                log = []
                rc = datamine.run(force_schema=bool(b.get("forceSchema")),
                                  include_intl=b.get("includeIntl", True), log=log.append)
                resp = {"log": log}
                if rc != 0:
                    resp["error"] = "\n".join(log) or "datamine failed"
                return self._send(200, resp)
            if self.path == "/api/convert":
                b = self._body()
                cfg = cfgmod.load()
                U = core.load_universe()
                if U is None:
                    return self._send(200, {"error": 'No item database. Click "Refresh 国服 database" first.'})
                _, results = convmod.convert_sources(cfg, U, core.load_class_rows(),
                                                      keys=b.get("files"), copy_to_game=bool(b.get("copyToGame")))
                return self._send(200, {"results": [_res_for_ui(r) for r in results]})
            self._send(404, {"error": "not found"})
        except Exception as e:
            self._send(500, {"error": str(e)})


def run(port: int = 8753) -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"\n  poe2cn-filter-helper UI:  http://localhost:{port}\n  (Ctrl-C to stop)\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0
