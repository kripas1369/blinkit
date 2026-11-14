# Frames format: what the flipbook reads (`spherex-blink-frames/1`)

The contract between the data pipeline (`backend/app/render.py`) and the website (`frontend/`).
Whoever makes the frames (`render.py` for the prepared targets, the `/api/frames` background job for any other position) writes **exactly this**, and the website shows it without changing any value.

---

## 1. Where the files go

```
frontend/frames/
  index.json                     which targets and detectors exist
  <target>/spectrum.json         brightness against wavelength per visit, all detectors (backend/app/spectrum.py)
  <target>/d<detector>/
    manifest.json                one per target and detector
    epoch<i>.png                 the picture of visit i
    epoch<i>_flags.png           red where the pixel is flagged bad (optional)
    epoch<i>.fits                the values behind the picture (section 8)
    gaia.json                    Gaia DR3 stars moved to each visit (section 6; backend/app/gaia.py)
    wise.json                    CatWISE2020 sources moved to each visit (section 7; backend/app/wise.py)
    diff.json, diff_<a>_<b>.png  difference of every visit pair (backend/app/diff.py)
    exposures.fits               every single exposure behind the frames (backend/app/lightcurve.py)
    lightcurve.json              the target's brightness in every exposure
    proof.json                   measured motion vs Gaia, and the data it rests on (backend/app/proof.py)
    spots.json                   spots above 5σ in every difference, SPHEREx's position per visit (backend/app/spots.py)
    recovery.json                how often the spot rule finds planted fake movers, per pair (backend/app/recovery.py)
    visits.json                  every single exposure of each visit, with JPL's known objects (backend/app/visit_frames.py)
    visit<i>_exp<k>.png          exposure k of visit i, in time order (+ _flags.png, and _res.png = minus the visit median)
```

- `<target>` is the key from `backend/app/targets.py`: `barnard`, `eps_ind_b`, `wise0855`, `rw_aur`, `r_dra`.
- `<detector>` is 1–6, e.g. `frontend/frames/barnard/d2/`.

`index.json`:
```json
{ "format": "spherex-blink-frames-index/1", "available": { "barnard": [1, 2, 3, 4, 5, 6], "wise0855": [5, 6] } }
```

---

## 2. The sky grid (must be identical, or frames cannot be compared)

| Rule | Value |
|---|---|
| Centre | the target's position at **2026.0**: SIMBAD J2000 position moved with its proper motion (`backend/app/motion.position_at`). The website uses the same rule, so the ring lands on the same spot. |
| Projection | `RA---TAN`, `DEC--TAN` |
| Pixel size | 6.15″ (`config.PIXEL_SCALE_ARCSEC`), `CDELT1 = -6.15/3600` (east to the left), `CDELT2 = +6.15/3600` |
| Size | `round(fov_arcmin × 60 / 6.15)`, forced odd: 3′ gives **29 × 29** |
| Reference pixel | `CRPIX = (size + 1) / 2` on both axes, so the target is the centre of the middle pixel |
| PNG rows | **north at the top**: FITS row 0 is south, so flip (`np.flipud`) before saving |

Code for this grid: `target_grid()` in `backend/app/align.py`.

---

## 3. `manifest.json`

### Top level

| Field | Type | Meaning | Required |
|---|---|---|---|
| `format` | text | always `"spherex-blink-frames/1"` | yes |
| `target`, `label` | text | key and display name, e.g. `"barnard"`, `"Barnard's Star"` | yes |
| `ra`, `dec` | number (deg) | grid centre, full precision, never rounded | yes |
| `position_source` | text | where the centre came from, e.g. `"SIMBAD (simbad.harvard.edu) NAME Barnard's star, moved to 2026.0"` | yes |
| `fov_arcmin`, `pixel_arcsec`, `size_px` | number | grid size; the website draws the 1′ scale bar from these | yes |
| `orientation` | text | `"north up, east left"` | yes |
| `band` | number | detector 1–6 | yes |
| `band_range_um` | [min, max] | detector range from `config.DETECTORS` | yes |
| `mode` | text | `"single"` or `"coadd"` | yes |
| `scale` | object | `{vmin, vmax, unit: "MJy/sr", method, stretch, asinh_softening}`: one scale for every frame; `stretch` is `"linear"` or `"asinh"` | yes |
| `method` | text | one sentence: how the pictures were made | yes |
| `made_by`, `made_at` | text | which script, and when (UTC) | yes |
| `data_credit` | text | `"NASA/IPAC Infrared Science Archive (IRSA), SPHEREx"` | yes |
| `collections_checked` | list of text | active science releases queried, e.g. `["spherex_dr1", "spherex_qr3"]` | yes |
| `newest_obs_date` | text | latest observation date in the checked collections, `"YYYY-MM-DD HH:MM UTC"` | yes |
| `notes` | list of text | measured warnings, shown in an orange box | no |
| `frames` | list | one per visit, in time order | yes |

### Each frame

