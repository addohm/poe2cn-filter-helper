# poe2cn-filter-helper

Make a [NeverSink / FilterBlade](https://www.filterblade.xyz) Path of Exile 2 loot filter load in
the **China (Tencent / WeGame / 国服) client**, which otherwise rejects the whole filter on the
first base type it doesn't recognise.

It does the minimum needed and nothing else:

- **Removes** only base types the 国服 client genuinely lacks (verified by datamining the client's
  own item database).
- **Case-fixes** names that exist but are spelled with different capitalisation.
- **Cross-over remaps** items that were renamed — matched by their language-independent metadata
  `Id` — so they keep working instead of being dropped.
- **Never touches styling or sounds.** Only `BaseType` value lists change.

Matching mirrors the client exactly: case-insensitive, with `==` lines matched in full and
no-operator lines matched as substrings.

> The conversion ships with the datamined item database (`data/`), so you can convert filters with
> **nothing but Python** — no game files, no Oodle, no Node. Re-datamining (after a 国服 patch) is a
> separate maintainer step.

## Requirements

- **Python 3.9+** (standard library only). Tested on Python 3.14 in WSL (Fedora).
- That's it, for converting. Re-datamining additionally needs Node + the game installed
  (see [maintainer/](maintainer/README.md)).

## Quick start

```bash
# from the repo root
python3 -m poe2cn convert        # convert filters/input/** -> filters/output/** (+ copy to game)
python3 -m poe2cn serve          # web UI at http://localhost:8753
```

On Windows you can instead double-click:

| File | Does |
| --- | --- |
| `Update-FilterBlade-CN.bat` | `python3 -m poe2cn convert` inside WSL |
| `FilterBlade-CN-Tool.bat` | opens the web UI |
| `Datamine-after-patch.bat` | maintainer: re-extract DB, then convert |

## Input layout — drop filters into `filters/input/`

Three shapes are understood, and the output name reflects where the input came from:

| Input | Output suffix | Example |
| --- | --- | --- |
| loose `.filter` | `_cn` (configurable) | `FilterBlade_custom.filter` → `FilterBlade_custom_cn.filter` |
| in a **subfolder** `Dark Mode/` | `_Dark Mode` | → `output/Dark Mode/FilterBlade_0_Soft_Dark Mode.filter` |
| a FilterBlade **`.zip`** download | the zip's name | `FilterBlade Zen.zip` → `output/Zen/FilterBlade_0_Soft_Zen.filter` |

Zips are read in place (no need to unzip). Outputs mirror the variant under `filters/output/`;
copies into the game folder are flat (the game lists filters from one folder), so the suffix is how
you tell `..._Zen` from `..._Dark Mode` in the in-game dropdown.

Then in game: **Options → UI → filter dropdown**, pick the converted one. Success looks like
**物品筛选器读取成功**.

## Configuration

Copy `config.example.json` to `config.json` (git-ignored) and edit. Windows paths (`C:\...`) are
auto-translated to WSL (`/mnt/c/...`). You can also edit everything in the web UI's Settings panel.

| Key | Meaning |
| --- | --- |
| `cnInstall` | 国服 / WeGame PoE2 install (the folder containing `Bundles2`) — datamining source |
| `intlInstall` | International install — optional, only for cross-over rename detection |
| `inputFolder` / `outputFolder` | defaults to `./filters/input` and `./filters/output` |
| `gameFolder` | your PoE2 *My Games* folder; converted filters are copied here |
| `outputSuffix` | suffix for loose files (default `_cn`) |

## After a 国服 patch

The item set changes with patches. Re-datamine to refresh `data/*.json`:

```bash
python3 -m poe2cn datamine        # needs Node + game installed (see maintainer/)
python3 -m poe2cn convert
```

If extraction looks wrong (row count / known items missing) it **aborts and keeps the previous
database** rather than writing a broken whitelist.

## How it works

- `poe2cn/core.py` — the engine: filter parsing, the keep/case-fix/remap/remove decision, zip &
  subfolder source enumeration, validation.
- `poe2cn/convert.py`, `poe2cn/serve.py`, `poe2cn/datamine.py` — CLI driver, web UI, maintainer
  datamining wrapper.
- `data/*.json` — the datamined 国服 + international `BaseItemTypes`/`ItemClasses` (the shipped
  whitelist).
- `maintainer/` — the Node-based datamining backend (uses
  [`pathofexile-dat`](https://github.com/SnosMe/poe-dat-viewer), which bundles an Oodle
  decompressor). Only the maintainer needs this.

See [docs/HANDOFF.md](docs/HANDOFF.md) for the original investigation (why the filter failed and how
the fix was proven).

## License

MIT — see [LICENSE](LICENSE). Not affiliated with Grinding Gear Games, Tencent, or NeverSink.
