import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import {
  FramesUnavailable, checkManifest, forget, frameLabel, framesQuery, loadFrames, loadIndex, loadManifest, manifestUrl,
  remember, resetApiCheck, spanDays, wavelengthText,
} from "../js/frames.js";
import { defaultBlinkPair, intervalMs, nextIndex, prevIndex, SPEEDS } from "../js/player.js";
import { SPEEDS as URL_SPEEDS } from "../js/urlstate.js";

const FIXTURES = new URL("./fixtures/", import.meta.url);
const FRAMES = new URL("../frames/", import.meta.url);
const readJson = (url) => JSON.parse(readFileSync(url, "utf8"));
const barnard = () => readJson(new URL("barnard_d2_manifest.json", FIXTURES));

function fakeFetch(files) {
  return async (url) => (url in files
    ? { ok: true, status: 200, json: async () => structuredClone(files[url]) }
    : { ok: false, status: 404, json: async () => ({}) });
}

function apiFetch(routes) {
  return async (url) => {
    const r = routes[url];
    if (r === undefined) return { ok: false, status: 404, json: async () => { throw new Error("not JSON"); } };
    return { ok: r.status === 200, status: r.status, json: async () => structuredClone(r.body) };
  };
}

test("frames made on this machine (frontend/frames/, not in git) pass the check and their images exist", {
  skip: existsSync(new URL("index.json", FRAMES)) ? false : "no frontend/frames/index.json yet",
}, () => {
  const index = readJson(new URL("index.json", FRAMES));
  const pairs = Object.entries(index.available).flatMap(([t, bands]) => bands.map((b) => [t, b]));
  assert.ok(pairs.length >= 1);
  for (const [target, band] of pairs) {
    const m = checkManifest(readJson(new URL(`${target}/d${band}/manifest.json`, FRAMES)));
    assert.equal(m.target, target);
    assert.equal(m.band, band);
    for (const f of m.frames) {
      for (const png of [f.png, f.flags_png].filter(Boolean)) {
        assert.ok(existsSync(new URL(`${target}/d${band}/${png}`, FRAMES)), `${target} d${band} ${png} missing`);
      }
    }
  }
  for (const target of readdirSync(FRAMES, { withFileTypes: true }).filter((d) => d.isDirectory())) {
    for (const band of readdirSync(new URL(`${target.name}/`, FRAMES))) {
      if (!existsSync(new URL(`${target.name}/${band}/manifest.json`, FRAMES))) continue;
      assert.ok((index.available[target.name] || []).includes(Number(band.slice(1))),
        `${target.name}/${band} has a manifest but is not in index.json`);
    }
  }
});

test("Barnard D2 add-up: real values give the expected label", () => {
  const m = checkManifest(barnard());
  assert.equal(m.mode, "coadd");
  assert.equal(m.frames.length, 3);
  assert.equal(m.size_px, 29);
  const f = m.frames[0];
  assert.equal(
    frameLabel(f, 0, 3),
    "Visit 1 of 3 · 2025-08-26 11:57 UTC · D2, 1.238–1.629 µm at the star (band 1.10–1.65 µm) · " +
      "8 exposures added of 18 in this visit · 2.6% pixels flagged · 0.2% with no value (striped)",
  );
  assert.ok(f.pct_no_value > 0, "Barnard's core is saturated, so some pixels have no value");
  assert.doesNotMatch(frameLabel({ ...f, pct_no_value: 0 }, 0, 3), /no value/);
  assert.ok(spanDays(m.frames) > 300 && spanDays(m.frames) < 400);
});

test("release and alignment warnings appear in the frame label", () => {
  const f = { ...barnard().frames[0], release: "spherex_dr1", align_offset_px: 0.62 };
  assert.match(frameLabel(f, 0, 3), /DR1 release/);
  assert.match(frameLabel(f, 0, 3), /possible misalignment \(0\.62 px\)/);
});

