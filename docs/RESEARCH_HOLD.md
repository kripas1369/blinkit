# Research notes — Six Eyes / 102 bands / spectra (HOLD)

**Status:** research only. No lab code yet. Do **not** push to GitHub until we decide.

Sources reviewed: local `nasa/learn/06_spherex.md`, `nasa/hackathon/FACTS.md`, `nasa/SPHEREx_Expsupp_QR.pdf` (referenced), Blinkit `docs/*`, IRSA archive docs, arXiv/IOP papers, GitHub tutorials/repos, Space Apps discussion #1847.

---

## 1. What “102 bands” actually are

| Fact | Detail | Source |
|------|--------|--------|
| Instrument | 6 H2RG detectors, each with an LVF | Instrument page; Crill/Doré overview |
| Channels | **6 × 17 = 102** nominal spectral channels | Spectral Response paper; Sky Simulator; FACTS.md |
| Wavelength | ~0.75–5.0 µm | Same |
| How a spectrum forms | One exposure → one λ at a sky point (row on LVF). Telescope steps → many λ → spectrum | `learn/06_spherex.md` §6.5; Caltech instrument page |
| Paired FPAs | Bands 1↔4, 2↔5, 3↔6 see the **same sky** at once (dichroic) | Pipeline paper / data products |

**Critical for Blinkit:** comparing two epochs at mismatched λ can look like variability when it is only colour (`learn/06_spherex.md` §6.6). Space Apps discussion [#1847](https://github.com/nasa/spaceapps/discussions/1847) agrees: match wavelength (or detector + tolerance) before blink/diff.

---

## 2. What the NASA challenge sentence really asks

> Separately add together all the data taken by each of the six detector arrays to improve S/N… Extra kudos if your tool can generate spectra on the fly.

Two layers:

1. **Per-detector coadd (Six Eyes)** — D1…D6 each get a quieter image (challenge example).  
2. **Spectra on the fly** — brightness vs wavelength at a click (kudos).

**Honest caveat (from papers + LVF physics):**  
Coadding *all* D2 exposures still mixes many of the **17 channels inside band 2**, because the target sits on different LVF rows in different exposures. So “deep D2” is a **band-averaged** quiet image, not one pure channel. Fine for discovery UI if labeled; not a science-grade single-channel mosaic.

True **102-plane** products are separate (see §3).

---

## 3. Official data products (do not reinvent blindly)

### Level-2 Spectral Image MEF (what Blinkit already uses)
- Per pointing, per detector: IMAGE, FLAGS, VARIANCE, ZODI, PSF/EPSF, WCS-WAVE  
- Docs: [SPHEREx Data Products](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/)  
- Collections: `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`

### DR1 All-Sky Cube (102 channels) — major research finding
- HEALPix tiles ~1.8°; each tile **512 × 512 × 102**  
- Zodi **already subtracted**; NHITS + FLAGS; SPECTRAL_CHANNELS table  
- Blank channels 51–52 (dichroic); He-line stripes possible  
- HiPS PNG stack for **visualization only** (stretch 0–40 MJy/sr)  
- Tutorial: [Using SPHEREx HiPS All-Sky Mosaic Cubes](https://caltech-ipac.github.io/irsa-tutorials/spherex-hipscube/)  
- HiPS URL (from tutorial): `https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube`

### IRSA Spectrophotometry Tool (science spectra)
- Forced photometry / Tractor across Spectral Images  
- Docs: [Spectrophotometry Tool help](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html)  
- Official stance: cube aperture spectra = **viz**; this tool = **science**

### Deep survey collections
- `*_deep` = extra coverage in deep fields (more hits), not the same as DIY coadd of wide-survey visits — but same coadd idea, more photons.

---

## 4. Papers / docs to lean on

| Work | Why it matters |
|------|----------------|
| SPHEREx overview (e.g. arXiv [2404.11017](https://arxiv.org/html/2404.11017)) | Mission + 102-band survey concept |
| Spectral Response of SPHEREx (IOP / arXiv) | LVF, 6×17 channels, coadd for S/N in calibration |
| Sky Simulator (IOP) | How channels are defined on the focal plane |
| Image & Spectrophotometry Pipeline (IOP / Akeson et al.) | How public products are made |
| Explanatory Supplement PDF (`nasa/SPHEREx_Expsupp_QR.pdf` + IRSA current PDF) | FLAGS, mosaic rules, cube §2.5, WCS-WAVE viz vs CWAVE science |
| Local `learn/06_spherex.md`, `FACTS.md` | Team-verified numbers and pitfalls |

---

## 5. Open-source tools / repos

| Repo / tool | Use for HOLD |
|-------------|--------------|
| [Caltech-IPAC/spherex-pipelines](https://github.com/Caltech-IPAC/spherex-pipelines) | Reference algorithms; **not** meant to run at home |
| [Caltech-IPAC/irsa-tutorials](https://github.com/Caltech-IPAC/irsa-tutorials) (`spherex`, `spherex_hipscube`) | Cutouts, HiPS cube, quick-look spectrum with Photutils |
| [cds-astro/aladin-lite](https://github.com/cds-astro/aladin-lite) | Already in Blinkit; supports **HiPS cubes** (channel slider) |
| Astropy / reproject / photutils / pyvo / astroquery | Already in Blinkit stack |
| [SPHEREx/SPHEREx-Visualizer-Lite](https://github.com/SPHEREx/SPHEREx-Visualizer-Lite) | Official-ish coverage viz (lightweight) |
| Other Space Apps apps (e.g. cosmic-echo) | Time timeline + Aladin; often **explicitly skip** 102 bands / spectra — gap we can own |

---

## 6. What Blinkit already has (relevant to HOLD)

| Piece | Role vs Six Eyes |
|-------|------------------|
| Visit coadd (`coadd.py`, `render.py`) | Layer A — within visit, one detector |
| Add visits (`stack.py`) | Layer B — across visits, **one** detector (closest to “deep D2”) |
| Detector switch D1–D6 | Wavelength tour, but **time flipbook**, not 2×3 deep grid |
| `spectrum.json` in frames contract | Multi-detector brightness vs λ (documented; confirm file present per target) |
| Diff pairs prefer closest λ | Correct LVF-aware practice |
| Aladin Lite + Gaia/WISE | Display + overlays (challenge tool hint) |

So HOLD is less “invent coadding” and more “**productize wavelength discovery**” and/or **hook official 102-channel products**.

---

## 7. Lab strategy options (decide before coding)

### Option A — DIY Six Eyes from Level-2 (matches challenge wording)
- Reuse `stack.py` / `coadd` per detector → `deep_D1`…`deep_D6`  
- Lab page: 2×3 grid + click → 6-point spectrum  
- Pros: uses existing pipeline; offline demo; clear “we added per array”  
- Cons: mixes channels within each detector; not full 102

### Option B — DR1 All-Sky Cube / HiPS (matches 102 literally)
- Lab: load cube tile or HiPS cube; show channel movie or Six Eyes = mean of 17 planes per detector  
- Click → up to 102-point viz spectrum (Photutils pattern from IRSA tutorial)  
- Pros: true 102; NASA product; Aladin HiPS cube possible  
- Cons: coarser pixels (12.9″); viz-only caveats; network/tile logic; blank ch 51–52

### Option C — Hybrid (recommended for research → lab)
1. **Lab v1:** Option A from existing `epoch*.fits` / stack (fast, no main-app change).  
2. **Lab v2:** Option B spectrum overlay from cube/HiPS for the same RA/Dec.  
3. Integrate only what looks good; label viz vs science; point judges to IRSA spectrophotometry for “real” spectra.

**Do not** change main `app.js` until lab review. **Do not** push.

---

## 8. Risks / honesty checklist for any lab

- [ ] Label deep detector images as **band-averaged / multi-channel coadd**, not “channel N”.  
- [ ] Movers (Barnard) will smear in deep — expected; keep flipbook for motion.  
- [ ] Cube/HiPS spectra = visualization; cite IRSA Spectrophotometry for science.  
- [ ] WCS-WAVE in L2 MEF = viz; CWAVE/CBAND cal product for science λ.  
- [ ] Mask FLAGS like Mosaic Tool list (already in Blinkit flags logic).  
- [ ] Prefer inverse-variance weights (already proven in `test_stack.py`).

---

## 9. Status (shipped / deferred)

| Piece | Status |
|-------|--------|
| Option A Six Eyes in main app | **Shipped** — panel + lightbox + coarse spectrum; builder `scripts/six_eyes_lab.py` → `frontend/frames/<target>/six_eyes/` |
| Isolated `/lab/` HTML pages | **Removed** (no longer needed) |
| Option B DR1 cube 102-channel page | **Deferred** — researched; script/page not in repo; see §7 |

Rebuild products locally (frames are gitignored): `python -m scripts.six_eyes_lab <target>` for each official target.

---

## 10. One-paragraph conclusion

The challenge’s “add per detector for S/N” is real and aligns with inverse-variance coadds Blinkit already does per visit and across visits; Six Eyes is now in the **main app** (deep D1–D6 + coarse spectrum). The deeper 102-band story remains available via NASA’s **DR1 All-Sky Cube / HiPS** and Spectrophotometry Tool if we add Option B later. Stay honest about LVF mixing and viz-vs-science limits.
