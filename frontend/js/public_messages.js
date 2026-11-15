/** Visitor-facing copy: hide pipeline paths and raw IRSA/TAP errors. */

const ARCHIVE_HINT =
  "NASA’s IRSA archive did not answer (or timed out). Blinkit is working — this is on IRSA’s side, not our server. Try again in a few minutes.";

const OVERLAY_HINT =
  "Star-catalogue overlays (Gaia / WISE) are incomplete right now because NASA IRSA did not answer. The flipbook still works; try overlays again later.";

/** True when the text is about NASA IRSA / TAP / ESA catalogue downtime. */
export function looksLikeArchiveOutage(text) {
  const t = String(text || "").toLowerCase();
  return /irsa|tap\/sync|tap is down|proxy error|\b502\b|timed out|timeout|esa gaia|catwise|archiveerror/.test(t);
}

/** Turn a raw API / pipeline string into something safe to show visitors. */
export function publicArchiveMessage(raw, { overlay = false } = {}) {
  const text = String(raw || "").trim();
  if (!text) return "";
  if (looksLikeArchiveOutage(text)) return overlay ? OVERLAY_HINT : ARCHIVE_HINT;
  return text;
}

/** Dedupe and rewrite pipeline warnings for the flipbook note. */
export function publicWarnings(list) {
  const out = [];
  for (const raw of list || []) {
    const overlay = /gaia|wise|catwise|marker/i.test(String(raw));
    const msg = publicArchiveMessage(raw, { overlay });
    if (msg && !out.includes(msg)) out.push(msg);
  }
  return out;
}
