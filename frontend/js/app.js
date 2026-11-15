import { matchCatalog } from "./catalog.js";
import { formatDec, formatRa, looksLikeName, parseCoordinates, parseField, splitPastedPair } from "./coords.js";
import { createDiffView } from "./diffview.js";
import { createFlipbook } from "./flipbook.js";
import { createSixEyes } from "./sixeyes.js";
import { positionAt, separationArcsec, VIEW_EPOCH } from "./motion.js";
import { createProof } from "./proof.js";
import { NameNotFound, resolveName } from "./resolve.js";
import { detectorsRated, RATINGS, TARGETS } from "./targets.js";
import { createTimeline } from "./timeline.js";
import { buildUrlState, DETECTORS, FOV_MAX, readUrlState, VIEW_DEFAULTS } from "./urlstate.js";

// Aladin Lite from two CDNs: the CDS server was unreachable on 31 Oct 2026, jsDelivr worked.
const ALADIN_SCRIPTS = [
  "https://cdn.jsdelivr.net/npm/aladin-lite@3.8.2/dist/aladin.js",
  "https://unpkg.com/aladin-lite@3.8.2/dist/aladin.js",
];

// Background images: ESA ESASky copies of the CDS surveys. They send CORS headers, which the
// WebGL map needs; the IRSA copies do not, and the CDS servers were unreachable on 31 Oct 2026.
const SURVEYS = [
  { id: "2mass", name: "2MASS near-infrared (J, H, K)", url: "https://skies.esac.esa.int/2MASSColor" },
  { id: "allwise", name: "AllWISE mid-infrared (W1, W2, W4)", url: "https://skies.esac.esa.int/AllWISEColor" },
  { id: "dss2", name: "DSS2 visible light", url: "https://skies.esac.esa.int/DSSColor" },
];
// The background surveys look very dark in the small map; lift them a little.
const MAP_LOOK = { brightness: 0.1 };

const COORD_PLACEHOLDERS = { deg: ["RA 269.452", "Dec +4.693"], hms: ["RA 17h57m48.5s", "Dec +04d41m36s"] };
const COORD_APPLY_MS = 800;   // pause in typing before a valid position is used
const ONBOARD_KEY = "spherex-blink-guide-dismissed";
const INSPECTOR_KEY = "spherex-blink-inspector-hidden";
// Same width as the one-column breakpoint in style.css: below it the inspector is a bottom sheet.
const phoneLayout = window.matchMedia("(max-width: 900px)");

const $ = (id) => document.getElementById(id);
const form = $("search-form");
const query = $("query");
const goButton = $("go");
const coordForm = $("coord-form");
const coordRa = $("coord-ra");
const coordDec = $("coord-dec");
const coordPreview = $("coord-preview");
const fovInput = $("fov");
const fovValue = $("fov-value");
const detSelect = $("det");
const surveySelect = $("survey");
const statusBox = $("status");
const selectionBox = $("selection");
const targetsBox = $("targets");
const mapMessage = $("map-message");
const suggestionsBox = $("query-suggestions");
const catalogList = $("catalog-list");
const catalogFilter = $("catalog-filter");
const split = $("split");
const inspectorToggle = $("inspector-toggle");
const sheetBackdrop = $("sheet-backdrop");
const shareButton = $("share-btn");
const fovSlowNote = $("fov-slow-note");
const fovFastMover = $("fov-fast-mover");
const dataReleases = $("data-releases");
const dataNewReleases = $("data-new-releases");
const flipDataAsOf = $("flip-data-as-of");
const mapGaiaCat = $("map-gaia-cat");
const mapWiseCat = $("map-wise-cat");

const state = { ra: null, dec: null, fov: 3, det: 2, ...VIEW_DEFAULTS, source: "", note: "", targetKey: null };
let catalog = [];
let A = null;
let aladin = null;
let fovOverlay = null;
// Bumped on every new position, so a slow SIMBAD answer cannot overwrite a newer choice.
let positionVersion = 0;
let coordUnit = "deg";
let coordTimer = null;
let flipbook = null;
let sixEyes = null;
let timeline = null;
let diffView = null;
let proofView = null;
let mapCatalogs = { gaia: null, wise: null };

function setStatus(message, kind = "info") {
  statusBox.textContent = message;
  statusBox.className = `status ${message ? kind : ""}`;
}

