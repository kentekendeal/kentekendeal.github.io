// Kenteken Deal — shared data + calculation logic (used by index.html and calibrate.html).
// All numbers that need tuning live in PARAMS / constants at the top.
// User-facing text comes from i18n.js (t("key")); load i18n.js before this file.

const API = "https://opendata.rdw.nl/resource/";

// ---------- tunable assumptions ----------
const PARAMS = {
  year1Drop: 0.20,   // value lost in the first year
  yearlyDrop: 0.12,  // value lost per year in years 2–6 (on remaining value)
  oldDrop: 0.05,     // value lost per year after year 6 (older cars lose value more slowly)
  brandUp: 1.08,     // brands that hold value
  brandDown: 0.90,   // brands that lose value faster
  dieselMax: 0.10,   // extra loss for old diesels (ramps in from 5 → 10 years)
  evMax: 0.10,       // extra loss for older EVs (ramps in from 1 → 4 years)
  kmPer10k: 0.03,    // value change per 10.000 km above/below normal
};
const FUEL_PRICE = { benzine: 1.95, diesel: 1.75, lpg: 0.95, elektriciteit: 0.35 }; // € per liter / kWh
const KM_PER_YEAR_TYPICAL = { diesel: 20000, other: 13000 };
const HOLDS_VALUE = ["TOYOTA","LEXUS","PORSCHE","SUZUKI","MAZDA","HONDA","KIA","HYUNDAI","MINI","VOLKSWAGEN","SKODA"];
const LOSES_VALUE = ["MASERATI","ALFA ROMEO","JAGUAR","LAND ROVER","CITROEN","DS","FIAT","RENAULT","OPEL","INFINITI","NISSAN"];

