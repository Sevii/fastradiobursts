"use strict";
// FRB Catalog 2 visual review — vanilla JS, no dependencies.

const STATUS = {
  eligible:               { label: "Eligible",      color: "--good",     ic: "✓" },
  provisionally_eligible: { label: "Provisional",   color: "--warning",  ic: "◐" },
  pending_manual_review:  { label: "Manual review", color: "--serious",  ic: "?" },
  processing_failure:     { label: "Proc. failure", color: "--critical", ic: "⚠" },
  excluded:               { label: "Excluded",      color: "--critical", ic: "✗" },
};
const STATUS_ORDER = ["eligible", "provisionally_eligible", "pending_manual_review",
                      "processing_failure", "excluded"];
const PAGE = 100;
const SVGNS = "http://www.w3.org/2000/svg";

let META = null, ALL = [], COLS = [];
let dmLo = 0, dmHi = 3;               // fixed log10 DM domain for the sky-map ramp
const SEQ = ["--seq-100", "--seq-250", "--seq-400", "--seq-550", "--seq-700"];

const state = {
  statuses: new Set(STATUS_ORDER),
  search: "", repeater: "", morph: "", reason: "",
  dmMin: null, dmMax: null, snrMin: null, snrMax: null,
  sortKey: "obs_utc", sortDir: 1, page: 0,
};

const $ = (id) => document.getElementById(id);
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

function trimG(s) { return s.indexOf("e") >= 0 ? s : (s.indexOf(".") >= 0 ? s.replace(/\.?0+$/, "") : s); }
function fmtNum(v, fmt) {
  if (v === null || v === undefined || v === "" || Number.isNaN(v)) return "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (!fmt) return String(v);
  const m = /^\.(\d+)([fg])$/.exec(fmt);
  if (m) { const d = +m[1]; return m[2] === "f" ? (+v).toFixed(d) : trimG((+v).toPrecision(d)); }
  return String(v);
}

// ── load ────────────────────────────────────────────────────────────────
async function boot() {
  [META, ALL] = await Promise.all([
    fetch("meta.json").then(r => r.json()),
    fetch("bursts.json").then(r => r.json()),
  ]);
  COLS = META.columns;
  // fixed DM color domain (log10 p5..p95) so color meaning is stable across filters
  const dms = ALL.map(b => b.dm_fitb).filter(v => v != null && v > 0).sort((a, b) => a - b);
  if (dms.length) {
    dmLo = Math.log10(dms[Math.floor(dms.length * 0.05)]);
    dmHi = Math.log10(dms[Math.floor(dms.length * 0.95)]);
    if (dmHi <= dmLo) dmHi = dmLo + 1;
  }
  $("subtitle").textContent =
    `${META.n_bursts.toLocaleString()} bursts · ${META.n_with_tierb.toLocaleString()} with Tier B waterfalls · `
    + `${META.n_repeaters} repeaters · generated ${META.generated_utc.replace("T", " ").replace("+00:00", " UTC")}`;
  initFilters();
  bindEvents();
  render();
}

function initFilters() {
  const morphs = [...new Set(ALL.map(b => b.morphology_label).filter(Boolean))].sort();
  for (const m of morphs) { const o = document.createElement("option"); o.value = m; o.textContent = m; $("fMorph").appendChild(o); }
  const reasons = [...new Set(ALL.map(b => b.primary_reason).filter(Boolean))].sort();
  for (const r of reasons) {
    const o = document.createElement("option"); o.value = r;
    o.textContent = META.reason_legend[r] ? `${r} — ${META.reason_legend[r]}` : r;
    $("fReason").appendChild(o);
  }
}

// ── filtering ───────────────────────────────────────────────────────────
function passes(b) {
  if (!state.statuses.has(b.status)) return false;
  if (state.search && !(b.tns_name || "").toLowerCase().includes(state.search)) return false;
  if (state.repeater === "1" && !b.is_repeater) return false;
  if (state.repeater === "0" && b.is_repeater) return false;
  if (state.morph && b.morphology_label !== state.morph) return false;
  if (state.reason && b.primary_reason !== state.reason) return false;
  const dm = b.dm_fitb;
  if (state.dmMin != null && !(dm != null && dm >= state.dmMin)) return false;
  if (state.dmMax != null && !(dm != null && dm <= state.dmMax)) return false;
  const sn = b.catalog_snr;
  if (state.snrMin != null && !(sn != null && sn >= state.snrMin)) return false;
  if (state.snrMax != null && !(sn != null && sn <= state.snrMax)) return false;
  return true;
}
function filtered() { return ALL.filter(passes); }

