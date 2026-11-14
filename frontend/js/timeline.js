// Coverage timeline: when SPHEREx looked at the position, one row per detector, from /api/coverage (or the
// prepared frames/<target>/coverage.json, made by backend/app/coverage.py). Each tick is one image; each bar
// is one visit, grouped per detector with the same rule as backend/app/archive.group_epochs, so a row's bars
// are the visits the flipbook can show for that detector.
import { hasApi, loadExtra, remember, FRAMES_ROOT } from "./frames.js";
import { DETECTORS } from "./urlstate.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

export const EPOCH_GAP_DAYS = 30;
export const EPOCH_MAX_SPAN_DAYS = 60;
const MJD_UNIX_EPOCH = 40587;
const SVG_W = 640;
const ROW_H = 26;
const PAD = { left: 44, right: 12, top: 22, bottom: 30 };

export const mjdToDate = (mjd) => new Date((mjd - MJD_UNIX_EPOCH) * 86400000);
const isoDay = (mjd) => mjdToDate(mjd).toISOString().slice(0, 10);

/** Visits of one detector's images (sorted or not): [{ mjd_min, mjd_max, n }]. */
export function groupVisits(mjds, gap = EPOCH_GAP_DAYS, maxSpan = EPOCH_MAX_SPAN_DAYS) {
  const visits = [];
  for (const t of [...mjds].sort((a, b) => a - b)) {
    const last = visits[visits.length - 1];
    if (!last || t - last.mjd_max > gap || t - last.mjd_min > maxSpan) visits.push({ mjd_min: t, mjd_max: t, n: 0 });
    const v = visits[visits.length - 1];
    v.mjd_max = t;
    v.n += 1;
  }
  return visits;
}

/** First day of every month (or every 3 months for long spans) between two MJDs. */
export function monthTicks(m0, m1) {
  const start = mjdToDate(m0);
  const months = (m1 - m0) / 30.4;
  const step = months > 15 ? 3 : months > 7 ? 2 : 1;
  const out = [];
  const d = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1));
  while (d.getUTCMonth() % step) d.setUTCMonth(d.getUTCMonth() + 1);
  for (; d.getTime() / 86400000 + MJD_UNIX_EPOCH <= m1; d.setUTCMonth(d.getUTCMonth() + step)) {
    out.push({ mjd: d.getTime() / 86400000 + MJD_UNIX_EPOCH, label: d.toISOString().slice(0, 7) });
  }
  return out;
}

const hhmm = (mjd) => mjdToDate(mjd).toISOString().slice(11, 16);

/** Images of one detector grouped per UTC day: [{ day, mjd_min, mjd_max, n }], in time order. */
export function groupDays(mjds) {
  const days = [];
  for (const t of [...mjds].sort((a, b) => a - b)) {
    const day = isoDay(t);
    const last = days[days.length - 1];
    if (last && last.day === day) {
      last.mjd_max = t;
      last.n += 1;
    } else {
      days.push({ day, mjd_min: t, mjd_max: t, n: 1 });
    }
  }
  return days;
}

export const dayClass = (n) => (n >= 10 ? "tl-many" : n >= 2 ? "tl-some" : "tl-one");

export function dayText(band, d) {
  if (d.n === 1) return `D${band} · ${d.day} ${hhmm(d.mjd_min)} UTC · 1 image`;
  return `D${band} · ${d.day} · ${d.n} images, ${hhmm(d.mjd_min)}–${hhmm(d.mjd_max)} UTC`;
}

/** Rows D1–D6: { band, mjds, visits }. */
export function coverageRows(coverage) {
  return Object.keys(DETECTORS).map(Number).map((band) => {
    const mjds = coverage.images.filter((im) => im.band === band).map((im) => im.mjd);
    return { band, mjds, visits: groupVisits(mjds) };
  });
}

