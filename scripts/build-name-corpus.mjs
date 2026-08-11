#!/usr/bin/env node
// Builds the name corpus from public SSA baby-name data, in two forms from one
// curation pass: src/lib/nameCorpus.ts for the client bundle, and
// api/src/babynames_api/corpus/names.json for the service's corpus seeder.
// Run manually (npm run corpus:build) — never in CI. Both generated artifacts
// are committed; the downloaded archive is not.
//
// See specs/001-expanded-name-corpus/contracts/name-corpus.md for the contract.

import { createWriteStream } from "node:fs";
import { mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import path from "node:path";

const execFileAsync = promisify(execFile);

const ROOT = path.resolve(import.meta.dirname, "..");
const CACHE = path.join(ROOT, ".corpus-cache");
const SSA_ZIP = "https://www.ssa.gov/oact/babynames/names.zip";
const SSA_REFERER = "https://www.ssa.gov/oact/babynames/limits.html";

// SSA sits behind Akamai, which 403s default HTTP agents — including for plain
// HTML. A full browser header set is required, not just a User-Agent.
const BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  Accept:
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
  "Sec-Fetch-Dest": "document",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "same-origin",
  "Sec-Fetch-User": "?1",
  "Upgrade-Insecure-Requests": "1",
  "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
  "sec-ch-ua-mobile": "?0",
  "sec-ch-ua-platform": '"Windows"',
};

const MIRROR_HISTORICAL =
  "https://raw.githubusercontent.com/hadley/data-baby-names/master/baby-names.csv";
const mirrorRecent = (year, sex) =>
  `https://raw.githubusercontent.com/aruljohn/popular-baby-names/master/${year}/${sex}_names_${year}.json`;

