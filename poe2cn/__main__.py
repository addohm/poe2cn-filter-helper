"""Command line entry point.

  python3 -m poe2cn convert         convert every input filter -> output (+ copy to game)
  python3 -m poe2cn serve           start the local web UI (http://localhost:8753)
  python3 -m poe2cn datamine        re-extract the 国服 item DB after a game patch (maintainer)
"""
from __future__ import annotations
import argparse
import sys

from . import core, config as cfgmod, convert as convmod


def _print_report(src, rep, ok, classMiss, copied):
    removed_n = sum(rep["removed"].values())
    tag = "VALID" if ok else "INVALID!"
    suffix = ""
    if copied and not str(copied).startswith("copy failed"):
        suffix = "  → copied to game"
    elif copied:
        suffix = f"  ({copied})"
    print(f"\n{src['display']}  →  {src['out_name']}   [{tag}]{suffix}")
    print(f"  changed {rep['lines_changed']} line(s); removed {removed_n}; "
          f"remapped {len(rep['remapped'])}; case-fixed {len(rep['normalized'])}; "
          f"dropped {rep['dropped_blocks']} rule(s)")
    if removed_n:
        print("  removed: " + repr(rep["removed"]))
    if rep["remapped"]:
        print("  remapped (cross-over): " + repr(rep["remapped"]))
    if rep["normalized"]:
        print("  case-fixed: " + repr(list(rep["normalized"].keys())))
    if classMiss:
        print("  Class WARNING (not in 国服): " + repr(classMiss))


def cmd_convert(args):
    cfg = cfgmod.load()
    U = core.load_universe()
    if U is None:
        print("ERROR: no item database in data/. Run 'datamine' first (or pull the repo's data/).")
        return 1
    class_rows = core.load_class_rows()
    print("poe2cn-filter-helper · convert")
    print("=" * 50)
    print(f"Item DB: {len(U.cn_names)} names" + ("  (cross-over ON)" if U.intl_by_name_lc else "  (no intl; cross-over off)"))
    sources, results = convmod.convert_sources(cfg, U, class_rows, copy_to_game=not args.no_copy)
    bad = [s for s in sources if s["kind"] == "ziperr"]
    for b in bad:
        print(f"  SKIP {b['display']}")
    print(f"Input: {cfg['inputFolder']}")
    print(f"Converting {len(results)} source(s)" + (f"  ({len(bad)} unreadable zip skipped)" if bad else ""))
    print("-" * 50)
    all_ok = True
    for r in results:
        all_ok = all_ok and r["ok"]
        _print_report(r["src"], r["report"], r["ok"], r["classMiss"], r["copied"])
        if not r["ok"]:
            print("  VALIDATION MISS — exact:" + repr(r["validate"]["exact"]) +
                  " substring:" + repr(r["validate"]["substring"]))
    print("\n" + "=" * 50)
    print("Done. All outputs valid — should load with 物品筛选器读取成功." if all_ok
          else "Done, but some outputs still invalid (see above).")
    return 0 if all_ok else 3


def cmd_serve(args):
    from . import serve
    return serve.run(port=args.port)


def cmd_datamine(args):
    from . import datamine
    return datamine.run(force_schema=args.force_schema, include_intl=not args.no_intl)


def main(argv=None):
    p = argparse.ArgumentParser(prog="poe2cn", description="FilterBlade → 国服 filter converter")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("convert", help="convert input filters → output (+ copy to game)")
    pc.add_argument("--no-copy", action="store_true", help="do not copy outputs to the game folder")
    pc.set_defaults(func=cmd_convert)

    ps = sub.add_parser("serve", help="start the local web UI")
    ps.add_argument("--port", type=int, default=8753)
    ps.set_defaults(func=cmd_serve)

    pd = sub.add_parser("datamine", help="re-extract the 国服 item DB after a patch (maintainer)")
    pd.add_argument("--no-intl", action="store_true", help="skip international install (disables cross-over)")
    pd.add_argument("--force-schema", action="store_true", help="re-download the dat-schema")
    pd.set_defaults(func=cmd_datamine)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
