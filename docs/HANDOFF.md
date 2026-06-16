# Handoff: Convert FilterBlade PoE2 filter to load in the China (Tencent / 国服) client

> Purpose of this doc: hand the full investigation to a local Claude Code session
> that can read the actual game data files and the two filter files. It records
> what is **confirmed**, what is **ruled out** (do not re-investigate these), the
> **root cause**, the **solution**, and the **exact next step**. Read it top to
> bottom before doing anything.

---

## 1. Objective

Take a NeverSink / FilterBlade item filter exported for the **international**
Path of Exile 2 client and make it **load without error in the Chinese (Tencent
/ WeGame / 国服) client**, while preserving as much of its behaviour as possible.

---

## 2. TL;DR / current status

- **Root cause is confirmed:** the 国服 client validates **every `BaseType`
  string** against its own item database and aborts the *entire* filter on the
  first base type it doesn't recognise. The FilterBlade file names items the
  国服 build doesn't have (first one hit: **"Refined Necrotic Catalyst"**).
- **It is NOT a filter-syntax / directive problem.** Every directive is
  supported (proven — see §5).
- **It is NOT a language or rename problem.** Match strings are English in both
  clients; the missing items are genuinely absent from the 国服 build, not
  renamed (see §6).
- **The fix:** remove (only) the base-type names the 国服 client lacks. To do this
  losslessly we need the authoritative list of base types in the 国服 build.
- **The remaining task (why we moved local):** datamine the 国服 client's
  `BaseItemTypes` data table to get that authoritative list, then run the
  removal tool (§8–9). This is the step that needs local file access.

---

## 3. Input files

Two filter files (plain text, CRLF line endings):

| Local name (suggested) | Original name | What it is |
| --- | --- | --- |
| `FilterBlade.filter` | `FilterBlade.filter` | International NeverSink/FilterBlade export. ASCII. ~5067 lines. Header version string `0.10.2c.2026.166.1`. This is the file we want to convert. |
| `poe2ggg.filter` | `file-1780089258145-570416889.filter` | A **known-good 国服 filter that loads successfully**. UTF-8 (no BOM). ~5902 lines. Chinese text only in comments; all match values English. Likely from the 国服 community (author "A大"); semi-templated. Use it as a **reference of base types confirmed valid in 国服**. |

Key structural facts about both:
- Both match `BaseType` / `Class` on **English** strings; Chinese appears only
  after `#` (comments). Verified: 0 Chinese characters in any matched value.
- `BaseType`/`Class` vocabularies overlap ~94% exactly.
- Encoding to emit for the 国服 client: **UTF-8, no BOM, CRLF** (matches poe2ggg).

---

## 4. Confirmed facts (from in-client testing on 国服 0.5.2)

1. Loading `poe2ggg.filter` → **"物品筛选器读取成功"** (success).
2. Loading `FilterBlade.filter` → **fails** with:
   `读取物品过滤失败。原因：行 3477:规则 BASETYPE 无法解析的参数:未找到精确匹配 "Refined Necrotic Catalyst" 的 基础类型`
   = "Failed to load filter. Line 3477: rule BaseType — invalid parameter: no
   exact-match base type found for 'Refined Necrotic Catalyst'."
3. Line 3477 of `FilterBlade.filter` is:
   `	BaseType == "Reaver Catalyst" "Refined Necrotic Catalyst" "Sibilant Catalyst"`
   — "Reaver Catalyst" and "Sibilant Catalyst" **are** in poe2ggg (valid in 国服);
   "Refined Necrotic Catalyst" is **not**. So it's a per-item gap on the line.
4. The client validates **substring** `BaseType` too, not just exact `==`. A
   one-line test `BaseType "Refined Necrotic Catalyst"` (no `==`) failed with
   `未找到匹配...` ("no match", the non-exact wording) — so dropping `==` does
   **not** help.
5. The error is reported **one at a time**; the client stops at the first bad
   base type. Fixing line 3477 will reveal the next offending item, etc.
6. The 国服 client self-reports version **0.5.2** (per the user).
7. The 国服 client is the Tencent/WeGame build, separate from international;
   launched alongside international at 0.3.0 (2025-09-11) and tracks it closely.

---

## 5. Why directives are NOT the problem (ruled out — do not revisit)