// The background maps are older than SPHEREx (2MASS 1997–2001, AllWISE 2010–2011, DSS2 older
// still), so fast stars sit away from today's position on them.
function oldMapWarning(movedSince2000Arcsec) {
  if (movedSince2000Arcsec < 5) return "";
  return ` The background maps are older than SPHEREx, so on 2MASS the star sits about ` +
    `${(movedSince2000Arcsec / 60).toFixed(1)}′ from the square (less on AllWISE).`;
}

function targetPosition(target) {
  return positionAt(target.ra, target.dec, target.pmra, target.pmdec, 2000.0, VIEW_EPOCH);
}

function targetMotionLine(target, ra, dec) {
  const moved = separationArcsec(target.ra, target.dec, ra, dec);
  return `Epoch ${VIEW_EPOCH.toFixed(1)} (+${moved.toFixed(1)}″ proper motion).`;
}

/** The official target within 5″ of a position, so a typed or shared position still gets its frames. */
function officialTargetAt(ra, dec) {
  return TARGETS.find((t) => {
    const p = targetPosition(t);
    return separationArcsec(p.ra, p.dec, ra, dec) < 5;
  }) || null;
}

function refreshFlipbook() {
  if (!flipbook || state.ra === null) return;
  const target = chosenTarget();
  const where = {
    targetKey: state.targetKey, label: target ? target.label : "", ra: state.ra, dec: state.dec, det: state.det, fov: state.fov,
  };
  const detail = document.querySelector(".workspace-detail");
  if (detail) detail.hidden = false;
  flipbook.show(where);
  timeline.show(where);
}

function setDetector(det) {
  state.det = det;
  detSelect.value = String(det);
  writeUrl();
  renderSelection();
  refreshFlipbook();
}

function updateFovSlowNote() {
  if (!fovSlowNote) return;
  if (state.fov > 15) {
    fovSlowNote.textContent =
      `Slower at ${state.fov}′: each exposure covers a much larger patch, so preparing these frames ` +
      "can take several minutes (it depends on how busy NASA IRSA is). The 5 prepared targets are 3′ wide.";
    fovSlowNote.hidden = false;
  } else {
    fovSlowNote.hidden = true;
    fovSlowNote.textContent = "";
  }
}

function releaseLabel(collection) {
  return collection.replace(/^spherex_/i, "").toUpperCase();
}

async function loadDataReleases() {
  if (!dataReleases && !flipDataAsOf) return;
  try {
    const body = await fetch("/api/releases").then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
    // New shape: { releases, searched, available, new_collections, newest }.
    // Older servers returned a bare array — still accept that.
    const rows = Array.isArray(body) ? body : (body.releases || []);
    if (!rows.length) throw new Error("no releases");
    const newest = (Array.isArray(body) ? null : body.newest) || rows.map((r) => r.last).sort().at(-1);
    const searched = Array.isArray(body) ? null : (body.searched || []);
    const newCols = Array.isArray(body) ? [] : (body.new_collections || []);
    const parts = rows.map((r) =>
      `${releaseLabel(r.collection)} (${r.n_images.toLocaleString()} images, ${r.first} to ${r.last})`);
    const line = `Data as of ${newest} · NASA IRSA · ${parts.join(" · ")}`;
    if (dataReleases) {
      const searchNote = searched?.length
        ? ` Searching: ${searched.map(releaseLabel).join(", ")}.`
        : "";
      dataReleases.textContent = `${line}.${searchNote} Prepared flipbooks are snapshots; any RA/Dec job pulls the latest exposures.`;
    }
    if (flipDataAsOf) flipDataAsOf.textContent = `Data as of ${newest} (live from NASA IRSA)`;
    if (dataNewReleases) {
      if (newCols.length) {
        dataNewReleases.hidden = false;
        dataNewReleases.textContent =
          `New IRSA collection(s) not searched yet: ${newCols.map(releaseLabel).join(", ")}. ` +
          `Enable with SPHEREX_COLLECTIONS (see README) — no code change needed — then re-render.`;
      } else {
        dataNewReleases.hidden = true;
        dataNewReleases.textContent = "";
      }
    }
  } catch {
    const fail = "NASA IRSA did not answer, so the release list is not shown. Frames and search still work; reload later to try again.";
    if (dataReleases) dataReleases.textContent = fail;
    if (flipDataAsOf) flipDataAsOf.textContent = "SPHEREx release info unavailable (IRSA).";
    if (dataNewReleases) {
      dataNewReleases.hidden = true;
      dataNewReleases.textContent = "";
    }
  }
}

