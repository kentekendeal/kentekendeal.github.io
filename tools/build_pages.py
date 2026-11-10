"""
Generate the SEO model pages (/auto/<model>/), the model overview (/auto/) and sitemap.xml
from RDW Open Data.

Run from anywhere:   python tools/build_pages.py        (or --home to only rebuild /en/index.html)
Builds every page in Dutch (/auto/) and English (/en/cars/), plus /en/index.html from index.html.
Re-run every month or so to refresh the numbers. Then commit + push.

The value / road-tax logic mirrors model.js. PARAMS and brand lists are read from model.js
so there is only one place to tune them.
"""
import concurrent.futures as cf
import datetime as dt
import html
import json
import math
import random
import re
import statistics
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://kentekendeal.nl"
API = "https://opendata.rdw.nl/resource/"
TODAY = dt.date.today()
NOW_YEAR = TODAY.year
FROM_YEAR = 2012
N_MODELS = 150
MAX_VARIANTS = 120   # RDW name variants per model used in queries (biggest first; keeps URLs short)
# Vans and camper bases registered as passenger cars: their value doesn't follow our car model.
SKIP_MODELS = {("MERCEDES-BENZ", "SPRINTER"), ("MERCEDES-BENZ", "VITO"), ("FIAT", "DUCATO"), ("VOLKSWAGEN", "CRAFTER"),
               ("FORD", "TRANSIT"), ("CITROEN", "JUMPER"), ("PEUGEOT", "BOXER"), ("RENAULT", "MASTER"), ("IVECO", "DAILY")}

# Merge RDW name variants into one model: (brand, regex on cleaned name) -> canonical name
ALIASES = [
    ("VOLKSWAGEN", r"^UP!?$", "UP!"),
    ("VOLKSWAGEN", r"^ID\.3\b", "ID.3"),
    ("VOLKSWAGEN", r"^ID\.4\b", "ID.4"),
    ("TOYOTA", r"^YARIS( HYBRID)?$", "YARIS"),
    ("LYNK&CO", r"^LYNK & CO 01\b", "01"),
    ("AUDI", r"^(A\d|Q\d)\b", None),          # A3 SPORTBACK -> A3, Q2 ... -> Q2
    ("OPEL", r"^ASTRA\b", "ASTRA"),
    ("OPEL", r"^CORSA(-E)?$", "CORSA"),
    ("KIA", r"^E-?NIRO$", "NIRO"),
]

BRAND_NAMES = {"BMW": "BMW", "MERCEDES-BENZ": "Mercedes-Benz", "LYNK&CO": "Lynk & Co", "ALFA ROMEO": "Alfa Romeo",
               "LAND ROVER": "Land Rover", "DS": "DS", "MG": "MG", "BYD": "BYD", "CITROEN": "Citroën", "MINI": "Mini", "KIA": "Kia"}


NAME_FIX = {"ASX": "ASX", "KA": "Ka", "ECOSPORT": "EcoSport", "IX20": "ix20", "ZOE": "Zoe", "SX4": "SX4", "S-CROSS": "S-Cross",
            "PROCEED": "ProCeed", "XCEED": "XCeed", "ID. BUZZ": "ID. Buzz", "GRANDLAND": "Grandland", "MX-5": "MX-5"}
MB_CODES = ("CLA", "CLS", "GLA", "GLB", "GLC", "GLE", "GLS", "EQA", "EQB", "EQC", "EQE", "EQS", "EQV", "SLK", "SLC", "SL")


def group_name(brand, name):
    """BMW and Mercedes-Benz are registered per engine variant ("118I", "A 180 D", "GLC 300 E 4MATIC").
    Group them into the model people search for: "1 SERIE", "X1", "IX3", "A-KLASSE", "GLC". Returns None to skip."""
    if brand == "BMW":
        m = re.match(r"^(\d)ER REIHE$", name) or re.match(r"^(\d)\d\d[A-Z]*\b", name) or re.match(r"^M(\d)\b", name)
        if m: return f"{m.group(1)} SERIE"
        m = re.match(r"^(IX\d?|I\d|X\d|Z\d)\b", name)
        if m: return m.group(1)
        return None
    if brand == "MERCEDES-BENZ":
        m = re.match(r"^(CLA|CLS|GLA|GLB|GLC|GLE|GLS|EQA|EQB|EQC|EQE|EQS|EQV|SLK|SLC|SL)\b", name)
        if m: return m.group(1)
        m = re.match(r"^([ABCEGSV])(-KLASSE| \d|\d)", name)
        if m: return f"{m.group(1)}-KLASSE"
        if name.startswith(("VITO", "EVITO", "SPRINTER")): return "VITO" if "VITO" in name else "SPRINTER"
        return None
    for b, pat, repl in MERGE:
        if b == brand: name = re.sub(pat, repl, name)
    return name


# More name variants that are the same model (brand, regex, replacement).
MERGE = [
    ("HYUNDAI", r"^I (\d+)$", r"I\1"),                 # "I 30" -> "I30"
    ("MAZDA", r"^MAZDA ?(\d)$", r"\1"),                 # "MAZDA2" -> "2"
    ("RENAULT", r"^(CLIO|CAPTUR|MEGANE|ARKANA|AUSTRAL) E-TECH.*$", r"\1"),
    ("OPEL", r"^(MOKKA|CROSSLAND|GRANDLAND) X$", r"\1"),
    ("SEAT", r"^LEON (ST|SPORTSTOURER)$", "LEON"),
    ("SKODA", r"^ENYAQ\b.*$", "ENYAQ"),
    ("KIA", r"^CEE ?'?D$", "CEED"),
    ("KIA", r"^PRO CEE ?'?D$", "PROCEED"),
]


# ---------------------------------------------------------------- helpers
def cap(s): return s[:1].upper() + s[1:].lower() if s else ""
def brand_name(b): return BRAND_NAMES.get(b) or " ".join(cap(w) for w in b.split(" "))
def model_name(m):
    if re.match(r"^\d SERIE$", m):            # BMW "3 SERIE" → "3 Serie" / "3 Series"
        return m[0] + (" Series" if LANG == "en" else " Serie")
    if re.match(r"^[A-Z]-KLASSE$", m):          # Mercedes "A-KLASSE" → "A-Klasse" / "A-Class"
        return m[0] + ("-Class" if LANG == "en" else "-Klasse")
    if m in NAME_FIX:
        return NAME_FIX[m]
    if m in MB_CODES:                           # Mercedes GLC, CLA, EQA ... stay in capitals
        return m
    if re.match(r"^I(X\d?|\d)$", m):            # BMW iX1, i4
        return "i" + m[1:]
    if m != m.upper():
        return m
    if re.match(r"^I\d+$", m):   # Hyundai i10, i20, i30
        return m.lower()
    return " ".join("-".join(p if re.search(r"\d", p) or len(p) <= 2 else cap(p) for p in w.split("-")) for w in m.split(" "))
