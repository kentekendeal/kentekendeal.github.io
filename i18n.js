// KentekenDeal: translations (Dutch = default, English = optional).
// Use t("key", { var: value }) in code; {var} placeholders are filled in.
// Load this file BEFORE model.js.

const I18N = {
  nl: {
    // page
    docTitle: "KentekenDeal: is deze auto zijn prijs waard?",
    navCars: "Auto's", navGuide: "Koopgids",
    heroTitle: "Is deze auto zijn prijs waard?",
    heroLead: "Vul een kenteken in en zie direct wat de auto waard is, of de vraagprijs eerlijk is en wat hij per maand kost.",
    plateLabel: "Kenteken", tryLabel: "Probeer:", recentLabel: "Recent:",
    footerNote: "Data: RDW Open Data. Waarde en kosten zijn schattingen, geen taxatie of officiële berekening.",
    footerModels: "Waarde per model", footerGuide: "Koopgids", footerChecklist: "Checklist tweedehands auto",
    // home
    howTitle: "Zo werkt het",
    step1T: "Vul het kenteken in", step1D: "We halen alle gegevens op bij de RDW.",
    step2T: "Vul de vraagprijs in", step2D: "Uit de advertentie, plus de kilometerstand.",
    step3T: "Zie of het een deal is", step3D: "Van koopje tot te duur, plus de kosten per maand.",
    popularTitle: "Populaire modellen", allModels: "Alle modellen →",
    guideTitle: "Koopgids", guideChecklist: "Checklist tweedehands auto kopen", guideImport: "Importauto kopen", guideCosts: "Wat kost een auto per maand?",
    // messages
    invalidPlate: "Vul een geldig kenteken in.",
    notFound: "Geen voertuig gevonden met kenteken {plate}.",
    notFoundHint: "Controleer het kenteken. Buitenlandse kentekens kunnen we niet opzoeken.",
    genericError: "Er ging iets mis.",
    rdwDown: "De RDW is nu niet bereikbaar. Probeer het later opnieuw.",
    // car card
    tileYear: "Bouwjaar", tilePower: "Vermogen", tileFuel: "Brandstof", tileApk: "APK tot",
    badgeApkExpired: "APK verlopen", badgeApkSoon: "APK verloopt binnenkort", badgeApkOk: "APK geldig",
    badgeKmBad: "Km-stand onlogisch", badgeKmOk: "Km-stand logisch", badgeRecall: "Openstaande terugroepactie",
    badgeUninsured: "Niet verzekerd (normaal bij dealervoorraad)", badgeExport: "Gemeld voor export", badgeImport: "Geïmporteerd",
    share: "Deel deze check", shareCopied: "Link gekopieerd ✓", shareTitle: "{car}: is dit een goede deal?",
    hp: "pk", hpElectric: "pk elektrisch", kmh: "km/u",
    // deal card
    dealTitle: "Waarde & deal-check", askLabel: "Vraagprijs (€)", kmLabel: "Kilometerstand", egAsk: "bijv. 8500", egKm: "bijv. 85000",
    valueLabel: "Je koopt deze auto ongeveer voor",
    mTooCheap: "Te goedkoop?", mBargain: "Koopje", mFair: "Eerlijk", mPricey: "Prijzig", mTooExp: "Te duur",
    askHint: "Vul de <b>vraagprijs</b> in om te zien of het een goede deal is.",
    valueNote: "Nieuwprijs {price} · {age} jaar oud",
    noteWithKm: "Staat en opties zijn niet meegenomen.", noteNoKm: "Met de kilometerstand wordt de schatting scherper.",
    // costs card
    costsTitle: "Kosten per maand", perMonth: "per maand", kmYearLabel: "Jouw km per jaar",
    costTax: "Wegenbelasting", costTaxSub: "schatting gemiddelde provincie", costPower: "Stroom", costFuel: "Brandstof",
    costDep: "Waardeverlies", costDepSub: "wat de auto per maand minder waard wordt",
    provLabel: "Provincie", provAvg: "Gemiddeld", insLabel: "Verzekering € p/m", insPh: "bijv. 65",
    costIns: "Verzekering", costInsSub: "jouw eigen premie", costTaxProv: "{prov}, {opc} opcenten",
    costsNoteIns: "Exclusief onderhoud. Brandstof: benzine € {b}, diesel € {d}, stroom € {e}/kWh.",
    costsNote: "Exclusief verzekering en onderhoud. Brandstof: benzine € {b}, diesel € {d}, stroom € {e}/kWh.",
    noCosts: "Voor dit voertuig kunnen we geen kosten berekenen.",
    compareText: "Vergelijk met wat nu te koop staat ({car}, bouwjaar {from}–{to}):", compareTextNoYear: "Vergelijk met wat nu te koop staat ({car}):",
    // APK history
    apkTitle: "APK-geschiedenis", apkChecks: "Keuringen", apkDefectsL: "Gebreken", apkAdviceL: "Adviespunten",
    apkClean: "Geen gebreken", apkDefect1: "1 gebrek", apkDefectN: "{n} gebreken", apkAdviceOnly: "Alleen advies", apkAdviceTag: "advies",
    apkNone: "Geen APK-keuringen gevonden sinds juni 2022.",
    apkTooNew: "Nog geen APK gehad: deze auto is te nieuw. De eerste APK is na 3 jaar (diesel, LPG, elektrisch) of 4 jaar (benzine, hybride).",
    apkNote: "Bron: RDW, keuringen vanaf juni 2022. Gebreken zijn bij de APK gevonden en meestal direct gerepareerd. Adviespunten zijn geen afkeur, maar wel iets om bij een proefrit op te letten.",
    apkError: "De APK-geschiedenis kon nu niet geladen worden.", apkUnknownDefect: "Gebrekcode {id}", apkDutch: "",
    apkMore: "Toon alle {n} keuringen",
    // specs
    specsTitle: "Specificaties", gEngine: "Motor & verbruik", gSize: "Afmetingen & gewicht", gReg: "Registratie",
    sFuel: "Brandstof", sPower: "Vermogen", sCc: "Motorinhoud", sCyl: "Cilinders", sUse: "Verbruik (WLTP)", sEUse: "Stroomverbruik (WLTP)",
    sRange: "Elektrische actieradius", sCo2: "CO₂ (WLTP)", sEuro: "Emissieklasse", sTop: "Topsnelheid",
    sBody: "Carrosserie", sDoors: "Deuren / zitplaatsen", sDims: "Lengte × breedte × hoogte", sMass: "Leeggewicht",
    sTowB: "Max. trekgewicht geremd", sTowU: "Max. trekgewicht ongeremd",
    sPlate: "Kenteken", sFirst: "Eerste toelating", sFirstNL: "Eerste keer op NL kenteken", sApk: "APK tot", sColour: "Kleur",
    sPrice: "Nieuwprijs (catalogus)", sLabel: "Zuinigheidslabel",
    // fuel
    fElectric: "Elektrisch", fPlugin: "Plug-in hybride ({fuel})", fHybrid: "Hybride ({fuel})", fPluginShort: "Plug-in", fHybridShort: "Hybride",
    fuel_benzine: "Benzine", fuel_diesel: "Diesel", fuel_lpg: "LPG", fuel_elektriciteit: "Elektrisch", fuel_waterstof: "Waterstof", fuel_cng: "CNG",
    // model.js: value estimate
    reasonNotCar: "Waardeschatting is alleen beschikbaar voor personenauto's.",
    reasonNoPrice: "Geen nieuwprijs bekend bij de RDW voor deze auto.",
    reasonClassic: "Klassieker (25+ jaar): de waarde hangt vooral af van staat en zeldzaamheid.",
    noteBrandUp: "merk houdt waarde goed vast", noteBrandDown: "merk verliest sneller waarde",
    noteOldDiesel: "oudere diesel (milieuzones)", noteOldEV: "oudere EV", noteKmBad: "kilometerstand onlogisch",
    noteHighKm: "veel km voor de leeftijd (normaal ±{k}k)", noteLowKm: "weinig km voor de leeftijd (normaal ±{k}k)",
    // model.js: verdict
    vSuspTitle: "Verdacht goedkoop", vSuspText: "{diff} onder onze schatting. Kan een koopje zijn, maar check schade, onderhoud en eigendom extra goed.",
    vGoodTitle: "Goede deal", vGoodText: "Ongeveer {diff} onder onze schatting.",
    vFairTitle: "Eerlijke prijs", vFairText: "De vraagprijs ligt rond onze schatting.",
    vPriceyTitle: "Aan de prijzige kant", vPriceyText: "Ongeveer {diff} boven onze schatting. Ruimte om te onderhandelen.",
    vExpTitle: "Te duur", vExpText: "Ongeveer {diff} boven onze schatting.",
    // model.js: road tax notes
    taxOldtimer: "oldtimer: vrijgesteld", taxLpg: "LPG-toeslag (grof)", taxSoot: "fijnstoftoeslag oude diesel", taxEV: "EV: 70% van benzinetarief in 2026",
  },

  en: {
    docTitle: "KentekenDeal: is this car worth the price?",
    navCars: "Car models", navGuide: "Buying guide",
    heroTitle: "Is this car worth the price?",
    heroLead: "Enter a Dutch licence plate and instantly see what the car is worth, whether the asking price is fair and what it costs per month.",
    plateLabel: "Licence plate", tryLabel: "Try:", recentLabel: "Recent:",
    footerNote: "Data: RDW Open Data. Values and costs are estimates, not an official valuation or calculation.",
    footerModels: "Value per model", footerGuide: "Buying guide", footerChecklist: "Used car checklist",
    howTitle: "How it works",
    step1T: "Enter the licence plate", step1D: "We fetch all vehicle data from the RDW (Dutch vehicle authority).",
    step2T: "Enter the asking price", step2D: "From the ad, plus the mileage.",
    step3T: "See if it's a good deal", step3D: "From bargain to too expensive, plus the monthly costs.",
    popularTitle: "Popular models", allModels: "All models →",
    guideTitle: "Buying guide", guideChecklist: "Used car buying checklist", guideImport: "Buying an imported car", guideCosts: "What does a car cost per month?",
    invalidPlate: "Enter a valid licence plate.",
    notFound: "No vehicle found with licence plate {plate}.",
    notFoundHint: "Check the plate. We can only look up Dutch licence plates.",
    genericError: "Something went wrong.",
    rdwDown: "The RDW can't be reached right now. Please try again later.",
    tileYear: "Year", tilePower: "Power", tileFuel: "Fuel", tileApk: "MOT (APK) until",
    badgeApkExpired: "MOT (APK) expired", badgeApkSoon: "MOT (APK) expires soon", badgeApkOk: "MOT (APK) valid",
    badgeKmBad: "Mileage not logical", badgeKmOk: "Mileage logical", badgeRecall: "Open recall",
    badgeUninsured: "Not insured (normal for dealer stock)", badgeExport: "Registered for export", badgeImport: "Imported",
    share: "Share this check", shareCopied: "Link copied ✓", shareTitle: "{car}: is this a good deal?",
    hp: "hp", hpElectric: "hp electric", kmh: "km/h",
    dealTitle: "Value & deal check", askLabel: "Asking price (€)", kmLabel: "Mileage (km)", egAsk: "e.g. 8500", egKm: "e.g. 85000",
    valueLabel: "You can buy this car for about",
    mTooCheap: "Too cheap?", mBargain: "Bargain", mFair: "Fair", mPricey: "Pricey", mTooExp: "Too expensive",
    askHint: "Enter the <b>asking price</b> to see if it's a good deal.",
    valueNote: "New price {price} · {age} years old",
    noteWithKm: "Condition and options are not included.", noteNoKm: "Add the mileage for a sharper estimate.",
    costsTitle: "Costs per month", perMonth: "per month", kmYearLabel: "Your km per year",
    costTax: "Road tax", costTaxSub: "estimate, average province", costPower: "Electricity", costFuel: "Fuel",
    costDep: "Depreciation", costDepSub: "how much value the car loses each month",
    provLabel: "Province", provAvg: "Average", insLabel: "Insurance € per month", insPh: "e.g. 65",
    costIns: "Insurance", costInsSub: "your own premium", costTaxProv: "{prov}, {opc} provincial surcharge",
    costsNoteIns: "Excluding maintenance. Fuel: petrol € {b}, diesel € {d}, electricity € {e}/kWh.",
    costsNote: "Excluding insurance and maintenance. Fuel: petrol € {b}, diesel € {d}, electricity € {e}/kWh.",
    noCosts: "We can't calculate costs for this vehicle.",
    compareText: "Compare with what's for sale right now ({car}, {from}–{to}):", compareTextNoYear: "Compare with what's for sale right now ({car}):",
    // APK history
    apkTitle: "MOT (APK) history", apkChecks: "Inspections", apkDefectsL: "Defects", apkAdviceL: "Advisories",
    apkClean: "No defects", apkDefect1: "1 defect", apkDefectN: "{n} defects", apkAdviceOnly: "Advisories only", apkAdviceTag: "advisory",
    apkNone: "No MOT (APK) inspections found since June 2022.",
    apkTooNew: "No MOT (APK) yet: this car is too new. The first APK is after 3 years (diesel, LPG, electric) or 4 years (petrol, hybrid).",
    apkNote: "Source: RDW, inspections from June 2022. Defects were found at the APK and usually repaired straight away. Advisories are not a failure, but worth checking on a test drive.",
    apkError: "The MOT (APK) history couldn't be loaded right now.", apkUnknownDefect: "Defect code {id}", apkDutch: "Some rare defect descriptions are only available in Dutch, as published by the RDW.",
    apkMore: "Show all {n} inspections",
    specsTitle: "Specifications", gEngine: "Engine & consumption", gSize: "Dimensions & weight", gReg: "Registration",
    sFuel: "Fuel", sPower: "Power", sCc: "Engine size", sCyl: "Cylinders", sUse: "Fuel use (WLTP)", sEUse: "Energy use (WLTP)",
    sRange: "Electric range", sCo2: "CO₂ (WLTP)", sEuro: "Emission class", sTop: "Top speed",
    sBody: "Body type", sDoors: "Doors / seats", sDims: "Length × width × height", sMass: "Empty weight",
    sTowB: "Max. towing weight (braked)", sTowU: "Max. towing weight (unbraked)",
    sPlate: "Licence plate", sFirst: "First registration", sFirstNL: "First Dutch registration", sApk: "MOT (APK) until", sColour: "Colour",
    sPrice: "New price (list price)", sLabel: "Energy label",
    fElectric: "Electric", fPlugin: "Plug-in hybrid ({fuel})", fHybrid: "Hybrid ({fuel})", fPluginShort: "Plug-in", fHybridShort: "Hybrid",
    fuel_benzine: "Petrol", fuel_diesel: "Diesel", fuel_lpg: "LPG", fuel_elektriciteit: "Electric", fuel_waterstof: "Hydrogen", fuel_cng: "CNG",
    reasonNotCar: "A value estimate is only available for passenger cars.",
    reasonNoPrice: "The RDW has no new price for this car.",
    reasonClassic: "Classic car (25+ years): the value mainly depends on condition and rarity.",
    noteBrandUp: "brand holds its value well", noteBrandDown: "brand loses value faster",
    noteOldDiesel: "older diesel (low-emission zones)", noteOldEV: "older EV", noteKmBad: "mileage not logical",
    noteHighKm: "high mileage for its age (normal ±{k}k)", noteLowKm: "low mileage for its age (normal ±{k}k)",
    vSuspTitle: "Suspiciously cheap", vSuspText: "{diff} below our estimate. Could be a bargain, but check damage, maintenance and ownership extra carefully.",
    vGoodTitle: "Good deal", vGoodText: "About {diff} below our estimate.",
    vFairTitle: "Fair price", vFairText: "The asking price is close to our estimate.",
    vPriceyTitle: "On the expensive side", vPriceyText: "About {diff} above our estimate. Room to negotiate.",
    vExpTitle: "Too expensive", vExpText: "About {diff} above our estimate.",
    taxOldtimer: "classic car: exempt", taxLpg: "LPG surcharge (rough)", taxSoot: "particulate surcharge, old diesel", taxEV: "EV: 70% of the petrol rate in 2026",
  },
};