function clearMapCatalog(which) {
  if (!aladin || !mapCatalogs[which]) return;
  aladin.removeCatalog(mapCatalogs[which]);
  mapCatalogs[which] = null;
}

function syncMapCatalogs() {
  if (!aladin || !A || state.ra === null) return;
  const target = `${state.ra} ${state.dec}`;
  const radius = Math.max(viewFovDegrees() / 2, 0.05);
  if (mapGaiaCat?.checked) {
    if (!mapCatalogs.gaia) {
      mapCatalogs.gaia = A.catalogFromVizieR("I/355/gaiadr3", target, radius, {
        color: "#9ad5ff", shape: "circle", sourceSize: 5, limit: 1500,
      });
      aladin.addCatalog(mapCatalogs.gaia);
    }
  } else clearMapCatalog("gaia");
  if (mapWiseCat?.checked) {
    if (!mapCatalogs.wise) {
      mapCatalogs.wise = A.catalogFromVizieR("II/328/allwise", target, radius, {
        color: "#ffb45a", shape: "square", sourceSize: 5, limit: 800,
      });
      aladin.addCatalog(mapCatalogs.wise);
    }
  } else clearMapCatalog("wise");
}

function refreshMapCatalogs() {
  clearMapCatalog("gaia");
  clearMapCatalog("wise");
  syncMapCatalogs();
}

function chosenTarget() {
  return TARGETS.find((t) => t.key === state.targetKey) || null;
}

/** The detector list; with an official target chosen, each option also says how it suits that target. */
function renderDetectors() {
  const target = chosenTarget();
  detSelect.innerHTML = Object.entries(DETECTORS)
    .map(([n, range]) => {
      const advice = target ? ` · ${RATINGS[target.detectors[n].rating]}` : "";
      return `<option value="${n}">D${n} · ${range}${advice}</option>`;
    })
    .join("");
  detSelect.value = String(state.det);
}

const DET_TIER_LABELS = {
  recommended: "Best",
  try: "Try",
  not: "Skip",
};

/** Compact Best / Try / Skip detector rows on hackathon target cards. */
function targetCardDetectors(target) {
  const rows = Object.keys(DET_TIER_LABELS)
    .map((rating) => {
      const dets = detectorsRated(target, rating);
      if (!dets.length) return "";
      const chips = dets
        .map((n) => {
          const why = target.detectors[n].why.replaceAll('"', "&quot;");
          const open = n === target.detector ? " target-det-open" : "";
          const openHint = n === target.detector ? " (opens here)" : "";
          return `<span class="det-chip det-${rating}${open}" title="D${n}${openHint}: ${why}">D${n}</span>`;
        })
        .join("");
      return `<div class="target-det-tier" data-rating="${rating}">
        <span class="target-det-tier-label">${DET_TIER_LABELS[rating]}</span>
        <span class="target-det-tier-chips">${chips}</span>
      </div>`;
    })
    .filter(Boolean)
    .join("");
  return rows
    ? `<div class="target-det-guide" aria-label="SPHEREx detectors for this target">${rows}</div>`
    : "";
}

function renderSurveys() {
  surveySelect.innerHTML = SURVEYS.map((s) => `<option value="${s.id}">${s.name}</option>`).join("");
}

function openTargetsCatalog() {
  const dropdown = $("targets-dropdown");
  if (dropdown) dropdown.open = true;
}

function renderTargets() {
  targetsBox.innerHTML = "";
  const namesBox = $("target-names");
  if (namesBox) namesBox.innerHTML = "";

  for (const target of TARGETS) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "target";
    button.setAttribute("aria-pressed", "false");
    button.dataset.key = target.key;
    button.innerHTML = `
      <span class="target-name">${target.label}</span>
      <span class="target-kind">${target.kind}</span>
      <span class="target-hint">${target.lookFor}</span>
      <span class="target-dets">${targetCardDetectors(target)}</span>`;
    button.addEventListener("click", () => chooseTarget(target));
    item.appendChild(button);
    targetsBox.appendChild(item);

    if (namesBox) {
      const link = document.createElement("button");
      link.type = "button";
      link.className = "targets-name-link";
      link.dataset.key = target.key;
      link.setAttribute("aria-pressed", "false");
      link.textContent = target.label;
      link.addEventListener("click", () => {
        chooseTarget(target);
        openTargetsCatalog();
      });
      namesBox.appendChild(link);
    }
  }
}