def slugify(s): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower().replace("ë", "e").replace("&", ""))).strip("-")
def esc(s): return html.escape(str(s), quote=True)
def euro(n): return "€ " + f"{round(n):,}".replace(",", ".")
def nl_int(n): return f"{round(n):,}".replace(",", ".")
def round250(n): return max(250, round(n / 250) * 250)


def rdw(dataset, params, tries=4):
    url = API + dataset + ".json?" + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def soql_str(s): return "'" + s.replace("'", "''") + "'"


# ---------------------------------------------------------------- model.js (single source of truth)
JS = (ROOT / "model.js").read_text(encoding="utf-8")
PARAMS = {k: float(v) for k, v in re.findall(r"^\s+(\w+):\s*([\d.]+),", re.search(r"const PARAMS = \{(.*?)\};", JS, re.S).group(1), re.M)}
HOLDS = re.findall(r'"([^"]+)"', re.search(r"const HOLDS_VALUE = \[(.*?)\]", JS, re.S).group(1))
LOSES = re.findall(r'"([^"]+)"', re.search(r"const LOSES_VALUE = \[(.*?)\]", JS, re.S).group(1))
FUEL_PRICE = {k: float(v) for k, v in re.findall(r"(\w+): ([\d.]+)", re.search(r"const FUEL_PRICE = \{(.*?)\}", JS).group(1))}


def value_factor(age, brand, fuel):
    """Share of the new price a car keeps at `age` years with typical mileage (mirrors estimateValue)."""
    P = PARAMS
    if age < 1:
        f = 1 - P["year1Drop"] * age
    else:
        f = (1 - P["year1Drop"]) * (1 - P["yearlyDrop"]) ** (min(age, 6) - 1) * (1 - P["oldDrop"]) ** max(age - 6, 0)
    if brand in HOLDS: f *= P["brandUp"]
    if brand in LOSES: f *= P["brandDown"]
    ramp = lambda a, b: min(1, max(0, (age - a) / (b - a)))
    if fuel == "Diesel" and age > 5: f *= 1 - P["dieselMax"] * ramp(5, 10)
    if fuel == "Elektrisch" and age > 1: f *= 1 - P["evMax"] * ramp(1, 4)
    return f


def road_tax_month(kg, fuel):
    """Mirrors roadTaxPerMonth in model.js (2026, average province)."""
    if not kg: return None
    if fuel == "Elektrisch": kg -= 125
    above = (kg - 1000) / 100
    if fuel == "Diesel":
        q = 246 + 44 * above if above >= 0 else max(150, 246 + 30 * above)
    else:
        q = 93 + 27.7 * above if above >= 0 else max(40, 93 + 20 * above)
    if fuel == "LPG": q *= 1.5
    if fuel == "Elektrisch": q *= 0.70
    return q / 3


# ---------------------------------------------------------------- data
def top_models():
    rows = rdw("m9d7-ebf2", {
        "$select": "merk,handelsbenaming,count(*) as n",
        "$where": f"voertuigsoort='Personenauto' AND datum_eerste_toelating_dt > '{FROM_YEAR - 1}-12-31T00:00:00'",
        "$group": "merk,handelsbenaming", "$order": "n DESC", "$limit": "6000"})
    agg, variants = Counter(), defaultdict(Counter)
    for r in rows:
        brand = r["merk"]
        raw = (r.get("handelsbenaming") or "").strip()
        if not raw: continue
        name = raw.upper()
        if name.startswith(brand + " "): name = name[len(brand) + 1:]
        for b, pat, canon in ALIASES:
            m = re.match(pat, name)
            if b == brand and m:
                name = canon or m.group(1)
                break
        name = group_name(brand, name)
        if not name or (brand, name) in SKIP_MODELS: continue
        agg[(brand, name)] += int(r["n"])
        variants[(brand, name)][raw] += int(r["n"])
    return [(b, n, sorted(v for v, _ in variants[(b, n)].most_common(MAX_VARIANTS)), c) for (b, n), c in agg.most_common(N_MODELS)]


def model_data(brand, name, variants):
    where = (f"voertuigsoort='Personenauto' AND merk={soql_str(brand)} AND handelsbenaming in ({','.join(soql_str(v) for v in variants)})"
             f" AND datum_eerste_toelating_dt > '{FROM_YEAR - 1}-12-31T00:00:00'")
    years = rdw("m9d7-ebf2", {"$select": "date_extract_y(datum_eerste_toelating_dt) as y,count(*) as n,avg(catalogusprijs) as p,avg(massa_ledig_voertuig) as kg",
                              "$where": where, "$group": "y", "$order": "y"})
    colours = rdw("m9d7-ebf2", {"$select": "eerste_kleur,count(*) as n", "$where": where, "$group": "eerste_kleur", "$order": "n DESC", "$limit": "6"})
    plates = [r["kenteken"] for r in rdw("m9d7-ebf2", {"$select": "kenteken", "$where": where + f" AND datum_eerste_toelating_dt > '{NOW_YEAR - 9}-12-31T00:00:00'",
                                                        "$order": "kenteken", "$limit": "160"})]
    fuel_rows = rdw("8ys7-d773", {"$where": f"kenteken in ({','.join(soql_str(p) for p in plates)})", "$limit": "1000"}) if plates else []
    return years, colours, fuel_rows


# ---------------------------------------------------------------- APK defects per model
APK_PER_YEAR = 40          # plates sampled per model year (2 random chunks of 20)
APK_MIN_CARS = 120         # fewer inspected cars than this → no APK section
ADVICE = re.compile(r"^(AC|RA|OP)\d")   # advisories, not defects
_defect_texts = None
APK_AVG = {}


def defect_texts():
    global _defect_texts
    if _defect_texts is None:
        _defect_texts = {r["gebrek_identificatie"]: r.get("gebrek_omschrijving", "") for r in rdw("hx2c-gt7k", {"$limit": "5000"})}
    return _defect_texts


