#!/usr/bin/env node
// Optional UI validation for the expanded name corpus (spec 001).
// Drives a real Chromium through the quickstart scenarios — most importantly
// §5, the upgrade case where a kept name absent from the corpus must stay
// listed. That is the data-loss guard this feature exists to provide.
//
// Playwright is NOT a project dependency (it is only needed for this check):
//
//   npm install --no-save playwright
//   npm run build && npm run preview -- --port 4173 &
//   node scripts/validate-corpus-ui.mjs
//
// Set PW_CHROMIUM to override the browser binary; defaults to the sandbox's
// pre-installed Chromium, falling back to Playwright's own resolution.

import { chromium } from "playwright";

const URL = process.env.PREVIEW_URL || "http://localhost:4173/";
const KEY = "babyname-swipe-v3";
const results = [];
const check = (name, pass, detail = "") =>
  results.push({ name, pass, detail }) && console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);

const executablePath = process.env.PW_CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const { existsSync } = await import("node:fs");
const browser = await chromium.launch(existsSync(executablePath) ? { executablePath } : {});

// ---------- §3 fresh install + §2b cold-load timing (4x CPU throttle) ----------
{
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });

  await page.goto(URL, { waitUntil: "load" });
  await page.evaluate((key) => {
    localStorage.setItem(key, JSON.stringify({
      people: [{ label: "A", picks: {} }, { label: "B", picks: {} }],
      lastName: "", genderFilter: "girl", onboarded: true,
    }));
  }, KEY);

  // Reload with an onboarded state so we time load → first card, not typing.
  await page.reload({ waitUntil: "load" });
  await page.waitForFunction(() =>
    [...document.querySelectorAll("div")].some(
      (d) => d.children.length === 0 && /^[A-Z][a-z'\u2019-]{1,14}$/.test(d.textContent?.trim() || "")
    )
  );
  const nav = await page.evaluate(() => {
    const e = performance.getEntriesByType("navigation")[0];
    return { domInteractive: Math.round(e.domInteractive), loadEnd: Math.round(e.loadEventEnd || performance.now()) };
  });
  const firstCard = await page.evaluate(() => Math.round(performance.now()));
  check("\u00a72b cold load \u2192 first card (4x CPU throttle)", firstCard < 2500,
    `${firstCard} ms to first card; domInteractive ${nav.domInteractive} ms`);

  const names = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll("div").forEach((d) => {
      const t = d.textContent?.trim();
      if (t && /^[A-Z][a-z'\u2019-]{1,14}$/.test(t) && d.children.length === 0) out.push(t);
    });
    return [...new Set(out)];
  });
  check("\u00a73 real names rendered on cards", names.length > 0, `sample: ${names.slice(0, 5).join(", ")}`);

  // §2b: switching filter to "both" builds the largest pool (105,966 shuffled)
  await page.evaluate(() => {
    const raw = JSON.parse(localStorage.getItem("babyname-swipe-v3"));
    raw.genderFilter = "both";
    localStorage.setItem("babyname-swipe-v3", JSON.stringify(raw));
  });
  const t = Date.now();
  await page.reload({ waitUntil: "load" });
  await page.waitForFunction(() =>
    [...document.querySelectorAll("div")].some(
      (d) => d.children.length === 0 && /^[A-Z][a-z'\u2019-]{1,14}$/.test(d.textContent?.trim() || "")
    )
  );
  const bothFirstCard = await page.evaluate(() => Math.round(performance.now()));
  check("\u00a72b both-mode (106k pool) \u2192 first card (4x CPU throttle)", bothFirstCard < 3000,
    `${bothFirstCard} ms in-page (${Date.now() - t} ms wall incl. navigation)`);

  await ctx.close();
}

// ---------- §4 shared order between swipers ----------
{
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(URL);
  await page.evaluate((key) => {
    localStorage.setItem(key, JSON.stringify({
      people: [{ label: "A", picks: {} }, { label: "B", picks: {} }],
      lastName: "", genderFilter: "girl", onboarded: true,
    }));
  }, KEY);
  await page.reload({ waitUntil: "networkidle" });

  const readTop = () => page.evaluate(() => {
    const els = [...document.querySelectorAll("div")].filter(
      (d) => d.children.length === 0 && /^[A-Z][a-z'’-]{1,14}$/.test(d.textContent?.trim() || "")
    );
    return els.map((e) => e.textContent.trim());
  });

  const swipe = async (n) => {
    const seen = [];
    for (let i = 0; i < n; i++) {
      const top = (await readTop())[0];
      if (top) seen.push(top);
      await page.keyboard.press("ArrowLeft");
      await page.waitForTimeout(320);
    }
    return seen;
  };

  const aSaw = await swipe(6);
  // switch to swiper B via stored state (segmented control label varies)
  await page.evaluate(() => {
    const raw = JSON.parse(localStorage.getItem("babyname-swipe-v3"));
    localStorage.setItem("babyname-swipe-v3", JSON.stringify(raw));
  });
  await page.getByRole("button", { name: "B" }).click().catch(() => {});
  await page.waitForTimeout(400);
  const bSaw = await swipe(6);

  const sameOrder = JSON.stringify(aSaw) === JSON.stringify(bSaw);
  check("§4 both swipers walk the same order", sameOrder, sameOrder ? aSaw.slice(0, 4).join(" → ") : `A: ${aSaw.join(",")} | B: ${bSaw.join(",")}`);

  const noRepeat = new Set(aSaw).size === aSaw.length;
  check("§4 no repeats within a swiper's run", noRepeat, aSaw.join(", "));
  await ctx.close();
}

// ---------- §5 upgrade scenario: legacy names must survive ----------
{
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(URL);
  await page.evaluate((key) => {
    localStorage.setItem(key, JSON.stringify({
      people: [
        { label: "A", picks: { Zzyzxia: "keep", Emma: "keep", Bartholomew: "keep" } },
        { label: "B", picks: { Zzyzxia: "keep", Emma: "keep" } },
      ],
      lastName: "Dudley", genderFilter: "girl", onboarded: true,
    }));
  }, KEY);
  await page.reload({ waitUntil: "networkidle" });

  // open the matches list
  await page.getByText(/MATCHES/i).first().click();
  await page.waitForTimeout(500);
  const body = await page.locator("body").innerText();

  check("§5 absent-from-corpus match still listed (Zzyzxia)", body.includes("Zzyzxia"), "");
  check("§5 in-corpus match still listed (Emma)", body.includes("Emma"), "");
  // Bartholomew IS in the corpus (boy), so girl-view correctly scopes it out —
  // that is today's behavior preserved. It must reappear in "both" view.
  check("§5 in-corpus boy keep scoped out of girl view (Bartholomew)", !body.includes("Bartholomew"), "correct scoping");
  await page.evaluate((key) => {
    const raw = JSON.parse(localStorage.getItem(key));
    raw.genderFilter = "both";
    localStorage.setItem(key, JSON.stringify(raw));
  }, KEY);
  await page.reload({ waitUntil: "load" });
  await page.getByText(/MATCHES/i).first().click();
  await page.waitForTimeout(500);
  const bothBody = await page.locator("body").innerText();
  check("§5 that same keep reappears in both view", bothBody.includes("Bartholomew"), "");
  check("§5 absent name still listed in both view too", bothBody.includes("Zzyzxia"), "");
  check("§5 no forced re-onboarding", !/what should we call you/i.test(body), "");

  // §6 storage shape unchanged
  const saved = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), KEY);
  const keys = Object.keys(saved).sort().join(",");
  check("§6 storage shape unchanged", keys === "genderFilter,lastName,onboarded,people", keys);
  check("§6 picks preserved verbatim", saved.people[0].picks.Zzyzxia === "keep", "");
  await ctx.close();
}

await browser.close();

const failed = results.filter((r) => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