function renderSelection() {
  for (const button of targetsBox.querySelectorAll(".target")) {
    button.setAttribute("aria-pressed", String(button.dataset.key === state.targetKey));
  }
  for (const link of document.querySelectorAll(".targets-name-link")) {
    link.setAttribute("aria-pressed", String(link.dataset.key === state.targetKey));
  }
  renderDetectors();
  shareButton.disabled = state.ra === null;
  if (state.ra === null) return;
  const target = chosenTarget();
  const advice = target ? target.detectors[state.det] : null;
  const viewLine =
    `${state.fov}′ · D${state.det} (${DETECTORS[state.det]})` +
    (advice ? ` · ${RATINGS[advice.rating]}` : "");
  const foot = target ? targetMotionLine(target, state.ra, state.dec) : state.note;
  const viewTitle = advice?.why ? ` title="${advice.why.replaceAll('"', "&quot;")}"` : "";
  selectionBox.innerHTML = `
    <div class="position-summary">
      <p class="position-line"><span class="position-k">RA</span>
        <span class="position-v">${formatRa(state.ra)} · ${state.ra.toFixed(6)}°</span></p>
      <p class="position-line"><span class="position-k">Dec</span>
        <span class="position-v">${formatDec(state.dec)} · ${state.dec.toFixed(6)}°</span></p>
      <p class="position-line"><span class="position-k">View</span>
        <span class="position-v position-view"${viewTitle}>${viewLine}</span></p>
      <p class="position-line position-line-meta"><span class="position-k">From</span>
        <span class="position-v position-from"></span></p>
    </div>`;
  const fromEl = selectionBox.querySelector(".position-from");
  fromEl.textContent = foot ? `${state.source} · ${foot}` : state.source;
  if (advice?.why) fromEl.setAttribute("title", advice.why);
}

function writeUrl() {
  if (state.ra === null) return;
  history.replaceState(null, "", buildUrlState(state));
}

function viewFovDegrees() {
  return Math.max(state.fov * 3, 6) / 60;
}

function drawFovBox() {
  if (!aladin || state.ra === null) return;
  const half = state.fov / 60 / 2;
  const cosDec = Math.max(Math.cos((state.dec * Math.PI) / 180), 1e-6);
  const dRa = half / cosDec;
  const { ra, dec } = state;
  fovOverlay.removeAll();
  fovOverlay.add(A.polygon([
    [ra - dRa, dec - half], [ra + dRa, dec - half], [ra + dRa, dec + half], [ra - dRa, dec + half],
  ]));
}

function moveMap() {
  if (!aladin || state.ra === null) return;
  aladin.gotoRaDec(state.ra, state.dec);
  aladin.setFoV(viewFovDegrees());
  drawFovBox();
  refreshMapCatalogs();
}

function applyPosition({ ra, dec, source, note = "", targetKey = null, queryText = null, fromCoordBoxes = false }) {
  positionVersion += 1;
  if (targetKey === null) targetKey = officialTargetAt(ra, dec)?.key ?? null;
  Object.assign(state, { ra, dec, source, note, targetKey });
  if (queryText !== null) query.value = queryText;
  if (!fromCoordBoxes) fillCoordBoxes(ra, dec);
  writeUrl();
  renderSelection();
  moveMap();
  refreshFlipbook();
  sixEyes?.show(state.targetKey);
}

function chooseTarget(target) {
  const { ra, dec } = targetPosition(target);
  state.det = target.detector;
  detSelect.value = String(target.detector);
  const moved = separationArcsec(target.ra, target.dec, ra, dec);
  applyPosition({
    ra, dec,
    source: `Official target: ${target.label}`,
    note: `SIMBAD J2000 position moved to ${VIEW_EPOCH.toFixed(1)} with its proper motion (${moved.toFixed(1)}″). ` +
      `${target.lookFor}${oldMapWarning(moved)}`,
    targetKey: target.key,
    queryText: target.label,
  });
  setStatus(`Showing ${target.label}.`, "ok");
}