def apk_sample(brand, name, variants, years):
    """Inspections + defects since June 2022 for a sample of cars old enough to have had an APK."""
    rng = random.Random(f"{brand}|{name}|{TODAY:%Y-%m}")   # stable within a month
    base = f"voertuigsoort='Personenauto' AND merk={soql_str(brand)} AND handelsbenaming in ({','.join(soql_str(v) for v in variants)})"
    plates = []
    for r in years:
        y, n = int(r["y"]), int(r["n"])
        if y < FROM_YEAR or y > NOW_YEAR - 4 or n < 60: continue
        where = base + f" AND datum_eerste_toelating_dt between '{y}-01-01T00:00:00' and '{y}-12-31T23:59:59'"
        for off in sorted(rng.sample(range(0, n - 20), 2)):
            plates += [x["kenteken"] for x in rdw("m9d7-ebf2", {"$select": "kenteken", "$where": where, "$order": "kenteken",
                                                                 "$limit": "20", "$offset": str(off)})]
    plates = sorted(set(plates))
    checks, found = [], []
    for i in range(0, len(plates), 150):
        inn = f"kenteken in ({','.join(soql_str(p) for p in plates[i:i + 150])})"
        checks += rdw("sgfe-77wx", {"$select": "kenteken,meld_datum_door_keuringsinstantie",
                                    "$where": inn + " AND soort_melding_ki_omschrijving='periodieke controle'", "$limit": "5000"})
        found += rdw("a34c-vvps", {"$select": "kenteken,meld_datum_door_keuringsinstantie,gebrek_identificatie,aantal_gebreken_geconstateerd",
                                   "$where": inn, "$limit": "20000"})
    return checks, found


def apk_stats(checks, found):
    inspections = {(c["kenteken"], c["meld_datum_door_keuringsinstantie"]) for c in checks}
    inspections |= {(g["kenteken"], g["meld_datum_door_keuringsinstantie"]) for g in found}
    cars = {k for k, _ in inspections}
    if len(cars) < APK_MIN_CARS: return None
    with_defect = set()
    per_code = defaultdict(set)          # code -> plates where it was found at least once
    n_defects = 0
    for g in found:
        code = g.get("gebrek_identificatie") or ""
        per_code[code].add(g["kenteken"])
        if not ADVICE.match(code):
            with_defect.add((g["kenteken"], g["meld_datum_door_keuringsinstantie"]))
            n_defects += int(g.get("aantal_gebreken_geconstateerd") or 1)
    return {"cars": len(cars), "inspections": len(inspections),
            "clean": 1 - len(with_defect) / len(inspections), "per_inspection": n_defects / len(inspections),
            "codes": {c: len(p) / len(cars) for c, p in per_code.items()}}


def classify_fuel(fuel_rows):
    """Fuel mix from a sample of recent plates + average WLTP use per type."""
    per = defaultdict(list)
    for r in fuel_rows: per[r["kenteken"]].append(r)
    kinds, use = Counter(), defaultdict(list)
    for rows in per.values():
        types = {(r.get("brandstof_omschrijving") or "").lower() for r in rows}
        klasse = next((r.get("klasse_hybride_elektrisch_voertuig") for r in rows if r.get("klasse_hybride_elektrisch_voertuig")), "")
        main = next((r for r in rows if (r.get("brandstof_omschrijving") or "").lower() != "elektriciteit"), rows[0])
        if types == {"elektriciteit"}: k = "Elektrisch"
        elif "elektriciteit" in types: k = "Plug-in hybride" if klasse == "OVC-HEV" else "Hybride"
        elif "diesel" in types: k = "Diesel"
        elif "lpg" in types: k = "LPG"
        elif "benzine" in types: k = "Benzine"
        else: k = "Overig"
        kinds[k] += 1
        if k == "Elektrisch":
            v = next((r.get("elektrisch_verbruik_enkel_elektrisch_wltp") for r in rows if r.get("elektrisch_verbruik_enkel_elektrisch_wltp")), None)
        else:
            v = main.get("brandstof_verbruik_gecombineerd_wltp") or main.get("brandstof_verbruik_gewogen_gecombineerd_wltp")
        try:
            if v and float(v) > 0: use[k].append(float(v))
        except ValueError:
            pass
    total = sum(kinds.values()) or 1
    mix = [(k, c / total) for k, c in kinds.most_common()]
    return mix, {k: statistics.median(v) for k, v in use.items() if v}


# ---------------------------------------------------------------- language
# Every page is built twice: Dutch (/auto/...) and English (/en/cars/...). T("nl", "en") picks the text.
LANG = "nl"
def T(nl, en): return en if LANG == "en" else nl

# Keep in sync with GUIDE_EN in i18n.js.
GUIDE_EN = {"tweedehands-auto-kopen-checklist": "used-car-buying-checklist", "importauto-kopen": "buying-an-imported-car",
            "kosten-auto-per-maand": "car-costs-per-month"}
def p_home(): return T("/", "/en/")
def p_models(): return T("/auto/", "/en/cars/")
def p_model(slug): return T(f"/auto/{slug}/", f"/en/cars/{slug}/")
def p_guides(): return T("/gids/", "/en/guide/")
def p_guide(nl_slug): return T(f"/gids/{nl_slug}/", f"/en/guide/{GUIDE_EN[nl_slug]}/")

COLOR_NL = {"ZWART": "Zwart", "WIT": "Wit", "GRIJS": "Grijs", "BLAUW": "Blauw", "ROOD": "Rood", "GROEN": "Groen", "GEEL": "Geel",
            "ORANJE": "Oranje", "BRUIN": "Bruin", "BEIGE": "Beige", "PAARS": "Paars", "ROZE": "Roze", "CREME": "Crème"}
COLOR_EN = {"ZWART": "Black", "WIT": "White", "GRIJS": "Grey", "BLAUW": "Blue", "ROOD": "Red", "GROEN": "Green", "GEEL": "Yellow",
            "ORANJE": "Orange", "BRUIN": "Brown", "BEIGE": "Beige", "PAARS": "Purple", "ROZE": "Pink", "CREME": "Cream"}
FUEL_EN = {"Benzine": "Petrol", "Diesel": "Diesel", "Elektrisch": "Electric", "Hybride": "Hybrid", "Plug-in hybride": "Plug-in hybrid",
           "LPG": "LPG", "Overig": "Other"}
def fuel_label(k): return FUEL_EN.get(k, k) if LANG == "en" else k
def colour_label(c): return (COLOR_EN if LANG == "en" else COLOR_NL).get(c) or cap(c or "")

# English texts for RDW defect codes (tools/defects_en.json). Missing codes fall back to the Dutch RDW text.
_DEFECTS_EN_FILE = ROOT / "tools" / "defects_en.json"
DEFECTS_EN = json.loads(_DEFECTS_EN_FILE.read_text(encoding="utf-8")) if _DEFECTS_EN_FILE.exists() else {}
# Some RDW texts are cut off at 60 characters; tools/defects_nl.json has the full Dutch text for those.
_DEFECTS_NL_FILE = ROOT / "tools" / "defects_nl.json"
DEFECTS_NL = json.loads(_DEFECTS_NL_FILE.read_text(encoding="utf-8")) if _DEFECTS_NL_FILE.exists() else {}
USED_CODES = set()   # codes shown on any page, so missing translations can be reported


