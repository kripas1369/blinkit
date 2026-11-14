import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { gaiaNote, scaleText } from "../js/flipbook.js";
import { separationArcsec } from "../js/motion.js";
import { directionText, expectedShift, percentAt, pixelToSky, pixelUnder, visibleStars } from "../js/sky.js";

const FIXTURES = new URL("./fixtures/", import.meta.url);
const readJson = (name) => JSON.parse(readFileSync(new URL(name, FIXTURES), "utf8"));

test("pixel to sky: centre, one pixel north, one pixel west", () => {
  const m = { ra: 180, dec: 10, size_px: 29, pixel_arcsec: 6.15 };
  assert.deepEqual(pixelToSky(14, 14, m), { ra: 180, dec: 10 });
  const north = pixelToSky(14, 13, m);
  assert.ok(Math.abs(separationArcsec(180, 10, north.ra, north.dec) - 6.15) < 0.01);
  assert.ok(north.dec > 10);
  const west = pixelToSky(15, 14, m);
  assert.ok(west.ra < 180, "x grows to the west, so RA gets smaller");
  assert.ok(Math.abs(separationArcsec(180, 10, west.ra, west.dec) - 6.15) < 0.01);
});

test("percent positions and the pixel under a pointer", () => {
  assert.deepEqual(percentAt([0, 0], 10), { left: 5, top: 5 });
  const rect = { left: 100, top: 50, width: 290, height: 290 };
  assert.deepEqual(pixelUnder(100, 50, rect, 29), { x: 0, y: 0 });
  assert.deepEqual(pixelUnder(389.9, 339.9, rect, 29), { x: 28, y: 28 });
  assert.equal(pixelUnder(99, 60, rect, 29), null);
});

test("directions on a north-up, east-left frame", () => {
  assert.equal(directionText(0, -1), "north");
  assert.equal(directionText(-1, 0), "east");
  assert.equal(directionText(-0.6, 0.4), "south-east");
  assert.equal(directionText(0.01, 0), "no measurable direction");
});

test("Barnard's Star: Gaia says 1.67 px north from the first to the last visit", () => {
  const g = readJson("barnard_d2_gaia.json");
  const s = expectedShift(g, 0, 2, 6.15);
  assert.ok(Math.abs(s.px - 1.67) < 0.01);
  assert.equal(directionText(s.dx, s.dy), "north");
  assert.match(gaiaNote(g, 6.15), /moves 1\.67 px \(10\.3″\) from the first to the last visit, toward the north\./);
  assert.ok(visibleStars(g, 16).length < visibleStars(g, null).length);
  assert.ok(visibleStars(g, 0).every((s2) => s2.target), "the target is always drawn");
});

test("WISE 0855 has no Gaia match, and the page says so", () => {
  const g = readJson("wise0855_d6_gaia.json");
  assert.equal(g.target_match, null);
  assert.match(gaiaNote(g, 6.15), /no star within 3″ of the frame centre/);
  assert.equal(gaiaNote(null, 6.15), "No Gaia markers for these frames.");
});

test("the brightness note warns when grey levels are stretched", () => {
  assert.equal(scaleText({ stretch: "linear" }), "Every frame uses the same brightness scale.");
  assert.match(scaleText({ stretch: "asinh" }), /not proportional to brightness/);
});
