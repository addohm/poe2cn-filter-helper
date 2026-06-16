# maintainer/ — datamining backend

This is only needed to **re-extract the 国服 item database after a game patch**. End users of
poe2cn-filter-helper never touch it — they convert against the `data/*.json` committed in the repo.

## What's here

- `datamine.mjs` — extracts `BaseItemTypes` + `ItemClasses` from the 国服 install (and
  `BaseItemTypes` from the international install, for cross-over) and writes `../data/*.json`.
  The Oodle decompression of the game bundles is provided by
  [`pathofexile-dat`](https://github.com/SnosMe/poe-dat-viewer), which bundles a WASM decompressor —
  so no `oo2core.dll` is required.
- `node/` — a portable Node.js (git-ignored). Used so the rest of the tool needs no Node install.
- `node_modules/` — `pathofexile-dat` etc. (git-ignored).

## Setup (one-time, on a fresh clone)

```bash
cd maintainer
npm install          # restores node_modules from package-lock.json
```

A portable Node is expected at `maintainer/node/node.exe` (Windows) — or just have `node` on your
PATH. `python3 -m poe2cn datamine` finds whichever is available and handles the WSL↔Windows path
translation automatically.

## Run

```bash
python3 -m poe2cn datamine                 # uses paths from config.json
# or directly:
node datamine.mjs --data ../data --cn "<国服 install>" --intl "<intl install>" [--force-schema]
```

After datamining, commit the refreshed `data/*.json` so downstream users get the new whitelist.