def money(n): return ("€" + f"{round(n):,}") if LANG == "en" else ("€ " + f"{round(n):,}".replace(",", "."))
def count(n): return f"{round(n):,}" if LANG == "en" else f"{round(n):,}".replace(",", ".")
def dec1(x): return f"{x:.1f}" if LANG == "en" else f"{x:.1f}".replace(".", ",")
def pct(x): return f"{round(x * 100)}%"


# ---------------------------------------------------------------- html
def layout(*, title, description, path, alt, crumbs, h1, lead, body, jsonld=(), check=True):
    """alt = {"nl": dutch_path, "en": english_path} for the hreflang links."""
    url = SITE + path
    crumb_html = " › ".join(f'<a href="{esc(u)}">{esc(t)}</a>' if u else esc(t) for t, u in crumbs)
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>\n' for j in jsonld)
    check_html = f"""
      <form class="check" action="{p_home()}" method="get">
        <div class="plate"><span class="nl">NL</span><input name="k" placeholder="XX-123-X" maxlength="10" aria-label="{T('Kenteken', 'Licence plate')}" autocomplete="off"></div>
        <button>Check</button>
      </form>""" if check else ""
    other = "en" if LANG == "nl" else "nl"
    switch = f'<a class="lang" href="{esc(alt[other])}" hreflang="{other}" lang="{other}">{other.upper()}</a>'
    return f"""<!doctype html>
<html lang="{LANG}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(url)}">
<link rel="alternate" hreflang="nl" href="{esc(SITE + alt['nl'])}">
<link rel="alternate" hreflang="en" href="{esc(SITE + alt['en'])}">
<link rel="alternate" hreflang="x-default" href="{esc(SITE + alt['nl'])}">
<meta name="theme-color" content="#0E1B3D">
<link rel="icon" href="/assets/logo-icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<meta property="og:type" content="article">
<meta property="og:site_name" content="KentekenDeal">
<meta property="og:locale" content="{T('nl_NL', 'en_GB')}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:image" content="{SITE}/assets/og-image.png">
<meta property="og:url" content="{esc(url)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/site.css">
<script data-goatcounter="https://kentekendeal.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
{ld}</head>
<body>
<header class="top">
  <div class="wrap">
    <div class="bar">
      <a class="brand" href="{p_home()}"><img src="/assets/logo-icon.svg" alt="">kenteken<b>deal</b></a>
      <nav class="nav"><a href="{p_home()}">{T('Kenteken check', 'Plate check')}</a><a href="{p_models()}">{T("Auto's", 'Cars')}</a><a href="{p_guides()}">{T('Koopgids', 'Buying guide')}</a>{switch}</nav>
    </div>
    <div class="intro">
      <div class="crumbs">{crumb_html}</div>
      <h1>{esc(h1)}</h1>
      <p class="lead">{lead}</p>{check_html}
    </div>
  </div>
</header>
<main class="wrap">
{body}
</main>
<footer class="wrap">
  <nav><a href="{p_home()}">{T('Kenteken check', 'Plate check')}</a><a href="{p_models()}">{T('Alle modellen', 'All models')}</a><a href="{p_guides()}">{T('Koopgids', 'Buying guide')}</a>{switch}</nav>
  {T(f"Data: RDW Open Data, bijgewerkt {TODAY.strftime('%d-%m-%Y')}. Waarden en kosten zijn schattingen, geen taxatie.",
     f"Data: RDW Open Data (Dutch vehicle authority), updated {TODAY.strftime('%d %b %Y')}. Values and costs are estimates, not a valuation.")}<br>© KentekenDeal
</footer>
</body>
</html>
"""


def bar_chart(points):
    """points: [(label, value)] -> inline SVG bar chart."""
    if not points: return ""
    W, H, pad_l, pad_b, pad_t = 700, 230, 8, 26, 22
    n = len(points)
    slot = (W - pad_l * 2) / n
    bw = min(34, slot * 0.7)
    vmax = max(v for _, v in points) or 1
    out = []
    for i, (label, v) in enumerate(points):
        h = (H - pad_b - pad_t) * v / vmax
        x = pad_l + i * slot + (slot - bw) / 2
        y = H - pad_b - h
        k = v / 1000
        val = f"{dec1(k)}k" if k < 10 else f"{k:.0f}k"
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" fill="var(--bar)"/>'
                   f'<text class="val" x="{x + bw / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle">{val}</text>'
                   f'<text x="{x + bw / 2:.1f}" y="{H - 8}" text-anchor="middle">{label}</text>')
    return (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{T("Geschatte waarde per bouwjaar", "Estimated value by year")}">'
            + "".join(out) + "</svg>")


def defect_label(code):
    USED_CODES.add(code)
    if LANG == "en" and code in DEFECTS_EN: return DEFECTS_EN[code]
    return DEFECTS_NL.get(code) or defect_texts().get(code) or T(f"Gebrekcode {code}", f"Defect code {code}")


