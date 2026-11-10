"""
Generate the SEO model pages (/auto/<model>/), the model overview (/auto/) and sitemap.xml
from RDW Open Data.

Run from anywhere:   python tools/build_pages.py
Re-run every month or so to refresh the numbers. Then commit + push.

The value / road-tax logic mirrors model.js. PARAMS and brand lists are read from model.js
so there is only one place to tune them.
"""
import concurrent.futures as cf
import datetime as dt
import html
import json
import math
import re
import statistics
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://kentekendeal.github.io"   # change when the custom domain goes live
API = "https://opendata.rdw.nl/resource/"
TODAY = dt.date.today()
NOW_YEAR = TODAY.year
FROM_YEAR = 2012
N_MODELS = 60
SKIP_BRANDS = {"MERCEDES-BENZ", "BMW"}  # RDW lists these by engine variant ("A 180"), not by model

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


# ---------------------------------------------------------------- helpers
def cap(s): return s[:1].upper() + s[1:].lower() if s else ""
def brand_name(b): return BRAND_NAMES.get(b) or " ".join(cap(w) for w in b.split(" "))
def model_name(m):
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
        "$group": "merk,handelsbenaming", "$order": "n DESC", "$limit": "1500"})
    agg, variants = Counter(), defaultdict(set)
    for r in rows:
        brand = r["merk"]
        raw = (r.get("handelsbenaming") or "").strip()
        if not raw or brand in SKIP_BRANDS: continue
        name = raw.upper()
        if name.startswith(brand + " "): name = name[len(brand) + 1:]
        for b, pat, canon in ALIASES:
            m = re.match(pat, name)
            if b == brand and m:
                name = canon or m.group(1)
                break
        agg[(brand, name)] += int(r["n"])
        variants[(brand, name)].add(raw)
    return [(b, n, sorted(variants[(b, n)]), c) for (b, n), c in agg.most_common(N_MODELS)]


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
            v = main.get("brandstof_verbruik_gecombineerd_wltp")
        try:
            if v and float(v) > 0: use[k].append(float(v))
        except ValueError:
            pass
    total = sum(kinds.values()) or 1
    mix = [(k, c / total) for k, c in kinds.most_common()]
    return mix, {k: statistics.median(v) for k, v in use.items() if v}


# ---------------------------------------------------------------- html
COLOR_NL = {"ZWART": "Zwart", "WIT": "Wit", "GRIJS": "Grijs", "BLAUW": "Blauw", "ROOD": "Rood", "GROEN": "Groen", "GEEL": "Geel",
            "ORANJE": "Oranje", "BRUIN": "Bruin", "BEIGE": "Beige", "PAARS": "Paars", "ROZE": "Roze", "CREME": "Crème"}


def layout(*, title, description, path, crumbs, h1, lead, body, jsonld=(), check=True):
    url = SITE + path
    crumb_html = " › ".join(f'<a href="{esc(u)}">{esc(t)}</a>' if u else esc(t) for t, u in crumbs)
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>\n' for j in jsonld)
    check_html = """
      <form class="check" action="/" method="get">
        <div class="plate"><span class="nl">NL</span><input name="k" placeholder="XX-123-X" maxlength="10" aria-label="Kenteken" autocomplete="off"></div>
        <button>Check</button>
      </form>""" if check else ""
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(url)}">
<meta name="theme-color" content="#0E1B3D">
<link rel="icon" href="/assets/logo-icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<meta property="og:type" content="article">
<meta property="og:site_name" content="KentekenDeal">
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
      <a class="brand" href="/"><img src="/assets/logo-icon.svg" alt="">kenteken<b>deal</b></a>
      <nav class="nav"><a href="/">Kenteken check</a><a href="/auto/">Auto's</a><a href="/gids/">Koopgids</a></nav>
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
  <nav><a href="/">Kenteken check</a><a href="/auto/">Alle modellen</a><a href="/gids/">Koopgids</a></nav>
  Data: RDW Open Data, bijgewerkt {TODAY.strftime('%d-%m-%Y')}. Waarden en kosten zijn schattingen, geen taxatie.<br>© KentekenDeal
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
        val = f"{k:.1f}k".replace(".", ",") if k < 10 else f"{k:.0f}k"
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" fill="var(--bar)"/>'
                   f'<text class="val" x="{x + bw / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle">{val}</text>'
                   f'<text x="{x + bw / 2:.1f}" y="{H - 8}" text-anchor="middle">{label}</text>')
    return (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Geschatte waarde per bouwjaar">'
            + "".join(out) + "</svg>")