// ── render orchestration ────────────────────────────────────────────────
function render() {
  const rows = filtered();
  renderKpis(rows);
  renderChips();
  renderCharts(rows);
  renderTable(rows);
}

function renderKpis(rows) {
  const el = $("kpis"); el.innerHTML = "";
  const repeaters = rows.filter(b => b.is_repeater).length;
  const withWf = rows.filter(b => b.has_tierb).length;
  const kpis = [
    ["Showing", rows.length.toLocaleString()],
    ["of total", ALL.length.toLocaleString()],
    ["Repeaters", repeaters.toLocaleString()],
    ["With waterfall", withWf.toLocaleString()],
  ];
  for (const [l, v] of kpis) {
    const d = document.createElement("div"); d.className = "kpi";
    d.innerHTML = `<div class="v">${v}</div><div class="l">${l}</div>`;
    el.appendChild(d);
  }
}

function renderChips() {
  const el = $("statusChips"); el.innerHTML = "";
  const counts = {}; for (const b of ALL) counts[b.status] = (counts[b.status] || 0) + 1;
  for (const s of STATUS_ORDER) {
    if (!(s in counts)) continue;
    const meta = STATUS[s] || { label: s, color: "--muted", ic: "" };
    const on = state.statuses.has(s);
    const c = document.createElement("div");
    c.className = "chip" + (on ? "" : " off");
    c.innerHTML = `<span class="dot" style="background:${cssVar(meta.color)}"></span>`
      + `<span class="ic" style="color:${cssVar(meta.color)}">${meta.ic}</span>`
      + `<span>${meta.label}</span><span class="n">${counts[s].toLocaleString()}</span>`;
    c.onclick = () => { if (state.statuses.has(s)) state.statuses.delete(s); else state.statuses.add(s); state.page = 0; render(); };
    el.appendChild(c);
  }
}

// ── charts ──────────────────────────────────────────────────────────────
function renderCharts(rows) {
  const c = $("charts"); c.innerHTML = "";
  c.appendChild(histCard("DM (pc cm⁻³)", rows.map(b => b.dm_fitb), false));
  c.appendChild(histCard("S/N (log₁₀)", rows.map(b => b.catalog_snr), true));
  c.appendChild(histCard("Fluence (log₁₀ Jy ms)", rows.map(b => b.fluence), true));
  c.appendChild(histCard("Burst width (log₁₀ s)", rows.map(b => b.bc_width), true));
  c.appendChild(skyCard(rows));
}

function svgEl(tag, attrs) { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }

