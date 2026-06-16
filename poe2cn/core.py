"""Core engine: turn a FilterBlade PoE2 filter into one the China (国服) client accepts.

Pure standard library. Reads the shipped item database (data/*.json) and rewrites only
BaseType value lists — removing genuinely-absent bases, fixing capitalisation, and
cross-over-remapping renamed items by metadata Id. Styling/sounds are never touched.
"""
from __future__ import annotations
import io
import json
import re
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"

CONDITIONS = {
    "BaseType", "Class", "Rarity", "ItemLevel", "Quality", "Sockets", "StackSize", "Corrupted",
    "Identified", "Mirrored", "TwiceCorrupted", "AnyEnchantment", "IsVaalUnique", "HasExplicitMod",
    "UnidentifiedItemTier", "WaystoneTier", "BaseArmour", "BaseEvasion", "BaseEnergyShield",
    "AreaLevel", "DropLevel", "GemLevel", "Width", "Height", "AlwaysShow", "HasVaalUniqueMod",
}

_QUOTED = re.compile(r'"([^"]+)"')
_HEADER_RE = re.compile(r"^\s*(Show|Hide)\b")
_FIRST_TOK = re.compile(r"^\s*([A-Za-z]+)\b")
_BASETYPE = re.compile(r"^(\s*BaseType\s*)(==\s*)?(.*)$")


# --------------------------------------------------------------------------- DB
class Universe:
    """The 国服 matching universe + intl cross-over map, built from extracted tables."""

    def __init__(self, cn_rows: list[dict], intl_rows: list[dict] | None = None):
        names = list(dict.fromkeys(r["Name"] for r in cn_rows if r.get("Name")))
        self.cn_names = names
        self.cn_names_set = set(names)
        self.cn_names_lc = {n.lower() for n in names}
        self.canon_by_lc: dict[str, str] = {}
        for n in names:
            self.canon_by_lc.setdefault(n.lower(), n)
        self.cn_blob_lc = "".join(n.lower() for n in names)
        self.cn_by_id = {r.get("Id"): r.get("Name") for r in cn_rows}
        self.intl_by_name_lc: dict[str, list[str]] | None = None
        if intl_rows:
            m: dict[str, list[str]] = {}
            for r in intl_rows:
                if r.get("Name"):
                    m.setdefault(r["Name"].lower(), []).append(r.get("Id"))
            self.intl_by_name_lc = m

    def sub_ci(self, v: str) -> bool:
        return v.lower() in self.cn_blob_lc

    def _remap(self, v: str):
        if not self.intl_by_name_lc:
            return None
        for cid in self.intl_by_name_lc.get(v.lower(), []):
            cn = self.cn_by_id.get(cid)
            if cn:
                return cn, cid
        return None

    def decide(self, v: str, exact: bool) -> dict:
        """Return {'action': keep|normalize|remap|remove, 'value': str, 'id'?: str}."""
        if exact:
            canon = self.canon_by_lc.get(v.lower())
            if canon is not None:
                return {"action": "keep" if canon == v else "normalize", "value": canon}
            r = self._remap(v)
            if r:
                return {"action": "remap", "value": r[0], "id": r[1]}
            return {"action": "remove", "value": v}
        else:
            if self.sub_ci(v):
                return {"action": "keep", "value": v}
            r = self._remap(v)
            if r:
                return {"action": "remap", "value": r[0], "id": r[1]}
            return {"action": "remove", "value": v}


def load_universe(data_dir: Path = DATA) -> Universe | None:
    cn = data_dir / "cn_baseitemtypes.json"
    if not cn.exists():
        return None
    cn_rows = json.loads(cn.read_text("utf-8"))
    intl_path = data_dir / "intl_baseitemtypes.json"
    intl_rows = json.loads(intl_path.read_text("utf-8")) if intl_path.exists() else None
    return Universe(cn_rows, intl_rows)


def load_class_rows(data_dir: Path = DATA) -> list[dict]:
    p = data_dir / "cn_itemclasses.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else []


# ---------------------------------------------------------------- filter text
def read_filter(raw: bytes) -> tuple[list[str], str]:
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    text = raw.decode("utf-8", errors="replace")
    term = "\r\n" if "\r\n" in text else "\n"
    lines = [l[:-1] if l.endswith("\r") else l for l in text.split("\n")]
    return lines, term


