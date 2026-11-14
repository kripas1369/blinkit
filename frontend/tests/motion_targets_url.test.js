import assert from "node:assert/strict";
import { test } from "node:test";

import { positionAt, separationArcsec, VIEW_EPOCH } from "../js/motion.js";
import { detectorsRated, RATINGS, TARGETS } from "../js/targets.js";
import { buildUrlState, MODES, readUrlState, VIEW_DEFAULTS } from "../js/urlstate.js";

test("every target rates all 6 detectors, with a reason, and never starts on a 'not recommended' one", () => {
  for (const t of TARGETS) {
    assert.deepEqual(Object.keys(t.detectors).map(Number), [1, 2, 3, 4, 5, 6], t.label);
    for (const d of Object.values(t.detectors)) {
      assert.ok(d.rating in RATINGS, `${t.label}: ${d.rating}`);
      assert.ok(d.why.length > 10, t.label);
    }
    assert.notEqual(t.detectors[t.detector].rating, "not", t.label);
  }
  const wise = TARGETS.find((t) => t.key === "wise0855");
  assert.deepEqual(detectorsRated(wise, "recommended"), [6]);
  assert.deepEqual(detectorsRated(wise, "not"), [1, 2, 3, 4]);
});

// Positions at 2026.0 computed by the Python backend (notes/DAY1_REPORT.md, cache/day1_report.json).
const BACKEND_2026 = {
  barnard: [269.446269, 4.768204],
  eps_ind_b: [331.096644, -56.80066],
  wise0855: [133.759765, -7.242186],
  rw_aur: [76.956587, 30.401291],
  r_dra: [248.167233, 66.755024],
};

test("target buttons land where the backend searched (within 0.1 arcsec)", () => {
  assert.equal(VIEW_EPOCH, 2026.0);
  for (const t of TARGETS) {
    const { ra, dec } = positionAt(t.ra, t.dec, t.pmra, t.pmdec, 2000.0, VIEW_EPOCH);
    const [bra, bdec] = BACKEND_2026[t.key];
    assert.ok(separationArcsec(ra, dec, bra, bdec) < 0.1, t.label);
  }
});

test("Barnard's Star moved about 270 arcsec from 2000 to 2026", () => {
  const b = TARGETS.find((t) => t.key === "barnard");
  const p = positionAt(b.ra, b.dec, b.pmra, b.pmdec, 2000.0, 2026.0);
  const moved = separationArcsec(b.ra, b.dec, p.ra, p.dec);
  assert.ok(Math.abs(moved - 270.2) < 0.5, String(moved));
});

test("RA wraps around 360", () => {
  const p = positionAt(359.9999, 0, 3.6e6, 0, 0, 1);
  assert.ok(p.ra >= 0 && p.ra < 1);
});

test("share link round trip", () => {
  const url = buildUrlState({ ra: 269.446269, dec: 4.768204, fov: 5, det: 6 });
  assert.equal(url, "?ra=269.446269&dec=4.768204&fov=5&det=6");
  const back = readUrlState(url);
  assert.deepEqual(back, { ra: 269.446269, dec: 4.768204, fov: 5, det: 6, ...VIEW_DEFAULTS, problems: [] });
});

test("view settings go in the link only when they differ from the defaults", () => {
  const view = { ra: 133.759765, dec: -7.242186, fov: 3, det: 6, mode: "blink", a: 0, b: 2,
    gaia: false, wise: true, flags: true, speed: 0.5 };
  const url = buildUrlState(view);
  assert.equal(url, "?ra=133.759765&dec=-7.242186&fov=3&det=6&mode=blink&a=0&b=2&gaia=0&wise=1&flags=1&speed=0.5");
  assert.deepEqual(readUrlState(url), { ...view, problems: [] });
  assert.equal(buildUrlState({ ...view, ...VIEW_DEFAULTS }), "?ra=133.759765&dec=-7.242186&fov=3&det=6");
});

test("bad links fall back to defaults and say why", () => {
  const s = readUrlState("?ra=500&dec=10&fov=99&det=9");
  assert.equal(s.ra, null);
  assert.equal(s.fov, 3);
  assert.equal(s.det, 2);
  assert.equal(s.problems.length, 3);
  assert.deepEqual(readUrlState(""), { ra: null, dec: null, fov: 3, det: 2, ...VIEW_DEFAULTS, problems: [] });
});

test("bad view settings fall back to defaults, one message each", () => {
  const s = readUrlState("?ra=10&dec=10&mode=wobble&a=x&gaia=yes&wise=2&flags=&speed=3");
  assert.equal(s.mode, "flip");
  assert.equal(s.a, null);
  assert.equal(s.gaia, true);
  assert.equal(s.wise, false);
  assert.equal(s.flags, false);
  assert.equal(s.speed, 1);
  assert.equal(s.problems.length, 6);
  assert.ok(s.problems[0].includes("wobble"));
  const same = readUrlState("?ra=10&dec=10&a=1&b=1");
  assert.deepEqual([same.a, same.b, same.problems.length], [null, null, 1]);
  for (const mode of Object.keys(MODES)) assert.equal(readUrlState(`?mode=${mode}`).mode, mode);
});