/** The SVG: a line per day with images, a bar per visit, ▼ at the flipbook's frames in the current detector's row. */
export function timelineChart(coverage, { det = null, frameMjds = [] } = {}) {
  const rows = coverageRows(coverage);
  const all = coverage.images.map((im) => im.mjd);
  const pad = Math.max(5, (Math.max(...all) - Math.min(...all)) * 0.03);
  const m0 = Math.min(...all) - pad;
  const m1 = Math.max(...all) + pad;
  const h = PAD.top + rows.length * ROW_H + PAD.bottom;
  const sx = (m) => PAD.left + ((m - m0) / (m1 - m0)) * (SVG_W - PAD.left - PAD.right);
  const rowY = (i) => PAD.top + i * ROW_H;
  const parts = [];
  for (const t of monthTicks(m0, m1)) {
    parts.push(`<line x1="${sx(t.mjd)}" x2="${sx(t.mjd)}" y1="${PAD.top}" y2="${h - PAD.bottom}" class="lc-grid"/>`,
      `<text x="${sx(t.mjd)}" y="${h - PAD.bottom + 16}" class="lc-tick" text-anchor="middle">${t.label}</text>`);
  }
  rows.forEach((row, i) => {
    const y = rowY(i);
    const current = row.band === det;
    parts.push(`<g class="tl-row${current ? " tl-current" : ""}" data-band="${row.band}" role="button" tabindex="0" ` +
      `aria-label="Show detector D${row.band}">` +
      `<title>D${row.band} (${DETECTORS[row.band]}): ${row.mjds.length} images in ${row.visits.length} visits. Click to show this detector.</title>` +
      `<rect x="0" y="${y}" width="${SVG_W}" height="${ROW_H}" class="tl-hit"/>` +
      `<text x="${PAD.left - 8}" y="${y + ROW_H / 2 + 4}" class="lc-tick tl-label" text-anchor="end">D${row.band}</text>`);
    for (const v of row.visits) {
      const x0 = sx(v.mjd_min) - 2;
      const w = Math.max(4, sx(v.mjd_max) - sx(v.mjd_min) + 4);
      parts.push(`<rect x="${x0}" y="${y + 5}" width="${w}" height="${ROW_H - 10}" rx="3" class="tl-visit">` +
        `<title>D${row.band}: ${v.n} images, ${isoDay(v.mjd_min)} to ${isoDay(v.mjd_max)}</title></rect>`);
    }
    parts.push(groupDays(row.mjds).map((d) => {
      const x = sx((d.mjd_min + d.mjd_max) / 2).toFixed(1);
      return `<line x1="${x}" x2="${x}" y1="${y + 7}" y2="${y + ROW_H - 7}" class="tl-image ${dayClass(d.n)}" ` +
        `data-n="${d.n}"><title>${dayText(row.band, d)}</title></line>`;
    }).join(""), "</g>");
    if (current) {
      for (const m of frameMjds) {
        const x = sx(m);
        parts.push(`<path d="M${x - 5},${y - 1}L${x + 5},${y - 1}L${x},${y + 6}Z" class="tl-frame">` +
          `<title>Shown in the flipbook: ${isoDay(m)}</title></path>`);
      }
    }
  });
  return `<svg viewBox="0 0 ${SVG_W} ${h}" class="lc-svg tl-svg" role="img" ` +
    `aria-label="SPHEREx images of this position over time, per detector">${parts.join("")}</svg>`;
}

/** A time span in words: "7 h" under a day, "1 day", "40 days". */
export function spanText(days) {
  if (days < 1) return `${Math.max(1, Math.round(days * 24))} h`;
  const n = Math.round(days);
  return `${n} day${n === 1 ? "" : "s"}`;
}

/** How long each visit lasted and the gaps between them, e.g. "Visit 1: 2025-08-21, 40 days · 162 days later · …". */
export function visitTimesText(visits) {
  return visits.map((v, i) => {
    const gap = i > 0 ? `${spanText(v.mjd_min - visits[i - 1].mjd_max)} later · ` : "";
    return `${gap}visit ${i + 1}: ${isoDay(v.mjd_min)}, lasted ${spanText(v.mjd_max - v.mjd_min)}`;
  }).join(" · ");
}

const releaseLabel = (collection) => collection.replace("spherex_", "");

