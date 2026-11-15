
export const RATINGS = {
  recommended: "Recommended",
  try: "Try",
  not: "Not recommended",
};

const NOT_RENDERED = "Frames not on disk yet (IRSA outage 15 Nov 2026); not re-measured.";

export const TARGETS = [
  {
    key: "barnard",
    label: "Barnard's Star",
    kind: "Moving star",
    timescale: "years",
    timescaleLabel: "Years (multi-pass)",
    ra: 269.452077, dec: 4.693365, pmra: -801.551, pmdec: 10362.394,
    lookFor: "The fastest-moving star in the sky (10.4″ per year). Watch it walk about 1.7 pixels.",
    detector: 2,
    detectors: {
      1: { rating: "try", why: "Motion agrees: 1.57 px measured vs Gaia 1.66 px (diff 0.18 px); D1 at 0.94 µm." },
      2: { rating: "recommended", why: "Best proof: 1.61 px vs Gaia 1.67 px (diff 0.05 px); reference D2 at 1.43 µm." },
      3: { rating: "try", why: "Motion agrees: 1.60 px vs Gaia 1.68 px; LVF centre ~1.85 µm." },
      4: { rating: "try", why: "Motion agrees: 1.64 px vs Gaia 1.66 px; more flagged pixels (~5.8%)." },
      5: { rating: "try", why: "Motion agrees: 1.51 px vs Gaia 1.67 px; longest baseline still saturates." },
      6: { rating: "not", why: "proof.json: not measurable (saturated-core/centroid failed both end visits at ~4.6 µm)." },
    },
  },
  {
    key: "eps_ind_b",
    label: "Epsilon Indi B",
    kind: "Brown-dwarf pair",
    timescale: "years",
    timescaleLabel: "Years (multi-pass)",
    ra: 331.044147, dec: -56.782844, pmra: 3981.977, pmdec: -2466.832,
    lookFor: "Two brown dwarfs moving together (4.7″ per year). A small shift of about 1 pixel.",
    detector: 2,
    detectors: {
      1: { rating: "not", why: "Too faint at 0.97 µm: motion disagrees (0.59 px vs Gaia 0.75 px)." },
      2: { rating: "recommended", why: "Five visits; motion agrees 0.98 px vs Gaia 1.09 px; cleanest coadd." },
      3: { rating: "try", why: "Four visits; motion agrees 1.02 px vs Gaia 1.06 px." },
      4: { rating: "try", why: "Motion agrees 0.65 px vs Gaia 0.75 px at ~3.3 µm." },
      5: { rating: "try", why: NOT_RENDERED },
      6: { rating: "try", why: NOT_RENDERED },
    },
  },
  {
    key: "wise0855",
    label: "WISE 0855",
    kind: "Coldest brown dwarf",
    timescale: "years",
    timescaleLabel: "Years (multi-pass)",
    ra: 133.818908, dec: -7.247048, pmra: -8123.7, pmdec: 673.2,
    lookFor: "Invisible at short wavelengths, it appears only at 4–5 µm (detectors D5–D6).",
    detector: 6,
    detectors: {
      1: { rating: "not", why: "Plan: too faint below ~4 µm; no frames rendered yet." },
      2: { rating: "not", why: "Plan: too faint below ~4 µm; no frames rendered yet." },
      3: { rating: "not", why: "Plan: too faint below ~4 µm; no frames rendered yet." },
      4: { rating: "not", why: "Plan: too faint below ~4 µm; no frames rendered yet." },
      5: { rating: "try", why: "Frames not on disk yet; expect weaker signal than D6 when rendered." },
      6: { rating: "recommended", why: "Frames not on disk yet; best band for Y-type brown dwarf (~4–5 µm)." },
    },
  },
  {
    key: "rw_aur",
    label: "RW Aurigae",
    kind: "Variable young star",
    timescale: "months",
    timescaleLabel: "Months (survey passes)",
    ra: 76.956526, dec: 30.401438, pmra: 7.23, pmdec: -20.33,
    lookFor: "A young star that dims and brightens between visits.",
    detector: 2,
    detectors: {
      1: { rating: "try", why: NOT_RENDERED },
      2: { rating: "recommended", why: "Frames not on disk yet; plan to check brightness swing at ~1.4 µm." },
      3: { rating: "try", why: NOT_RENDERED },
      4: { rating: "try", why: NOT_RENDERED },
      5: { rating: "try", why: NOT_RENDERED },
      6: { rating: "try", why: NOT_RENDERED },
    },
  },
  {
    key: "r_dra",
    label: "R Draconis",
    kind: "Pulsating giant",
    timescale: "months",
    timescaleLabel: "Months (survey passes)",
    ra: 248.167611, dec: 66.754979, pmra: -20.643, pmdec: 6.149,
    lookFor: "A Mira variable: its brightness rises and falls over about 245 days.",
    detector: 2,
    detectors: {
      1: { rating: "try", why: NOT_RENDERED },
      2: { rating: "recommended", why: "Frames not on disk yet; crowded field — match wavelength range before judging variability." },
      3: { rating: "try", why: NOT_RENDERED },
      4: { rating: "try", why: NOT_RENDERED },
      5: { rating: "try", why: NOT_RENDERED },
      6: { rating: "try", why: NOT_RENDERED },
    },
  },
];

/** Detector numbers of one target with this rating, in order (e.g. [5, 6]). */
export function detectorsRated(target, rating) {
  return Object.entries(target.detectors)
    .filter(([, d]) => d.rating === rating)
    .map(([n]) => Number(n));
}