def apk_section(full, apk):
    """Returns (html, faq_answer) for the APK block, or ("", None) without enough data."""
    if not apk: return "", None
    avg = APK_AVG.get("codes", {})
    top = [(c, s) for c, s in sorted(apk["codes"].items(), key=lambda kv: -kv[1]) if s >= 0.02][:8]
    if len(top) < 3: return "", None
    lift = lambda c: apk["codes"][c] / avg[c] if avg.get(c) else 1
    hot = {c for c, s in apk["codes"].items() if s >= 0.03 and lift(c) >= 1.6}
    peak = top[0][1]
    items = "".join(
        f'<li><div class="row"><span>{esc(defect_label(c))}'
        + (f' <span class="tag">{T("advies", "advisory")}</span>' if ADVICE.match(c) else "")
        + (f' <span class="tag hot">{dec1(lift(c))}× {T("vaker dan gemiddeld", "more often than average")}</span>' if c in hot else "")
        + f'</span><b>{pct(s)}</b></div><div class="track"><span style="width:{s / peak * 100:.0f}%"></span></div></li>'
        for c, s in top)
    extra = sorted((c for c in hot if c not in dict(top)), key=lambda c: -lift(c))[:3]
    extra_html = (f"<p><b>{T('Ook opvallend vaak bij de', 'Also unusually common on the')} {esc(full)}:</b> "
                  + "; ".join(f"{esc(defect_label(c).lower())} ({pct(apk['codes'][c])}, {dec1(lift(c))}× {T('het gemiddelde', 'the average')})" for c in extra)
                  + ".</p>") if extra else ""
    avg_clean, avg_per = APK_AVG.get("clean"), APK_AVG.get("per_inspection")
    avg_note = T(f"Gemiddeld over alle populaire modellen: {pct(avg_clean)} zonder gebreken, {dec1(avg_per)} gebreken per keuring. Oudere modellen scoren vanzelf slechter.",
                 f"Average across all popular models: {pct(avg_clean)} without defects, {dec1(avg_per)} defects per inspection. Older models naturally score worse.") if avg_clean else ""
    dutch_note = (" Some defect descriptions are only available in Dutch." if LANG == "en" and any(c not in DEFECTS_EN for c, _ in top) else "")
    html_ = f"""
<section class="card">
  <h2>{T(f"Bekende APK-gebreken van de {esc(full)}", f"Common APK (MOT) defects of the {esc(full)}")}</h2>
  <p>{T(f"Wat keurmeesters sinds juni 2022 het vaakst vonden bij de {esc(full)}. Percentage = deel van de gekeurde auto's waarbij het minstens één keer is gevonden.",
        f"What inspectors found most often on the {esc(full)} at the Dutch APK (the yearly roadworthiness test, like the MOT) since June 2022. Percentage = share of inspected cars where it was found at least once.")}</p>
  <div class="stats">
    <div class="stat"><div class="l">{T('Keuringen zonder gebreken', 'Inspections without defects')}</div><div class="v">{pct(apk['clean'])}</div></div>
    <div class="stat"><div class="l">{T('Gebreken per keuring', 'Defects per inspection')}</div><div class="v">{dec1(apk['per_inspection'])}</div></div>
    <div class="stat"><div class="l">{T("Gekeurde auto's", 'Inspected cars')}</div><div class="v">{count(apk['cars'])}</div></div>
  </div>
  {f'<p class="note" style="margin-top:8px">{avg_note}</p>' if avg_note else ''}
  <ul class="defects">{items}</ul>
  {extra_html}
  <p class="note">{T(f"Bron: RDW (APK-meldingen vanaf juni 2022), steekproef van {count(apk['cars'])} auto's met bouwjaar {FROM_YEAR}–{NOW_YEAR - 4}, {count(apk['inspections'])} keuringen. Gevonden gebreken worden meestal direct gerepareerd. 'Advies' is geen afkeur. Wil je de APK-geschiedenis van één auto zien? Vul hieronder het kenteken in.",
                     f"Source: RDW (APK reports from June 2022), sample of {count(apk['cars'])} cars built {FROM_YEAR}–{NOW_YEAR - 4}, {count(apk['inspections'])} inspections. Defects found are usually repaired straight away. An 'advisory' is not a failure. Want the APK history of one specific car? Enter the licence plate below.")}{dutch_note}</p>
</section>
"""
    names = [defect_label(c).lower() for c, _ in top[:3]]
    faq = T(f"Bij de APK van de {full} vonden keurmeesters het vaakst: {names[0]} ({pct(top[0][1])} van de auto's), {names[1]} ({pct(top[1][1])}) "
            f"en {names[2]} ({pct(top[2][1])}). {pct(apk['clean'])} van de keuringen was zonder gebreken"
            + (f" (gemiddeld over alle populaire modellen: {pct(avg_clean)})." if avg_clean else ".")
            + f" Gebaseerd op {count(apk['inspections'])} keuringen sinds juni 2022 (RDW).",
            f"At the APK inspection of the {full}, inspectors most often found: {names[0]} ({pct(top[0][1])} of cars), {names[1]} ({pct(top[1][1])}) "
            f"and {names[2]} ({pct(top[2][1])}). {pct(apk['clean'])} of inspections had no defects"
            + (f" (average across all popular models: {pct(avg_clean)})." if avg_clean else ".")
            + f" Based on {count(apk['inspections'])} inspections since June 2022 (RDW).")
    return html_, faq