/** What a release name means, with this position's own dates. */
export function releaseHint(coverage, collection) {
  const label = releaseLabel(collection);
  const m = /^(qr|dr)(\d+)(_deep)?$/.exec(label);
  const kind = !m ? `${label} is a SPHEREx data collection at NASA IRSA.`
    : m[1] === "dr"
      ? `${label.toUpperCase()} = SPHEREx Data Release ${m[2]}: a full release that comes months after the images were taken.`
      : `${label.toUpperCase()} = SPHEREx Quick Release ${m[2]}: images IRSA publishes soon after they are taken.`;
  const deep = m && m[3] ? " Deep: extra visits to the SPHEREx Deep Fields near the ecliptic poles." : "";
  const images = coverage.images.filter((im) => im.release === collection);
  if (!images.length) return kind + deep;
  const mjds = images.map((im) => im.mjd);
  const range = (a, b) => (a === b ? a : `${a} to ${b}`);
  const published = images.map((im) => String(im.release_date).slice(0, 10)).sort();
  return `${kind}${deep} Here: ${images.length} image${images.length === 1 ? "" : "s"}, ` +
    `taken ${range(isoDay(Math.min(...mjds)), isoDay(Math.max(...mjds)))}, ` +
    `published ${range(published[0], published[published.length - 1])}.`;
}

export function exposuresHint(summary) {
  return "Exposure = one SPHEREx snapshot. Each spot of sky lands on two detectors at once (D1 + D4, D2 + D5 or " +
    `D3 + D6), so one exposure usually gives two images: here ${summary.n_exposures} exposures gave ` +
    `${summary.n_images} images.`;
}

/** Words in the summary that explain themselves when clicked: [{ term, hint }]. */
export function summaryTerms(coverage) {
  const s = coverage.summary;
  if (!s.n_images) return [];
  return [
    { term: "exposures", hint: exposuresHint(s) },
    ...Object.keys(s.per_collection || {}).map((c) => ({ term: releaseLabel(c), hint: releaseHint(coverage, c) })),
  ];
}

/** One sentence for the whole position, and two for the flipbook's detector. */
export function timelineSummary(coverage, det = null, nFrames = null) {
  const s = coverage.summary;
  if (!s.n_images) return ["SPHEREx has no images of this position yet."];
  const releases = Object.entries(s.per_collection || {}).map(([c, n]) => `${releaseLabel(c)} ${n}`).join(", ");
  const all = coverage.images.map((im) => im.mjd);
  const out = [`${s.n_images} images (${s.n_exposures} exposures) from ${s.first} to ${s.last} ` +
    `(${spanText(Math.max(...all) - Math.min(...all))})` +
    `${releases ? ` · releases: ${releases}` : ""} · newest image released ${String(s.latest_release).slice(0, 10)} · ` +
    `IRSA asked ${coverage.asked_at}.`];
  if (det !== null) {
    const row = coverageRows(coverage).find((r) => r.band === det);
    let line = `D${det}: ${row.mjds.length} images in ${row.visits.length} visit${row.visits.length === 1 ? "" : "s"}`;
    if (nFrames !== null) {
      line += nFrames === row.visits.length
        ? `; the flipbook shows all ${nFrames}.`
        : `; the flipbook shows ${nFrames} (a visit is left out when none of its images covers enough of the square, ` +
          `and visits released after the frames were made are not in them yet).`;
    } else {
      line += ".";
    }
    out.push(line);
    if (row.visits.length) out.push(`Time: ${visitTimesText(row.visits)}.`);
  }
  return out;
}

export async function loadCoverage(where, fetchFn = fetch) {
  // IRSA's search can take minutes, so an official target's prepared answer comes first.
  if (where.targetKey) {
    const prepared = await loadExtra(`${FRAMES_ROOT}/${where.targetKey}`, "coverage.json", fetchFn).catch(() => null);
    if (prepared) return prepared;
  }
  if (await hasApi(fetchFn)) {
    const params = new URLSearchParams({ ra: where.ra.toFixed(6), dec: where.dec.toFixed(6) });
    const url = `/api/coverage?${params}`;
    return remember(fetchFn, `coverage:${url}`, async () => {
      let resp;
      try {
        resp = await fetchFn(url, { cache: "no-cache" });
      } catch {
        throw new Error("Could not reach the data API");
      }
      const body = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(body.error || `The data API answered HTTP ${resp.status}`);
      return body;
    });
  }
  if (!where.targetKey) throw new Error("The timeline for any position needs the data API; this server only has the 5 prepared targets.");
  throw new Error("No coverage file was prepared for this target.");
}

