// One-line meanings for the flag legend (from docs/plan/FACTS.md section 2).
export const FLAG_HELP = {
  SOURCE: "a known catalogue object is here",
  TRANSIENT: "possible transient or cosmic ray",
  OVERFLOW: "pixel saturated (may still be usable)",
  SUR_ERROR: "surface-brightness error flag",
  PHANTOM: "phantom signal",
  REFERENCE: "reference-pixel issue",
  NONFUNC: "non-functional pixel",
  DICHROIC: "dichroic-related flag",
  MISSING_DATA: "missing data",
  HOT: "hot pixel",
  COLD: "cold pixel",
  FULLSAMPLE: "full-well sample",
  PHANMISS: "phantom missing",
  NONLINEAR: "non-linear response",
  PERSIST: "persistence from a bright source",
  OUTLIER: "statistical outlier (shown, not always masked)",
  CROSSTALK: "detector crosstalk",
  GHOST: "ghost image",
  GHOST_FPA: "ghost on the focal-plane array",
  GHOST_EXT: "external ghost",
  STREAK: "streak artifact",
  BLOOM: "blooming from a bright star",
  SNOWBALL: "snowball artifact",
  HALO: "optical halo",
  SATELLITE_HALO: "satellite halo",
};

/** HTML list of flagged-pixel counts for the current visit (empty string when none). */
export function flagLegendHtml(flagCounts) {
  if (!flagCounts || typeof flagCounts !== "object") return "";
  const rows = Object.entries(flagCounts)
    .filter(([, n]) => typeof n === "number" && n > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([name, n]) => {
      const meaning = FLAG_HELP[name] || name.replaceAll("_", " ").toLowerCase();
      const sourceNote = name === "SOURCE" ? " (label, not a defect)" : "";
      return `<li><span class="flag-name">${name}</span> <span class="flag-count">${n.toLocaleString()} px</span> — ${meaning}${sourceNote}</li>`;
    });
  return rows.length
    ? `<p class="flag-legend-title">Flagged pixels this visit</p><ul class="flag-legend">${rows.join("")}</ul>`
    : "";
}