def build_model_page(m, others, write=True):
    brand, name, years, colours, mix, use = m["brand"], m["name"], m["years"], m["colours"], m["mix"], m["use"]
    full = f"{brand_name(brand)} {model_name(name)}"
    main_fuel = mix[0][0] if mix else "Benzine"
    total = sum(int(r["n"]) for r in years)

    rows = []
    for r in years:
        y, n = int(r["y"]), int(r["n"])
        p = float(r["p"]) if r.get("p") else None
        kg = float(r["kg"]) if r.get("kg") else None
        if y > NOW_YEAR: continue
        row = {"y": y, "n": n, "p": p, "kg": kg, "mid": None}
        age = (TODAY - dt.date(y, 7, 1)).days / 365.25
        if p and n >= 30 and 1 <= age <= 25 and y < NOW_YEAR:
            row["age"] = age
            row["mid"] = max(p * value_factor(max(age, 0.1), brand, main_fuel), 500)
            row["next"] = max(p * value_factor(age + 1, brand, main_fuel), 500)
        rows.append(row)
    valued = [r for r in rows if r["mid"]]
    if len(valued) < 3:
        return None
    if not write:
        return True

    # example: a ~5 year old car (or the closest year we have)
    ex = min(valued, key=lambda r: abs(r["y"] - (NOW_YEAR - 5)))
    km_year = 12000
    tax = road_tax_month(ex["kg"], "Benzine" if main_fuel in ("Hybride", "Plug-in hybride") else main_fuel)
    u = use.get(main_fuel)
    is_ev = main_fuel == "Elektrisch"
    if is_ev:
        fuel_cost = km_year / 12 * (u or 170) / 1000 * FUEL_PRICE["elektriciteit"]; fuel_use = f"{round((u or 170) / 10)} kWh/100 km"
    else:
        lit = max(u or 6.0, 4.5) if main_fuel == "Plug-in hybride" else (u or 6.0)
        price = FUEL_PRICE["diesel"] if main_fuel == "Diesel" else FUEL_PRICE["lpg"] if main_fuel == "LPG" else FUEL_PRICE["benzine"]
        fuel_cost = km_year / 12 * lit / 100 * price; fuel_use = f"{dec1(lit)} l/100 km"
    dep = max(0, (ex["mid"] - ex["next"]) / 12)
    month_total = (tax or 0) + fuel_cost + dep

    newest = max(valued, key=lambda r: r["y"])
    fuel_txt = ", ".join(f"{fuel_label(k).lower()} ({round(s * 100)}%)" for k, s in mix[:3]) if mix else T("onbekend", "unknown")
    colour_txt = ", ".join(colour_label(c.get("eerste_kleur")) for c in colours[:3]
                           if c.get("eerste_kleur") and "niet" not in c["eerste_kleur"].lower())

    slug = m["slug"]
    path = p_model(slug)
    alt = {"nl": f"/auto/{slug}/", "en": f"/en/cars/{slug}/"}
    range_txt = lambda r: f"{money(round250(r['mid'] * 0.85))} – {money(round250(r['mid'] * 1.15))}"
    table_rows = "".join(
        f"<tr><td>{r['y']}</td><td>{count(r['n'])}</td><td>{money(r['p']) if r['p'] else '–'}</td>"
        f"<td>{range_txt(r) if r['mid'] else '–'}</td>"
        f"<td>{(str(round(r['mid'] / r['p'] * 100)) + '%') if r['mid'] and r['p'] else '–'}</td></tr>"
        for r in sorted(rows, key=lambda r: -r["y"]))
    chart = bar_chart([(str(r["y"])[2:] if len(valued) > 10 else str(r["y"]), r["mid"]) for r in valued])
    energy = T("stroom", "electricity") if is_ev else T("brandstof", "fuel")

    faq = [
        (T(f"Wat is een {full} uit {ex['y']} waard?", f"What is a {ex['y']} {full} worth?"),
         T(f"Een {full} uit {ex['y']} is volgens onze schatting ongeveer {range_txt(ex)} waard, "
           f"bij een gemiddelde kilometerstand en normale staat. De gemiddelde nieuwprijs van dat bouwjaar was {money(ex['p'])}.",
           f"We estimate a {ex['y']} {full} in the Netherlands at about {range_txt(ex)}, "
           f"with average mileage and in normal condition. The average new price for that year was {money(ex['p'])}.")),
        (T(f"Wat kost een {full} per maand?", f"How much does a {full} cost per month?"),
         T(f"Voor een {full} uit {ex['y']} rekenen we met ongeveer {money(month_total)} per maand bij {count(km_year)} km per jaar: "
           f"wegenbelasting {money(tax or 0)}, {energy} {money(fuel_cost)} en waardeverlies {money(dep)}. Verzekering en onderhoud komen daar nog bij.",
           f"For a {ex['y']} {full} we calculate about {money(month_total)} per month at {count(km_year)} km per year: "
           f"Dutch road tax {money(tax or 0)}, {energy} {money(fuel_cost)} and depreciation {money(dep)}. Insurance and maintenance come on top.")),
        (T(f"Hoeveel auto's van het type {full} rijden er in Nederland?", f"How many {full} cars are there in the Netherlands?"),
         T(f"In het RDW-register staan {count(total)} auto's van het type {full} met bouwjaar {FROM_YEAR} of later.",
           f"The RDW register lists {count(total)} {full} cars built in {FROM_YEAR} or later.")),
        (T(f"Welke brandstof heeft een {full}?", f"What fuel does a {full} use?"),
         T(f"Bij recente bouwjaren zien we vooral: {fuel_txt}. Dit is gebaseerd op een steekproef uit het RDW-register.",
           f"For recent years we mostly see: {fuel_txt}. This is based on a sample from the RDW register.")),
    ]
    apk_html, apk_faq = apk_section(full, m.get("apk"))
    if apk_faq: faq.insert(2, (T(f"Wat zijn veelvoorkomende APK-gebreken van de {full}?", f"What are common APK (MOT) defects of the {full}?"), apk_faq))
    faq_html = "".join(f'<details class="faq"{" open" if i == 0 else ""}><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for i, (q, a) in enumerate(faq))

    same_brand = [o for o in others if o["brand"] == brand and o is not m][:6]
    popular = [o for o in others if o["brand"] != brand][:8]
    link = lambda o: f'<a class="pill" href="{p_model(o["slug"])}">{esc(brand_name(o["brand"]) + " " + model_name(o["name"]))}</a>'

    body = f"""
<section class="card">
  <div class="stats">
    <div class="stat"><div class="l">{T('In Nederland', 'In the Netherlands')}</div><div class="v">{count(total)}</div></div>
    <div class="stat"><div class="l">{T('Nieuwprijs', 'New price')} {newest['y']}</div><div class="v">{money(newest['p'])}</div></div>
    <div class="stat"><div class="l">{T('Meest gekozen', 'Most common')}</div><div class="v">{esc(fuel_label(main_fuel))}</div></div>
  </div>
  <p class="note" style="margin-top:12px">{T(f"Aantal met bouwjaar {FROM_YEAR} of later volgens het RDW-register. Nieuwprijs is het gemiddelde van alle uitvoeringen.",
                                             f"Number built in {FROM_YEAR} or later according to the RDW register. New price is the average of all versions.")}</p>
</section>

<section class="card">
  <h2>{T(f"Wat is een {esc(full)} waard?", f"What is a {esc(full)} worth?")}</h2>
  <p>{T("Geschatte waarde per bouwjaar, bij een gemiddelde kilometerstand en normale staat.", "Estimated value by year of manufacture, with average mileage and in normal condition.")}</p>
  {chart}
  <div class="table-wrap"><table>
    <thead><tr><th>{T('Bouwjaar', 'Year')}</th><th>{T('Aantal', 'Number')}</th><th>{T('Gem. nieuwprijs', 'Avg. new price')}</th><th>{T('Geschatte waarde', 'Estimated value')}</th><th>{T('Behouden', 'Retained')}</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table></div>
  <p class="note">{T("De waarde van één specifieke auto hangt af van uitvoering, kilometerstand, opties en staat. Vul het kenteken in voor een persoonlijke schatting en deal-check.",
                     "The value of one specific car depends on version, mileage, options and condition. Enter the licence plate for a personal estimate and deal check.")}</p>
</section>

<section class="card">
  <h2>{T(f"Wat kost een {esc(full)} per maand?", f"What does a {esc(full)} cost per month?")}</h2>
  <p>{T(f"Voorbeeld: een {esc(full)} uit {ex['y']} ({esc(fuel_label(main_fuel).lower())}), {count(km_year)} km per jaar.",
        f"Example: a {ex['y']} {esc(full)} ({esc(fuel_label(main_fuel).lower())}), {count(km_year)} km per year.")}</p>
  <div class="costs">
    <span>{T('Wegenbelasting (gemiddelde provincie)', 'Road tax (average province)')}</span><span>{money(tax or 0)}</span>
    <span>{esc(energy.capitalize())} ({esc(fuel_use)})</span><span>{money(fuel_cost)}</span>
    <span>{T('Waardeverlies', 'Depreciation')}</span><span>{money(dep)}</span>
    <span class="t">{T('Totaal per maand', 'Total per month')}</span><span class="t">{money(month_total)}</span>
  </div>
  <p class="note">{T('Exclusief verzekering en onderhoud. Lees ook:', 'Excluding insurance and maintenance. Also read:')} <a href="{p_guide('kosten-auto-per-maand')}">{T('wat kost een auto per maand?', 'what does a car cost per month in the Netherlands?')}</a></p>
</section>
{apk_html}
<section class="card">
  <h2>{T('Brandstof en kleuren', 'Fuel and colours')}</h2>
  <p><b>{T('Brandstof (recente bouwjaren):', 'Fuel (recent years):')}</b> {esc(fuel_txt)}.</p>
  <p><b>{T('Populairste kleuren:', 'Most popular colours:')}</b> {esc(colour_txt or T('onbekend', 'unknown'))}.</p>
</section>

<section class="card cta">
  <h2>{T(f"Staat er een {esc(full)} te koop?", f"Looking at a {esc(full)} for sale?")}</h2>
  <p>{T("Vul het kenteken en de vraagprijs in. Je ziet direct of het een goede deal is, wat de auto per maand kost, de APK-geschiedenis en of er een terugroepactie openstaat.",
        "Enter the Dutch licence plate and the asking price. You'll instantly see whether it's a good deal, what the car costs per month, its APK history and whether there's an open recall.")}</p>
  <form class="check" action="{p_home()}" method="get">
    <div class="plate"><span class="nl">NL</span><input name="k" placeholder="XX-123-X" maxlength="10" aria-label="{T('Kenteken', 'Licence plate')}" autocomplete="off"></div>
    <button>Check</button>
  </form>
</section>

<section class="card">
  <h2>{T('Veelgestelde vragen', 'Frequently asked questions')}</h2>
  {faq_html}
</section>

<section class="card">
  {('<h2>' + T('Meer van ', 'More from ') + esc(brand_name(brand)) + '</h2><div class="pills">' + "".join(link(o) for o in same_brand) + '</div>') if same_brand else ''}
  <h2 style="margin-top:{'20px' if same_brand else '0'}">{T('Andere populaire modellen', 'Other popular models')}</h2>
  <div class="pills">{"".join(link(o) for o in popular)}</div>
</section>
"""
    jsonld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + p_home()},
            {"@type": "ListItem", "position": 2, "name": T("Auto's", "Cars"), "item": SITE + p_models()},
            {"@type": "ListItem", "position": 3, "name": full, "item": SITE + path}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": LANG, "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    page = layout(
        title=T(f"{full}: waarde, kosten per maand en APK-gebreken ({NOW_YEAR}) | KentekenDeal",
                f"{full} in the Netherlands: value, monthly costs and MOT (APK) defects ({NOW_YEAR}) | KentekenDeal"),
        description=T(f"Wat is een {full} waard? Geschatte waarde per bouwjaar, kosten per maand en de vaakst gevonden APK-gebreken, op basis van RDW-data. Check ook of een {full} te koop een goede deal is.",
                      f"What is a used {full} worth in the Netherlands? Estimated value by year, monthly costs incl. Dutch road tax, and the most common APK (MOT) defects, based on RDW data."),
        path=path, alt=alt, crumbs=[("Home", p_home()), (T("Auto's", "Cars"), p_models()), (full, None)],
        h1=T(f"{full}: wat is hij waard en wat kost hij?", f"{full}: what is it worth and what does it cost?"),
        lead=T(f"Geschatte waarde per bouwjaar en kosten per maand van de {esc(full)}, op basis van RDW-data. Heb je een kenteken? Check direct of de vraagprijs eerlijk is.",
               f"Estimated value by year and monthly costs of a {esc(full)} in the Netherlands, based on official RDW data. Have a Dutch licence plate? Check right away whether the asking price is fair."),
        body=body, jsonld=jsonld)
    out = ROOT / path.strip("/") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return path