function histCard(title, raw, log) {
  const card = document.createElement("div"); card.className = "card";
  const h = document.createElement("h3"); h.textContent = title; card.appendChild(h);
  let vals = raw.filter(v => v != null && !Number.isNaN(v));
  if (log) vals = vals.filter(v => v > 0).map(v => Math.log10(v));
  const W = 240, H = 118, m = { l: 26, r: 6, t: 6, b: 16 };
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}` });
  if (vals.length < 2) { const t = svgEl("text", { x: W / 2, y: H / 2, "text-anchor": "middle" }); t.textContent = "no data"; svg.appendChild(t); card.appendChild(svg); return card; }
  let lo = Math.min(...vals), hi = Math.max(...vals); if (hi === lo) hi = lo + 1;
  const NB = 24, counts = new Array(NB).fill(0);
  for (const v of vals) { let i = Math.floor((v - lo) / (hi - lo) * NB); if (i === NB) i = NB - 1; counts[i]++; }
  const cmax = Math.max(...counts);
  const px = (i) => m.l + i / NB * (W - m.l - m.r);
  const py = (v) => H - m.b - v / cmax * (H - m.t - m.b);
  svg.appendChild(svgEl("line", { class: "axisline", x1: m.l, y1: H - m.b, x2: W - m.r, y2: H - m.b }));
  for (let i = 0; i < NB; i++) {
    const x = px(i), w = px(i + 1) - px(i) - 1, y = py(counts[i]);
    const bar = svgEl("rect", { class: "bar", x: x, y: y, width: Math.max(w, 0.5), height: (H - m.b) - y, rx: 1 });
    const lo_i = lo + i / NB * (hi - lo), hi_i = lo + (i + 1) / NB * (hi - lo);
    const tt = svgEl("title"); tt.textContent = `${trimG(lo_i.toPrecision(3))}–${trimG(hi_i.toPrecision(3))}: ${counts[i]}`;
    bar.appendChild(tt); svg.appendChild(bar);
  }
  for (const frac of [0, 0.5, 1]) {
    const v = lo + frac * (hi - lo);
    const t = svgEl("text", { x: px(NB * frac), y: H - 4, "text-anchor": frac === 0 ? "start" : frac === 1 ? "end" : "middle" });
    t.textContent = trimG(v.toPrecision(3)); svg.appendChild(t);
  }
  const ct = svgEl("text", { x: 2, y: m.t + 8 }); ct.textContent = cmax; svg.appendChild(ct);
  card.appendChild(svg); return card;
}

function skyCard(rows) {
  const card = document.createElement("div"); card.className = "card wide";
  const h = document.createElement("h3"); h.textContent = "Sky position (RA / Dec) — colour = DM"; card.appendChild(h);
  const W = 500, H = 240, m = { l: 30, r: 8, t: 8, b: 22 };
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}` });
  const X = (ra) => m.l + ra / 360 * (W - m.l - m.r);
  const Y = (dec) => m.t + (90 - dec) / 180 * (H - m.t - m.b);
  // grid
  for (const ra of [0, 90, 180, 270, 360]) { svg.appendChild(svgEl("line", { class: "gridline", x1: X(ra), y1: m.t, x2: X(ra), y2: H - m.b })); const t = svgEl("text", { x: X(ra), y: H - 6, "text-anchor": "middle" }); t.textContent = ra + "°"; svg.appendChild(t); }
  for (const dec of [-90, -45, 0, 45, 90]) { svg.appendChild(svgEl("line", { class: "gridline", x1: m.l, y1: Y(dec), x2: W - m.r, y2: Y(dec) })); const t = svgEl("text", { x: 3, y: Y(dec) + 3 }); t.textContent = dec + "°"; svg.appendChild(t); }
  const seq = SEQ.map(cssVar);
  for (const b of rows) {
    if (b.ra == null || b.dec == null) continue;
    let col = cssVar("--muted");
    if (b.dm_fitb != null && b.dm_fitb > 0) { const tnorm = (Math.log10(b.dm_fitb) - dmLo) / (dmHi - dmLo); col = seq[Math.max(0, Math.min(4, Math.floor(tnorm * 5)))]; }
    const dot = svgEl("circle", { cx: X(b.ra), cy: Y(b.dec), r: b.is_repeater ? 2.6 : 1.6, fill: col, "fill-opacity": 0.85 });
    if (b.is_repeater) { dot.setAttribute("stroke", cssVar("--violet")); dot.setAttribute("stroke-width", "0.8"); }
    const tt = svgEl("title"); tt.textContent = `${b.tns_name}  RA ${fmtNum(b.ra, ".1f")}  Dec ${fmtNum(b.dec, ".1f")}  DM ${fmtNum(b.dm_fitb, ".0f")}`;
    dot.appendChild(tt); dot.style.cursor = "pointer"; dot.onclick = () => openDrawer(b);
    svg.appendChild(dot);
  }
  card.appendChild(svg);
  const cap = document.createElement("div"); cap.style.cssText = "font-size:11px;color:var(--muted);padding:2px 2px 6px";
  cap.textContent = `DM ramp ${Math.round(10 ** dmLo)}→${Math.round(10 ** dmHi)} pc cm⁻³ (light→dark) · ringed = repeater`;
  card.appendChild(cap);
  return card;
}

