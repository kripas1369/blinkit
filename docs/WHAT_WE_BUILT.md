# What we built — new methods, inspiration, and what is still out of scope

Blinkit is a **SPHEREx visit flipbook**: same sky, several times, so movers and changes are obvious by eye. Team **Not42** (Kripas Khatiwada & Govinda). Live: [https://blinkit.study](https://blinkit.study) · AWS backup: [https://aws.blinkit.study](https://aws.blinkit.study).

## Inspiration we actually used

### WiseView (Backyard Worlds)

- Site: [http://byw.tools/wiseview](http://byw.tools/wiseview)  
- NASA Space Apps points to WiseView as a model for blinking WISE data. Volunteers used it to find hundreds of brown dwarfs.
- **What we took:** blink / flip animation, contrast that makes movers pop, **minus-median** style residuals, color-from-epochs idea, shareable position in the URL.
- **What is different:** Blinkit is built for **SPHEREx** (six detectors, LVF wavelengths, IRSA + AWS Level-2), not WISE coadds. We add visit **difference in σ**, **Gaia proof**, **visit stack**, and **Six Eyes** (deep stack per detector).

### Papers and PDFs we studied (practice library)

Stored under `wise-blink-practice/researchpdf/` (not copied into this repo). Main ones that shaped design:

| File / paper | Why it mattered for Blinkit |
|--------------|-----------------------------|
| `01_Bock2026_SPHEREx_Satellite_Mission.pdf` — Bock et al. 2026, SPHEREx mission overview | Mission revisit story; IRSA tool table (no official visit blinker); time-domain goals |
| `02_Kuchner2017_Backyard_Worlds_First_Brown_Dwarf.pdf` — Kuchner et al. 2017 | Human blink discovery; artifact rate in IR surveys (~why flags and honest warnings matter) |
| `03_Meisner2018_Planet_Nine_Search_WISE_NEOWISE.pdf` — Meisner et al. 2018 | Wide-area IR search practice; slow outer Solar System context |
| `08_Luhman2014_WISE0855_…` / `07_Luhman2014_…` | WISE 0855 as a hard faint mover (one of our official targets) |
| `09_GaiaCollab2023_Gaia_DR3_Summary.pdf` | Gaia DR3 as the motion reference for proofs and overlays |
| `10_Koutoulaki2019_RW_Aur_Dimming.pdf` | RW Aur as a variable-star demo target |
| Planet Nine set (`04`–`06` Batygin/Brown) | Challenge framing (distant movers), not a Planet Nine claim in the app |

Related open links we used while building: Gaia DR3; IRSA SPHEREx docs; Aladin Lite / ESA HiPS CDN; difference-imaging classics (Alard & Lupton; ZOGY) as background reading — our shipped diff is a practical σ-normalized visit subtract, not a full ZOGY pipeline.

## Methods that are unusual for a hackathon SPHEREx demo

Things teams rarely ship end-to-end in one weekend — **we did ship these**:

1. **Full visit pipeline on real Level-2** — S3 range reads, defect masks, north-up reproject, inverse-variance coadd, PNG + FITS products, not mock tiles.
2. **Prepared + live sky** — five official targets offline-fast; any RA/Dec as a background job with the same product shape.
3. **WiseView-style minus-median + RGB visit composite** on SPHEREx visits.
4. **σ-difference maps** with wavelength-aware default pair (closest λ to cut chromatic junk).
5. **Gaia DR3 motion proof** (measured shift vs prediction) on the same cutout.
6. **Six Eyes** — deep stack per detector D1–D6 + coarse 6-point spectrum for visualization.
7. **Shareable / embeddable URLs** (`ra`, `dec`, `fov`, `det`, mode) for other sites.
8. **Release-aware search** — `SPHEREX_COLLECTIONS` env; SIA→TAP failover; friendly archive-down UX.
9. **Provenance** — `PIXSRC` / pixel_source so each frame knows AWS vs IRSA cutout.

## Done for this submission (Phase 1 complete)

- Flipbook modes: images / blink, color, minus-median, add visits, difference.
- Overlays: Gaia, CatWISE; FOV on the sky map.
- Proof + Six Eyes on official targets.
- Tests + frame audit (`check_frames` 30/30) + hosting docs.
- Public sites: **blinkit.study** (primary VPS) and **aws.blinkit.study** (AWS EC2 backup).

## Not done (on purpose for this hackathon)

We studied these in practice notes; they are **out of scope** for the shipped app:

| Idea | Why we left it out |
|------|--------------------|
| **Eclipse / occultation mode** (practice-only experiments) | Not needed for the Planet X + SPHEREx blink story this weekend |
| Full **102-channel All-Sky Cube** browser | Different product; Six Eyes is a 6-detector deep-stack stand-in only |
| Automatic mover catalog / ML ranking | Human blink first; spots-as-discovery UI stayed unfinished and was removed |
| Light-curve / full spectrum panels wired in the main UI | Partial HTML existed without JS; removed for a clean Phase 1 |
| Scientist “raw detector canvas” / inside-visit hour-scale flip | Advanced lab UI; removed from the public frontend |
| Claiming a new Planet Nine or brown dwarf | Demo + method, not a discovery paper |

## One-line takeaway

**WiseView taught us how people spot movers; Bock/IRSA showed the SPHEREx gap; Blinkit is the visit blinker for SPHEREx we wished already existed.**