// RDW values shown to the user (colours and body types), translated for English.
const RDW_EN = {
  ZWART: "Black", WIT: "White", GRIJS: "Grey", BLAUW: "Blue", ROOD: "Red", GROEN: "Green", GEEL: "Yellow", ORANJE: "Orange",
  BRUIN: "Brown", BEIGE: "Beige", PAARS: "Purple", ROZE: "Pink", CREME: "Cream", DIVERSEN: "Various",
  "hatchback": "Hatchback", "sedan": "Saloon", "stationwagen": "Estate", "mpv": "MPV", "cabriolet": "Convertible",
  "coupe": "Coupé", "terreinvoertuig": "SUV / off-road", "gesloten opbouw": "Van",
};

// Language comes from the page: "/" and the Dutch pages are Dutch, everything under /en/ is English
// (<html data-lang="en">). Pages without data-lang (tools) fall back to ?lang= or the last choice.
let LANG = (() => {
  const page = document.documentElement.dataset.lang;
  if (page === "en" || page === "nl") return page;
  try {
    const q = new URLSearchParams(location.search).get("lang");
    if (q === "en" || q === "nl") return q;
    const saved = localStorage.getItem("lang");
    if (saved === "en" || saved === "nl") return saved;
  } catch {}
  return "nl";
})();

