// Maintainer-only: datamine the 国服 (and intl) item tables -> ../data/*.json
// Needs the Oodle decompressor, provided by the bundled pathofexile-dat library.
// Invoked by `python3 -m poe2cn datamine` (which passes native paths), or directly:
//   node datamine.mjs --data <dir> --cn <gameDir> [--intl <gameDir>] [--force-schema]
import * as fs from 'fs/promises';
import { existsSync } from 'fs';
import * as path from 'path';

const PKG = './node_modules/pathofexile-dat/dist/';
const { decompressSliceInBundle, decompressedBundleSize } = await import(PKG + 'bundles/bundle.js');
const { readIndexBundle, getFileInfo } = await import(PKG + 'bundles/index-bundle.js');
const { getHeaderLength } = await import(PKG + 'dat/header.js');
const { readDatFile } = await import(PKG + 'dat/dat-file.js');
const { readColumn } = await import(PKG + 'dat/reader.js');
const { ValidFor } = await import('pathofexile-dat-schema');

// ---- argv ----
const A = process.argv.slice(2);
const opt = (name) => { const i = A.indexOf(name); return i >= 0 ? A[i + 1] : null; };
const DATA = opt('--data');
const CN = opt('--cn');
const INTL = opt('--intl');
const FORCE_SCHEMA = A.includes('--force-schema');
if (!DATA || !CN) { console.error('usage: datamine.mjs --data <dir> --cn <gameDir> [--intl <gameDir>] [--force-schema]'); process.exit(64); }

const SCHEMA_URL = 'https://github.com/poe-tool-dev/dat-schema/releases/download/latest/schema.min.json';
const SCHEMA_CACHE = path.join(DATA, 'schema.cache.json');

async function getSchema() {
  if (!FORCE_SCHEMA && existsSync(SCHEMA_CACHE)) {
    try { return { schema: JSON.parse(await fs.readFile(SCHEMA_CACHE, 'utf8')), source: 'cache' }; } catch {}
  }
  try { const r = await (await fetch(SCHEMA_URL)).json(); await fs.writeFile(SCHEMA_CACHE, JSON.stringify(r)); return { schema: r, source: 'downloaded' }; }
  catch (e) { const c = JSON.parse(await fs.readFile(SCHEMA_CACHE, 'utf8')); return { schema: c, source: 'cache (download failed)' }; }
}

async function openInstall(gameDir) {
  const indexBin = await fs.readFile(path.join(gameDir, 'Bundles2', '_.index.bin'));
  const indexBundle = new Uint8Array(decompressedBundleSize(indexBin));
  decompressSliceInBundle(indexBin, 0, indexBundle);
  const idx = readIndexBundle(indexBundle);
  const cache = new Map();
  return async (fullPath) => {
    const loc = getFileInfo(fullPath, idx.bundlesInfo, idx.filesInfo);
    if (!loc) return null;
    let bin = cache.get(loc.bundle);
    if (!bin) { bin = await fs.readFile(path.join(gameDir, 'Bundles2', loc.bundle)); cache.set(loc.bundle, bin); }
    const out = new Uint8Array(loc.size); decompressSliceInBundle(bin, loc.offset, out); return out;
  };
}

function importHeaders(schema, name, datFile) {
  const found = schema.tables.filter(s => s.name === name);
  const sch = found.find(s => s.validFor & ValidFor.PoE2) ?? found[0];
  if (!sch) throw new Error(`no schema for ${name}`);
  const headers = []; let offset = 0;
  for (const c of sch.columns) {
    const h = { name: c.name || '', offset, type: {
      array: c.array, interval: c.interval,
      integer: c.type === 'u16' ? { unsigned: true, size: 2 } : c.type === 'u32' ? { unsigned: true, size: 4 }
        : c.type === 'i16' ? { unsigned: false, size: 2 } : c.type === 'i32' ? { unsigned: false, size: 4 }
        : c.type === 'enumrow' ? { unsigned: false, size: 4 } : undefined,
      decimal: c.type === 'f32' ? { size: 4 } : undefined, string: c.type === 'string' ? {} : undefined,
      boolean: c.type === 'bool' ? {} : undefined,
      key: (c.type === 'row' || c.type === 'foreignrow') ? { foreign: c.type === 'foreignrow' } : undefined } };
    headers.push(h); offset += getHeaderLength(h, datFile);
  }
  return headers;
}

async function extract(getFile, schema, table) {
  const bytes = await getFile(`Data/Balance/${table}.datc64`);
  if (!bytes) throw new Error(`table not found: Data/Balance/${table}.datc64`);
  const datFile = readDatFile('.datc64', bytes);
  const headers = importHeaders(schema, table, datFile);
  const want = ['Id', 'Name'].filter(c => headers.some(h => h.name === c));
  const cols = want.map(n => ({ n, data: readColumn(headers.find(h => h.name === n), datFile) }));
  return Array(datFile.rowCount).fill(0).map((_, i) => Object.fromEntries(cols.map(c => [c.n, c.data[i]])));
}

const { schema, source } = await getSchema();
console.log(`Schema: ${source} (v${schema.version})`);
if (!existsSync(path.join(CN, 'Bundles2', '_.index.bin'))) { console.error(`ERROR: 国服 install not found at ${CN}`); process.exit(2); }

const cnGet = await openInstall(CN);
const cnBit = await extract(cnGet, schema, 'BaseItemTypes');
const names = new Set(cnBit.map(r => r.Name).filter(Boolean));
const sentinels = ['Chaos Orb', 'Exalted Orb', 'Scroll of Wisdom'].filter(s => names.has(s));
if (cnBit.length < 3000 || sentinels.length < 3) { console.error(`SANITY FAILED (rows=${cnBit.length}, sentinels=${JSON.stringify(sentinels)}); aborting, kept old DB`); process.exit(3); }
const cnCls = await extract(cnGet, schema, 'ItemClasses');
await fs.writeFile(path.join(DATA, 'cn_baseitemtypes.json'), JSON.stringify(cnBit));
await fs.writeFile(path.join(DATA, 'cn_itemclasses.json'), JSON.stringify(cnCls));
console.log(`国服 BaseItemTypes: ${cnBit.length} rows, ${names.size} names (sanity OK)`);
console.log(`国服 ItemClasses: ${cnCls.length} rows`);

let intlInfo = 'skipped';
if (INTL && existsSync(path.join(INTL, 'Bundles2', '_.index.bin'))) {
  try { const intlBit = await extract(await openInstall(INTL), schema, 'BaseItemTypes');
    await fs.writeFile(path.join(DATA, 'intl_baseitemtypes.json'), JSON.stringify(intlBit));
    intlInfo = `${intlBit.length} rows`; console.log(`International BaseItemTypes: ${intlInfo} (cross-over enabled)`); }
  catch (e) { intlInfo = 'failed: ' + e.message; console.log('International extract failed: ' + e.message); }
} else if (INTL) { intlInfo = 'install not found'; console.log('International install not found; cross-over disabled.'); }

await fs.writeFile(path.join(DATA, 'extract.meta.json'), JSON.stringify({
  when: new Date().toISOString(), schemaVersion: schema.version, cnRows: cnBit.length, cnNames: names.size, intl: intlInfo }, null, 2));
console.log('Datamine complete.');