async function search(text) {
  const clean = text.trim();
  const known = TARGETS.find((t) => t.label.toLowerCase() === clean.toLowerCase());
  if (known) return chooseTarget(known);

  try {
    const { ra, dec } = parseCoordinates(clean);
    applyPosition({ ra, dec, source: "Typed position", note: "Used exactly as typed (no motion correction)." });
    setStatus("Position set.", "ok");
    return;
  } catch (parseError) {
    if (!looksLikeName(clean)) {
      setStatus(parseError.message, "error");
      return;
    }
  }

  setStatus(`Looking up "${clean}" in SIMBAD…`, "info");
  goButton.disabled = true;
  const versionAtStart = positionVersion;
  try {
    const star = await resolveName(clean);
    if (positionVersion !== versionAtStart) {
      setStatus(`Found ${star.simbadId}, but you chose another position meanwhile, so it was not used.`, "warn");
      return;
    }
    let { ra, dec } = star;
    let note = `SIMBAD (${star.server}) J2000 position. No proper motion in SIMBAD, so not moved.`;
    if (star.pmra !== null && star.pmdec !== null) {
      ({ ra, dec } = positionAt(star.ra, star.dec, star.pmra, star.pmdec, star.epoch, VIEW_EPOCH));
      const moved = separationArcsec(star.ra, star.dec, ra, dec);
      note = `SIMBAD (${star.server}) J2000 position moved to ${VIEW_EPOCH.toFixed(1)} with its proper motion (${moved.toFixed(1)}″).${oldMapWarning(moved)}`;
    }
    applyPosition({ ra, dec, source: `SIMBAD: ${star.simbadId}`, note, queryText: clean });
    setStatus(`Found ${star.simbadId}.`, "ok");
  } catch (err) {
    setStatus(err.message, err instanceof NameNotFound ? "warn" : "error");
  } finally {
    goButton.disabled = false;
  }
}

async function loadCatalog() {
  try {
    const response = await fetch("/data/catalog.json");
    if (response.ok) catalog = await response.json();
  } catch {
    catalog = [];
  }
}

function pickCatalogEntry(entry) {
  hideSuggestions();
  query.value = entry.label;
  const text = entry.official ? entry.label : entry.simbad;
  search(text);
}

function hideSuggestions() {
  suggestionsBox.hidden = true;
  query.setAttribute("aria-expanded", "false");
  suggestionsBox.innerHTML = "";
}

function renderSuggestions(matches) {
  if (!matches.length) {
    hideSuggestions();
    return;
  }
  suggestionsBox.innerHTML = matches.map((entry, i) => {
    const badge = entry.official ? '<span class="suggest-badge">Official</span>' : "";
    return `<li role="presentation"><button type="button" role="option" data-idx="${i}" id="suggest-${i}">
      <span class="suggest-name">${entry.label}${badge}</span>
      <span class="suggest-meta">${entry.category} · ${entry.hint}</span>
    </button></li>`;
  }).join("");
  for (const button of suggestionsBox.querySelectorAll("button")) {
    const entry = matches[Number(button.dataset.idx)];
    button.addEventListener("mousedown", (e) => e.preventDefault());
    button.addEventListener("click", () => pickCatalogEntry(entry));
  }
  suggestionsBox.hidden = false;
  query.setAttribute("aria-expanded", "true");
}

function updateSuggestions() {
  renderSuggestions(matchCatalog(catalog, query.value, 8));
}

function renderCatalogList(filterText = "") {
  if (!catalogList) return;
  const matches = filterText.trim() ? matchCatalog(catalog, filterText, 50) : catalog;
  catalogList.innerHTML = matches.map((entry, i) => {
    const tag = entry.official ? ' <span class="suggest-badge">Official</span>' : "";
    return `<li class="catalog-item"><button type="button" data-idx="${i}">
      <span class="suggest-name">${entry.label}${tag}</span>
      <div class="catalog-hint">${entry.category}: ${entry.hint}</div>
    </button></li>`;
  }).join("");
  for (const button of catalogList.querySelectorAll("button")) {
    const entry = matches[Number(button.dataset.idx)];
    if (!entry) continue;
    button.addEventListener("click", () => {
      query.value = entry.label;
      pickCatalogEntry(entry);
      $("catalog-browse").open = false;
    });
  }
}