def build_overview(models):
    by_brand = defaultdict(list)
    for m in models: by_brand[m["brand"]].append(m)
    blocks = "".join(
        f'<div class="brand-block"><h3>{esc(brand_name(b))}</h3><div class="pills">'
        + "".join(f'<a class="pill" href="{p_model(m["slug"])}">{esc(model_name(m["name"]))}</a>' for m in ms) + "</div></div>"
        for b, ms in sorted(by_brand.items(), key=lambda kv: brand_name(kv[0])))
    body = (f'<section class="card"><h2>{T("Populaire modellen in Nederland", "Popular models in the Netherlands")}</h2>'
            f'<p>{T("Kies een model voor de geschatte waarde per bouwjaar, de kosten per maand en de bekende APK-gebreken.", "Pick a model for its estimated value by year, monthly costs and common APK (MOT) defects.")}</p>{blocks}</section>')
    page = layout(title=T("Auto's: waarde en kosten per model | KentekenDeal", "Used car values and costs per model in the Netherlands | KentekenDeal"),
                  description=T("Wat is jouw auto waard en wat kost hij per maand? Overzicht van de populairste automodellen in Nederland, op basis van RDW-data.",
                                "What is a used car worth in the Netherlands and what does it cost per month? The most popular models, based on official RDW data."),
                  path=p_models(), alt={"nl": "/auto/", "en": "/en/cars/"}, crumbs=[("Home", p_home()), (T("Auto's", "Cars"), None)],
                  h1=T("Waarde en kosten per automodel", "Value and costs per car model"),
                  lead=T("De populairste modellen in Nederland: geschatte waarde per bouwjaar en wat ze per maand kosten.",
                         "The most popular models in the Netherlands: estimated value by year and what they cost per month."),
                  body=body)
    out = ROOT / p_models().strip("/") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")


