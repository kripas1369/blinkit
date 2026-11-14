import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { resetApiCheck } from "../js/frames.js";
import {
  coverageRows, dayClass, dayText, groupDays, groupVisits, loadCoverage, monthTicks, releaseHint, spanText, summaryTerms, timelineChart, timelineSummary, visitTimesText,
} from "../js/timeline.js";

const FIXTURES = new URL("./fixtures/", import.meta.url);
const readJson = (name) => JSON.parse(readFileSync(new URL(name, FIXTURES), "utf8"));
const coverage = readJson("barnard_coverage.json");
const manifest = readJson("barnard_d2_manifest.json");

test("visits: a gap of more than 30 days, or more than 60 days in one visit, starts a new one", () => {
  assert.deepEqual(groupVisits([10, 0, 5]), [{ mjd_min: 0, mjd_max: 10, n: 3 }]);
  assert.equal(groupVisits([0, 31]).length, 2);
  assert.equal(groupVisits([0, 30]).length, 1);
  assert.equal(groupVisits([0, 25, 50, 61]).length, 2);
  assert.deepEqual(groupVisits([]), []);
});

test("month ticks: first of the month, every 2 or 3 months for long spans", () => {
  const short = monthTicks(60900, 61000);   // 2025-08-13 .. 2025-11-21
  assert.deepEqual(short.map((t) => t.label), ["2025-09", "2025-10", "2025-11"]);
  const year = monthTicks(60900, 61310);   // 13.5 months
  assert.ok(year.every((t) => Number(t.label.slice(5)) % 2 === 1));
  const long = monthTicks(60900, 61400);   // 16.4 months
  assert.ok(long.every((t) => Number(t.label.slice(5)) % 3 === 1));
  assert.ok(long.every((t, i) => i === 0 || t.mjd > long[i - 1].mjd));
});

test("rows: every image is in one detector row, and the rows agree with the server's counts", () => {
  const rows = coverageRows(coverage);
  assert.deepEqual(rows.map((r) => r.band), [1, 2, 3, 4, 5, 6]);
  assert.equal(rows.reduce((s, r) => s + r.mjds.length, 0), coverage.summary.n_images);
  for (const r of rows) assert.equal(r.mjds.length, coverage.summary.per_detector[String(r.band)]);
  assert.equal(rows.find((r) => r.band === 2).visits.length, manifest.frames.length);
});

test("days: images of the same UTC day share one line; its colour says 1, 2–9 or 10+ images", () => {
  const day = 60913;   // 2025-08-26 00:00 UTC
  const days = groupDays([day + 0.5, day + 0.25, day + 1.125]);
  assert.deepEqual(days.map((d) => [d.day, d.n]), [["2025-08-26", 2], ["2025-08-27", 1]]);
  assert.equal(dayText(2, days[0]), "D2 · 2025-08-26 · 2 images, 06:00–12:00 UTC");
  assert.equal(dayText(2, days[1]), "D2 · 2025-08-27 03:00 UTC · 1 image");
  assert.deepEqual([1, 2, 9, 10, 18].map(dayClass), ["tl-one", "tl-some", "tl-some", "tl-many", "tl-many"]);
});

test("time spans: hours under a day, then days; gaps run from the end of one visit to the start of the next", () => {
  assert.equal(spanText(0.25), "6 h");
  assert.equal(spanText(0.001), "1 h");
  assert.equal(spanText(1.2), "1 day");
  assert.equal(spanText(40.4), "40 days");
  const visits = [{ mjd_min: 60900, mjd_max: 60909 }, { mjd_min: 61105, mjd_max: 61105.5 }];
  assert.equal(visitTimesText(visits),
    "visit 1: 2025-08-13, lasted 9 days · 196 days later · visit 2: 2026-03-06, lasted 12 h");
});