function wireCatalogUi() {
  query.addEventListener("input", updateSuggestions);
  query.addEventListener("focus", updateSuggestions);
  query.addEventListener("blur", () => setTimeout(hideSuggestions, 150));
  if (catalogFilter) {
    catalogFilter.addEventListener("input", () => renderCatalogList(catalogFilter.value));
  }
  const browse = $("catalog-browse");
  browse.addEventListener("toggle", () => { if (browse.open) catalogFilter.focus(); });
  document.addEventListener("click", (event) => {
    if (browse.open && !browse.contains(event.target)) browse.open = false;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && browse.open) {
      browse.open = false;
      browse.querySelector("summary").focus();
    }
  });
  renderCatalogList();
}

function setGuideOpen(open) {
  const modal = $("onboard-guide");
  const help = $("help-toggle");
  const dialog = modal?.querySelector(".guide-dialog");
  if (!modal) return;
  modal.hidden = !open;
  document.body.classList.toggle("guide-open", open);
  if (help) help.setAttribute("aria-expanded", String(open));
  if (open) {
    dialog?.focus();
  } else {
    help?.focus();
  }
}

function wireOnboarding() {
  const modal = $("onboard-guide");
  const help = $("help-toggle");
  const dialog = modal?.querySelector(".guide-dialog");
  if (!modal) return;

  if (dialog) {
    if (!dialog.hasAttribute("tabindex")) dialog.setAttribute("tabindex", "-1");
  }

  const closeGuide = (remember = false) => {
    if (remember) localStorage.setItem(ONBOARD_KEY, "1");
    setGuideOpen(false);
  };

  if (localStorage.getItem(ONBOARD_KEY) !== "1") setGuideOpen(true);

  help?.addEventListener("click", () => {
    setGuideOpen(modal.hidden);
  });

  for (const id of ["onboard-dismiss", "onboard-close", "onboard-backdrop"]) {
    $(id)?.addEventListener("click", () => closeGuide(id === "onboard-dismiss"));
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeGuide(false);
  });

  $("onboard-try")?.addEventListener("click", () => {
    const barnard = TARGETS.find((t) => t.key === "barnard");
    if (barnard) chooseTarget(barnard);
    closeGuide(true);
    document.querySelector(".flipbook")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(location.href);
    shareButton.textContent = "Copied";
    setStatus("Shareable link copied (RA/Dec in the URL — paste anywhere or use as an iframe src).", "ok");
    setTimeout(() => { shareButton.textContent = "Share"; }, 1500);
  } catch {
    setStatus(`Copy this embeddable link: ${location.href}`, "info");
  }
}

// The sky map panel: a column that can be hidden on wide screens (remembered),
// a bottom sheet on narrow ones (closed until asked for).

function inspectorOpen() {
  return phoneLayout.matches ? split.classList.contains("sheet-open") : !split.classList.contains("inspector-closed");
}

function syncInspector() {
  const open = inspectorOpen();
  inspectorToggle.setAttribute("aria-expanded", String(open));
  sheetBackdrop.hidden = !(phoneLayout.matches && open);
  document.body.classList.toggle("sheet-locked", phoneLayout.matches && open);
}

function setInspector(open) {
  if (phoneLayout.matches) {
    split.classList.toggle("sheet-open", open);
  } else {
    split.classList.toggle("inspector-closed", !open);
    localStorage.setItem(INSPECTOR_KEY, open ? "0" : "1");
  }
  syncInspector();
}

function wireInspector() {
  split.classList.toggle("inspector-closed", localStorage.getItem(INSPECTOR_KEY) === "1");
  inspectorToggle.addEventListener("click", () => setInspector(!inspectorOpen()));
  $("inspector-close").addEventListener("click", () => setInspector(false));
  sheetBackdrop.addEventListener("click", () => setInspector(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && phoneLayout.matches && inspectorOpen() && $("onboard-guide").hidden) setInspector(false);
  });
  phoneLayout.addEventListener("change", () => {
    split.classList.remove("sheet-open");
    syncInspector();
  });
  syncInspector();
}

function readCoordBoxes() {
  return { ra: parseField(coordRa.value, true, coordUnit), dec: parseField(coordDec.value, false, coordUnit) };
}

