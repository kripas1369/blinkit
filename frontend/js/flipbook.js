// The SPHEREx flipbook panel: images (play/blink), color composite, minus-median, add visits, or difference.
import { buildCompositeFromManifest } from "./composite.js";
import { findPair, pairFacts } from "./diffview.js";
import { flagLegendHtml } from "./flags_legend.js";
import { frameLabel, loadExtra, loadFrames, loadImage, loadIndex, loadSidecar, spanDays } from "./frames.js";
import {
  BLINK_SPEEDS, DEFAULT_BLINK_SPEED, DEFAULT_SPEED, SPEEDS, defaultBlinkPair, intervalMs, nextIndex, prevIndex,
} from "./player.js";
import { publicArchiveMessage, publicWarnings } from "./public_messages.js";
import { directionText, expectedShift, gaiaTarget, percentAt, pixelUnder, visibleStars } from "./sky.js";

const $ = (id) => document.getElementById(id);
const POLL_MS = 10000;
export const GAIA_LIMITS = [
  { value: "14", label: "brighter than G = 14" },
  { value: "16", label: "brighter than G = 16" },
  { value: "18", label: "brighter than G = 18" },
  { value: "all", label: "all Gaia stars" },
];
export const DEFAULT_GAIA_LIMIT = "16";

/** Draw Gaia markers for frame `i` into `layer` (a positioned box over the frame). */
export function drawGaia(layer, gaia, i, size, gMax, { trail = true } = {}) {
  layer.replaceChildren();
  if (!gaia) return;
  for (const star of visibleStars(gaia, gMax)) {
    if (!Array.isArray(star.xy) || !star.xy[i]) continue;
    if (star.target && trail) {
      star.xy.forEach((xy, k) => {
        if (k === i || !xy) return;
        const dot = document.createElement("span");
        dot.className = "gaia-trail";
        const { left, top } = percentAt(xy, size);
        Object.assign(dot.style, { left: `${left}%`, top: `${top}%` });
        layer.append(dot);
      });
    }
    const mark = document.createElement("span");
    mark.className = star.target ? "gaia-mark gaia-target" : "gaia-mark";
    const { left, top } = percentAt(star.xy[i], size);
    Object.assign(mark.style, { left: `${left}%`, top: `${top}%`, width: `${100 / size}%` });
    mark.title = `Gaia DR3 ${star.source_id}` + (star.g_mag !== null ? `, G ${star.g_mag}` : "") +
      (star.has_motion ? "" : " (no Gaia proper motion)");
    layer.append(mark);
  }
}

/** CatWISE2020 sources of a wise.json (spherex-blink-wise/1 lists them under "sources"). */
export function wiseSources(wise) {
  return wise ? wise.sources || wise.stars || [] : [];
}

/** CatWISE2020 markers (orange squares; Gaia markers are white circles). */
export function drawWise(layer, wise, i, size) {
  layer.replaceChildren();
  for (const src of wiseSources(wise)) {
    const mark = document.createElement("span");
    mark.className = src.target ? "wise-mark wise-target" : "wise-mark";
    const { left, top } = percentAt(src.xy[i], size);
    Object.assign(mark.style, { left: `${left}%`, top: `${top}%`, width: `${100 / size}%` });
    const name = src.source_name || src.source_id;
    mark.title = `CatWISE2020 ${name}` + (src.w1_mag != null ? `, W1 ${src.w1_mag}` : "") +
      (src.w2_mag != null ? `, W2 ${src.w2_mag}` : "");
    layer.append(mark);
  }
}

export function gaiaNote(gaia, pixelArcsec) {
  if (!gaia) return "No Gaia markers for these frames.";
  const t = gaiaTarget(gaia);
  const base = "Circles: where Gaia DR3 says each star should be on this visit's date (its 2016.0 position moved " +
    "with its proper motion; parallax not applied). ";
  if (!t) return `${base}Gaia DR3 lists no star within 3″ of the frame centre, so there is no target marker.`;
  const shift = expectedShift(gaia, 0, gaia.frames.length - 1, pixelArcsec);
  return `${base}Thick circle: the target, Gaia DR3 ${t.source_id}` + (t.g_mag !== null ? ` (G ${t.g_mag})` : "") +
    `; dots are its predicted places on the other visits. Gaia: it moves ${shift.px.toFixed(2)} px ` +
    `(${shift.arcsec.toFixed(1)}″) from the first to the last visit` +
    (shift.px >= 0.05 ? `, toward the ${directionText(shift.dx, shift.dy)}.` : ".");
}

/** How the grey levels relate to brightness (manifest `scale`). */
export function scaleText(scale) {
  return scale.stretch === "asinh"
    ? "Every frame uses the same brightness scale, stretched (asinh) so faint light and bright stars both show; " +
      "grey levels are not proportional to brightness, so do not judge brightness changes by eye."
    : "Every frame uses the same brightness scale.";
}

