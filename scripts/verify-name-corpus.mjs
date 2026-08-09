#!/usr/bin/env node
// Asserts the generated name corpus satisfies its contract.
// Run via `npm run corpus:verify`. Dependency-free by design.
//
// Contract: specs/001-expanded-name-corpus/contracts/name-corpus.md §1

import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const MODULE_PATH = path.join(ROOT, "src/lib/nameCorpus.ts");

// Expected magnitudes from the full SSA corpus; a large swing means a source
// or parsing regression rather than a legitimate data refresh.
const EXPECTED = {
  girl: 39749,
  boy: 24131,
  girlCore: 7457,
  boyCore: 5707,
  tolerance: 0.1,
};
const VALID_NAME = /^[A-Z][A-Za-z'-]{1,14}$/;

const problems = [];
const note = (message) => problems.push(message);

/**
 * The module is TypeScript, so it can't be imported directly by node. It has a
 * fixed generated shape — two packed string literals — so read it as text.
 */
async function loadCorpus() {
  const { readFile } = await import("node:fs/promises");
  let source;
  try {
    source = await readFile(MODULE_PATH, "utf8");
  } catch {
    console.error(
      `\n  verify-name-corpus: ${path.relative(ROOT, MODULE_PATH)} not found.\n` +
        `  Generate it first: npm run corpus:build\n`
    );
    process.exit(1);
  }

  const extract = (exportName) => {
    const match = source.match(
      new RegExp(`export const ${exportName}: string\\[\\] = ("(?:[^"\\\\]|\\\\.)*")\\.split\\(","\\);`)
    );
    if (!match) {
      console.error(
        `\n  verify-name-corpus: could not find a packed ${exportName} in ` +
          `${path.relative(ROOT, MODULE_PATH)}.\n  Was it edited by hand?\n`
      );
      process.exit(1);
    }
    return JSON.parse(match[1]).split(",");
  };

  const size = (name) => {
    const m = source.match(new RegExp(`export const ${name} = (\\d+);`));
    if (!m) {
      console.error(`\n  verify-name-corpus: missing ${name} in the generated module.\n`);
      process.exit(1);
    }
    return Number(m[1]);
  };

  return {
    girl: extract("GIRL_CORPUS"),
    boy: extract("BOY_CORPUS"),
    girlCore: size("GIRL_CORE_SIZE"),
    boyCore: size("BOY_CORE_SIZE"),
  };
}

function checkList(list, label) {
  const seen = new Set();
  let invalid = 0;
  let commas = 0;
  let duplicates = 0;

  for (const name of list) {
    if (name.includes(",")) commas++;
    else if (!VALID_NAME.test(name)) {
      if (invalid < 5) note(`${label}: invalid entry ${JSON.stringify(name)}`);
      invalid++;
    }
    if (seen.has(name)) {
      if (duplicates < 5) note(`${label}: duplicate entry ${JSON.stringify(name)}`);
      duplicates++;
    }
    seen.add(name);
  }

  if (invalid > 5) note(`${label}: …and ${invalid - 5} more invalid entries`);
  if (commas) note(`${label}: ${commas} entries contain a comma (corrupts the packed form)`);
  if (duplicates > 5) note(`${label}: …and ${duplicates - 5} more duplicates`);
  if (!list.length) note(`${label}: pool is empty`);

  return seen;
}

function checkMagnitude(actual, expected, label) {
  const drift = Math.abs(actual - expected) / expected;
  if (drift > EXPECTED.tolerance) {
    note(
      `${label}: ${actual.toLocaleString()} entries is ${(drift * 100).toFixed(0)}% off the ` +
        `expected ~${expected.toLocaleString()} — source or parsing regression?`
    );
  }
}

const { girl, boy, girlCore, boyCore } = await loadCorpus();

const girlSet = checkList(girl, "girl");
const boySet = checkList(boy, "boy");

const overlap = [...girlSet].filter((name) => boySet.has(name));
if (overlap.length) {
  note(
    `${overlap.length} spelling(s) appear in both pools (breaks name-keyed picks in "both" mode): ` +
      overlap.slice(0, 5).join(", ")
  );
}

checkMagnitude(girl.length, EXPECTED.girl, "girl");
checkMagnitude(boy.length, EXPECTED.boy, "boy");
checkMagnitude(girlCore, EXPECTED.girlCore, "girl core");
checkMagnitude(boyCore, EXPECTED.boyCore, "boy core");

// The core must be a real prefix of each list, or the deck's core-first
// ordering would silently deal tail names early.
for (const [size, list, label] of [[girlCore, girl, "girl"], [boyCore, boy, "boy"]]) {
  if (!(size > 0 && size < list.length)) {
    note(`${label}: core size ${size} is not inside the list (${list.length})`);
  }
}

if (problems.length) {
  console.error(`\n  verify-name-corpus: FAILED\n\n    - ${problems.join("\n    - ")}\n`);
  process.exit(1);
}

console.log(`
  verify-name-corpus: PASS

  girl:    ${girl.length.toLocaleString()} (${girlCore.toLocaleString()} core)
  boy:     ${boy.length.toLocaleString()} (${boyCore.toLocaleString()} core)
  total:   ${(girl.length + boy.length).toLocaleString()}
  overlap: none
  format:  all entries match ${VALID_NAME}
`);
