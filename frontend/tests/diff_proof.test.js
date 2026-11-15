import assert from "node:assert/strict";
import { test } from "node:test";

import { findPair, pairFacts, pairWarnings, stepPair } from "../js/diffview.js";
import { dataLines, motionText } from "../js/proof.js";

test("diff: findPair and stepPair keep A before B", () => {
  const diff = {
    pairs: [
      { a: 0, b: 1, png: "diff_0_1.png" },
      { a: 0, b: 2, png: "diff_0_2.png" },
      { a: 1, b: 2, png: "diff_1_2.png" },
    ],
  };
  assert.equal(findPair(diff, 0, 2).png, "diff_0_2.png");
  assert.equal(findPair(diff, 2, 0), null);
  const ids = [0, 1, 2, 3];
  assert.deepEqual(stepPair(ids, 0, 2, "a", 1), [1, 2]);
  assert.equal(stepPair(ids, 1, 2, "a", 1), null);
  assert.equal(stepPair(ids, 0, 3, "b", 1), null);
});

test("diff: pairFacts and pairWarnings use the numbers from the pair", () => {
  const pair = {
    days: 360.2, wl_gap_um: 0.003, sky_change: -0.01, pct_flagged: 3.2, pct_no_value: 0.2,
    max_sigma: 8.1, min_sigma: -7.4, scatter_sigma: 1.1,
  };
  const fa = { wl_target_um: 1.428, wl_target_range_um: [1.24, 1.63], n_images: 8 };
  const fb = { wl_target_um: 1.425, wl_target_range_um: [1.31, 1.54], n_images: 8 };
  assert.match(pairFacts(pair, fa, fb), /360\.2 days apart/);
  assert.match(pairFacts(pair, fa, fb), /1\.428(?: µm)? → 1\.425/);
  const warnings = pairWarnings(pair, fa, fb);
  assert.ok(warnings[0].includes("strongest +8.1σ"));
  assert.ok(warnings.some((w) => w.includes("mixes wavelengths")));
});

test("proof: agrees verdict and discrepancy line", () => {
  const proof = {
    pixel_arcsec: 6.15,
    motion: {
      status: "agrees",
      gaia_source_id: "4472832130942575872",
      visits: ["2025-08-26", "2026-08-21"],
      expected_px: [0.128, -1.662],
      expected_size_px: 1.67,
      measured_px: [0.111, -1.611],
      measured_size_px: 1.61,
      difference_px: 0.05,
      direction_difference_deg: 0.5,
      method: "saturated-core centre",
      limits: { max_error_px: 0.5, max_direction_deg: 30, min_testable_px: 0.3 },
    },
  };
  const { verdict, lines } = motionText(proof);
  assert.equal(verdict, "Agrees with Gaia DR3");
  assert.match(lines[0], /Expected \(Gaia DR3 4472832130942575872/);
  assert.match(lines[1], /Measured shift \(saturated-core centre\): 1\.61 px/);
  assert.match(lines[2], /Discrepancy: 0\.05 px \(C4 limit 0\.5 px/);
});

test("proof: disagrees and not_measurable are not shown as a pass", () => {
  const bad = motionText({
    pixel_arcsec: 6.15,
    motion: {
      status: "disagrees",
      gaia_source_id: "1",
      visits: ["2025-04-26", "2026-04-21"],
      expected_px: [-0.637, 0.395],
      expected_size_px: 0.75,
      measured_px: [0.272, -0.525],
      measured_size_px: 0.59,
      difference_px: 1.29,
      direction_difference_deg: 140,
      method: "centroid",
      limits: { max_error_px: 0.5, max_direction_deg: 30, min_testable_px: 0.3 },
    },
  });
  assert.equal(bad.verdict, "Does not agree with Gaia DR3");
  assert.ok(bad.lines.some((l) => l.startsWith("Discrepancy: 1.29 px")));

  const none = motionText({
    pixel_arcsec: 6.15,
    motion: { status: "not_measurable", reason: "Neither the centroid nor the saturated-core centre could be measured." },
  });
  assert.equal(none.verdict, "Not measurable");
  assert.deepEqual(none.lines, ["Neither the centroid nor the saturated-core centre could be measured."]);
});

test("proof: data lines come from the file", () => {
  const proof = {
    data: {
      n_visits: 3, span_days: 360.2, n_exposures_used: 24, n_exposures_taken: 61,
      pct_flagged_range: [2.6, 3.6], newest_exposure: "2026-08-21 17:06 UTC",
      frames_made_at: "2026-11-14 15:01 UTC",
      releases: { spherex_dr1: { n_exposures: 16, release_date: "2026-04-21 00:00:00" } },
      asked_irsa_at: "2026-11-14 20:00 UTC",
    },
  };
  const lines = dataLines(proof);
  assert.equal(lines[0], "3 visits over 360 days.");
  assert.equal(lines[1], "24 of the 61 exposures taken in these visits are added up.");
  assert.equal(lines[2], "Flagged pixels: 2.6–3.6% per visit.");
  assert.ok(lines.some((l) => l.startsWith("Data releases: spherex_dr1")));
});
