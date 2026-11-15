/** Six Eyes — per-detector deep stacks + coarse spectrum for official targets. */

const BAND_LABEL = {
  1: "0.75–1.09 µm",
  2: "1.10–1.62 µm",
  3: "1.63–2.41 µm",
  4: "2.42–3.82 µm",
  5: "3.83–4.41 µm",
  6: "4.42–5.00 µm",
};

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

export function createSixEyes() {
  const root = $("six-eyes-view");
  const row = $("six-eyes-row");
  const message = $("six-eyes-message");
  const summary = $("six-eyes-summary");
  const detail = $("six-eyes-detail");
  const canvas = $("six-eyes-spectrum");
  const hover = $("six-eyes-hover");
  const limits = $("six-eyes-limits");

  const lightbox = $("six-eyes-lightbox");
  const lbImg = $("six-eyes-lb-img");
  const lbTitle = $("six-eyes-lb-title");
  const lbBand = $("six-eyes-lb-band");
  const lbKicker = $("six-eyes-lb-kicker");
  const lbMeta = $("six-eyes-lb-meta");
  const lbPrev = $("six-eyes-lb-prev");
  const lbNext = $("six-eyes-lb-next");
  const lbClose = $("six-eyes-lb-close");
  const lbBackdrop = $("six-eyes-lb-backdrop");

  let product = null;
  let activeBand = null;
  let loadToken = 0;
  let lightboxOpen = false;

  function okEyes() {
    return (product?.eyes || []).filter((e) => e.status === "ok");
  }

  function eyeByBand(band) {
    return product?.eyes?.find((e) => e.band === band && e.status === "ok") || null;
  }

  function hide() {
    closeLightbox();
    if (root) root.hidden = true;
    product = null;
  }

  async function show(targetKey) {
    if (!root || !targetKey) {
      hide();
      return;
    }
    const token = ++loadToken;
    root.hidden = false;
    message.hidden = false;
    message.textContent = "Loading Six Eyes…";
    row.innerHTML = "";
    detail.hidden = true;
    summary.textContent = "";
    limits.innerHTML = "";
    closeLightbox();
    try {
      const res = await fetch(`/frames/${targetKey}/six_eyes/six_eyes.json`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (token !== loadToken) return;
      product = data;
      render(data);
      message.hidden = true;
      detail.hidden = false;
    } catch {
      if (token !== loadToken) return;
      product = null;
      message.hidden = false;
      message.textContent =
        "Six Eyes is not prepared for this target yet. Official targets with deep stacks will appear here.";
      detail.hidden = true;
      drawSpectrum([]);
    }
  }

  function render(p) {
    const ok = p.eyes.filter((e) => e.status === "ok").length;
    summary.textContent = `${p.label || p.target} · ${ok}/6 detectors · deep coadds across visits`;
    row.innerHTML = "";
    for (const eye of p.eyes) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "six-eye";
      btn.dataset.band = String(eye.band);
      btn.setAttribute("aria-pressed", "false");
      if (eye.status !== "ok") {
        btn.disabled = true;
        btn.innerHTML = `
          <span class="six-eye-frame six-eye-miss">D${eye.band}</span>
          <span class="six-eye-cap"><strong>D${eye.band}</strong><span>Unavailable</span></span>`;
      } else {
        const src = eye.png_url || `/frames/${p.target}/six_eyes/${eye.png}`;
        const gain = eye.noise_ratio_vs_single_visit != null
          ? `×${eye.noise_ratio_vs_single_visit} quieter`
          : `${eye.n_visits} visits`;
        btn.innerHTML = `
          <span class="six-eye-frame">
            <img src="${src}" alt="" width="160" height="160" loading="lazy" decoding="async">
          </span>
          <span class="six-eye-cap">
            <strong>D${eye.band}</strong>
            <span>${BAND_LABEL[eye.band] || ""}</span>
            <span class="six-eye-meta">${escapeHtml(gain)}</span>
          </span>`;
        btn.addEventListener("click", () => {
          selectBand(eye.band);
          openLightbox(eye.band);
        });
      }
      row.appendChild(btn);
    }

    limits.innerHTML = "";
    for (const line of (p.limitations || []).slice(0, 3)) {
      const li = document.createElement("li");
      li.textContent = line;
      limits.appendChild(li);
    }

    const first = p.eyes.find((e) => e.status === "ok");
    selectBand(first ? first.band : null);
  }

  function selectBand(band) {
    activeBand = band;
    for (const btn of row.querySelectorAll(".six-eye")) {
      const on = Number(btn.dataset.band) === band;
      btn.setAttribute("aria-pressed", String(on));
      btn.classList.toggle("is-active", on);
    }
    const s = product?.spectrum?.find((x) => x.band === band);
    if (s && s.flux_mjy_sr != null) {
      hover.textContent =
        `Selected: D${s.band} · ${s.wl_um.toFixed(2)} µm · ${s.flux_mjy_sr.toFixed(3)} MJy/sr`;
    } else if (band != null) {
      hover.textContent = `Selected: D${band} · no aperture measurement`;
    } else {
      hover.textContent = "";
    }
    drawSpectrum(product?.spectrum || []);
    if (lightboxOpen) fillLightbox(band);
  }

  function openLightbox(band) {
    if (!lightbox || !eyeByBand(band)) return;
    lightboxOpen = true;
    lightbox.hidden = false;
    document.body.style.overflow = "hidden";
    fillLightbox(band);
    lbClose?.focus();
  }

  function closeLightbox() {
    if (!lightbox || lightbox.hidden) return;
    lightboxOpen = false;
    lightbox.hidden = true;
    document.body.style.overflow = "";
  }

  function fillLightbox(band) {
    const eye = eyeByBand(band);
    if (!eye || !product) return;
    activeBand = band;
    const src = eye.png_url || `/frames/${product.target}/six_eyes/${eye.png}`;
    const phot = eye.photometry || {};
    const spec = product.spectrum?.find((x) => x.band === band);

    lbKicker.textContent = product.label || product.target;
    lbTitle.textContent = `D${eye.band}`;
    lbBand.textContent = BAND_LABEL[eye.band] || "";
    lbImg.src = src;
    lbImg.alt = `Deep stack detector ${eye.band}`;

    const rows = [
      ["Visits stacked", String(eye.n_visits ?? "—")],
      ["Exposures", String(eye.n_images ?? "—")],
      ["Noise vs 1 visit", eye.noise_ratio_vs_single_visit != null ? `×${eye.noise_ratio_vs_single_visit} quieter` : "—"],
      ["Aperture flux", spec?.flux_mjy_sr != null ? `${spec.flux_mjy_sr.toFixed(4)} MJy/sr` : "—"],
      ["σ", phot.sigma_mjy_sr != null ? `${phot.sigma_mjy_sr.toFixed(4)} MJy/sr` : "—"],
      ["Anchor", phot.anchor === "peak_in_search_box" ? "Peak near centre (saturated core)" : "Cutout centre"],
    ];
    lbMeta.innerHTML = rows
      .map(([k, v]) => `<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`)
      .join("");

    const list = okEyes();
    const idx = list.findIndex((e) => e.band === band);
    lbPrev.disabled = idx <= 0;
    lbNext.disabled = idx < 0 || idx >= list.length - 1;

    for (const btn of row.querySelectorAll(".six-eye")) {
      const on = Number(btn.dataset.band) === band;
      btn.setAttribute("aria-pressed", String(on));
      btn.classList.toggle("is-active", on);
    }
    drawSpectrum(product.spectrum || []);
  }

  function stepLightbox(delta) {
    const list = okEyes();
    if (!list.length) return;
    const idx = list.findIndex((e) => e.band === activeBand);
    const next = list[Math.max(0, Math.min(list.length - 1, (idx < 0 ? 0 : idx) + delta))];
    if (next) selectBand(next.band);
  }

  function drawSpectrum(points) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0a0a0a";
    ctx.fillRect(0, 0, w, h);

    const pad = { l: 48, r: 18, t: 18, b: 40 };
    const plotW = w - pad.l - pad.r;
    const plotH = h - pad.t - pad.b;
    const usable = points.filter((p) => p.flux_mjy_sr != null);

    ctx.strokeStyle = "#2c2c2e";
    ctx.strokeRect(pad.l + 0.5, pad.t + 0.5, plotW - 1, plotH - 1);

    if (!usable.length) {
      ctx.fillStyle = "#86868b";
      ctx.font = "13px -apple-system, BlinkMacSystemFont, sans-serif";
      ctx.fillText("Spectrum appears when Six Eyes data is ready.", pad.l + 14, pad.t + 28);
      return;
    }

    const xs = usable.map((p) => p.wl_um);
    const ys = usable.map((p) => p.flux_mjy_sr);
    const x0 = Math.min(...xs) - 0.12;
    const x1 = Math.max(...xs) + 0.12;
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);
    const padY = Math.max((yMax - yMin) * 0.18, 0.02);
    const y0 = Math.max(0, yMin - padY);
    const y1 = yMax + padY;
    const xScale = (x) => pad.l + ((x - x0) / (x1 - x0)) * plotW;
    const yScale = (y) => pad.t + plotH - ((y - y0) / (y1 - y0)) * plotH;

    for (let d = 1; d <= 6; d++) {
      const pt = points.find((p) => p.band === d);
      if (!pt) continue;
      const x = xScale(pt.wl_um);
      ctx.fillStyle = "#1c1c1e";
      ctx.fillRect(x - 18, pad.t, 36, plotH);
    }

    ctx.beginPath();
    ctx.strokeStyle = "#f5f5f7";
    ctx.lineWidth = 1.75;
    ctx.lineJoin = "round";
    usable.forEach((p, i) => {
      const x = xScale(p.wl_um);
      const y = yScale(p.flux_mjy_sr);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    for (const p of usable) {
      const x = xScale(p.wl_um);
      const y = yScale(p.flux_mjy_sr);
      const active = p.band === activeBand;
      ctx.beginPath();
      ctx.fillStyle = active ? "#fff" : "#a1a1a6";
      ctx.arc(x, y, active ? 5.5 : 3.5, 0, Math.PI * 2);
      ctx.fill();
      if (active) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x, y, 9, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = "#86868b";
      ctx.font = "600 11px -apple-system, BlinkMacSystemFont, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`D${p.band}`, x, pad.t + plotH + 18);
    }

    ctx.textAlign = "left";
    ctx.fillStyle = "#86868b";
    ctx.font = "12px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.fillText("Wavelength (µm)", pad.l, h - 8);
    ctx.save();
    ctx.translate(14, pad.t + plotH / 2 + 28);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("MJy/sr", 0, 0);
    ctx.restore();
  }

  canvas?.addEventListener("click", (ev) => {
    if (!product?.spectrum) return;
    const usable = product.spectrum.filter((p) => p.flux_mjy_sr != null);
    if (!usable.length) return;
    const rect = canvas.getBoundingClientRect();
    const mx = ((ev.clientX - rect.left) / rect.width) * canvas.width;
    const padL = 48;
    const plotW = canvas.width - padL - 18;
    const xs = usable.map((p) => p.wl_um);
    const x0 = Math.min(...xs) - 0.12;
    const x1 = Math.max(...xs) + 0.12;
    const wl = x0 + ((mx - padL) / plotW) * (x1 - x0);
    let best = usable[0];
    let bestD = Infinity;
    for (const p of usable) {
      const d = Math.abs(p.wl_um - wl);
      if (d < bestD) {
        bestD = d;
        best = p;
      }
    }
    selectBand(best.band);
    openLightbox(best.band);
  });

  lbPrev?.addEventListener("click", () => stepLightbox(-1));
  lbNext?.addEventListener("click", () => stepLightbox(1));
  lbClose?.addEventListener("click", closeLightbox);
  lbBackdrop?.addEventListener("click", closeLightbox);

  document.addEventListener("keydown", (ev) => {
    if (!lightboxOpen) return;
    if (ev.key === "Escape") {
      ev.preventDefault();
      closeLightbox();
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      stepLightbox(-1);
    } else if (ev.key === "ArrowRight") {
      ev.preventDefault();
      stepLightbox(1);
    }
  });

  return { show, hide };
}