def build_en_home():
    """/en/index.html = the app (index.html) with English head + static text, so search engines see an English page."""
    global LANG
    LANG = "en"
    src = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "i18n.js").read_text(encoding="utf-8")
    en_block = re.search(r"\n  en: \{(.*?)\n  \},", js, re.S).group(1)
    EN = {k: json.loads('"' + v + '"') for k, v in re.findall(r'(\w+): "((?:[^"\\]|\\.)*)"', en_block)}
    desc = "Enter a Dutch licence plate: specs, what the car is worth, whether the asking price is fair, monthly costs and the APK (MOT) history. Free, based on RDW data."
    reps = [
        ('<html lang="nl" data-lang="nl">', '<html lang="en" data-lang="en">'),
        ("<title>KentekenDeal: is deze auto zijn prijs waard?</title>", f"<title>{esc(EN['docTitle'])}</title>"),
        ('<meta name="description" content="Vul een kenteken in: specificaties, wat de auto waard is, of de vraagprijs eerlijk is en wat hij per maand kost.">',
         f'<meta name="description" content="{esc(desc)}">'),
        ('<meta property="og:title" content="Is deze auto zijn prijs waard?">', f'<meta property="og:title" content="{esc(EN["heroTitle"])}">'),
        ('<meta property="og:description" content="Vul een kenteken in en zie direct de waarde, of de vraagprijs eerlijk is en wat hij per maand kost.">',
         f'<meta property="og:description" content="{esc(EN["heroLead"])}">'),
        ('<meta property="og:url" content="https://kentekendeal.nl/">', f'<meta property="og:url" content="{SITE}/en/">'),
        ('<link rel="canonical" href="https://kentekendeal.nl/">', f'<link rel="canonical" href="{SITE}/en/">'),
        ('"url":"https://kentekendeal.nl/","applicationCategory"', f'"url":"{SITE}/en/","applicationCategory"'),
        ('"inLanguage":["nl","en"],"description":"Vul een kenteken in en zie de RDW-gegevens, de geschatte waarde, of de vraagprijs eerlijk is en wat de auto per maand kost."',
         f'"inLanguage":"en","description":"{desc}"'),
        ('aria-label="Kenteken"', 'aria-label="Licence plate"'),
        ('aria-label="Switch language">EN</button>', 'aria-label="Schakel naar Nederlands">NL</button>'),
        ('<a class="brand" href="/"', '<a class="brand" href="/en/"'),
    ]
    for a, b in reps:
        if a not in src: raise SystemExit(f"build_en_home: can't find {a[:60]!r} in index.html; update build_en_home().")
        src = src.replace(a, b)
    src = re.sub(r'(<[^>]*\bdata-i18n="(\w+)"[^>]*>)([^<]*)(<)', lambda mo: mo.group(1) + esc(EN.get(mo.group(2), mo.group(3))) + mo.group(4), src)
    src = re.sub(r'href="/auto/', 'href="/en/cars/', src)
    src = re.sub(r'href="/gids/([^"/]*)/?"', lambda mo: f'href="/en/guide/{(GUIDE_EN.get(mo.group(1), mo.group(1)) + "/") if mo.group(1) else ""}"', src)
    src = src.replace("<!doctype html>", "<!doctype html>\n<!-- GENERATED from index.html by tools/build_pages.py (build_en_home). Do not edit; edit index.html. -->", 1)
    (ROOT / "en").mkdir(exist_ok=True)
    (ROOT / "en" / "index.html").write_text(src, encoding="utf-8")
    LANG = "nl"


def build_sitemap(model_slugs):
    guides = sorted(p.parent.name for p in (ROOT / "gids").glob("*/index.html"))
    paths = ["/", "/en/", "/auto/", "/en/cars/", "/gids/", "/en/guide/"]
    for g in guides:
        paths.append(f"/gids/{g}/")
        if g in GUIDE_EN and (ROOT / "en" / "guide" / GUIDE_EN[g] / "index.html").exists(): paths.append(f"/en/guide/{GUIDE_EN[g]}/")
    for s in model_slugs: paths += [f"/auto/{s}/", f"/en/cars/{s}/"]
    items = "".join(f"<url><loc>{SITE}{p}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>\n" for p in paths)
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}</urlset>\n', encoding="utf-8")
    return len(paths)


def fetch_all():
    print("Top models…")
    tops = top_models()
    models = [{"brand": b, "name": n, "variants": v, "count": c, "slug": slugify(f"{brand_name(b)} {n}")} for b, n, v, c in tops]

    def fetch(m):
        years, colours, fuel_rows = model_data(m["brand"], m["name"], m["variants"])
        mix, use = classify_fuel(fuel_rows)
        try:
            apk = apk_stats(*apk_sample(m["brand"], m["name"], m["variants"], years))
        except Exception as e:   # APK data is a bonus; never fail the whole build on it
            print(f"  APK data failed for {m['brand']} {m['name']}: {e}")
            apk = None
        m.update(years=years, colours=colours, mix=mix, use=use, apk=apk)
        print(f"  fetched {m['brand']} {m['name']} ({time.time() - t_start:.0f}s)", flush=True)
        return m

    t_start = time.time()
    defect_texts()
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(fetch, models))
    return models


def main():
    """python tools/build_pages.py            full build (~4 min, fetches RDW data)
       python tools/build_pages.py --home     only rebuild /en/index.html (after editing index.html)
       KD_CACHE=file.json                     reuse fetched data (handy while editing templates)"""
    global LANG, _defect_texts
    import os, sys
    t0 = time.time()
    build_en_home()
    if "--home" in sys.argv:
        print("Rebuilt en/index.html"); return

    cache = os.environ.get("KD_CACHE")
    if cache and Path(cache).exists():
        data = json.loads(Path(cache).read_text(encoding="utf-8"))
        models, _defect_texts = data["models"], data["texts"]
        print(f"Using cached data from {cache}")
    else:
        models = fetch_all()
        if cache: Path(cache).write_text(json.dumps({"models": models, "texts": defect_texts()}, ensure_ascii=False), encoding="utf-8")

    # Averages over all models, to say whether a defect is typical for a model.
    sampled = [m["apk"] for m in models if m["apk"]]
    if sampled:
        codes = {c for a in sampled for c in a["codes"]}
        APK_AVG.update(clean=statistics.mean(a["clean"] for a in sampled),
                       per_inspection=statistics.mean(a["per_inspection"] for a in sampled),
                       codes={c: statistics.mean(a["codes"].get(c, 0) for a in sampled) for c in codes})

    # Pass 1 finds which models have enough data; pass 2 builds them (both languages), linking only to built pages.
    built = [m for m in models if build_model_page(m, models, write=False)]
    for m in models:
        if m not in built:
            print(f"  skipped {m['brand']} {m['name']} (not enough data)")
    for lang in ("nl", "en"):
        LANG = lang
        for m in built: build_model_page(m, built)
        build_overview(built)
    LANG = "nl"
    for m in built:
        print(f"  /auto/{m['slug']}/ + /en/cars/{m['slug']}/  ({m['count']:,} cars, {m['mix'][0][0] if m['mix'] else '?'})")
    n = build_sitemap([m["slug"] for m in built])
    missing = sorted(c for c in USED_CODES if c not in DEFECTS_EN)
    if missing:
        print(f"Note: {len(missing)} defect codes have no English text yet (add them to tools/defects_en.json): " + ", ".join(missing))
    print(f"Done: {len(built)} models × 2 languages, sitemap with {n} URLs, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