// ── table ───────────────────────────────────────────────────────────────
function renderTable(rows) {
  const sorted = rows.slice().sort((a, b) => {
    let x = a[state.sortKey], y = b[state.sortKey];
    if (x == null) return 1; if (y == null) return -1;
    if (typeof x === "string") return state.sortDir * x.localeCompare(y);
    return state.sortDir * (x - y);
  });
  const npages = Math.max(1, Math.ceil(sorted.length / PAGE));
  if (state.page >= npages) state.page = npages - 1;
  const slice = sorted.slice(state.page * PAGE, state.page * PAGE + PAGE);

  const thead = $("tbl").querySelector("thead"); thead.innerHTML = "";
  const tr = document.createElement("tr");
  for (const c of COLS) {
    const th = document.createElement("th"); if (c.kind === "num") th.className = "num";
    const arrow = state.sortKey === c.key ? `<span class="arrow">${state.sortDir > 0 ? "▲" : "▼"}</span>` : "";
    th.innerHTML = `${c.label} ${arrow}`;
    th.onclick = () => { if (state.sortKey === c.key) state.sortDir *= -1; else { state.sortKey = c.key; state.sortDir = c.kind === "num" ? -1 : 1; } render(); };
    tr.appendChild(th);
  }
  thead.appendChild(tr);

  const tb = $("tbl").querySelector("tbody"); tb.innerHTML = "";
  for (const b of slice) {
    const tr = document.createElement("tr");
    tr.onclick = () => openDrawer(b);
    for (const c of COLS) {
      const td = document.createElement("td");
      if (c.kind === "status") { const s = STATUS[b.status] || { label: b.status, color: "--muted" };
        td.innerHTML = `<span class="pill"><span class="dot" style="background:${cssVar(s.color)}"></span>${s.label}</span>`;
      } else if (c.kind === "id") {
        td.innerHTML = `${b.tns_name}${b.is_repeater ? ' <span class="tag rep">R</span>' : ""}${b.quarantined ? ' <span class="tag">candidate</span>' : ""}`;
      } else if (c.kind === "bool") { td.textContent = b[c.key] ? "yes" : "no";
      } else if (c.kind === "cat") { td.textContent = b[c.key] || "—";
      } else { td.textContent = fmtNum(b[c.key], c.fmt); }
      tr.appendChild(td);
    }
    tb.appendChild(tr);
  }
  $("tableCount").textContent = `${sorted.length.toLocaleString()} bursts match`;
  $("pageInfo").textContent = `page ${state.page + 1} / ${npages}`;
  $("prev").disabled = state.page === 0;
  $("next").disabled = state.page >= npages - 1;
}