export function createTimeline({ onDetector = () => {} } = {}) {
  const el = { box: $("tl-view"), message: $("tl-message"), body: $("tl-body"), chart: $("tl-chart"), summary: $("tl-summary") };
  let version = 0;
  let coverage = null;
  let coverageKey = "";
  let det = null;
  let frameMjds = [];

  /** A paragraph where each known term is a button that shows its hint in `hintBox`. */
  function paragraphWithTerms(text, terms, hintBox) {
    const p = document.createElement("p");
    p.className = "help";
    const known = new Map(terms.map((t) => [t.term, t.hint]));
    const pattern = new RegExp(`\\b(${terms.map((t) => t.term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`, "g");
    let last = 0;
    for (const match of terms.length ? text.matchAll(pattern) : []) {
      p.append(text.slice(last, match.index));
      const button = document.createElement("button");
      button.type = "button";
      button.className = "term";
      button.textContent = match[0];
      button.setAttribute("aria-expanded", "false");
      button.addEventListener("click", () => {
        const open = button.getAttribute("aria-expanded") === "true";
        el.summary.querySelectorAll(".term").forEach((b) => b.setAttribute("aria-expanded", "false"));
        hintBox.hidden = open;
        if (!open) {
          hintBox.textContent = known.get(match[0]);
          button.setAttribute("aria-expanded", "true");
        }
      });
      p.append(button);
      last = match.index + match[0].length;
    }
    p.append(text.slice(last));
    return p;
  }

  function draw() {
    if (!coverage) return;
    el.chart.innerHTML = coverage.images.length ? timelineChart(coverage, { det, frameMjds }) : "";
    const [first, ...rest] = timelineSummary(coverage, det, frameMjds.length ? frameMjds.length : null);
    const hintBox = document.createElement("p");
    hintBox.className = "help term-hint";
    hintBox.hidden = true;
    hintBox.setAttribute("aria-live", "polite");
    el.summary.replaceChildren(paragraphWithTerms(first, summaryTerms(coverage), hintBox), hintBox,
      ...rest.map((t) => paragraphWithTerms(t, [], hintBox)));
  }

  function message(text) {
    el.body.hidden = true;
    el.message.hidden = false;
    el.message.textContent = text;
  }

  /** A new position or detector ({ ra, dec, det, targetKey }). */
  async function show(where) {
    det = where.det;
    frameMjds = [];
    const key = `${where.ra.toFixed(5)},${where.dec.toFixed(5)}`;
    if (key === coverageKey && coverage) return draw();
    const v = ++version;
    coverage = null;
    coverageKey = key;
    message("Asking NASA IRSA when SPHEREx looked here…");
    try {
      const answer = await loadCoverage(where);
      if (v !== version) return;
      coverage = answer;
    } catch (err) {
      if (v === version) {
        coverageKey = "";
        message(`Could not get the list of SPHEREx images for this position (${err.message}). ` +
          "NASA IRSA may be busy: the flipbook frames still work, and you can pick the target again in a few minutes.");
      }
      return;
    }
    el.message.hidden = true;
    el.body.hidden = false;
    draw();
  }

  /** The flipbook loaded frames: mark their dates. */
  function markFrames(loaded) {
    frameMjds = loaded ? loaded.manifest.frames.map((f) => f.mjd) : [];
    draw();
  }

  el.chart.addEventListener("click", (e) => {
    const row = e.target.closest("[data-band]");
    if (row) onDetector(Number(row.dataset.band));
  });
  el.chart.addEventListener("keydown", (e) => {
    const row = e.target.closest("[data-band]");
    if (row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onDetector(Number(row.dataset.band)); }
  });
  return { show, markFrames };
}