| Field | Type | Meaning | Required |
|---|---|---|---|
| `png` | text | file name in the same folder | yes |
| `flags_png` | text | red flagged-pixel overlay, same size | no |
| `fits` | text | the visit's data file (section 8) | no |
| `epoch_id` | number | visit number from `archive.group_epochs` | yes |
| `mjd` | number | observation time: `MJD-AVG` from header (never `DATE`) | yes |
| `date_iso` | text | `"YYYY-MM-DD HH:MM UTC"` | yes |
| `band` | number | detector 1–6 | yes |
| `wl_min_um`, `wl_max_um` | number | wavelength range of the exposure(s) | yes |
| `wl_target_um`, `bw_target_um` | number or null | wavelength and bandwidth at the target pixel from spectral WCS (`key="W"`) | yes |
| `wl_target_range_um` | [min, max] | add-ups only: lowest and highest target wavelength among exposures | no |
| `n_images` | number | exposures added in this picture | yes |
| `n_images_in_epoch` | number | exposures of this detector in the visit | no |
| `pct_flagged` | number | % of grid pixels flagged bad | yes |
| `pct_no_value` | number | % of pixels inside image with no value (NaN) | no |
| `pct_covered` | number | % of the grid inside the exposure | no |
| `release` | text | `"DR1"` or `"QR3"` | yes |
| `flag_counts` | object | bad flag names to pixel counts, e.g. `{"TRANSIENT": 12, "SUR_ERROR": 4}` | yes |
| `pixel_source` | text | provenance: `"aws-s3"` (all exposures read from S3), `"irsa-cutout"` (IRSA cutout service), or `"mixed"` | yes |
| `align_offset_px` | number or null | median centroid offset against slow-moving Gaia DR3 control stars (<0.50 px) | yes |
| `obs_id`, `collection` | text | which exposure (single mode) | no |

### PNG rules
- Grey RGBA, size `size_px × size_px`, north up.
- Grey = `t × 255` with `t = clip((value − vmin) / (vmax − vmin), 0, 1)`.
- `stretch: "asinh"`: `grey = asinh(t / a) / asinh(1 / a) × 255`, `a = asinh_softening` (0.002).
- Alpha 0 where there is no value.
- Flags PNG: `(255, 40, 40, 200)` on flagged pixels, alpha 0 elsewhere.

---

## 4. `gaia.json` (`spherex-blink-gaia/1`, made by `backend/app/gaia.py`)

| Field | Meaning |
|---|---|
| `catalogue`, `catalogue_epoch` | `"Gaia DR3 (gaia_dr3_source at NASA/IPAC IRSA)"`, `2016.0` |
| `query` | `{ra, dec, radius_deg, n_returned}` |
| `method`, `pixel_convention`, `target_match_rule` | one sentence each |
| `target_match` | `{source_id, sep_arcsec}` of nearest Gaia star at 2026.0 within 3″, or `null` |
| `frames` | `[{"epoch_id", "mjd", "year"}, ...]` |
| `stars` | one per Gaia star on the grid |

Each star in `stars`:
- `source_id` (text: 19-digit IDs)
- `g_mag` (float or null)
- `pmra`, `pmdec` (mas/year)
- `parallax` (mas)
- `has_motion` (boolean)
- `target` (true only on matched target star)
- `xy`: list of `[x, y]` per frame in PNG pixels (0 = centre of first pixel)

Positions are propagated from epoch 2016.0 to each frame's MJD using straight-line proper motion.

---

## 5. `wise.json` (`spherex-blink-wise/1`, made by `backend/app/wise.py`)

| Field | Meaning |
|---|---|
| `catalogue`, `catalogue_epoch`, `catalogue_mjd` | `"CatWISE2020 (catwise_2020 at NASA/IPAC IRSA)"`, `2015.4018`, `57170.0` |
| `query` | `{ra, dec, radius_deg, n_returned}` |
| `method`, `pixel_convention`, `target_match_rule` | one sentence each |
| `target_match` | `{source_name, sep_arcsec}` of nearest CatWISE source within 3″, or `null` |
| `frames` | `[{"epoch_id", "mjd", "year"}, ...]` |
| `sources` | one per CatWISE2020 source on the grid |

Each source in `sources`:
- `source_name` (text, e.g. `"J175748.49+044136.2"`)
- `w1_mag`, `w2_mag` (float or null: W1/W2 magnitudes)
- `w1_snr`, `w2_snr` (float or null: signal-to-noise ratio)
- `pmra`, `pmdec` (arcsec/year: CatWISE unit; converted to mas/year for coordinate propagation)
- `has_motion` (boolean)
- `target` (true only on matched target source)
- `xy`: list of `[x, y]` per frame in PNG pixels

Positions are propagated from epoch MJD 57170 (2015.4) to each frame's MJD using proper motion.

---

## 6. `diff.json` (`spherex-blink-diff/1`, made by `backend/app/diff.py`)

Top level: `target`, `band`, `size_px`, `unit`, `limit_sigma` (5), `colours` (`brighter` `#ff6e28`, `fainter` `#468cff`, `zero` `#12141a`), `method`, `row_order` (north first), `state_codes`, `default_pair`, `made_by`, `made_at`.

- `frames`: one per visit (`epoch_id`, `value`, `sigma`, `state`).
- `pairs`: every visit pair with `a < b` (`png`, `days`, `wl_a_um`, `wl_b_um`, `sky_change`, `scatter_sigma`, `pct_valid`, `pct_flagged`, `pct_no_value`, `z`).
- `default_pair`: `{a, b, reason}` (closest mean wavelength at target, then longest time apart).

---

## 7. `epoch<i>.fits` (the values behind each picture)

Primary HDU with `PIXSRC` keyword (`aws-s3`, `irsa-cutout`, or `mixed`), then 4 image extensions:
- `IMAGE`: float32, MJy/sr (IMAGE − ZODI)
- `SIGMA`: float32, MJy/sr (1σ noise from VARIANCE)
- `FLAGGED`: uint8 (1 = flagged bad)
- `HAS_VALUE`: uint8 (1 = has a usable value)

Each header contains the grid WCS plus `BUNIT`, `MJD-AVG`, `NIMAGES`, `DETECTOR`, `MODE`, and `PIXSRC`.