// Dutch path → English path (and back). Keep in sync with GUIDE_EN in tools/build_pages.py.
const GUIDE_EN = { "tweedehands-auto-kopen-checklist": "used-car-buying-checklist", "importauto-kopen": "buying-an-imported-car",
  "kosten-auto-per-maand": "car-costs-per-month" };
function pathFor(path, lang = LANG) {
  if (lang !== "en") return path;
  if (path === "/") return "/en/";
  let m = path.match(/^\/auto\/(.*)$/);
  if (m) return "/en/cars/" + m[1];
  m = path.match(/^\/gids\/([^/]*)\/?$/);
  if (m) return "/en/guide/" + (m[1] ? (GUIDE_EN[m[1]] || m[1]) + "/" : "");
  return path;
}

const LOCALE = () => (LANG === "en" ? "en-GB" : "nl-NL");

function t(key, vars = {}) {
  const s = I18N[LANG]?.[key] ?? I18N.nl[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ""));
}

// Translate an RDW value (colour/body type) when English is selected.
function rdwText(v) {
  if (!v) return v;
  const capFirst = v.charAt(0).toUpperCase() + v.slice(1).toLowerCase();
  if (LANG !== "en") return capFirst;
  return RDW_EN[v] || RDW_EN[v.toLowerCase()] || capFirst;
}

// Switch language = go to the same page in the other language (keeps ?k=&km=&p= so a check survives).
function setLang(lang) {
  lang = lang === "en" ? "en" : "nl";
  try { localStorage.setItem("lang", lang); } catch {}
  const q = new URLSearchParams(location.search); q.delete("lang");
  const qs = q.toString() ? "?" + q : "";
  location.href = (lang === "en" ? "/en/" : "/") + qs;
}