// ── detail drawer ───────────────────────────────────────────────────────
function kvRow(k, v) { return `<div class="row"><span class="k">${k}</span><span class="val">${v}</span></div>`; }
function openDrawer(b) {
  const s = STATUS[b.status] || { label: b.status, color: "--muted", ic: "" };
  const wf = `/api/waterfall/${b.tns_name}.png`;
  const loc = `/api/localization/${b.tns_name}.png`;
  const reasons = [];
  if (b.primary_reason) reasons.push(b.primary_reason + (META.reason_legend[b.primary_reason] ? ` — ${META.reason_legend[b.primary_reason]}` : ""));
  if (b.secondary_reasons) for (const r of String(b.secondary_reasons).split(",").map(x => x.trim()).filter(Boolean)) reasons.push(r + (META.reason_legend[r] ? ` — ${META.reason_legend[r]}` : ""));

  const science = [
    ["S/N", fmtNum(b.catalog_snr, ".1f")], ["DM (fitb)", fmtNum(b.dm_fitb, ".1f")],
    ["DM err", fmtNum(b.dm_fitb_err, ".2f")], ["DM (bonsai)", fmtNum(b.bonsai_dm, ".1f")],
    ["DM exc NE2001", fmtNum(b.dm_exc_ne2001, ".1f")], ["DM exc YMW16", fmtNum(b.dm_exc_ymw16, ".1f")],
    ["Fluence", fmtNum(b.fluence, ".2f") + " Jy ms"], ["Flux", fmtNum(b.flux, ".2f") + " Jy"],
    ["Width", fmtNum(b.bc_width, ".3g") + " s"], ["Scattering", fmtNum(b.scat_time, ".3g") + " s"],
    ["Spectral idx", fmtNum(b.sp_idx, ".2f")], ["Spectral run", fmtNum(b.sp_run, ".2f")],
    ["Peak freq", fmtNum(b.peak_freq, ".0f") + " MHz"], ["Sub-bursts", fmtNum(b.n_subbursts)],
    ["Morphology", b.morphology_label || "—"],
  ];
  const quality = [
    ["Usable bandwidth", fmtNum(b.usable_bandwidth_mhz, ".0f") + " MHz"],
    ["Usable channels", fmtNum(b.n_usable_channels)], ["Time bins", fmtNum(b.num_time)],
    ["Masked pixel frac", fmtNum(b.orig_masked_pixel_frac, ".3f")],
    ["Off-pulse region", b.has_pulse_region ? "yes" : "no"],
    ["Calibration", b.has_calibration ? "yes" : "no"],
    ["Time downsample", fmtNum(b.time_downsample_factor)],
    ["Has Tier B", b.has_tierb ? "yes" : "no"],
  ];
  const postime = [
    ["RA", fmtNum(b.ra, ".3f") + "°"], ["RA err", fmtNum(b.ra_err, ".3f")],
    ["Dec", fmtNum(b.dec, ".3f") + "°"], ["Dec err", fmtNum(b.dec_err, ".3f")],
    ["Galactic l", fmtNum(b.gl, ".2f") + "°"], ["Galactic b", fmtNum(b.gb, ".2f") + "°"],
    ["Obs UTC", b.obs_utc || "—"], ["DM incoherent", fmtNum(b.dm_incoherent, ".1f")],
  ];
  const prov = [
    ["Event ID", b.event_id ?? "—"], ["Repeater name", b.repeater_name || "—"],
    ["Config hash", b.config_hash || "—"], ["Code commit", (b.code_commit || "").slice(0, 10) || "—"],
  ];
  const grid = (arr) => `<div class="kv">${arr.map(([k, v]) => kvRow(k, v)).join("")}</div>`;

  $("drawerBody").innerHTML =
    `<h2>${b.tns_name}${b.is_repeater ? ' <span class="tag rep">repeater</span>' : ""}${b.quarantined ? ' <span class="tag">candidate · quarantined</span>' : ""}</h2>`
    + `<div class="status-line"><span class="pill"><span class="dot" style="background:${cssVar(s.color)}"></span>`
      + `<span style="color:${cssVar(s.color)}">${s.ic}</span> <strong>${s.label}</strong></span>`
      + `${b.reversible ? ' <span class="tag">reversible</span>' : ""}</div>`
    + (reasons.length ? `<div class="explain">${b.explanation || ""}<div class="reasons">${reasons.map(r => "• " + r).join("<br>")}</div></div>` : (b.explanation ? `<div class="explain">${b.explanation}</div>` : ""))
    + `<div class="sec">Standardized dynamic spectrum</div>`
    + `<img class="plot" src="${wf}" alt="waterfall" loading="lazy">`
    + `<div class="sec">Localization</div>`
    + `<img class="plot" src="${loc}" alt="localization" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='block'">`
    + `<div class="imgcap" style="display:none">no localization image for this burst</div>`
    + `<div class="sec">Burst science</div>${grid(science)}`
    + `<div class="sec">Data quality</div>${grid(quality)}`
    + `<div class="sec">Position &amp; time</div>${grid(postime)}`
    + `<div class="sec">Provenance</div>${grid(prov)}`
    + `<div style="margin-top:10px"><a href="/api/pdf/${b.tns_name}" target="_blank">Open source data PDF ↗</a></div>`;
  $("drawer").classList.add("open"); $("drawer").setAttribute("aria-hidden", "false");
  $("drawerBg").classList.add("open");
}
function closeDrawer() { $("drawer").classList.remove("open"); $("drawerBg").classList.remove("open"); $("drawer").setAttribute("aria-hidden", "true"); }

// ── events ──────────────────────────────────────────────────────────────
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
function bindEvents() {
  const num = (v) => v === "" ? null : (Number.isNaN(+v) ? null : +v);
  const upd = debounce(() => {
    state.search = $("fSearch").value.trim().toLowerCase();
    state.repeater = $("fRepeater").value; state.morph = $("fMorph").value; state.reason = $("fReason").value;
    state.dmMin = num($("fDmMin").value); state.dmMax = num($("fDmMax").value);
    state.snrMin = num($("fSnrMin").value); state.snrMax = num($("fSnrMax").value);
    state.page = 0; render();
  }, 160);
  for (const id of ["fSearch", "fRepeater", "fMorph", "fReason", "fDmMin", "fDmMax", "fSnrMin", "fSnrMax"])
    $(id).addEventListener("input", upd);
  $("fReset").onclick = () => {
    for (const id of ["fSearch", "fRepeater", "fMorph", "fReason", "fDmMin", "fDmMax", "fSnrMin", "fSnrMax"]) $(id).value = "";
    Object.assign(state, { search: "", repeater: "", morph: "", reason: "", dmMin: null, dmMax: null, snrMin: null, snrMax: null, statuses: new Set(STATUS_ORDER), page: 0 });
    render();
  };
  $("prev").onclick = () => { if (state.page > 0) { state.page--; render(); } };
  $("next").onclick = () => { state.page++; render(); };
  $("drawerClose").onclick = closeDrawer; $("drawerBg").onclick = closeDrawer;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
}

boot().catch(e => { $("subtitle").textContent = "failed to load: " + e; });