def build_model_page(m, others):
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

    # example: a ~5 year old car (or the closest year we have)
    ex = min(valued, key=lambda r: abs(r["y"] - (NOW_YEAR - 5)))
    km_year = 12000
    tax = road_tax_month(ex["kg"], "Benzine" if main_fuel in ("Hybride", "Plug-in hybride") else main_fuel)
    u = use.get(main_fuel)
    if main_fuel == "Elektrisch":
        fuel_cost = km_year / 12 * (u or 170) / 1000 * FUEL_PRICE["elektriciteit"]; fuel_use = f"{round((u or 170) / 10)} kWh/100 km"
    else:
        lit = max(u or 6.0, 4.5) if main_fuel == "Plug-in hybride" else (u or 6.0)
        price = FUEL_PRICE["diesel"] if main_fuel == "Diesel" else FUEL_PRICE["lpg"] if main_fuel == "LPG" else FUEL_PRICE["benzine"]
        fuel_cost = km_year / 12 * lit / 100 * price; fuel_use = f"{lit:.1f} l/100 km".replace(".", ",")
    dep = max(0, (ex["mid"] - ex["next"]) / 12)
    month_total = (tax or 0) + fuel_cost + dep

    newest = max(valued, key=lambda r: r["y"])
    fuel_txt = ", ".join(f"{k.lower()} ({round(s * 100)}%)" for k, s in mix[:3]) if mix else "onbekend"
    colour_txt = ", ".join(f"{COLOR_NL.get(c.get('eerste_kleur'), cap(c.get('eerste_kleur') or ''))}" for c in colours[:3]
                           if c.get("eerste_kleur") and "niet" not in c["eerste_kleur"].lower())

    slug = slugify(f"{brand_name(brand)} {name}")
    path = f"/auto/{slug}/"
    table_rows = "".join(
        f"<tr><td>{r['y']}</td><td>{nl_int(r['n'])}</td><td>{euro(r['p']) if r['p'] else '–'}</td>"
        f"<td>{(euro(round250(r['mid'] * 0.85)) + ' – ' + euro(round250(r['mid'] * 1.15))) if r['mid'] else '–'}</td>"
        f"<td>{(str(round(r['mid'] / r['p'] * 100)) + '%') if r['mid'] and r['p'] else '–'}</td></tr>"
        for r in sorted(rows, key=lambda r: -r["y"]))
    chart = bar_chart([(str(r["y"])[2:] if len(valued) > 10 else str(r["y"]), r["mid"]) for r in valued])

    faq = [
        (f"Wat is een {full} uit {ex['y']} waard?",
         f"Een {full} uit {ex['y']} is volgens onze schatting ongeveer {euro(round250(ex['mid'] * 0.85))} tot {euro(round250(ex['mid'] * 1.15))} waard, "
         f"bij een gemiddelde kilometerstand en normale staat. De gemiddelde nieuwprijs van dat bouwjaar was {euro(ex['p'])}."),
        (f"Wat kost een {full} per maand?",
         f"Voor een {full} uit {ex['y']} rekenen we met ongeveer {euro(month_total)} per maand bij {nl_int(km_year)} km per jaar: "
         f"wegenbelasting {euro(tax or 0)}, {'stroom' if main_fuel == 'Elektrisch' else 'brandstof'} {euro(fuel_cost)} en waardeverlies {euro(dep)}. "
         f"Verzekering en onderhoud komen daar nog bij."),
        (f"Hoeveel auto's van het type {full} rijden er in Nederland?",
         f"In het RDW-register staan {nl_int(total)} auto's van het type {full} met bouwjaar {FROM_YEAR} of later."),
        (f"Welke brandstof heeft een {full}?",
         f"Bij recente bouwjaren zien we vooral: {fuel_txt}. Dit is gebaseerd op een steekproef uit het RDW-register."),
    ]
    faq_html = "".join(f'<details class="faq"{" open" if i == 0 else ""}><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for i, (q, a) in enumerate(faq))

    same_brand = [o for o in others if o["brand"] == brand and o is not m][:6]
    popular = [o for o in others if o["brand"] != brand][:8]
    link = lambda o: f'<a class="pill" href="/auto/{o["slug"]}/">{esc(brand_name(o["brand"]) + " " + model_name(o["name"]))}</a>'

    body = f"""
<section class="card">
  <div class="stats">
    <div class="stat"><div class="l">In Nederland</div><div class="v">{nl_int(total)}</div></div>
    <div class="stat"><div class="l">Nieuwprijs {newest['y']}</div><div class="v">{euro(newest['p'])}</div></div>
    <div class="stat"><div class="l">Meest gekozen</div><div class="v">{esc(main_fuel)}</div></div>
  </div>
  <p class="note" style="margin-top:12px">Aantal met bouwjaar {FROM_YEAR} of later volgens het RDW-register. Nieuwprijs is het gemiddelde van alle uitvoeringen.</p>
</section>

<section class="card">
  <h2>Wat is een {esc(full)} waard?</h2>
  <p>Geschatte waarde per bouwjaar, bij een gemiddelde kilometerstand en normale staat.</p>
  {chart}
  <div class="table-wrap"><table>
    <thead><tr><th>Bouwjaar</th><th>Aantal</th><th>Gem. nieuwprijs</th><th>Geschatte waarde</th><th>Behouden</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table></div>
  <p class="note">De waarde van één specifieke auto hangt af van uitvoering, kilometerstand, opties en staat. Vul het kenteken in voor een persoonlijke schatting en deal-check.</p>
</section>

<section class="card">
  <h2>Wat kost een {esc(full)} per maand?</h2>
  <p>Voorbeeld: een {esc(full)} uit {ex['y']} ({esc(main_fuel.lower())}), {nl_int(km_year)} km per jaar.</p>
  <div class="costs">
    <span>Wegenbelasting (gemiddelde provincie)</span><span>{euro(tax or 0)}</span>
    <span>{'Stroom' if main_fuel == 'Elektrisch' else 'Brandstof'} ({esc(fuel_use)})</span><span>{euro(fuel_cost)}</span>
    <span>Waardeverlies</span><span>{euro(dep)}</span>
    <span class="t">Totaal per maand</span><span class="t">{euro(month_total)}</span>
  </div>
  <p class="note">Exclusief verzekering en onderhoud. Lees ook: <a href="/gids/kosten-auto-per-maand/">wat kost een auto per maand?</a></p>
</section>

<section class="card">
  <h2>Brandstof en kleuren</h2>
  <p><b>Brandstof (recente bouwjaren):</b> {esc(fuel_txt)}.</p>
  <p><b>Populairste kleuren:</b> {esc(colour_txt or 'onbekend')}.</p>
</section>

<section class="card cta">
  <h2>Staat er een {esc(full)} te koop?</h2>
  <p>Vul het kenteken en de vraagprijs in. Je ziet direct of het een goede deal is, wat de auto per maand kost en of er een terugroepactie openstaat.</p>
  <form class="check" action="/" method="get">
    <div class="plate"><span class="nl">NL</span><input name="k" placeholder="XX-123-X" maxlength="10" aria-label="Kenteken" autocomplete="off"></div>
    <button>Check</button>
  </form>
</section>

<section class="card">
  <h2>Veelgestelde vragen</h2>
  {faq_html}
</section>

<section class="card">
  {('<h2>Meer van ' + esc(brand_name(brand)) + '</h2><div class="pills">' + "".join(link(o) for o in same_brand) + '</div>') if same_brand else ''}
  <h2 style="margin-top:{'20px' if same_brand else '0'}">Andere populaire modellen</h2>
  <div class="pills">{"".join(link(o) for o in popular)}</div>
</section>
"""
    jsonld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Auto's", "item": SITE + "/auto/"},
            {"@type": "ListItem", "position": 3, "name": full, "item": SITE + path}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    page = layout(
        title=f"{full}: waarde per bouwjaar en kosten per maand ({NOW_YEAR}) | KentekenDeal",
        description=f"Wat is een {full} waard? Geschatte waarde per bouwjaar, kosten per maand en meer, op basis van RDW-data. Check ook of een {full} te koop een goede deal is.",
        path=path, crumbs=[("Home", "/"), ("Auto's", "/auto/"), (full, None)],
        h1=f"{full}: wat is hij waard en wat kost hij?",
        lead=f"Geschatte waarde per bouwjaar en kosten per maand van de {esc(full)}, op basis van RDW-data. Heb je een kenteken? Check direct of de vraagprijs eerlijk is.",
        body=body, jsonld=jsonld)
    out = ROOT / "auto" / slug / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return path


def build_overview(models):
    by_brand = defaultdict(list)
    for m in models: by_brand[m["brand"]].append(m)
    blocks = "".join(
        f'<div class="brand-block"><h3>{esc(brand_name(b))}</h3><div class="pills">'
        + "".join(f'<a class="pill" href="/auto/{m["slug"]}/">{esc(model_name(m["name"]))}</a>' for m in ms) + "</div></div>"
        for b, ms in sorted(by_brand.items(), key=lambda kv: brand_name(kv[0])))
    body = f'<section class="card"><h2>Populaire modellen in Nederland</h2><p>Kies een model voor de geschatte waarde per bouwjaar en de kosten per maand.</p>{blocks}</section>'
    page = layout(title="Auto's: waarde en kosten per model | KentekenDeal",
                  description="Wat is jouw auto waard en wat kost hij per maand? Overzicht van de populairste automodellen in Nederland, op basis van RDW-data.",
                  path="/auto/", crumbs=[("Home", "/"), ("Auto's", None)],
                  h1="Waarde en kosten per automodel", lead="De populairste modellen in Nederland: geschatte waarde per bouwjaar en wat ze per maand kosten.",
                  body=body)
    (ROOT / "auto" / "index.html").write_text(page, encoding="utf-8")


def build_sitemap(paths):
    guides = sorted("/" + p.parent.relative_to(ROOT).as_posix() + "/" for p in (ROOT / "gids").glob("*/index.html"))
    all_paths = ["/", "/auto/", "/gids/"] + guides + paths
    items = "".join(f"<url><loc>{SITE}{p}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>\n" for p in all_paths)
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}</urlset>\n', encoding="utf-8")
    return len(all_paths)


def main():
    t0 = time.time()
    print("Top models…")
    tops = top_models()
    models = [{"brand": b, "name": n, "variants": v, "count": c, "slug": slugify(f"{brand_name(b)} {n}")} for b, n, v, c in tops]

    def fetch(m):
        years, colours, fuel_rows = model_data(m["brand"], m["name"], m["variants"])
        mix, use = classify_fuel(fuel_rows)
        m.update(years=years, colours=colours, mix=mix, use=use)
        return m

    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(fetch, models))

    # Pass 1 finds which models have enough data; pass 2 builds them, linking only to built pages.
    built = [m for m in models if build_model_page(m, models)]
    for m in models:
        if m not in built:
            print(f"  skipped {m['brand']} {m['name']} (not enough data)")
    paths = []
    for m in built:
        paths.append(build_model_page(m, built))
        print(f"  {paths[-1]}  ({m['count']:,} auto's, {m['mix'][0][0] if m['mix'] else '?'})")
    build_overview(built)
    n = build_sitemap(paths)
    print(f"Done: {len(paths)} model pages, sitemap with {n} URLs, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