def _first_tok(line: str):
    s = line.lstrip()
    if not s or s.startswith("#"):
        return None
    m = _FIRST_TOK.match(line)
    return m.group(1) if m else None


def _is_header(s: str) -> bool:
    return not s.lstrip().startswith("#") and bool(_HEADER_RE.match(s))


def _segments(lines: list[str]):
    segs, i, n = [], 0, len(lines)
    while i < n:
        if _is_header(lines[i]):
            body = [lines[i]]
            i += 1
            while i < n and lines[i].strip() != "" and not _is_header(lines[i]):
                body.append(lines[i]); i += 1
            segs.append(("rule", body))
        else:
            loose = []
            while i < n and not _is_header(lines[i]):
                loose.append(lines[i]); i += 1
            segs.append(("loose", loose))
    return segs


def convert_filter(raw: bytes, U: Universe) -> tuple[str, dict]:
    lines, term = read_filter(raw)
    rep = {"removed": {}, "normalized": {}, "remapped": {}, "emptied_lines": 0,
           "dropped_blocks": 0, "dropped_labels": [], "lines_changed": 0}
    out: list[str] = []
    for kind, body in _segments(lines):
        if kind == "loose":
            out.extend(body); continue
        header = body[0]
        new_body = [header]
        had_base = emptied_base = False
        for l in body[1:]:
            if _first_tok(l) != "BaseType":
                new_body.append(l); continue
            had_base = True
            hash_idx = l.find("#")
            code = l if hash_idx == -1 else l[:hash_idx]
            comment = "" if hash_idx == -1 else l[hash_idx + 1:]
            m = _BASETYPE.match(code)
            prefix = m.group(1) + (m.group(2) or "")
            exact = bool(m.group(2))
            vals = _QUOTED.findall(m.group(3))
            if not vals:
                new_body.append(l); continue
            kept, changed = [], False
            for v in vals:
                d = U.decide(v, exact)
                act = d["action"]
                if act == "remove":
                    rep["removed"][v] = rep["removed"].get(v, 0) + 1; changed = True
                elif act == "normalize":
                    rep["normalized"][f"{v} => {d['value']}"] = 1; kept.append(d["value"]); changed = True
                elif act == "remap":
                    rep["remapped"][f"{v} => {d['value']}"] = d.get("id", ""); kept.append(d["value"]); changed = True
                else:
                    kept.append(v)
            if not changed:
                new_body.append(l); continue
            rep["lines_changed"] += 1
            if kept:
                nl = prefix + " ".join(f'"{v}"' for v in kept)
                if hash_idx != -1:
                    nl = nl.rstrip() + "  #" + comment
                new_body.append(nl)
            else:
                rep["emptied_lines"] += 1; emptied_base = True
        still_base = any(_first_tok(b) == "BaseType" for b in new_body[1:])
        conds = [b for b in new_body[1:] if _first_tok(b) in CONDITIONS]
        if emptied_base and had_base and not still_base and not conds:
            rep["dropped_blocks"] += 1
            label = header.split("#", 1)[1].strip() if "#" in header else "(no label)"
            rep["dropped_labels"].append(label)
            continue
        out.extend(new_body)
    return term.join(out), rep


def validate_filter(raw: bytes, U: Universe) -> dict:
    lines, _ = read_filter(raw)
    fails = {"exact": [], "substring": []}
    for l in lines:
        cp = l.split("#", 1)[0]
        if not re.match(r"^\s*BaseType\b", cp):
            continue
        m = re.match(r"^\s*BaseType\s*(==)?\s*(.*)$", cp)
        exact = bool(m.group(1))
        for v in _QUOTED.findall(m.group(2)):
            ok = (v.lower() in U.cn_names_lc) if exact else U.sub_ci(v)
            if not ok:
                fails["exact" if exact else "substring"].append(v)
    fails["exact"] = list(dict.fromkeys(fails["exact"]))
    fails["substring"] = list(dict.fromkeys(fails["substring"]))
    return fails