// ---------- helpers ----------
const clean = (s) => String(s).toUpperCase().replace(/[^A-Z0-9]/g, "");
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
const euro = (n) => "€ " + Math.round(n).toLocaleString(LOCALE());
const num = (s) => { const n = parseFloat(String(s).replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", ".")); return isFinite(n) ? n : null; };
const parseDate = (s) => s ? new Date(+s.slice(0,4), +s.slice(4,6) - 1, +s.slice(6,8)) : null;
const fmtDate = (d) => d ? d.toLocaleDateString(LOCALE(), { day: "numeric", month: "long", year: "numeric" }) : "–";
const cap = (s) => s ? s.charAt(0) + s.slice(1).toLowerCase() : "";
const known = (v) => v && !/niet geregistreerd|n\.v\.t\.|geen verstrekking/i.test(v);
const round250 = (n) => Math.max(250, Math.round(n / 250) * 250);
// Brand names that don't follow simple capitalisation. Keep in sync with tools/build_pages.py.
const BRAND_NAMES = { "BMW": "BMW", "MERCEDES-BENZ": "Mercedes-Benz", "LYNK&CO": "Lynk & Co", "ALFA ROMEO": "Alfa Romeo",
  "LAND ROVER": "Land Rover", "DS": "DS", "MG": "MG", "BYD": "BYD", "CITROEN": "Citroën", "MINI": "Mini", "KIA": "Kia" };
const brandName = (b) => BRAND_NAMES[b] || (b || "").split(" ").map(cap).join(" ");
// "COROLLA" → "Corolla", "T-ROC" → "T-Roc"; keep codes like "XC60", "ID.3", "C-HR" in capitals.
const modelName = (m) => /^I\d+$/.test(m) ? m.toLowerCase()   // Hyundai i10, i20, i30
  : m === m.toUpperCase()
  ? m.split(" ").map(w => w.split("-").map(p => /\d/.test(p) || p.length <= 2 ? p : cap(p)).join("-")).join(" ")
  : m;
// "AUDI" + "AUDI A1" → "Audi A1"
const carName = (car) => {
  const brand = car.merk || "";
  let model = (car.handelsbenaming || "").trim();
  if (brand && model.toUpperCase().startsWith(brand + " ")) model = model.slice(brand.length + 1);
  if (brand === "LYNK&CO") model = model.replace(/^LYNK & CO /i, "");
  return `${brandName(brand)} ${modelName(model)}`.trim();
};

// ---------- RDW lookup ----------
async function lookup(plate) {
  const [carRes, fuelRes] = await Promise.all([
    fetch(`${API}m9d7-ebf2.json?kenteken=${plate}`),
    fetch(`${API}8ys7-d773.json?kenteken=${plate}`),
  ]);
  if (!carRes.ok) throw new Error(t("rdwDown"));
  const cars = await carRes.json();
  const fuel = fuelRes.ok ? await fuelRes.json() : [];
  fuel.sort((a, b) => (+a.brandstof_volgnummer || 0) - (+b.brandstof_volgnummer || 0));
  return { car: cars[0], fuel };
}

// APK history (RDW publishes inspections from June 2022 onwards).
// Returns [{ date, defects: [{ id, text, count, advice }] }], newest first.
// Codes AC*/RA*/OP* are advisories ("adviespunten"), everything else is a defect found at the inspection.
async function apkHistory(plate) {
  const q = (d, extra = "") => fetch(`${API}${d}.json?kenteken=${plate}${extra}&$limit=500`).then(r => r.ok ? r.json() : Promise.reject());
  const [checks, found] = await Promise.all([
    q("sgfe-77wx", "&soort_melding_ki_omschrijving=periodieke%20controle"),
    q("a34c-vvps"),
  ]);
  const byDate = new Map();
  const visit = (d) => { if (!byDate.has(d)) byDate.set(d, { date: parseDate(d), defects: [] }); return byDate.get(d); };
  for (const c of checks) visit(c.meld_datum_door_keuringsinstantie);
  for (const g of found) visit(g.meld_datum_door_keuringsinstantie).defects.push({
    id: g.gebrek_identificatie, count: +g.aantal_gebreken_geconstateerd || 1,
    advice: /^(AC|RA|OP)\d/.test(g.gebrek_identificatie || ""),
  });
  const ids = [...new Set(found.map(g => g.gebrek_identificatie).filter(id => /^[A-Z0-9]{1,6}$/i.test(id)))];
  const texts = {};
  if (ids.length) {
    const where = encodeURIComponent(`gebrek_identificatie in(${ids.map(id => `'${id}'`).join(",")})`);
    try {
      for (const d of await fetch(`${API}hx2c-gt7k.json?$where=${where}&$limit=500`).then(r => r.json()))
        texts[d.gebrek_identificatie] = d.gebrek_omschrijving;
    } catch { /* descriptions are optional */ }
  }
  const list = [...byDate.values()].filter(x => x.date).sort((a, b) => b.date - a.date);
  for (const x of list) {
    for (const g of x.defects) g.text = texts[g.id] || t("apkUnknownDefect", { id: g.id });
    x.defects.sort((a, b) => a.advice - b.advice);
  }
  return list;
}

// Derived facts used by several features.
function facts(car, fuel) {
  const f = fuel[0] || {};
  const types = fuel.map(x => (x.brandstof_omschrijving || "").toLowerCase());
  const elec = fuel.find(x => /elektriciteit/i.test(x.brandstof_omschrijving)) || null;
  const isEV = types.length === 1 && types[0] === "elektriciteit";
  const isHybrid = !isEV && !!elec;
  // RDW: OVC-HEV = plug-in hybrid, NOVC-HEV = normal (self-charging) hybrid.
  const hybridClass = fuel.map(x => x.klasse_hybride_elektrisch_voertuig).find(Boolean) || "";
  const isPHEV = isHybrid && (hybridClass ? hybridClass === "OVC-HEV" : !!elec.actie_radius_enkel_elektrisch_wltp);
  const main = (fuel.find(x => !/elektriciteit/i.test(x.brandstof_omschrijving)) || f);
  const fuelType = isEV ? "elektriciteit" : (main.brandstof_omschrijving || "").toLowerCase();
  const first = parseDate(car.datum_eerste_toelating);
  const age = first ? (Date.now() - first) / (365.25 * 864e5) : null;
  const kwElec = elec ? (+elec.netto_max_vermogen_elektrisch || +elec.nominaal_continu_maximumvermogen || null) : null;
  const kw = isEV ? kwElec : (+main.nettomaximumvermogen || null);
  const fuelName = t("fuel_" + fuelType) !== "fuel_" + fuelType ? t("fuel_" + fuelType) : cap(fuelType);
  const fuelLabel = isEV ? t("fElectric")
    : isPHEV ? t("fPlugin", { fuel: fuelName })
    : isHybrid ? t("fHybrid", { fuel: fuelName })
    : fuelName || "–";
  return { f, main, elec, fuelType, fuelName, fuelLabel, isEV, isHybrid, isPHEV, first, age,
           kw: kw ? Math.round(kw) : null, kwElec: isHybrid && kwElec ? Math.round(kwElec) : null };
}

// ---------- value estimate ----------
// Depreciation from catalogue price; optional mileage narrows the range.
function estimateValue(car, fx, km, ageAhead = 0, P = PARAMS) {
  const price = +car.catalogusprijs;
  if (car.voertuigsoort !== "Personenauto") return { ok: false, reason: t("reasonNotCar") };
  if (!price || fx.age == null) return { ok: false, reason: t("reasonNoPrice") };
  const age = fx.age + ageAhead;
  if (age > 25) return { ok: false, reason: t("reasonClassic") };

  let factor = age < 1 ? 1 - P.year1Drop * age
    : (1 - P.year1Drop) * Math.pow(1 - P.yearlyDrop, Math.min(age, 6) - 1) * Math.pow(1 - P.oldDrop, Math.max(age - 6, 0));
  const notes = [];

  if (HOLDS_VALUE.includes(car.merk)) { factor *= P.brandUp; notes.push(t("noteBrandUp")); }
  if (LOSES_VALUE.includes(car.merk)) { factor *= P.brandDown; notes.push(t("noteBrandDown")); }

  // Gradual penalties (no sudden jump at a birthday).
  const ramp = (from, to) => Math.min(1, Math.max(0, (age - from) / (to - from)));
  if (fx.fuelType === "diesel" && age > 5) { factor *= 1 - P.dieselMax * ramp(5, 10); if (age > 7) notes.push(t("noteOldDiesel")); }
  if (fx.isEV && age > 1) { factor *= 1 - P.evMax * ramp(1, 4); if (age > 3) notes.push(t("noteOldEV")); }
  if (/onlogisch/i.test(car.tellerstandoordeel || "")) { factor *= 0.80; notes.push(t("noteKmBad")); }

  if (km != null) {
    const perYear = fx.fuelType === "diesel" ? KM_PER_YEAR_TYPICAL.diesel : KM_PER_YEAR_TYPICAL.other;
    const expected = Math.max(age, 0.5) * perYear;
    const adj = Math.min(1.15, Math.max(0.65, 1 - P.kmPer10k * (km - expected) / 10000));
    factor *= adj;
    if (adj < 0.97) notes.push(t("noteHighKm", { k: Math.round(expected / 1000) }));
    if (adj > 1.03) notes.push(t("noteLowKm", { k: Math.round(expected / 1000) }));
  }

  const mid = Math.max(price * factor, 500);
  const spread = km != null ? 0.15 : 0.25;
  return { ok: true, mid, low: round250(mid * (1 - spread)), high: round250(mid * (1 + spread)), price, age, notes, withKm: km != null };
}

// ---------- deal verdict ----------
function verdict(asking, v) {
  const r = asking / v.mid, diff = asking - v.mid;
  if (r < 0.6)  return ["warn", t("vSuspTitle"), t("vSuspText", { diff: euro(-diff) })];
  if (r < 0.88) return ["good", t("vGoodTitle"), t("vGoodText", { diff: euro(-diff) })];
  if (r <= 1.1) return ["ok", t("vFairTitle"), t("vFairText")];
  if (r <= 1.3) return ["warn", t("vPriceyTitle"), t("vPriceyText", { diff: euro(diff) })];
  return ["bad", t("vExpTitle"), t("vExpText", { diff: euro(diff) })];
}

// ---------- road tax (MRB) estimate, 2026 ----------
// Calibrated on 2026 amounts for Noord-Brabant (87 opcenten, near the national middle).
// Petrol: 1000 kg ≈ €93, 1200 ≈ €148, 1500 ≈ €231 per quarter. Diesel: 246 / 334 / 466.
// Provincial surcharge (opcenten) 2026. They are charged on the petrol base rate, so the difference
// with Noord-Brabant is: base × (opc − 87) / 100, where base = petrol amount NB / 1.87.
// Sources: ANWB, provincial budgets 2026. Friesland lowered to 92.1 from March 2026.
const OPCENTEN = { GR: 95.7, FR: 92.1, DR: 92.0, OV: 82.2, FL: 84.7, GE: 98.3, UT: 86.4, NH: 82.1, ZH: 104.4, ZE: 84.4, NB: 87.0, LI: 88.5 };
const PROVINCES = { GR: "Groningen", FR: "Friesland", DR: "Drenthe", OV: "Overijssel", FL: "Flevoland", GE: "Gelderland",
  UT: "Utrecht", NH: "Noord-Holland", ZH: "Zuid-Holland", ZE: "Zeeland", NB: "Noord-Brabant", LI: "Limburg" };
const OPC_BASE = 87.0;

function roadTaxPerMonth(car, fx, prov = "") {
  if (car.voertuigsoort !== "Personenauto") return null;
  if (fx.age != null && fx.age >= 40) return { amount: 0, note: t("taxOldtimer") };
  let kg = +car.massa_ledig_voertuig || (+car.massa_rijklaar - 100);
  if (!kg) return null;
  if (fx.isEV) kg -= 125; // EV weight correction

  const above = (kg - 1000) / 100;
  const petrol = above >= 0 ? 93 + 27.7 * above : Math.max(40, 93 + 20 * above);
  let quarter = fx.fuelType === "diesel" ? (above >= 0 ? 246 + 44 * above : Math.max(150, 246 + 30 * above)) : petrol;

  let note = "";
  if (fx.fuelType === "lpg") { quarter *= 1.5; note = t("taxLpg"); }
  if (fx.fuelType === "diesel" && /EURO [1-4]\b/i.test(fx.main.uitlaatemissieniveau || "")) { quarter *= 1.15; note = t("taxSoot"); }
  const opc = OPCENTEN[prov];
  if (opc) quarter += petrol / (1 + OPC_BASE / 100) * (opc - OPC_BASE) / 100;
  if (fx.isEV) { quarter *= 0.70; note = t("taxEV"); }
  return { amount: Math.max(0, quarter / 3), note };
}

// ---------- fuel cost ----------
function fuelPerMonth(fx, kmYear) {
  const f = fx.isEV ? fx.f : fx.main;
  if (fx.isEV) {
    const whkm = +f.elektrisch_verbruik_enkel_elektrisch_wltp;
    if (!whkm) return null;
    return { amount: kmYear / 12 * whkm / 1000 * FUEL_PRICE.elektriciteit, use: `${Math.round(whkm / 10)} kWh/100 km` };
  }
  // Plug-ins often only have a "weighted" figure (assumes charging every day, e.g. 1.0 l/100 km).
  let l = +f.brandstof_verbruik_gecombineerd_wltp || +f.brandstof_verbruik_gewogen_gecombineerd_wltp;
  if (!l && +f.brandstofverbruik_gecombineerd) l = +f.brandstofverbruik_gecombineerd * 1.2; // NEDC → realistic
  // No consumption figure at all (happens for some hybrids): derive it from CO₂ (g/km per l/100 km).
  if (!l && +f.emissie_co2_gecombineerd_wltp) l = +f.emissie_co2_gecombineerd_wltp / ({ diesel: 26.4, lpg: 16.6 }[fx.fuelType] || 23.1);
  if (fx.isPHEV) l = Math.max(l || 0, 4.5); // real-world PHEV use without daily charging is higher than WLTP
  if (!l) return null;
  const price = FUEL_PRICE[fx.fuelType] || FUEL_PRICE.benzine;
  return { amount: kmYear / 12 * l / 100 * price, use: `${l.toFixed(1)} l/100 km` };
}