/** The boxes as degrees, shown under them; null (and the reason shown) when they cannot be read. */
function updatePreview() {
  coordPreview.classList.remove("error");
  if (!coordRa.value.trim() && !coordDec.value.trim()) {
    coordPreview.textContent = "";
    return null;
  }
  try {
    const { ra, dec } = readCoordBoxes();
    coordPreview.textContent =
      `= ${ra.toFixed(4)}°, ${dec >= 0 ? "+" : ""}${dec.toFixed(4)}° · ${formatRa(ra)} ${formatDec(dec)}`;
    return { ra, dec };
  } catch (err) {
    coordPreview.textContent = err.message;
    coordPreview.classList.add("error");
    return null;
  }
}

function showUnit(unit) {
  coordUnit = unit;
  for (const button of coordForm.querySelectorAll("[data-unit]")) {
    button.setAttribute("aria-pressed", String(button.dataset.unit === unit));
  }
  [coordRa.placeholder, coordDec.placeholder] = COORD_PLACEHOLDERS[unit];
}

function fillCoordBoxes(ra, dec) {
  coordRa.value = coordUnit === "deg" ? ra.toFixed(6) : formatRa(ra);
  coordDec.value = coordUnit === "deg" ? `${dec >= 0 ? "+" : ""}${dec.toFixed(6)}` : formatDec(dec);
  updatePreview();
}

/** Switching units rewrites what is typed, when it can be read. */
function changeUnit(unit) {
  if (unit === coordUnit) return;
  let position = null;
  try {
    position = readCoordBoxes();
  } catch {
    // leave the text as typed; the preview says what is wrong
  }
  showUnit(unit);
  if (position) fillCoordBoxes(position.ra, position.dec);
  else updatePreview();
}

function useCoordBoxes() {
  clearTimeout(coordTimer);
  const position = updatePreview();
  if (!position) return false;
  if (position.ra === state.ra && position.dec === state.dec) return true;
  applyPosition({
    ...position,
    source: "Typed coordinates",
    note: "Used exactly as typed (no motion correction).",
    queryText: `${position.ra.toFixed(5)} ${position.dec.toFixed(5)}`,
    fromCoordBoxes: true,
  });
  setStatus("Position set.", "ok");
  return true;
}

function onCoordInput() {
  clearTimeout(coordTimer);
  if (updatePreview()) coordTimer = setTimeout(useCoordBoxes, COORD_APPLY_MS);
}

function onCoordPaste(event) {
  const pair = splitPastedPair(event.clipboardData?.getData("text") ?? "");
  if (!pair) return;
  event.preventDefault();
  showUnit(pair.unit);
  coordRa.value = pair.ra;
  coordDec.value = pair.dec;
  onCoordInput();
}

// The npm build of Aladin Lite 3.8 is an ES module (export default), not a global script.
async function loadAladin() {
  for (const src of ALADIN_SCRIPTS) {
    try {
      return (await import(src)).default;
    } catch {
      // try the next CDN
    }
  }
  return null;
}

async function startMap() {
  A = await loadAladin();
  if (!A) {
    mapMessage.textContent = "The sky map could not load (Aladin Lite is unreachable). Search, targets and share links still work.";
    return;
  }
  try {
    await A.init;
  } catch (err) {
    mapMessage.textContent = `The sky map could not start (${err}). Search, targets and share links still work.`;
    return;
  }
  mapMessage.remove();
  const first = state.ra !== null ? state : targetPosition(TARGETS[0]);
  aladin = A.aladin("#aladin", {
    survey: SURVEYS[0].url,
    target: `${first.ra} ${first.dec}`,
    fov: state.ra !== null ? viewFovDegrees() : 0.5,
    cooFrame: "ICRS",
    showReticle: true,
    reticleColor: "#ffffff",
    showZoomControl: true,
    showFullscreenControl: true,
    showLayersControl: false,
    showGotoControl: false,
    showProjectionControl: false,
    showSimbadPointerControl: false,
    showShareControl: false,
    showCooGrid: false,
    showFrame: true,
  });
  aladin.setBaseImageLayer(A.imageHiPS(SURVEYS[0].url, { name: SURVEYS[0].name, ...MAP_LOOK }));
  fovOverlay = A.graphicOverlay({ color: "#ffffff", lineWidth: 2 });
  aladin.addOverlay(fovOverlay);
  // Aladin sometimes reports the end of a pan as a click; only a still press picks a position.
  const mapBox = $("aladin");
  let pressedAt = null;
  let wasDrag = false;
  mapBox.addEventListener("pointerdown", (e) => { pressedAt = [e.clientX, e.clientY]; wasDrag = false; }, true);
  mapBox.addEventListener("pointerup", (e) => {
    wasDrag = pressedAt !== null && Math.hypot(e.clientX - pressedAt[0], e.clientY - pressedAt[1]) > 5;
    pressedAt = null;
  }, true);
  aladin.on("click", (event) => {
    if (event.isDragging || wasDrag) return;
    applyPosition({
      ra: event.ra,
      dec: event.dec,
      source: "Clicked on the sky map",
      note: "Position picked on the map.",
      queryText: `${event.ra.toFixed(5)} ${event.dec.toFixed(5)}`,
    });
    setStatus("Position set from the map.", "ok");
  });
  drawFovBox();
}