def validate_classes(raw: bytes, class_rows: list[dict]) -> list[str]:
    lines, _ = read_filter(raw)
    names = [r["Name"] for r in class_rows if r.get("Name")]
    set_lc = {n.lower() for n in names}
    blob_lc = "".join(n.lower() for n in names)
    miss = []
    for l in lines:
        cp = l.split("#", 1)[0]
        if not re.match(r"^\s*Class\b", cp):
            continue
        m = re.match(r"^\s*Class\s*(==)?\s*(.*)$", cp)
        exact = bool(m.group(1))
        for v in _QUOTED.findall(m.group(2)):
            ok = (v.lower() in set_lc) if exact else (v.lower() in blob_lc)
            if not ok and v not in miss:
                miss.append(v)
    return miss


# ----------------------------------------------------------- input sources
def _cap_first(s: str) -> str:
    return s[:1].upper() + s[1:]


def clean_zip_variant(zip_filename: str) -> str:
    v = re.sub(r"\.zip$", "", zip_filename, flags=re.I)
    v = re.sub(r"^filterblade[\s_-]+", "", v, flags=re.I)
    return v.strip()


def _variant_to_suffix(variant: str, output_suffix: str) -> str:
    if not variant:
        return output_suffix or "_cn"
    return "_" + "_".join(_cap_first(s) for s in variant.split("/") if s)


def _parse_header(text: str) -> dict:
    def get(k):
        m = re.search(r"^#\s*" + k + r":\s*(.+)$", text, re.M)
        return m.group(1).strip() if m else ""
    return {"version": get("VERSION"), "type": get("TYPE"), "style": get("STYLE"), "author": get("AUTHOR")}


def enumerate_sources(input_folder: Path, output_suffix: str = "_cn") -> list[dict]:
    """Loose files, files in subfolders, and FilterBlade .zip downloads -> source dicts."""
    input_folder = Path(input_folder)
    out: list[dict] = []
    if not input_folder.exists():
        return out
    files, zips = [], []
    for p in sorted(input_folder.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(input_folder).as_posix()
        if rel.lower().endswith(".filter"):
            files.append(rel)
        elif rel.lower().endswith(".zip"):
            zips.append(rel)
    for rel in files:
        variant = rel.rsplit("/", 1)[0] if "/" in rel else ""
        base = re.sub(r"\.filter$", "", rel.rsplit("/", 1)[-1], flags=re.I)
        out_name = base + _variant_to_suffix(variant, output_suffix) + ".filter"
        try:
            header = _parse_header((input_folder / rel).read_bytes()[:4000].decode("utf-8", "replace"))
        except Exception:
            header = {}
        out.append({"key": "file::" + rel, "display": rel, "kind": "file", "rel": rel,
                    "variant": variant, "out_subdir": variant, "out_name": out_name,
                    "game_name": out_name, "source": "folder" if variant else "loose", **header})
    for rel in zips:
        zip_name = rel.rsplit("/", 1)[-1]
        variant = clean_zip_variant(zip_name)
        try:
            zf = zipfile.ZipFile(input_folder / rel)
        except Exception as e:
            out.append({"key": "ziperr::" + rel, "display": f"{rel}  (cannot read: {e})",
                        "kind": "ziperr", "source": "zip"})
            continue
        with zf:
            for info in zf.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".filter"):
                    continue
                name = info.filename.replace("\\", "/")
                base = re.sub(r"\.filter$", "", name.rsplit("/", 1)[-1], flags=re.I)
                out_name = base + _variant_to_suffix(variant, output_suffix) + ".filter"
                try:
                    header = _parse_header(zf.read(info)[:4000].decode("utf-8", "replace"))
                except Exception:
                    header = {}
                out.append({"key": f"zip::{rel}::{name}", "display": f"{zip_name} → {name}",
                            "kind": "zip", "zip_rel": rel, "entry": name, "variant": variant,
                            "out_subdir": variant, "out_name": out_name, "game_name": out_name,
                            "source": "zip", **header})
    out.sort(key=lambda s: s.get("display", ""))
    return out


def read_source_bytes(input_folder: Path, src: dict) -> bytes:
    input_folder = Path(input_folder)
    if src["kind"] == "file":
        return (input_folder / src["rel"]).read_bytes()
    if src["kind"] == "zip":
        with zipfile.ZipFile(input_folder / src["zip_rel"]) as zf:
            return zf.read(src["entry"])
    raise ValueError("source is not readable: " + src.get("display", src.get("kind", "?")))