test("clickable words: what each release and 'exposures' mean, with this position's own dates", () => {
  const terms = summaryTerms(coverage);
  assert.deepEqual(terms.map((t) => t.term), ["exposures", "qr2", "qr3"]);
  assert.match(terms[0].hint, /^Exposure = one SPHEREx snapshot\. .* here 181 exposures gave 359 images\.$/);
  assert.match(terms[2].hint, /^QR3 = SPHEREx Quick Release 3: images IRSA publishes soon after they are taken\. Here: 119 images, taken 20\d\d-/);
  const live = {
    summary: { n_images: 2 },
    images: [
      { band: 2, mjd: 60907.5, release: "spherex_dr1", release_date: "2026-10-04T00:00:00" },
      { band: 5, mjd: 61165.5, release: "spherex_dr1_deep", release_date: "2026-10-09T00:00:00" },
    ],
  };
  assert.equal(releaseHint(live, "spherex_dr1"),
    "DR1 = SPHEREx Data Release 1: a full release that comes months after the images were taken. " +
    "Here: 1 image, taken 2025-08-20, published 2026-10-04.");
  assert.match(releaseHint(live, "spherex_dr1_deep"), /^DR1_DEEP = .* Deep: extra visits to the SPHEREx Deep Fields near the ecliptic poles\. Here:/);
  assert.equal(summaryTerms({ summary: { n_images: 0 }, images: [] }).length, 0);
});

test("chart: every image is in a day line, a clickable row per detector, ▼ only in the current row", () => {
  const svg = timelineChart(coverage, { det: 2, frameMjds: manifest.frames.map((f) => f.mjd) });
  const counts = [...svg.matchAll(/class="tl-image tl-\w+" data-n="(\d+)"/g)].map((m) => Number(m[1]));
  assert.equal(counts.reduce((a, b) => a + b, 0), coverage.summary.n_images);
  assert.equal((svg.match(/<title>D\d · \d{4}-\d\d-\d\d/g) || []).length, counts.length);
  assert.equal((svg.match(/class="tl-row/g) || []).length, 6);
  assert.equal((svg.match(/tl-row tl-current" data-band="2"/g) || []).length, 1);
  assert.equal((svg.match(/class="tl-frame"/g) || []).length, manifest.frames.length);
  assert.equal((timelineChart(coverage).match(/class="tl-frame"/g) || []).length, 0);
});

test("summary: from the file, and says why the flipbook can show fewer visits", () => {
  const [all, d2, time] = timelineSummary(coverage, 2, 3);
  assert.match(all, /^359 images \(181 exposures\) from 2025-08-15 to 2026-09-22 \(403 days\) · releases: qr2 240, qr3 119/);
  assert.equal(d2, "D2: 61 images in 3 visits; the flipbook shows all 3.");
  assert.match(time, /^Time: visit 1: \d{4}-\d\d-\d\d, lasted \d+ (days?|h) · \d+ days later · visit 2: .* visit 3: .*\.$/);
  assert.match(timelineSummary(coverage, 2, 2)[1], /shows 2 \(a visit is left out/);
  const empty = { ...coverage, summary: { n_images: 0 }, images: [] };
  assert.deepEqual(timelineSummary(empty, 2), ["SPHEREx has no images of this position yet."]);
});

test("coverage: an official target's prepared file first, IRSA through the API otherwise", async () => {
  const asked = [];
  const routes = {
    "/api/health": { ok: true },
    "frames/barnard/coverage.json": coverage,
    "/api/coverage?ra=10.000000&dec=20.000000": { ...coverage, ra: 10, dec: 20 },
  };
  const fetchFn = async (url) => {
    asked.push(url);
    return url in routes
      ? { ok: true, status: 200, json: async () => structuredClone(routes[url]) }
      : { ok: false, status: 404, json: async () => ({ error: "not found" }) };
  };
  resetApiCheck();
  assert.equal((await loadCoverage({ targetKey: "barnard", ra: 269.4, dec: 4.7 }, fetchFn)).summary.n_images, 359);
  assert.ok(!asked.some((u) => u.startsWith("/api/coverage")), "IRSA is not asked when the file exists");
  assert.equal((await loadCoverage({ targetKey: null, ra: 10, dec: 20 }, fetchFn)).ra, 10);
  assert.equal((await loadCoverage({ targetKey: "r_dra", ra: 10, dec: 20 }, fetchFn)).ra, 10,
    "a target without a prepared file falls back to the API");
  resetApiCheck();
});