The filter errors at **line 3477**, which means the client parsed lines 1–3476
cleanly. Those lines already contain the directives we'd previously suspected,
so they are all **supported**:

| Directive | First active line (before 3477 ⇒ accepted) |
| --- | --- |
| `PlayEffect <Color> Temp` | 142 |
| `AreaLevel` | 155 |
| `PlayAlertSound` | 212 |
| `Continue` | 594 |
| `Width` / `Height` | 621 / 622 |
| `AlwaysShow` | 1817 |
| `DisableDropSound` | 1846 |
| `GemLevel` | 2507 |

Cross-checked against GGG's official filter spec
(https://www.pathofexile.com/item-filter/about): all are real current directives,
several tagged "PoE2-only". An earlier "strip unsupported directives" approach
was a **dead end** — discard it. Do not strip or modify any directive.

Also note: GGG provides "ignore-if-missing" variants only for `Import` and
`CustomAlertSound` (`...Optional`). There is **no** tolerant/optional variant
for `BaseType`, and no ID-based matching syntax — matching is purely by name
string. So an unknown base type **must** be removed; there is no syntax trick.

---

## 6. Why it's NOT language / rename (ruled out)

- Both clients match on **English** base-type strings (Chinese only in comments).
- The catalyst family is **identical character-for-character** between the two
  files except 国服 is missing exactly "Necrotic Catalyst" and "Refined Necrotic
  Catalyst". poe2ggg contains **no** extra/renamed catalyst that could be a
  renamed Necrotic. Pattern ⇒ genuine **content gap**, not a rename.
- poe2db.tw `/cn/` is only a **Simplified-Chinese localization of the
  international dataset** (its language switcher is just languages; economy is
  "US Realm"; no Tencent realm). It cannot tell us the 国服 item set. Don't rely
  on it for the whitelist.

---

## 7. Solution approach

1. Obtain the **authoritative set of base types present in the 国服 build**
   (English names, or internal `Id`s mapped to English names).
2. For every `BaseType` line in `FilterBlade.filter`, remove only the quoted
   names that are NOT in that set. Keep the valid names on the same line (e.g.
   line 3477 → `BaseType == "Reaver Catalyst" "Sibilant Catalyst"`).
3. If a `BaseType` line loses all its names, drop that line; if the rule then has
   no conditions at all, drop the rule (but keep intentionally condition-less
   catch-alls like NeverSink's final "unknown item" rule).
4. Leave everything else untouched (all directives are fine).
5. Emit UTF-8, no BOM, CRLF.

This is **lossless** given an accurate 国服 whitelist: items removed are ones the
国服 client genuinely lacks, so they could never have matched anyway.

`Class` is fine: only 5 FilterBlade classes aren't in poe2ggg
(`Skill Gems`, `Support Gems`, `Fishing Rods`, `Expedition Logbook`,
`Instance Local Items`) and all are standard classes that parse fine (they occur
before line 3477). Don't touch `Class` unless a class error actually appears.

---

## 8. THE LOCAL TASK: get the 国服 `BaseItemTypes` list

How international DB sites (poe2db etc.) get item data: they datamine the game's
content files. PoE2 stores data in a bundle/`Content.ggpk` system; the item list
is the **`BaseItemTypes.datc64`** table (columns include `Id` = metadata path,
and `Name` = localized display name). The **Tencent client uses the same engine**,
so its install contains the same table populated with the 国服 item set.

### Recommended steps for local Claude Code

1. **Locate the 国服 client content files.** It installs via WeGame; find the
   PoE2 install dir (look for `Content.ggpk` and/or a `Bundles2/` folder with
   `_.index.bin`). Ask the user for the path if not obvious.
2. **Extract & parse `BaseItemTypes`.** Candidate tools (same ones the intl
   sites use; should work on Tencent files since it's the same engine — verify):
   - `ggpk-tool` (juddisjudd, PoE2-specific): `bundle-category data` then
     `parse-dat -f BaseItemTypes.datc64` → JSON. Has `--all-languages`.
   - `LibGGPK3` / `VisualGGPK3` (aianlinb): GUI to browse/extract bundles.
   - `poe-dat-export` (moepmoep12): TS lib; can also pull intl bundles from CDN.
   - Schema for column layouts: `dat-schema` (poe-tool-dev) on GitHub.
3. **Mind the language subtlety.** Filters match the **English** base-type name,
   but the 国服 client's `Name` column may be **Chinese**. The `Id` (metadata
   path, e.g. `Metadata/Items/.../CurrencyJewelleryQualityAttack`) is
   **language-independent and identical across all clients**. Robust recipe:
   - Get the set of `Id`s present in 国服's `BaseItemTypes`.
   - Get the `Id → English Name` mapping from the **international** data (easy:
     `poe-dat-export` OnlineBundleLoader, or extract intl `BaseItemTypes` in
     English, or scrape poe2db).
   - 国服-valid English names = English names of the `Id`s present in 国服.
   - (If the 国服 client already ships an English `BaseItemTypes` table, you can
     read English names directly and skip the mapping.)
4. **Produce a clean newline-separated list of 国服-valid English base-type names.**
   Save as e.g. `cn_basetypes.txt`.

### Alternative (no extraction): community 国服 data
- 踩蘑菇 (caimogu.cc) "A大" PoE2 国服 patch/tool/filter index thread.
- 柒书 (liuqi.cool) trade plugin maintains separate 国服 item data.
- These may or may not expose a clean base-type list; verify before relying.

---

## 9. Tools already built (bring these local)

Two artifacts were produced and should be copied into the local working dir:

### `make_probe_and_fix.py` (Python 3.8+, no deps)
- `--probe --reference poe2ggg.filter -o probe.filter`
  Emits a probe filter containing every FilterBlade base type NOT in the
  reference (poe2ggg) — 251 of them — each as its own `Show / BaseType == "X"`
  rule. Loading it in 国服 surfaces the next genuinely-missing item per reload
  (valid bases never error), so reloads ≈ number of missing items. This is the
  fallback if datamining doesn't pan out.
- `--apply LIST -o out.filter`
  Given a list (file or inline, comma/newline separated) of base-type names to
  remove, surgically strips just those names from every `BaseType` line, drops a
  `BaseType` line that becomes empty, and drops a rule only if removing the
  BaseType left it with no conditions (preserves intentionally condition-less
  catch-alls). Verified correct on "Refined Necrotic Catalyst".

**Intended final command** once we have the 国服 whitelist:
- Compute `to_remove = {FilterBlade base types} − {国服-valid base types}`.
  (Note: use the FULL 国服 list from §8, NOT poe2ggg's 1154 — poe2ggg is a
  partial subset and would over-remove ~250 valid gear bases like "Closed Helm",
  "Champion Helm", "Cavalry Bow", etc.)
- `python3 make_probe_and_fix.py FilterBlade.filter --apply to_remove.txt -o FilterBlade_cn.filter`
- The local agent may instead extend the script to take the whitelist directly
  and compute the diff internally — cleaner.

### `probe_basetypes.filter`
- Pre-generated probe of the 251 poe2ggg-diff suspects (fallback discovery tool).

---

## 10. Validation

- Load the output in the 国服 client. Success = **"物品筛选器读取成功"**.
- If it still errors, the message names the offending base type; add it to the
  removal list and re-run. (With an accurate datamined whitelist there should be
  zero iterations.)
- Re-run after any 国服 patch; the valid set changes over time.

---

## 11. Key bounded numbers (sanity checks)

- FilterBlade distinct `BaseType` values: **1353**.
- poe2ggg distinct `BaseType` values: **1154** (a partial, proven-valid subset).
- FilterBlade bases not in poe2ggg (suspect set, upper bound on removals): **251**
  — but MOST of these are ordinary gear that 国服 almost certainly has; the true
  missing set is a small subset (e.g. the Necrotic catalysts). This is exactly
  why we want the real 国服 `BaseItemTypes` list instead of the poe2ggg subset.

---

## 12. Concrete next steps for the local session

1. Confirm the 国服 install path and whether `ggpk-tool` / `LibGGPK3` can open its
   bundles (it's the same engine; verify Tencent didn't change packing).
2. Extract `BaseItemTypes`; build `cn_basetypes.txt` (English names) via the
   `Id`-mapping recipe in §8.
3. Diff against FilterBlade's base types → `to_remove.txt`.
4. Run `make_probe_and_fix.py --apply` → `FilterBlade_cn.filter`.
5. Load in 国服; expect success. Keep the script + whitelist for future re-runs.

If extraction is blocked, fall back to `probe_basetypes.filter` (§9) to discover
the missing items by reload, then `--apply`.
