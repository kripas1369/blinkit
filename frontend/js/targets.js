
export const RATINGS = {
  recommended: "Recommended",
  try: "Try",
  not: "Not recommended",
};

const GAIA_EMPTY = "Frames ready; Gaia overlay empty (NASA IRSA catalogue busy — not a Blinkit outage).";

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
      1: { rating: "try", why: "Motion agrees: 1.57 px vs Gaia 1.66 px." },
      2: { rating: "recommended", why: "Best proof: 1.61 px vs Gaia 1.67 px (diff 0.05 px)." },
      3: { rating: "try", why: "Motion agrees: 1.60 px vs Gaia 1.68 px." },
      4: { rating: "try", why: "Motion agrees: 1.64 px vs Gaia 1.66 px; ~5.8% flagged." },
      5: { rating: "try", why: "Motion agrees: 1.51 px vs Gaia 1.67 px." },
      6: { rating: "not", why: "proof.json not measurable at ~4.6 µm; use D2." },
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
      1: { rating: "not", why: "Too faint at 0.97 µm: motion disagrees (0.59 vs 0.75 px)." },
      2: { rating: "recommended", why: "Five visits; motion agrees 0.98 vs Gaia 1.09 px." },
      3: { rating: "try", why: "Four visits; motion agrees 1.02 vs Gaia 1.06 px." },
      4: { rating: "try", why: "Motion agrees 0.65 vs Gaia 0.75 px." },
      5: { rating: "try", why: "Five visits rendered. " + GAIA_EMPTY },
      6: { rating: "try", why: "Four visits rendered. " + GAIA_EMPTY },
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
      1: { rating: "not", why: "Rendered; expected non-detection below ~4 µm." },
      2: { rating: "not", why: "Rendered; expected non-detection below ~4 µm." },
      3: { rating: "not", why: "Rendered; expected non-detection below ~4 µm." },
      4: { rating: "not", why: "Rendered; still short of peak mid-IR." },
      5: { rating: "try", why: "Four visits / 30 exposures at ~4 µm. " + GAIA_EMPTY },
      6: { rating: "recommended", why: "Three visits at ~4.5–5 µm — blink here. " + GAIA_EMPTY },
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
      1: { rating: "try", why: "Three visits; match wl_target_um before judging brightness. " + GAIA_EMPTY },
      2: { rating: "recommended", why: "Three visits at ~1.3–1.5 µm; default variability blink. " + GAIA_EMPTY },
      3: { rating: "try", why: "Three visits; LVF wavelengths change between visits. " + GAIA_EMPTY },
      4: { rating: "try", why: "Three visits; watch saturation / flags. " + GAIA_EMPTY },
      5: { rating: "try", why: "Three visits at ~4 µm. " + GAIA_EMPTY },
      6: { rating: "try", why: "Three visits at ~4.7 µm. " + GAIA_EMPTY },
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
      1: { rating: "try", why: "Five visits; crowded deep field, 3–8% flagged. " + GAIA_EMPTY },
      2: { rating: "recommended", why: "Three visits; compare wavelength range first. " + GAIA_EMPTY },
      3: { rating: "try", why: "Four visits; higher flag rates. " + GAIA_EMPTY },
      4: { rating: "try", why: "Five visits; 13–19% flagged — expect stripes. " + GAIA_EMPTY },
      5: { rating: "try", why: "Three visits; 8–13% flagged. " + GAIA_EMPTY },
      6: { rating: "try", why: "Four visits (capped at 8 exposures each). " + GAIA_EMPTY },
    },
  },
];

/** Detector numbers of one target with this rating, in order (e.g. [5, 6]). */
export function detectorsRated(target, rating) {
  return Object.entries(target.detectors)
    .filter(([, d]) => d.rating === rating)
    .map(([n]) => Number(n));
}