function fillSpeeds(select, speeds, chosen) {
  select.innerHTML = speeds.map((s) => `<option value="${s}">${s} per second</option>`).join("");
  select.value = String(chosen);
}

/**
 * `onDetector(n)`: the user picked a detector that has prepared frames.
 * `onFrames(loaded | null)`: frames were shown ({ manifest, base, gaia, where }) or cleared.
 * `onPixel({ x, y })`: the user clicked a pixel of the frame (PNG pixels, 0 = first).
 * `onVisit(i)`: frame `i` is now on screen.
 * `view`: the link's starting view ({ mode, a, b, gaia, flags, speed } from urlstate.js).
 * `onView(changes)`: the user changed one of those keys (mode flip|blink|minus|stack|diff; a/b for blink/diff).
 */
export function createFlipbook({
  onDetector, onFrames = () => {}, onPixel = () => {}, onVisit = () => {}, view = {}, onView = () => {},
}) {
  const el = {
    gaia: $("flip-gaia"), wise: $("flip-wise"), showGaia: $("flip-show-gaia"), showWise: $("flip-show-wise"),
    gaiaMag: $("flip-gaia-mag"), gaiaNoteBox: $("flip-gaia-note"), flagLegend: $("flip-flag-legend"),
    detBar: $("flip-det-bar"),
    stage: $("flip-stage"), img: $("flip-img"), flags: $("flip-flags"), message: $("flip-message"),
    summary: $("flip-summary"), label: $("flip-label"), note: $("flip-note"), cautions: $("flip-cautions"),
    prev: $("flip-prev"), play: $("flip-play"), next: $("flip-next"), slider: $("flip-slider"),
    position: $("flip-position"), speed: $("flip-speed"), loop: $("flip-loop"), showFlags: $("flip-show-flags"),
    modeImages: $("mode-images"), modeComposite: $("mode-composite"), modeMinus: $("mode-minus"),
    modeStack: $("mode-stack"), modeDiff: $("mode-diff"),
    imagesControls: $("images-controls"), compositeControls: $("composite-controls"),
    minusControls: $("minus-controls"),
    stackControls: $("stack-controls"), diffControls: $("diff-controls"),
    compositeFacts: $("composite-facts"),
    modePlay: $("mode-play"), modeBlink: $("mode-blink"), playControls: $("play-controls"),
    blinkControls: $("blink-controls"), blinkA: $("blink-a"), blinkB: $("blink-b"),
    blinkToggle: $("blink-toggle"), blinkSpeed: $("blink-speed"),
    minusSlider: $("minus-slider"), minusPosition: $("minus-position"),
    stackList: $("stack-visit-list"), stackNoise: $("stack-noise"),
    flipDiffA: $("flip-diff-a"), flipDiffB: $("flip-diff-b"), flipDiffDefault: $("flip-diff-default"),
    flipDiffFacts: $("flip-diff-facts"),
    overlays: document.querySelectorAll(".flip-target, .flip-compass, .flip-scale"),
    scale: document.querySelector(".flip-scale"),
  };
  fillSpeeds(el.speed, SPEEDS, DEFAULT_SPEED);
  fillSpeeds(el.blinkSpeed, BLINK_SPEEDS, DEFAULT_BLINK_SPEED);
  el.gaiaMag.innerHTML = GAIA_LIMITS.map((o) => `<option value="${o.value}">${o.label}</option>`).join("");
  el.gaiaMag.value = DEFAULT_GAIA_LIMIT;
  if (SPEEDS.includes(view.speed)) el.speed.value = String(view.speed);
  if (typeof view.flags === "boolean") el.showFlags.checked = view.flags;
  if (typeof view.gaia === "boolean") el.showGaia.checked = view.gaia;
  if (typeof view.wise === "boolean" && el.showWise) el.showWise.checked = view.wise;

  let manifest = null;
  let wantedPair = Number.isInteger(view.a) && Number.isInteger(view.b) ? [view.a, view.b] : null;
  let gaia = null;
  let wise = null;
  let diff = null;
  let stack = null;
  let pollTimer = null;
  let folder = "";
  let index = 0;
  let timer = null;
  // Top-level modes match urlstate: flip|blink|composite|minus|stack|diff. "play" is Images/Play.
  let mode = view.mode === "blink" ? "blink"
    : view.mode === "composite" ? "composite"
      : view.mode === "minus" ? "minus"
        : view.mode === "stack" ? "stack"
          : view.mode === "diff" ? "diff" : "flip";
  let blinkShowingA = true;
  let loadVersion = 0;
  let available = null;
  let stackChosen = null; // epoch_id list, or null = all
  let compositeUrl = null;
  let compositeBuild = 0;
  // Frames start moving by themselves, except for people whose system asks for less motion.
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const count = () => (manifest ? manifest.frames.length : 0);
  const isImages = () => mode === "flip" || mode === "blink";

  function stop() {
    clearInterval(timer);
    timer = null;
    el.play.textContent = "Play";
    el.play.setAttribute("aria-label", "Play");
    el.blinkToggle.textContent = "Start blinking";
  }

  function setControlsEnabled(on) {
    for (const c of [el.prev, el.play, el.next, el.slider, el.speed, el.loop, el.blinkA, el.blinkB,
      el.blinkToggle, el.blinkSpeed, el.showFlags, el.minusSlider, el.flipDiffA, el.flipDiffB,
      el.flipDiffDefault]) {
      if (c) c.disabled = !on;
    }
    el.showGaia.disabled = el.gaiaMag.disabled = !(on && gaia && isImages());
    if (el.showWise) el.showWise.disabled = !(on && wise && isImages());
    for (const box of el.stackList?.querySelectorAll("input") || []) box.disabled = !on;
  }

  const gaiaLimit = () => (el.gaiaMag.value === "all" ? null : Number(el.gaiaMag.value));

  function renderGaia() {
    el.gaia.hidden = !(manifest && gaia && el.showGaia.checked);
    if (!el.gaia.hidden) drawGaia(el.gaia, gaia, index, manifest.size_px, gaiaLimit());
  }

  function renderWise() {
    if (!el.wise) return;
    el.wise.hidden = !(manifest && wise && el.showWise?.checked);
    if (!el.wise.hidden) drawWise(el.wise, wise, index, manifest.size_px);
  }

  function renderFlagLegend() {
    if (!el.flagLegend) return;
    const frame = manifest ? manifest.frames[index] : null;
    const html = frame?.flag_counts ? flagLegendHtml(frame.flag_counts) : "";
    el.flagLegend.innerHTML = html;
    el.flagLegend.hidden = !html;
  }

  function renderDetBar(active) {
    if (!el.detBar) return;
    for (const button of el.detBar.querySelectorAll("[data-det]")) {
      const n = Number(button.dataset.det);
      const on = n === active;
      button.classList.toggle("det-active", on);
      button.setAttribute("aria-pressed", String(on));
    }
  }

  function showMessage(text, detectorChoices = []) {
    stop();
    manifest = null;
    gaia = null;
    wise = null;
    diff = null;
    stack = null;
    el.gaia.hidden = true;
    if (el.wise) el.wise.hidden = true;
    if (el.flagLegend) {
      el.flagLegend.innerHTML = "";
      el.flagLegend.hidden = true;
    }
    el.gaiaNoteBox.textContent = "";
    el.img.hidden = true;
    el.flags.hidden = true;
    el.overlays.forEach((o) => { o.hidden = true; });
    el.message.hidden = false;
    el.message.textContent = text;
    for (const d of detectorChoices) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-small";
      button.textContent = `Show D${d}`;
      button.addEventListener("click", () => onDetector(d));
      el.message.append(" ", button);
    }
    el.summary.textContent = "";
    el.label.textContent = "";
    el.note.textContent = "";
    el.cautions.hidden = true;
    el.position.textContent = "–";
    setControlsEnabled(false);
  }

  function renderImageVisit(i) {
    index = i;
    const frame = manifest.frames[i];
    el.img.src = `${folder}/${frame.png}`;
    el.img.alt = `SPHEREx D${frame.band} image of ${manifest.label}, visit ${i + 1}, ${frame.date_iso}`;
    el.flags.hidden = !(el.showFlags.checked && frame.flags_png);
    if (frame.flags_png) el.flags.src = `${folder}/${frame.flags_png}`;
    el.label.textContent = frameLabel(frame, i, count());
    el.slider.value = String(i);
    el.position.textContent = `${i + 1} of ${count()}`;
    renderGaia();
    renderWise();
    renderFlagLegend();
    onVisit(i);
  }

  function renderMinus(i) {
    index = i;
    const frame = manifest.frames[i];
    const mm = diff?.minus_median?.frames?.find((f) => f.epoch_id === frame.epoch_id);
    el.flags.hidden = true;
    el.gaia.hidden = true;
    if (el.wise) el.wise.hidden = true;
    if (el.flagLegend) el.flagLegend.hidden = true;
    if (!mm) {
      el.img.hidden = true;
      el.label.textContent = `Visit ${i + 1}: no minus-median frame was made yet.`;
    } else {
      el.img.hidden = false;
      el.img.src = `${folder}/${mm.png}`;
      el.img.alt = `Visit ${i + 1} minus the median of all visits`;
      el.label.textContent = `Visit ${i + 1} of ${count()} · ${frame.date_iso} · minus median` +
        (mm.sky_change != null ? ` · sky offset ${mm.sky_change >= 0 ? "+" : ""}${mm.sky_change} MJy/sr removed` : "");
    }
    if (el.minusSlider) {
      el.minusSlider.value = String(i);
      el.minusPosition.textContent = `${i + 1} of ${count()}`;
    }
    onVisit(i);
  }

  function renderStack() {
    el.flags.hidden = true;
    el.gaia.hidden = true;
    if (el.wise) el.wise.hidden = true;
    if (el.flagLegend) el.flagLegend.hidden = true;
    if (!stack) {
      el.img.hidden = true;
      el.label.textContent = "No stacked image yet.";
      if (el.stackNoise) el.stackNoise.textContent = "";
      return;
    }
    el.img.hidden = false;
    el.img.src = stack.png_url || `${folder}/stack.png`;
    el.img.alt = `Stack of ${stack.n_visits} visits of ${manifest.label}`;
    el.label.textContent = `Add visits · ${stack.n_visits} visit${stack.n_visits === 1 ? "" : "s"} · ` +
      `${stack.n_images} exposures · noise ${stack.noise_ratio_vs_single_visit}× lower than one visit`;
    if (el.stackNoise) {
      el.stackNoise.textContent = `Noise per pixel ${stack.noise_per_pixel} ${stack.unit || "MJy/sr"} ` +
        `(single visit ${stack.single_visit_noise}); gain ${stack.noise_ratio_vs_single_visit}× ` +
        `(theory about ${Math.sqrt(stack.n_visits).toFixed(2)}× for ${stack.n_visits} independent visits).`;
    }
  }

  function renderDiffPair() {
    el.flags.hidden = true;
    el.gaia.hidden = true;
    if (el.wise) el.wise.hidden = true;
    if (el.flagLegend) el.flagLegend.hidden = true;
    const a = Number(el.flipDiffA.value);
    const b = Number(el.flipDiffB.value);
    const pair = diff ? findPair(diff, a, b) : null;
    const ia = manifest.frames.findIndex((f) => f.epoch_id === a);
    const ib = manifest.frames.findIndex((f) => f.epoch_id === b);
    if (!pair || ia < 0 || ib < 0) {
      el.img.hidden = true;
      el.label.textContent = "No difference map for this visit pair.";
      if (el.flipDiffFacts) el.flipDiffFacts.textContent = "";
      return;
    }
    el.img.hidden = false;
    el.img.src = `${folder}/${pair.png}`;
    el.img.alt = `Difference visit ${a} to ${b}`;
    const fa = manifest.frames[ia];
    const fb = manifest.frames[ib];
    el.label.textContent = `Difference · A visit ${ia + 1} (${fa.date_iso.slice(0, 10)}) → ` +
      `B visit ${ib + 1} (${fb.date_iso.slice(0, 10)}) · strongest +${pair.max_sigma}σ / ${pair.min_sigma}σ`;
    if (el.flipDiffFacts) el.flipDiffFacts.textContent = pairFacts(pair, fa, fb);
  }

  async function renderComposite() {
    if (!manifest || count() < 2) {
      el.img.hidden = true;
      el.flags.hidden = true;
      el.gaia.hidden = true;
      if (el.wise) el.wise.hidden = true;
      if (el.flagLegend) el.flagLegend.hidden = true;
      el.label.textContent = "Need at least two visits for a color composite.";
      if (el.compositeFacts) el.compositeFacts.textContent = "";
      return;
    }
    const buildId = ++compositeBuild;
    el.flags.hidden = true;
    el.gaia.hidden = true;
    if (el.wise) el.wise.hidden = true;
    if (el.flagLegend) el.flagLegend.hidden = true;
    el.label.textContent = "Building color composite…";
    if (el.compositeFacts) el.compositeFacts.textContent = "";
    try {
      const built = await buildCompositeFromManifest(manifest, folder);
      if (buildId !== compositeBuild || mode !== "composite") return;
      if (!built?.canvas) {
        el.img.hidden = true;
        el.label.textContent = "Could not build a color composite from these visits.";
        return;
      }
      if (compositeUrl) URL.revokeObjectURL(compositeUrl);
      compositeUrl = built.canvas.toDataURL("image/png");
      el.img.hidden = false;
      el.img.src = compositeUrl;
      el.img.alt = `Color composite of ${manifest.label}, D${manifest.band}`;
      const { pick } = built;
      const date = (f) => (f.date_iso || "").slice(0, 10);
      if (pick.twoEpoch) {
        el.label.textContent = `Color composite · 2 visits · cyan = ${date(pick.first)} · red = ${date(pick.last)}`;
        if (el.compositeFacts) {
          el.compositeFacts.textContent =
            "Two visits: earliest → cyan, latest → red. A mover leaves a cyan trail and appears as a red dot.";
        }
      } else {
        el.label.textContent =
          `Color composite · blue ${date(pick.first)} · green ${date(pick.middle)} · red ${date(pick.last)}`;
        if (el.compositeFacts) {
          el.compositeFacts.textContent =
            "Earliest visit → blue channel, middle → green, latest → red. White/grey = same in all visits.";
        }
      }
    } catch (err) {
      if (buildId !== compositeBuild) return;
      el.img.hidden = true;
      el.label.textContent = `Color composite failed: ${err.message || err}`;
    }
  }

  function render(i = index) {
    if (!manifest) return;
    if (mode === "composite") return renderComposite();
    if (mode === "minus") return renderMinus(i);
    if (mode === "stack") return renderStack();
    if (mode === "diff") return renderDiffPair();
    renderImageVisit(i);
  }

  function step(direction) {
    if (mode === "stack" || mode === "diff" || mode === "composite") return;
    const loop = mode === "minus" ? true : el.loop.checked;
    const n = direction > 0 ? nextIndex(index, count(), loop) : prevIndex(index, count(), loop);
    if (n === null) {
      stop();
      return;
    }
    render(n);
  }

  function togglePlay() {
    if (timer) return stop();
    if (mode !== "flip") setMode("flip");
    if (!el.loop.checked && index === count() - 1) render(0);
    timer = setInterval(() => step(1), intervalMs(Number(el.speed.value)));
    el.play.textContent = "Pause";
    el.play.setAttribute("aria-label", "Pause");
  }

  function blinkPair() {
    return [Number(el.blinkA.value), Number(el.blinkB.value)];
  }

  function pairView() {
    const [a, b] = blinkPair();
    return a !== b ? { a, b } : { a: null, b: null };
  }

  function toggleBlink() {
    if (timer) return stop();
    if (mode !== "blink") setMode("blink");
    const [a, b] = blinkPair();
    blinkShowingA = true;
    render(a);
    timer = setInterval(() => {
      blinkShowingA = !blinkShowingA;
      render(blinkShowingA ? a : b);
    }, intervalMs(Number(el.blinkSpeed.value)));
    el.blinkToggle.textContent = "Stop blinking";
  }

  function setMode(next) {
    stop();
    mode = next;
    const top = {
      images: isImages(),
      composite: mode === "composite",
      minus: mode === "minus",
      stack: mode === "stack",
      diff: mode === "diff",
    };
    el.modeImages.setAttribute("aria-selected", String(top.images));
    el.modeComposite?.setAttribute("aria-selected", String(top.composite));
    el.modeMinus.setAttribute("aria-selected", String(top.minus));
    el.modeStack.setAttribute("aria-selected", String(top.stack));
    el.modeDiff.setAttribute("aria-selected", String(top.diff));
    el.imagesControls.hidden = !top.images;
    if (el.compositeControls) el.compositeControls.hidden = !top.composite;
    el.minusControls.hidden = !top.minus;
    el.stackControls.hidden = !top.stack;
    el.diffControls.hidden = !top.diff;
    el.modePlay.setAttribute("aria-selected", String(mode === "flip"));
    el.modeBlink.setAttribute("aria-selected", String(mode === "blink"));
    el.playControls.hidden = mode !== "flip";
    el.blinkControls.hidden = mode !== "blink";
    el.showGaia.disabled = el.gaiaMag.disabled = !(manifest && gaia && isImages());
    if (el.showWise) el.showWise.disabled = !(manifest && wise && isImages());
    if (manifest) {
      if (mode === "blink") {
        fillBlinkChoices();
        render(blinkPair()[0]);
      } else if (mode === "diff") {
        fillDiffChoices();
        render();
      } else if (mode === "stack") loadStack();
      else render(index);
    }
  }

  function restartIfRunning() {
    if (!timer) return;
    stop();
    if (mode === "flip") togglePlay();
    else if (mode === "blink") toggleBlink();
  }

  /** Blink UI uses frame indexes; Diff UI uses epoch_id. Shared links may carry either. */
  function resolveBlinkIndexes() {
    const fallback = defaultBlinkPair(count());
    if (!wantedPair) return fallback;
    const [a, b] = wantedPair;
    if (Number.isInteger(a) && Number.isInteger(b) && a >= 0 && b >= 0 && a < count() && b < count() && a !== b) {
      return [a, b];
    }
    const ia = manifest.frames.findIndex((f) => f.epoch_id === a);
    const ib = manifest.frames.findIndex((f) => f.epoch_id === b);
    return ia >= 0 && ib >= 0 && ia !== ib ? [ia, ib] : fallback;
  }

  function resolveDiffEpochs() {
    const def = diff?.default_pair;
    if (!def) return null;
    if (!wantedPair) return [def.a, def.b];
    const [a, b] = wantedPair;
    const asEpoch = manifest.frames.some((f) => f.epoch_id === a)
      && manifest.frames.some((f) => f.epoch_id === b)
      && a !== b;
    if (asEpoch) return [a, b];
    if (Number.isInteger(a) && Number.isInteger(b) && a >= 0 && b >= 0 && a < count() && b < count() && a !== b) {
      return [manifest.frames[a].epoch_id, manifest.frames[b].epoch_id];
    }
    return [def.a, def.b];
  }

  function fillBlinkChoices() {
    const options = manifest.frames
      .map((f, i) => `<option value="${i}">${i + 1}: ${f.date_iso.slice(0, 10)}</option>`).join("");
    el.blinkA.innerHTML = options;
    el.blinkB.innerHTML = options;
    const [a, b] = resolveBlinkIndexes();
    el.blinkA.value = String(a);
    el.blinkB.value = String(b);
  }

  function fillDiffChoices() {
    if (!el.flipDiffA || !diff) return;
    const options = manifest.frames
      .map((f, i) => `<option value="${f.epoch_id}">${i + 1}: ${f.date_iso.slice(0, 10)}</option>`).join("");
    el.flipDiffA.innerHTML = options;
    el.flipDiffB.innerHTML = options;
    const pair = resolveDiffEpochs();
    el.flipDiffA.value = String(pair[0]);
    el.flipDiffB.value = String(pair[1]);
  }

  function fillStackChoices() {
    if (!el.stackList) return;
    const chosen = new Set(stackChosen ?? manifest.frames.map((f) => f.epoch_id));
    el.stackList.replaceChildren(...manifest.frames.map((f, i) => {
      const label = document.createElement("label");
      label.className = "check";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = String(f.epoch_id);
      box.checked = chosen.has(f.epoch_id);
      box.addEventListener("change", () => {
        const ids = [...el.stackList.querySelectorAll("input:checked")].map((b) => Number(b.value));
        if (!ids.length) {
          // Do not treat “none checked” as “all visits” — that misleads.
          stackChosen = [];
          stack = null;
          if (el.stackNoise) el.stackNoise.textContent = "Select at least one visit to stack.";
          if (mode === "stack") renderStack();
          return;
        }
        stackChosen = ids.length === manifest.frames.length ? null : ids;
        loadStack();
      });
      label.append(box, document.createTextNode(` Visit ${i + 1}: ${f.date_iso.slice(0, 10)}`));
      return label;
    }));
  }

  async function loadStack() {
    if (!manifest) return;
    if (Array.isArray(stackChosen) && stackChosen.length === 0) {
      stack = null;
      if (el.stackNoise) el.stackNoise.textContent = "Select at least one visit to stack.";
      if (mode === "stack") renderStack();
      return;
    }
    const params = new URLSearchParams();
    if (manifest.target && !String(folder).includes("jobframes")) {
      params.set("target", manifest.target);
    } else {
      params.set("ra", String(manifest.ra));
      params.set("dec", String(manifest.dec));
    }
    params.set("band", String(manifest.band));
    if (stackChosen && stackChosen.length) params.set("visits", stackChosen.join(","));
    try {
      const resp = await fetch(`/api/stack?${params}`, { cache: "no-cache" });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${resp.status}`);
      }
      stack = await resp.json();
      if (!stack.png_url) stack.png_url = `${folder}/${stack.png || "stack.png"}`;
    } catch (err) {
      stack = null;
      if (el.stackNoise) el.stackNoise.textContent = `Could not load the stack: ${err.message}`;
    }
    if (mode === "stack") renderStack();
  }

  function describe(m, fov) {
    const n = m.frames.length;
    el.summary.textContent = `${m.label} · D${m.band} · ${n} visit${n === 1 ? "" : "s"}` +
      (n > 1 ? ` over ${spanDays(m.frames)} days` : "");
    const sizeNote = fov !== m.fov_arcmin
      ? ` These frames are ${m.fov_arcmin}′ wide; other sizes need the data API.` : "";
    const howMade = m.mode === "single"
      ? "Each frame is one SPHEREx exposure (not an add-up of the whole visit). "
      : "Each frame adds up several exposures of one visit, weighted by their noise, so faint things show " +
        "better; flagged pixels are left out of the add-up. ";
    el.note.textContent = `Real SPHEREx data from NASA IRSA, lined up north-up on ${m.size_px} × ${m.size_px} ` +
      `pixels of ${m.pixel_arcsec}″. ${howMade}${scaleText(m.scale)} Each exposure also sees a slightly ` +
      `different wavelength (shown in the label), so brightness can differ for that reason too. ` +
      (m.mode === "single"
        ? "Striped pixels have no value in the SPHEREx file (for example a saturated star core). "
        : "Striped pixels have no usable value: the files have none there (for example a saturated star " +
          "core), or every exposure flagged that pixel (turn on the flagged-pixel overlay to see which). ") +
      (m.position_source.includes("2026") ? "The dashed ring marks the target's 2026 position. "
        : "The dashed ring marks the centre of the frame. ") +
      (m.made_at ? ` Prepared ${m.made_at}.` : "") +
      sizeNote;
    el.scale.style.width = `${(60 / m.pixel_arcsec / m.size_px) * 100}%`;
    const list = el.cautions.querySelector("ul");
    list.replaceChildren(...(m.notes || []).map((text) => {
      const item = document.createElement("li");
      item.textContent = text;
      return item;
    }));
    el.cautions.hidden = !(m.notes && m.notes.length);
  }

  async function preparedBands(targetKey) {
    if (!targetKey) return [];
    try {
      if (available === null) available = await loadIndex();
    } catch {
      return [];
    }
    return available[targetKey] || [];
  }

  /**
   * Show the frames for a position and detector ({ targetKey, label, ra, dec, det, fov }).
   * While the data API prepares frames for a new position, it asks again every 10 seconds.
   */
  async function show(where) {
    const version = ++loadVersion;
    clearTimeout(pollTimer);
    stop();
    const { label, det } = where;
    const name = label || "this position";
    try {
      showMessage(`Loading SPHEREx frames for ${name}, D${det}…`);
      renderDetBar(det);
      onFrames(null);
      const result = await loadFrames(where);
      if (version !== loadVersion) return;
      if (result.status === "working") {
        showMessage(`${result.message} Checking again every ${POLL_MS / 1000} seconds.`);
        pollTimer = setTimeout(() => { if (version === loadVersion) show(where); }, POLL_MS);
        return;
      }
      if (result.status === "none") {
        const bands = (await preparedBands(where.targetKey)).filter((b) => b !== det);
        if (version !== loadVersion) return;
        const hint = bands.length
          ? `${result.message} Try another detector (D1–D6) or the prepared bands below.`
          : `${result.message} Try another detector, a wider field (up to 30′), or wait if the data API is preparing this patch.`;
        showMessage(bands.length ? `${hint} Prepared:` : hint, bands);
        return;
      }
      const m = result.manifest;
      const dir = result.base;
      const [extraGaia, extraWise, extraDiff] = await Promise.all([
        loadSidecar(where, "gaia", dir).catch(() => null),
        loadSidecar(where, "wise", dir).catch(() => null),
        loadExtra(dir, "diff.json").catch(() => null),
        ...m.frames.flatMap((f) => [f.png, f.flags_png].filter(Boolean).map((p) => loadImage(`${dir}/${p}`))),
      ]);
      if (version !== loadVersion) return;
      manifest = m;
      gaia = extraGaia && extraGaia.frames?.length === m.frames.length ? extraGaia : null;
      wise = extraWise && extraWise.frames?.length === m.frames.length ? extraWise : null;
      diff = extraDiff;
      stack = null;
      stackChosen = null;
      folder = dir;
      el.message.hidden = true;
      el.img.hidden = false;
      el.overlays.forEach((o) => { o.hidden = false; });
      el.slider.max = String(count() - 1);
      if (el.minusSlider) el.minusSlider.max = String(count() - 1);
      setControlsEnabled(true);
      el.blinkA.disabled = el.blinkB.disabled = el.blinkToggle.disabled = count() < 2;
      el.modeMinus.disabled = !(diff && diff.minus_median?.frames?.length);
      el.modeDiff.disabled = !(diff && diff.pairs?.length);
      el.modeStack.disabled = count() < 1;
      if (el.modeComposite) el.modeComposite.disabled = count() < 2;
      fillBlinkChoices();
      fillDiffChoices();
      fillStackChoices();
      describe(m, where.fov);
      const friendly = publicWarnings(result.warnings);
      if (friendly.length) {
        const alert = document.createElement("span");
        alert.className = "flip-note-alert";
        alert.textContent = ` NASA IRSA is down right now — ${friendly.join(" ")}`;
        el.note.appendChild(alert);
      }
      el.gaiaNoteBox.textContent = gaiaNote(gaia, m.pixel_arcsec);
      setMode(mode);
      onFrames({ manifest: m, base: dir, gaia, wise, diff, where });
      renderDetBar(where.det);
      if (count() > 1 && !reduceMotion.matches && isImages()) {
        (mode === "blink" ? toggleBlink : togglePlay)();
      }
    } catch (err) {
      if (version !== loadVersion) return;
      showMessage(`Could not load the SPHEREx frames: ${publicArchiveMessage(err.message)}`);
    }
  }

  el.prev.addEventListener("click", () => { stop(); step(-1); });
  el.next.addEventListener("click", () => { stop(); step(1); });
  el.play.addEventListener("click", togglePlay);
  el.slider.addEventListener("input", () => { stop(); render(Number(el.slider.value)); });
  el.speed.addEventListener("change", () => { restartIfRunning(); onView({ speed: Number(el.speed.value) }); });
  el.blinkSpeed.addEventListener("change", restartIfRunning);
  el.blinkToggle.addEventListener("click", toggleBlink);
  for (const [select, side] of [[el.blinkA, 0], [el.blinkB, 1]]) {
    select.addEventListener("change", () => {
      stop();
      render(blinkPair()[side]);
      wantedPair = blinkPair();
      onView({ mode: "blink", ...pairView() });
    });
  }
  el.modeImages.addEventListener("click", () => {
    setMode("flip");
    onView({ mode: "flip", a: null, b: null });
  });
  el.modeComposite?.addEventListener("click", () => {
    setMode("composite");
    onView({ mode: "composite", a: null, b: null });
  });
  el.modeMinus.addEventListener("click", () => {
    setMode("minus");
    onView({ mode: "minus", a: null, b: null });
  });
  el.modeStack.addEventListener("click", () => {
    setMode("stack");
    onView({ mode: "stack", a: null, b: null });
  });
  el.modeDiff.addEventListener("click", () => {
    setMode("diff");
    const a = Number(el.flipDiffA?.value);
    const b = Number(el.flipDiffB?.value);
    onView({ mode: "diff", a: Number.isInteger(a) ? a : null, b: Number.isInteger(b) ? b : null });
  });
  el.modePlay.addEventListener("click", () => { setMode("flip"); onView({ mode: "flip", a: null, b: null }); });
  el.modeBlink.addEventListener("click", () => { setMode("blink"); onView({ mode: "blink", ...pairView() }); });
  el.minusSlider?.addEventListener("input", () => { stop(); render(Number(el.minusSlider.value)); });
  for (const select of [el.flipDiffA, el.flipDiffB]) {
    select?.addEventListener("change", () => {
      let a = Number(el.flipDiffA.value);
      let b = Number(el.flipDiffB.value);
      if (a === b) {
        const ids = manifest.frames.map((f) => f.epoch_id);
        const k = ids.indexOf(a);
        b = ids[k + 1] ?? ids[k - 1];
        el.flipDiffB.value = String(b);
      }
      if (manifest.frames.findIndex((f) => f.epoch_id === a) > manifest.frames.findIndex((f) => f.epoch_id === b)) {
        [a, b] = [b, a];
        el.flipDiffA.value = String(a);
        el.flipDiffB.value = String(b);
      }
      wantedPair = [a, b];
      render();
      onView({ mode: "diff", a, b });
    });
  }
  el.flipDiffDefault?.addEventListener("click", () => {
    if (!diff) return;
    el.flipDiffA.value = String(diff.default_pair.a);
    el.flipDiffB.value = String(diff.default_pair.b);
    wantedPair = [diff.default_pair.a, diff.default_pair.b];
    render();
    onView({ mode: "diff", a: diff.default_pair.a, b: diff.default_pair.b });
  });
  el.showFlags.addEventListener("change", () => {
    if (manifest && isImages()) render(index);
    onView({ flags: el.showFlags.checked });
  });
  el.showGaia.addEventListener("change", () => { renderGaia(); onView({ gaia: el.showGaia.checked }); });
  el.gaiaMag.addEventListener("change", renderGaia);
  el.showWise?.addEventListener("change", () => { renderWise(); onView({ wise: el.showWise.checked }); });
  el.detBar?.addEventListener("click", (e) => {
    const button = e.target.closest("[data-det]");
    if (button) onDetector(Number(button.dataset.det));
  });
  el.stage.addEventListener("click", (e) => {
    if (!manifest || !isImages()) return;
    const p = pixelUnder(e.clientX, e.clientY, el.img.getBoundingClientRect(), manifest.size_px);
    if (p) onPixel(p);
  });
  el.stage.tabIndex = 0;
  el.stage.addEventListener("keydown", (e) => {
    if (!manifest) return;
    if (e.key === "ArrowRight") { stop(); step(1); e.preventDefault(); }
    if (e.key === "ArrowLeft") { stop(); step(-1); e.preventDefault(); }
    if (e.key === " " && isImages()) {
      (mode === "blink" ? toggleBlink : togglePlay)();
      e.preventDefault();
    }
  });

  showMessage("Pick one of the 5 official targets, or type a position, to see its SPHEREx visits.");
  setMode(mode);
  return { show, gaiaLimit: () => el.gaiaMag.value };
}
