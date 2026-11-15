export const FOV_DEFAULT = 3;   // arcminutes
export const FOV_MIN = 1;
export const FOV_MAX = 30;
export const DET_DEFAULT = 2;

export const DETECTORS = {
  1: "0.75–1.09 µm",
  2: "1.10–1.62 µm",
  3: "1.63–2.41 µm",
  4: "2.42–3.82 µm",
  5: "3.83–4.41 µm",
  6: "4.42–5.00 µm",
};

export const MODES = {
  flip: "the flipbook",
  blink: "blink two visits",
  composite: "color composite",
  diff: "difference",
  stack: "add visits",
  minus: "minus median",
};
export const SPEEDS = [0.5, 1, 2, 4];   // frames per second

// Left out of the link when they have these values, so plain links stay short.
export const VIEW_DEFAULTS = { mode: "flip", a: null, b: null, gaia: true, wise: false, flags: false, speed: 1 };

function readSwitch(params, key, problems) {
  const text = params.get(key);
  if (text === "0" || text === "1") return text === "1";
  problems.push(`"${key}" must be 0 or 1; using ${VIEW_DEFAULTS[key] ? 1 : 0}.`);
  return VIEW_DEFAULTS[key];
}

function readVisit(params, key, problems) {
  const text = params.get(key);
  if (/^\d{1,3}$/.test(text)) return Number(text);
  problems.push(`Visit "${key}" must be a visit number (0, 1, 2…); ignored.`);
  return null;
}

/** "?ra=..&dec=.." -> { ra, dec, fov, det, mode, a, b, gaia, wise, flags, speed, problems }; ra/dec are null when missing or invalid. */
export function readUrlState(search) {
  const params = new URLSearchParams(search);
  const problems = [];
  let ra = null;
  let dec = null;
  if (params.has("ra") || params.has("dec")) {
    const r = Number(params.get("ra"));
    const d = Number(params.get("dec"));
    if (params.get("ra") !== "" && params.get("dec") !== "" && r >= 0 && r < 360 && d >= -90 && d <= 90) {
      ra = r;
      dec = d;
    } else {
      problems.push("The link has an invalid position (ra must be 0–360, dec −90 to +90).");
    }
  }
  let fov = Number(params.get("fov") ?? FOV_DEFAULT);
  if (!(fov >= FOV_MIN && fov <= FOV_MAX)) {
    if (params.has("fov")) problems.push(`Field of view must be ${FOV_MIN}–${FOV_MAX} arcmin; using ${FOV_DEFAULT}.`);
    fov = FOV_DEFAULT;
  }
  let det = Number(params.get("det") ?? DET_DEFAULT);
  if (!DETECTORS[det]) {
    if (params.has("det")) problems.push(`Detector must be 1–6; using D${DET_DEFAULT}.`);
    det = DET_DEFAULT;
  }

  const view = { ...VIEW_DEFAULTS };
  if (params.has("mode")) {
    const mode = params.get("mode");
    if (mode in MODES) view.mode = mode;
    else problems.push(`Unknown mode "${mode}"; showing ${MODES[VIEW_DEFAULTS.mode]}.`);
  }
  for (const key of ["a", "b"]) {
    if (params.has(key)) view[key] = readVisit(params, key, problems);
  }
  if (view.a !== null && view.a === view.b) {
    problems.push("Visits a and b are the same; ignored.");
    view.a = view.b = null;
  }
  for (const key of ["gaia", "wise", "flags"]) {
    if (params.has(key)) view[key] = readSwitch(params, key, problems);
  }
  if (params.has("speed")) {
    const speed = Number(params.get("speed"));
    if (SPEEDS.includes(speed)) view.speed = speed;
    else problems.push(`Speed must be one of ${SPEEDS.join(", ")} per second; using ${VIEW_DEFAULTS.speed}.`);
  }
  return { ra, dec, fov, det, ...view, problems };
}

/** { ra, dec, fov, det, mode, ... } -> "?ra=269.446269&dec=4.768204&fov=3&det=2[&mode=blink&a=0&b=2...]" */
export function buildUrlState(state) {
  const params = new URLSearchParams();
  params.set("ra", state.ra.toFixed(6));
  params.set("dec", state.dec.toFixed(6));
  params.set("fov", String(state.fov));
  params.set("det", String(state.det));
  for (const [key, fallback] of Object.entries(VIEW_DEFAULTS)) {
    const value = state[key] ?? fallback;
    if (value === fallback) continue;
    params.set(key, typeof value === "boolean" ? (value ? "1" : "0") : String(value));
  }
  return "?" + params.toString();
}
