/**
 * WiseView-style color composite from greyscale epoch PNGs.
 * Earliest → Blue, middle → Green, latest → Red.
 * Stationary stars look white/grey; movers tint red (in) or blue (out).
 */

const NO_VALUE_SKIP = 50; // skip visits with pct_no_value above this

/** @param {Array<{ png: string, pct_no_value?: number, date_iso?: string }>} frames */
export function pickCompositeFrames(frames) {
  const usable = frames
    .map((f, i) => ({ ...f, index: i }))
    .filter((f) => (f.pct_no_value ?? 0) <= NO_VALUE_SKIP);
  const pool = usable.length >= 2 ? usable : frames.map((f, i) => ({ ...f, index: i }));
  if (pool.length < 2) return null;
  const first = pool[0];
  const last = pool[pool.length - 1];
  const middle = pool[Math.floor(pool.length / 2)];
  return { first, middle, last, twoEpoch: pool.length === 2 };
}

function loadImageData(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = img.width;
      c.height = img.height;
      const cx = c.getContext("2d", { willReadFrequently: true });
      cx.drawImage(img, 0, 0);
      resolve(cx.getImageData(0, 0, img.width, img.height));
    };
    img.onerror = () => reject(new Error(`Could not load ${src}`));
    img.src = src;
  });
}

/**
 * @param {string[]} pngPaths absolute or site-relative URLs, ordered earliest → latest
 * @param {{ twoEpoch?: boolean }} [opts]
 * @returns {Promise<HTMLCanvasElement | null>}
 */
export async function buildColorComposite(pngPaths, opts = {}) {
  const n = pngPaths.length;
  if (n < 2) return null;
  const images = await Promise.all(pngPaths.map((src) => loadImageData(src)));
  const { width, height } = images[0];
  for (const im of images) {
    if (im.width !== width || im.height !== height) {
      throw new Error("Composite frames must be the same size.");
    }
  }
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const out = ctx.createImageData(width, height);

  const twoEpoch = opts.twoEpoch || n === 2;
  const iFirst = 0;
  const iLast = n - 1;
  const iMiddle = Math.floor(n / 2);
  const first = images[iFirst].data;
  const middle = images[twoEpoch ? iFirst : iMiddle].data;
  const last = images[iLast].data;

  for (let i = 0; i < width * height; i++) {
    const p = i * 4;
    if (twoEpoch) {
      // Cyan = earliest (G+B), Red = latest — WiseView 2-visit look.
      out.data[p] = last[p];
      out.data[p + 1] = first[p];
      out.data[p + 2] = first[p];
    } else {
      out.data[p] = last[p];
      out.data[p + 1] = middle[p];
      out.data[p + 2] = first[p];
    }
    out.data[p + 3] = Math.max(first[p + 3], middle[p + 3], last[p + 3]);
  }
  ctx.putImageData(out, 0, 0);
  return canvas;
}

/** Build from a prepared manifest + base folder URL. */
export async function buildCompositeFromManifest(manifest, folder) {
  const pick = pickCompositeFrames(manifest.frames || []);
  if (!pick) return null;
  const paths = pick.twoEpoch
    ? [`${folder}/${pick.first.png}`, `${folder}/${pick.last.png}`]
    : [`${folder}/${pick.first.png}`, `${folder}/${pick.middle.png}`, `${folder}/${pick.last.png}`];
  const canvas = await buildColorComposite(paths, { twoEpoch: pick.twoEpoch });
  return { canvas, pick };
}