function changeSurvey() {
  const survey = SURVEYS.find((s) => s.id === surveySelect.value);
  if (!aladin || !survey) return;
  aladin.setBaseImageLayer(A.imageHiPS(survey.url, { name: survey.name, ...MAP_LOOK }));
}

async function start() {
  await loadCatalog();
  wireInspector();
  wireOnboarding();
  wireCatalogUi();
  renderDetectors();
  renderSurveys();
  renderTargets();

  const fromUrl = readUrlState(location.search);
  for (const key of ["fov", "det", ...Object.keys(VIEW_DEFAULTS)]) state[key] = fromUrl[key];
  fovInput.value = String(state.fov);
  fovValue.textContent = String(state.fov);
  updateFovSlowNote();
  detSelect.value = String(state.det);
  loadDataReleases();
  if (fromUrl.problems.length) setStatus(fromUrl.problems.join(" "), "warn");
  timeline = createTimeline({ onDetector: setDetector });
  diffView = createDiffView();
  proofView = createProof();
  flipbook = createFlipbook({
    onDetector: setDetector,
    onFrames: (loaded) => {
      timeline.markFrames(loaded);
      diffView.show(loaded);
      proofView.show(loaded);
    },
    view: state,
    onView: (changes) => {
      Object.assign(state, changes);
      writeUrl();
    },
  });
  sixEyes = createSixEyes();
  if (fromUrl.ra !== null) {
    const target = officialTargetAt(fromUrl.ra, fromUrl.dec);
    applyPosition({
      ra: fromUrl.ra,
      dec: fromUrl.dec,
      source: target ? `Official target: ${target.label}` : "Shared link",
      note: target ? "" : "Position from the link.",
      targetKey: target ? target.key : null,
      queryText: target ? target.label : `${fromUrl.ra.toFixed(5)} ${fromUrl.dec.toFixed(5)}`,
    });
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    search(query.value);
  });
  shareButton.addEventListener("click", copyLink);
  coordForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!useCoordBoxes()) setStatus(coordPreview.textContent, "error");
  });
  for (const box of [coordRa, coordDec]) {
    box.addEventListener("input", onCoordInput);
    box.addEventListener("paste", onCoordPaste);
  }
  for (const button of coordForm.querySelectorAll("[data-unit]")) {
    button.addEventListener("click", () => changeUnit(button.dataset.unit));
  }
  fovInput.max = String(FOV_MAX);
  fovInput.addEventListener("input", () => {
    fovValue.textContent = fovInput.value;
    state.fov = Number(fovInput.value);
    updateFovSlowNote();
  });
  fovInput.addEventListener("change", () => {
    state.fov = Number(fovInput.value);
    writeUrl();
    renderSelection();
    updateFovSlowNote();
    moveMap();
    refreshFlipbook();
  });
  fovFastMover?.addEventListener("click", () => {
    state.fov = FOV_MAX;
    fovInput.value = String(FOV_MAX);
    fovValue.textContent = String(FOV_MAX);
    updateFovSlowNote();
    writeUrl();
    renderSelection();
    moveMap();
    refreshFlipbook();
  });
  for (const [box, key] of [[mapGaiaCat, "gaia"], [mapWiseCat, "wise"]]) {
    box?.addEventListener("change", () => {
      if (box.checked) syncMapCatalogs();
      else clearMapCatalog(key);
    });
  }
  detSelect.addEventListener("change", () => setDetector(Number(detSelect.value)));
  surveySelect.addEventListener("change", changeSurvey);

  startMap();
}

start();