const VALID_NAME = /^[A-Z][A-Za-z'-]{1,14}$/;

function parseArgs(argv) {
  const opts = {
    source: "ssa",
    input: null,
    limit: null,
    since: 1995,
    minUses: 25,
    coreSince: 2005,
    coreMin: 300,
    out: path.join(ROOT, "src/lib/nameCorpus.ts"),
    jsonOut: path.join(ROOT, "api/src/babynames_api/corpus/names.json"),
  };
  for (let i = 0; i < argv.length; i++) {
    const [flag, inlineValue] = argv[i].split("=");
    const value = inlineValue ?? argv[++i];
    switch (flag) {
      case "--source":
        opts.source = value;
        break;
      case "--input":
        opts.input = path.resolve(value);
        break;
      case "--limit":
        opts.limit = Number(value);
        break;
      case "--since":
        opts.since = Number(value);
        break;
      case "--min-uses":
        opts.minUses = Number(value);
        break;
      case "--core-since":
        opts.coreSince = Number(value);
        break;
      case "--core-min":
        opts.coreMin = Number(value);
        break;
      case "--out":
        opts.out = path.resolve(value);
        break;
      case "--json-out":
        opts.jsonOut = path.resolve(value);
        break;
      default:
        fail(`unknown flag: ${flag}`);
    }
  }
  if (!["ssa", "mirror"].includes(opts.source)) {
    fail(`--source must be "ssa" or "mirror", got "${opts.source}"`);
  }
  return opts;
}

function fail(message) {
  console.error(`\n  build-name-corpus: ${message}\n`);
  process.exit(1);
}

async function fetchOrFail(url, { headers = {}, what = url } = {}) {
  const res = await fetch(url, { headers });
  if (res.status === 403 && url.startsWith("https://www.ssa.gov")) {
    fail(
      `SSA returned 403 for ${what}.\n` +
        `  This is Akamai edge filtering, NOT a network-policy denial — the request\n` +
        `  needs the full browser header set (User-Agent, Accept, Accept-Language,\n` +
        `  Sec-Fetch-*, Upgrade-Insecure-Requests, sec-ch-ua*). Check BROWSER_HEADERS.\n` +
        `  Workarounds: --input <local names.zip>, or --source mirror.`
    );
  }
  if (!res.ok) fail(`fetch failed (${res.status} ${res.statusText}) for ${what}`);
  return res;
}

/** Download SSA's names.zip (cached) and return the extracted per-year rows. */
async function loadFromSsa(inputPath) {
  const zipPath = inputPath ?? path.join(CACHE, "names.zip");
  if (!inputPath) {
    await mkdir(CACHE, { recursive: true });
    let cached = false;
    try {
      const { size } = await import("node:fs/promises").then((fs) => fs.stat(zipPath));
      cached = size > 1_000_000;
    } catch {
      cached = false;
    }
    if (cached) {
      console.log(`  using cached archive: ${path.relative(ROOT, zipPath)}`);
    } else {
      console.log(`  downloading ${SSA_ZIP} …`);
      const res = await fetchOrFail(SSA_ZIP, {
        headers: { ...BROWSER_HEADERS, Referer: SSA_REFERER },
        what: "names.zip",
      });
      await pipeline(Readable.fromWeb(res.body), createWriteStream(zipPath));
    }
  }

  // Node has no built-in zip reader; shell out to unzip into the cache dir.
  const extractDir = path.join(CACHE, "yob");
  await rm(extractDir, { recursive: true, force: true });
  await mkdir(extractDir, { recursive: true });
  try {
    await execFileAsync("unzip", ["-qo", zipPath, "-d", extractDir], {
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch (err) {
    fail(`could not unzip ${zipPath} (is \`unzip\` installed?): ${err.message}`);
  }

  const { readdir } = await import("node:fs/promises");
  const files = (await readdir(extractDir)).filter((f) => /^yob\d{4}\.txt$/.test(f)).sort();
  if (!files.length) fail(`no yobYYYY.txt files found inside ${zipPath}`);

  const rows = [];
  for (const file of files) {
    const year = Number(file.slice(3, 7));
    const text = await readFile(path.join(extractDir, file), "utf8");
    for (const line of text.split("\n")) {
      if (!line) continue;
      const [name, sex, count] = line.trim().split(",");
      if (!name) continue;
      rows.push({ year, name, sex, count: Number(count) });
    }
  }
  console.log(`  parsed ${files.length} yearly files (${files[0]} … ${files.at(-1)})`);
  return { rows, sourceId: `SSA names.zip (${files.length} files, ${files[0]} … ${files.at(-1)})` };
}

/** Offline fallback: public SSA-derived mirrors. Lower coverage; see research.md. */
async function loadFromMirror() {
  console.log(`  fetching historical CSV mirror …`);
  const csv = await (await fetchOrFail(MIRROR_HISTORICAL, { what: "baby-names.csv" })).text();
  const rows = [];
  const lines = csv.split("\n");
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const [year, name, percent, sex] = line.split(",").map((c) => c.replace(/"/g, ""));
    rows.push({
      year: Number(year),
      name,
      sex: sex === "girl" ? "F" : "M",
      // Percent scaled to a pseudo-count so both sources share one code path.
      count: Math.round(Number(percent) * 1_000_000),
    });
  }

  console.log(`  fetching recent-year mirrors …`);
  for (let year = 2009; year <= 2024; year++) {
    for (const [sex, code] of [["girl", "F"], ["boy", "M"]]) {
      try {
        const res = await fetch(mirrorRecent(year, sex));
        if (!res.ok) continue;
        const { names } = await res.json();
        // Rank-only source: synthesize a descending count from list position.
        names.forEach((name, idx) =>
          rows.push({ year, name, sex: code, count: Math.max(1, 1000 - idx) })
        );
      } catch {
        // A missing year is tolerable for the fallback source.
      }
    }
  }
  return { rows, sourceId: "GitHub mirrors (hadley/data-baby-names + aruljohn/popular-baby-names)" };
}

function curate(rows, { since, limit, minUses, coreSince, coreMin }) {
  const allTime = new Map(); // name -> { F, M }
  const recent = new Map(); // name -> { F, M } since `since`
  const core = new Map(); // name -> { F, M } since `coreSince`
  const bump = (map, name, sex, count) => {
    let entry = map.get(name);
    if (!entry) map.set(name, (entry = { F: 0, M: 0 }));
    entry[sex] += count;
  };

  for (const { year, name, sex, count } of rows) {
    if (sex !== "F" && sex !== "M") continue;
    bump(allTime, name, sex, count);
    if (year >= since) bump(recent, name, sex, count);
    if (year >= coreSince) bump(core, name, sex, count);
  }

  const dropped = { invalid: 0, tooRare: 0 };
  const girl = [];
  const boy = [];

  for (const [name, counts] of allTime) {
    if (!VALID_NAME.test(name) || name.includes(",")) {
      dropped.invalid++;
      continue;
    }
    // Gender assignment uses all-time counts (stable); ranking uses recent
    // births (keeps the deck contemporary). See research.md Decision 2.
    const isGirl = counts.F >= counts.M;
    const key = isGirl ? "F" : "M";
    const total = counts[key];
    // Floor on the whole list: SSA's own cutoff is 5 occurrences in a single
    // year, which lets through spellings used once nationally. This removes
    // that noise without curating the list down to a "good names" selection.
    if (total < minUses) {
      dropped.tooRare++;
      continue;
    }
    const rank = (recent.get(name) ?? { F: 0, M: 0 })[key];
    const coreCount = (core.get(name) ?? { F: 0, M: 0 })[key];
    (isGirl ? girl : boy).push({ name, rank, coreCount, total });
  }

  // Core names lead the deck; everything else follows. Within each part the
  // order is by popularity, so an index is still a rank.
  // The core is ranked by the same recent-births metric that selects it, so a
  // low index means "familiar today" rather than "was popular in the 90s".
  const byCore = (a, b) =>
    b.coreCount - a.coreCount || b.total - a.total || a.name.localeCompare(b.name);
  const byPopularity = (a, b) =>
    b.rank - a.rank || b.total - a.total || a.name.localeCompare(b.name);
  const split = (list) => {
    const inCore = list.filter((e) => e.coreCount >= coreMin).sort(byCore);
    const tail = list.filter((e) => e.coreCount < coreMin).sort(byPopularity);
    const names = [...inCore, ...tail].map((e) => e.name);
    return { names: limit ? names.slice(0, limit) : names, coreSize: inCore.length };
  };

  const g = split(girl);
  const b = split(boy);
  return { girl: g.names, boy: b.names, girlCore: g.coreSize, boyCore: b.coreSize, dropped };
}

function assertInvariants(girl, boy) {
  const problems = [];
  const check = (list, label) => {
    const seen = new Set();
    for (const name of list) {
      if (!VALID_NAME.test(name)) problems.push(`${label}: invalid entry "${name}"`);
      if (name.includes(",")) problems.push(`${label}: entry contains a comma "${name}"`);
      if (seen.has(name)) problems.push(`${label}: duplicate "${name}"`);
      seen.add(name);
    }
    return seen;
  };
  const girlSet = check(girl, "girl");
  const boySet = check(boy, "boy");
  for (const name of girlSet) {
    if (boySet.has(name)) problems.push(`"${name}" appears in both pools`);
  }
  if (!girl.length || !boy.length) problems.push("a pool is empty");
  if (problems.length) {
    fail(`refusing to write a corpus that violates its contract:\n    - ${problems.slice(0, 10).join("\n    - ")}`);
  }
}

function renderModule({ girl, boy, girlCore, boyCore, sourceId, since, limit, minUses, coreSince, coreMin }) {
  const packed = (list) => JSON.stringify(list.join(","));
  return `// Generated by scripts/build-name-corpus.mjs — do not edit by hand.
// Source: ${sourceId}
// Generated: ${new Date().toISOString().slice(0, 10)} | Ranked by births since ${since}${limit ? ` | Cut: top ${limit}/gender` : ""}
// Floor: ${minUses}+ all-time births | Core: ${coreMin}+ births since ${coreSince}
// Counts: ${girl.length} girl (${girlCore} core) / ${boy.length} boy (${boyCore} core)
//
// Packed as delimited strings rather than array literals: this parses far
// faster than a ~60k-element array literal and drops the per-name quote bytes.
// Ordered by descending popularity — index is the popularity rank — with the
// core names first. GIRL_CORE_SIZE / BOY_CORE_SIZE mark where the core ends;
// the deck deals the core before the long tail.

export const GIRL_CORE_SIZE = ${girlCore};
export const BOY_CORE_SIZE = ${boyCore};

export const GIRL_CORPUS: string[] = ${packed(girl)}.split(",");

export const BOY_CORPUS: string[] = ${packed(boy)}.split(",");
`;
}

/**
 * The backend's copy of the same curated corpus. `api/scripts/seed_corpus.py`
 * loads this into the `names` table, so it must come from this one curation
 * pass rather than by re-parsing the TypeScript module — that module is deleted
 * once the client stops bundling the corpus, and the seeder has to outlive it.
 * Array index is the popularity rank, matching the TS module exactly.
 */
function renderJson({ girl, boy, girlCore, boyCore, sourceId, since, minUses, coreSince, coreMin }) {
  return `${JSON.stringify(
    {
      _comment: "Generated by scripts/build-name-corpus.mjs — do not edit by hand.",
      source: sourceId,
      generated: new Date().toISOString().slice(0, 10),
      rankedSince: since,
      minUses,
      coreSince,
      coreMin,
      girlCoreSize: girlCore,
      boyCoreSize: boyCore,
      girl,
      boy,
    },
    null,
    0
  )}\n`;
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  console.log(`\n  building name corpus (source: ${opts.source}, since: ${opts.since}, floor: ${opts.minUses}+ all-time, core: ${opts.coreMin}+ since ${opts.coreSince})`);

  const { rows, sourceId } =
    opts.source === "ssa" ? await loadFromSsa(opts.input) : await loadFromMirror();

  const { girl, boy, girlCore, boyCore, dropped } = curate(rows, opts);
  assertInvariants(girl, boy);

  const module = renderModule({ girl, boy, girlCore, boyCore, sourceId, ...opts });
  await mkdir(path.dirname(opts.out), { recursive: true });
  await writeFile(opts.out, module);

  const json = renderJson({ girl, boy, girlCore, boyCore, sourceId, ...opts });
  await mkdir(path.dirname(opts.jsonOut), { recursive: true });
  await writeFile(opts.jsonOut, json);

  console.log(`
  girl:    ${girl.length.toLocaleString()} (${girlCore.toLocaleString()} core)
  boy:     ${boy.length.toLocaleString()} (${boyCore.toLocaleString()} core)
  total:   ${(girl.length + boy.length).toLocaleString()}
  dropped: ${dropped.invalid.toLocaleString()} invalid, ${dropped.tooRare.toLocaleString()} under the ${opts.minUses}-use floor
  wrote:   ${path.relative(ROOT, opts.out)} (${(Buffer.byteLength(module) / 1024).toFixed(0)} KB raw)
           ${path.relative(ROOT, opts.jsonOut)} (${(Buffer.byteLength(json) / 1024).toFixed(0)} KB raw)

  core head girl: ${girl.slice(0, 6).join(", ")}
  core head boy:  ${boy.slice(0, 6).join(", ")}
  core edge girl: ${girl.slice(girlCore - 3, girlCore).join(", ")}
  tail head girl: ${girl.slice(girlCore, girlCore + 3).join(", ")}
`);
}

await main();
