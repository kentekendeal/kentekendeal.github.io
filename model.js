// Kenteken Deal — shared data + calculation logic (used by index.html and calibrate.html).
// All numbers that need tuning live in PARAMS / constants at the top.

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
const euro = (n) => "€ " + Math.round(n).toLocaleString("nl-NL");
const num = (s) => { const n = parseFloat(String(s).replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", ".")); return isFinite(n) ? n : null; };
const parseDate = (s) => s ? new Date(+s.slice(0,4), +s.slice(4,6) - 1, +s.slice(6,8)) : null;
const fmtDate = (d) => d ? d.toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" }) : "–";
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
  if (!carRes.ok) throw new Error("De RDW is nu niet bereikbaar. Probeer het later opnieuw.");
  const cars = await carRes.json();
  const fuel = fuelRes.ok ? await fuelRes.json() : [];
  fuel.sort((a, b) => (+a.brandstof_volgnummer || 0) - (+b.brandstof_volgnummer || 0));
  return { car: cars[0], fuel };
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
  const fuelLabel = isEV ? "Elektrisch"
    : isPHEV ? `Plug-in hybride (${cap(fuelType)})`
    : isHybrid ? `Hybride (${cap(fuelType)})`
    : cap(fuelType) || "–";
  return { f, main, elec, fuelType, fuelLabel, isEV, isHybrid, isPHEV, first, age,
           kw: kw ? Math.round(kw) : null, kwElec: isHybrid && kwElec ? Math.round(kwElec) : null };
}

// ---------- value estimate ----------
// Depreciation from catalogue price; optional mileage narrows the range.
function estimateValue(car, fx, km, ageAhead = 0, P = PARAMS) {
  const price = +car.catalogusprijs;
  if (car.voertuigsoort !== "Personenauto") return { ok: false, reason: "Waardeschatting is alleen beschikbaar voor personenauto's." };
  if (!price || fx.age == null) return { ok: false, reason: "Geen nieuwprijs bekend bij de RDW voor deze auto." };
  const age = fx.age + ageAhead;
  if (age > 25) return { ok: false, reason: "Klassieker (25+ jaar): de waarde hangt vooral af van staat en zeldzaamheid." };

  let factor = age < 1 ? 1 - P.year1Drop * age
    : (1 - P.year1Drop) * Math.pow(1 - P.yearlyDrop, Math.min(age, 6) - 1) * Math.pow(1 - P.oldDrop, Math.max(age - 6, 0));
  const notes = [];

  if (HOLDS_VALUE.includes(car.merk)) { factor *= P.brandUp; notes.push("merk houdt waarde goed vast"); }
  if (LOSES_VALUE.includes(car.merk)) { factor *= P.brandDown; notes.push("merk verliest sneller waarde"); }

  // Gradual penalties (no sudden jump at a birthday).
  const ramp = (from, to) => Math.min(1, Math.max(0, (age - from) / (to - from)));
  if (fx.fuelType === "diesel" && age > 5) { factor *= 1 - P.dieselMax * ramp(5, 10); if (age > 7) notes.push("oudere diesel (milieuzones)"); }
  if (fx.isEV && age > 1) { factor *= 1 - P.evMax * ramp(1, 4); if (age > 3) notes.push("oudere EV"); }
  if (/onlogisch/i.test(car.tellerstandoordeel || "")) { factor *= 0.80; notes.push("kilometerstand onlogisch"); }

  if (km != null) {
    const perYear = fx.fuelType === "diesel" ? KM_PER_YEAR_TYPICAL.diesel : KM_PER_YEAR_TYPICAL.other;
    const expected = Math.max(age, 0.5) * perYear;
    const adj = Math.min(1.15, Math.max(0.65, 1 - P.kmPer10k * (km - expected) / 10000));
    factor *= adj;
    if (adj < 0.97) notes.push(`veel km voor de leeftijd (normaal ±${Math.round(expected / 1000)}k)`);
    if (adj > 1.03) notes.push(`weinig km voor de leeftijd (normaal ±${Math.round(expected / 1000)}k)`);
  }

  const mid = Math.max(price * factor, 500);
  const spread = km != null ? 0.15 : 0.25;
  return { ok: true, mid, low: round250(mid * (1 - spread)), high: round250(mid * (1 + spread)), price, age, notes, withKm: km != null };
}

// ---------- deal verdict ----------
function verdict(asking, v) {
  const r = asking / v.mid, diff = asking - v.mid;
  if (r < 0.6)  return ["warn", "Verdacht goedkoop", `${euro(-diff)} onder onze schatting. Kan een koopje zijn, maar check schade, onderhoud en eigendom extra goed.`];
  if (r < 0.88) return ["good", "Goede deal", `Ongeveer ${euro(-diff)} onder onze schatting.`];
  if (r <= 1.1) return ["ok", "Eerlijke prijs", "De vraagprijs ligt rond onze schatting."];
  if (r <= 1.3) return ["warn", "Aan de prijzige kant", `Ongeveer ${euro(diff)} boven onze schatting. Ruimte om te onderhandelen.`];
  return ["bad", "Te duur", `Ongeveer ${euro(diff)} boven onze schatting.`];
}

// ---------- road tax (MRB) estimate, 2026 ----------
// Calibrated on 2026 amounts for Noord-Brabant (87 opcenten, near the national middle).
// Petrol: 1000 kg ≈ €93, 1200 ≈ €148, 1500 ≈ €231 per quarter. Diesel: 246 / 334 / 466.
function roadTaxPerMonth(car, fx) {
  if (car.voertuigsoort !== "Personenauto") return null;
  if (fx.age != null && fx.age >= 40) return { amount: 0, note: "oldtimer: vrijgesteld" };
  let kg = +car.massa_ledig_voertuig || (+car.massa_rijklaar - 100);
  if (!kg) return null;
  if (fx.isEV) kg -= 125; // EV weight correction

  const above = (kg - 1000) / 100;
  let quarter;
  if (fx.fuelType === "diesel") quarter = above >= 0 ? 246 + 44 * above : Math.max(150, 246 + 30 * above);
  else                          quarter = above >= 0 ? 93 + 27.7 * above : Math.max(40, 93 + 20 * above);

  let note = "";
  if (fx.fuelType === "lpg") { quarter *= 1.5; note = "LPG-toeslag (grof)"; }
  if (fx.fuelType === "diesel" && /EURO [1-4]\b/i.test(fx.main.uitlaatemissieniveau || "")) { quarter *= 1.15; note = "fijnstoftoeslag oude diesel"; }
  if (fx.isEV) { quarter *= 0.70; note = "EV: 70% van benzinetarief in 2026"; }
  return { amount: quarter / 3, note };
}

// ---------- fuel cost ----------
function fuelPerMonth(fx, kmYear) {
  const f = fx.isEV ? fx.f : fx.main;
  if (fx.isEV) {
    const whkm = +f.elektrisch_verbruik_enkel_elektrisch_wltp;
    if (!whkm) return null;
    return { amount: kmYear / 12 * whkm / 1000 * FUEL_PRICE.elektriciteit, use: `${Math.round(whkm / 10)} kWh/100 km` };
  }
  let l = +f.brandstof_verbruik_gecombineerd_wltp;
  if (!l && +f.brandstofverbruik_gecombineerd) l = +f.brandstofverbruik_gecombineerd * 1.2; // NEDC → realistic
  if (!l) return null;
  if (fx.isPHEV) l = Math.max(l, 4.5); // real-world PHEV use without daily charging is higher than WLTP
  const price = FUEL_PRICE[fx.fuelType] || FUEL_PRICE.benzine;
  return { amount: kmYear / 12 * l / 100 * price, use: `${l.toFixed(1)} l/100 km` };
}
