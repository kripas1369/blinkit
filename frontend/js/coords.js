
const SEXAGESIMAL_MARK = /[hmsd:°'"]/i;

function readSexagesimal(token, isRa) {
  const sign = token.trim().startsWith("-") ? -1 : 1;
  const parts = token.match(/\d+(?:\.\d+)?/g);
  if (!parts || parts.length === 0 || parts.length > 3) {
    throw new Error(`Could not read "${token}"`);
  }
  const [a, b = 0, c = 0] = parts.map(Number);
  if (b >= 60 || c >= 60) throw new Error(`Minutes and seconds must be below 60 in "${token}"`);
  const value = sign * (a + b / 60 + c / 3600);
  return isRa ? value * 15 : value;
}

function checkRange(ra, dec) {
  if (!(ra >= 0 && ra < 360)) throw new Error(`RA must be between 0 and 360 degrees (0h to 24h), got ${ra.toFixed(4)}`);
  if (!(dec >= -90 && dec <= 90)) throw new Error(`Dec must be between -90 and +90 degrees, got ${dec.toFixed(4)}`);
}


export function parseCoordinates(text) {
  const clean = String(text).replace(/,/g, " ").trim();
  if (!clean) throw new Error("Type a position (RA and Dec) or a star name");
  const tokens = clean.split(/\s+/);

  let ra;
  let dec;
  if (SEXAGESIMAL_MARK.test(clean)) {
    if (tokens.length !== 2) throw new Error("Expected two values: RA and Dec");
    ra = readSexagesimal(tokens[0], true);
    dec = readSexagesimal(tokens[1], false);
  } else if (tokens.length === 6 && tokens.every((t) => /^[-+]?\d+(\.\d+)?$/.test(t))) {
    ra = readSexagesimal(tokens.slice(0, 3).join(":"), true);
    dec = readSexagesimal(tokens.slice(3).join(":"), false);
  } else if (tokens.length === 2 && tokens.every((t) => /^[-+]?\d+(\.\d+)?$/.test(t))) {
    ra = Number(tokens[0]);
    dec = Number(tokens[1]);
  } else {
    throw new Error("Expected two values: RA and Dec");
  }
  checkRange(ra, dec);
  return { ra, dec };
}


export function parseField(text, isRa, unit) {
  const name = isRa ? "RA" : "Dec";
  const clean = String(text).trim();
  if (!clean) throw new Error(`Type the ${name}`);
  let value;
  if (unit === "deg") {
    if (!/^[-+]?\d+(\.\d+)?°?$/.test(clean)) {
      throw new Error(`${name} in degrees must be a number, like ${isRa ? "269.452" : "+4.693"}`);
    }
    value = Number(clean.replace("°", ""));
  } else {
    value = readSexagesimal(clean.replace(/\s+/g, ":"), isRa);
  }
  if (isRa && !(value >= 0 && value < 360)) throw new Error("RA must be between 0h and 24h (0–360°)");
  if (!isRa && !(value >= -90 && value <= 90)) throw new Error("Dec must be between -90 and +90");
  return value;
}

/**
 * Pasted text holding both values -> { ra, dec, unit } as text for the two boxes, or null.
 * "RA=133.79 Dec=-7.24", "ra: 08h55m10.8s, dec: -07d14m42s", "269.452 4.693", "17:57:48 +04:41:36".
 */
export function splitPastedPair(text) {
  const clean = String(text).trim();
  const labelled = clean.match(/^ra\s*[=:]?\s*(.+?)\s*[,;]?\s*dec\s*[=:]?\s*(.+)$/i);
  if (labelled) {
    const ra = labelled[1].trim();
    const dec = labelled[2].trim();
    const sexagesimal = SEXAGESIMAL_MARK.test(ra + dec) || /\d\s+\d/.test(ra);
    return { ra, dec, unit: sexagesimal ? "hms" : "deg" };
  }
  try {
    const { ra, dec } = parseCoordinates(clean);
    return { ra: ra.toFixed(6), dec: dec.toFixed(6), unit: "deg" };
  } catch {
    return null;
  }
}

/** True when the text looks like a name ("Barnard's Star", "M31") rather than numbers. */
export function looksLikeName(text) {
  // h, m, s, d count as units only straight after a digit ("17h57m"); "M31" stays a name.
  return /[a-z]/i.test(String(text).replace(/(\d)[hmsd]/gi, "$1"));
}

function pad(value, width, decimals = 0) {
  const s = value.toFixed(decimals);
  const [whole, frac] = s.split(".");
  return whole.padStart(width, "0") + (frac !== undefined ? "." + frac : "");
}

/** Degrees -> "17h57m47.10s" */
export function formatRa(raDeg) {
  let totalSeconds = Math.round((((raDeg % 360) + 360) % 360) / 15 * 3600 * 100) / 100;
  const h = Math.floor(totalSeconds / 3600);
  totalSeconds -= h * 3600;
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds - m * 60;
  return `${pad(h % 24, 2)}h${pad(m, 2)}m${pad(s, 2, 2)}s`;
}

/** Degrees -> "+04°46′05.5″" */
export function formatDec(decDeg) {
  const sign = decDeg < 0 ? "-" : "+";
  let totalSeconds = Math.round(Math.abs(decDeg) * 3600 * 10) / 10;
  const d = Math.floor(totalSeconds / 3600);
  totalSeconds -= d * 3600;
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds - m * 60;
  return `${sign}${pad(d, 2)}°${pad(m, 2)}′${pad(s, 2, 1)}″`;
}