test("label wording for single exposures, add-ups and unknown wavelength", () => {
  const single = { ...barnard().frames[0], n_images: 1, wl_target_range_um: undefined };
  assert.match(frameLabel(single, 0, 3), / · 1 exposure of 18 in this visit · /);
  const frame = { ...barnard().frames[0], n_images: 7, n_images_in_epoch: undefined, wl_target_um: null };
  assert.match(frameLabel(frame, 1, 3), /^Visit 2 of 3 · .* · 7 exposures added · /);
  assert.match(wavelengthText(frame), /^wavelength at the star unknown \(band /);
  const mixed = { ...frame, wl_target_um: 1.2, wl_target_range_um: [1.18, 1.25] };
  assert.match(wavelengthText(mixed), /^1\.180–1\.250 µm at the star \(band /);
  assert.match(wavelengthText({ ...mixed, wl_target_range_um: [1.2, 1.2] }), /^1\.200 µm at the star/);
});

test("bad manifests are refused, not shown", () => {
  const cases = [
    [(m) => { m.format = "other"; }, /format/],
    [(m) => { delete m.size_px; }, /size_px/],
    [(m) => { m.scale.vmax = m.scale.vmin; }, /scale/],
    [(m) => { m.scale.stretch = "log"; }, /stretch/],
    [(m) => { m.scale.stretch = "asinh"; delete m.scale.asinh_softening; }, /asinh_softening/],
    [(m) => { m.frames = []; }, /no frames/],
    [(m) => { m.frames[1].band = 6; }, /D6 in a D2/],
    [(m) => { delete m.frames[0].mjd; }, /observation time/],
    [(m) => { m.frames[2].mjd = m.frames[0].mjd; }, /time order/],
    [(m) => { delete m.frames[0].pct_flagged; }, /counts/],
    [(m) => { m.notes = "look closely"; }, /notes/],
  ];
  for (const [breakIt, message] of cases) {
    const m = barnard();
    breakIt(m);
    assert.throws(() => checkManifest(m), message);
  }
});

test("extra manifest fields (release, flag_counts, pixel_source) are allowed", () => {
  const m = { ...barnard(), collections_checked: ["spherex_qr3", "spherex_dr1"], newest_obs_date: "2026-09-22" };
  m.frames = m.frames.map((f) => ({ ...f, release: "DR1", flag_counts: { HOT: 3 }, pixel_source: "aws-s3" }));
  assert.equal(checkManifest(m).frames.length, 3);
});

test("loading: missing files mean 'not prepared', server errors are reported", async () => {
  const m = barnard();
  const fetchFn = fakeFetch({
    "frames/index.json": { available: { barnard: [2] } },
    [manifestUrl("barnard", 2)]: m,
  });
  assert.deepEqual(await loadIndex(fetchFn), { barnard: [2] });
  assert.equal((await loadManifest("barnard", 2, fetchFn)).frames.length, 3);
  assert.equal(await loadManifest("barnard", 6, fetchFn), null);
  assert.deepEqual(await loadIndex(fakeFetch({})), {});
  const broken = async () => ({ ok: false, status: 500 });
  await assert.rejects(loadManifest("barnard", 2, broken), FramesUnavailable);
  const offline = async () => { throw new TypeError("network"); };
  await assert.rejects(loadIndex(offline), FramesUnavailable);
});

test("cache: a target loaded once is not downloaded again; failures and 'still preparing' are asked again", async () => {
  const asked = [];
  const files = fakeFetch({ [manifestUrl("barnard", 2)]: barnard() });
  const counting = async (url, opts) => { asked.push(url); return files(url, opts); };
  const [a, b] = await Promise.all([loadManifest("barnard", 2, counting), loadManifest("barnard", 2, counting)]);
  assert.equal(await loadManifest("barnard", 2, counting), a);
  assert.equal(a, b);
  assert.deepEqual(asked, [manifestUrl("barnard", 2)]);

  let up = false;
  const flaky = async () => {
    if (!up) return { ok: false, status: 500 };
    return { ok: true, status: 200, json: async () => barnard() };
  };
  await assert.rejects(loadManifest("barnard", 2, flaky), FramesUnavailable);
  up = true;
  assert.equal((await loadManifest("barnard", 2, flaky)).frames.length, 3);

  let calls = 0;
  const later = await remember(counting, "k", async () => ++calls);
  assert.equal(await remember(counting, "k", async () => ++calls), later);
  forget(counting, "k");
  assert.equal(await remember(counting, "k", async () => ++calls), 2);
});

test("cache: the API's 'preparing' answer is not kept, its finished frames are", async () => {
  resetApiCheck();
  let ready = false;
  let framesAsked = 0;
  const api = async (url) => {
    if (url === "/api/health") return { ok: true, status: 200, json: async () => ({ ok: true }) };
    framesAsked += 1;
    if (!ready) return { ok: false, status: 202, json: async () => ({ message: "Preparing" }) };
    return { ok: true, status: 200, json: async () => ({ ...barnard(), base_url: "frames/barnard/d2/" }) };
  };
  const where = { targetKey: "barnard", ra: 269.45, dec: 4.69, det: 2, fov: 3 };
  assert.equal((await loadFrames(where, api)).status, "working");
  ready = true;
  assert.equal((await loadFrames(where, api)).status, "ready");
  assert.equal((await loadFrames(where, api)).status, "ready");
  assert.equal(framesAsked, 2);
  resetApiCheck();
});

test("frames come from the API when there is one: ready, working, none, error", async () => {
  const m = barnard();
  const where = { targetKey: "barnard", ra: m.ra, dec: m.dec, det: 2, fov: 3 };
  const health = { "/api/health": { status: 200, body: { ok: true } } };
  assert.equal(framesQuery(where), "/api/frames?target=barnard&band=2");
  assert.match(framesQuery({ ...where, targetKey: null, fov: 5 }),
    /^\/api\/frames\?ra=269\.446\d{3}&dec=4\.768\d{3}&band=2&fov_arcmin=5$/);

  resetApiCheck();
  const ready = await loadFrames(where, apiFetch({
    ...health, [framesQuery(where)]: { status: 200, body: { ...m, base_url: "/frames/barnard/d2/", warnings: [] } },
  }));
  assert.equal(ready.status, "ready");
  assert.equal(ready.base, "/frames/barnard/d2");

  resetApiCheck();
  const working = await loadFrames(where, apiFetch({
    ...health, [framesQuery(where)]: { status: 202, body: { status: "working", message: "Preparing…" } },
  }));
  assert.deepEqual(working, { status: "working", message: "Preparing…" });

  resetApiCheck();
  const none = await loadFrames(where, apiFetch({ ...health, [framesQuery(where)]: { status: 404, body: { error: "No SPHEREx images" } } }));
  assert.deepEqual(none, { status: "none", message: "No SPHEREx images" });

  resetApiCheck();
  await assert.rejects(
    loadFrames(where, apiFetch({ ...health, [framesQuery(where)]: { status: 502, body: { error: "IRSA did not answer" } } })),
    /IRSA did not answer/,
  );

  resetApiCheck();
  await assert.rejects(
    loadFrames({ ...where, targetKey: null }, apiFetch({
      ...health,
      [framesQuery({ ...where, targetKey: null })]: { status: 503, body: { error: "needs backend/app/render.py" } },
    })),
    /render\.py/,
  );
  resetApiCheck();
});

test("without the API: prepared files for targets, an honest message for other positions", async () => {
  const m = barnard();
  resetApiCheck();
  const files = apiFetch({ "frames/barnard/d2/manifest.json": { status: 200, body: m } });
  const ready = await loadFrames({ targetKey: "barnard", det: 2, fov: 3 }, files);
  assert.equal(ready.base, "frames/barnard/d2");
  resetApiCheck();
  const none = await loadFrames({ targetKey: null, ra: 10, dec: 20, det: 2, fov: 3 }, files);
  assert.equal(none.status, "none");
  assert.match(none.message, /need the data API/);
  resetApiCheck();
});

test("player: stepping, looping, blink pair and speed", () => {
  assert.equal(nextIndex(0, 3, false), 1);
  assert.equal(nextIndex(2, 3, false), null);
  assert.equal(nextIndex(2, 3, true), 0);
  assert.equal(prevIndex(0, 3, false), null);
  assert.equal(prevIndex(0, 3, true), 2);
  assert.equal(nextIndex(0, 0, true), null);
  assert.deepEqual(defaultBlinkPair(5), [0, 4]);
  assert.deepEqual(defaultBlinkPair(1), [0, 0]);
  assert.equal(intervalMs(2), 500);
  assert.equal(intervalMs(0.5), 2000);
});

test("the player's speeds are the ones a shared link may carry", () => {
  assert.deepEqual(SPEEDS, URL_SPEEDS);
});
