# KentekenDeal

**Is this car worth the price?** Enter a Dutch licence plate and see the RDW vehicle data, an estimated value,
whether the asking price is a good deal, and what the car costs per month.

Live: https://kentekendeal.nl (also reachable via https://kentekendeal.github.io, which redirects)

Static site, no server, no build step for the app. Vehicle data comes live from
[RDW Open Data](https://opendata.rdw.nl) in the visitor's browser.

## Structure

| Path | What it is |
|---|---|
| `index.html` | The app (Dutch, at `/`): plate lookup, deal meter, monthly costs, APK history, specs. |
| `en/index.html` | **Generated** English copy of the app at `/en/`. Edit `index.html`, then run `python tools/build_pages.py --home`. |
| `model.js` | All calculations: RDW lookup, value estimate, deal verdict, road tax, fuel cost. **Tunable numbers live in `PARAMS` at the top.** |
| `i18n.js` | All user-facing text in Dutch and English (`t("key")`). Load before `model.js`. |
| `calibrate.html` | Hidden tool (noindex): paste real ads (`PLATE KM PRICE`) → compares with our estimate and suggests better `PARAMS`. |
| `auto/`, `en/cars/` | **Generated** model pages (~150 most popular models incl. BMW / Mercedes grouped per series), Dutch and English. Do not edit by hand. |
| `gids/`, `en/guide/` | Hand-written buyer guides, Dutch and English. Each pair links to the other with `hreflang`. |
| `tools/defects_en.json`, `tools/defects_nl.json` | English texts for the 120 most common APK defect codes, and full Dutch texts where the RDW cuts them off. Used by the app and the model pages. |
| `assets/` | Logo, icons, social preview image, `site.css` (shared style for `auto/` and `gids/`). |
| `tools/build_pages.py` | Generates `auto/` and `sitemap.xml` from RDW data. Reads `PARAMS` etc. from `model.js`. |
| `.github/workflows/update-pages.yml` | Runs `build_pages.py` on the 1st of every month and publishes changes. |
| `robots.txt`, `sitemap.xml` | Search engine rules. Plate checks (`/?k=`) are kept out of search engines on purpose. |

## Languages

- The URL decides the language: `/`, `/auto/`, `/gids/` are Dutch; `/en/`, `/en/cars/`, `/en/guide/` are English.
  Every page has `hreflang` links to its twin, so Google shows the right one. The NL/EN button goes to the twin page.
- Old links with `?lang=en` and visitors who chose English before are sent from `/` to `/en/`.
- Path mapping lives in two places: `GUIDE_EN` in `i18n.js` and in `tools/build_pages.py`. Keep them in sync.
- A new guide needs both a Dutch and an English page, a `GUIDE_EN` entry, and the hreflang links.

## Common tasks

**Change the app or text** → edit `index.html` / `model.js` / `i18n.js`, commit, push. GitHub Pages publishes in ~1 minute.

**Tune the price model** → collect ads, paste them into `/calibrate.html`, copy the suggested `PARAMS` into `model.js`,
then regenerate the model pages (below).

**Regenerate model pages + sitemap** (takes ~8 min locally, longer on GitHub; includes the APK-defects sample per model):
```
python tools/build_pages.py
```
Or on GitHub: Actions → "Update model pages" → Run workflow. It also runs automatically every month.

**Change the site address** (e.g. custom domain) → update `SITE` in `tools/build_pages.py`, the absolute URLs
(canonical / og:url / og:image / JSON-LD) in `index.html` and `gids/*/index.html`, the `Sitemap:` line in
`robots.txt`, then regenerate.

## Analytics

[GoatCounter](https://www.goatcounter.com) (no cookies). Only page paths and event names are sent, never plates.
Events: `kenteken-gezocht`, `kenteken-niet-gevonden`, `deal-check`, `voorbeeld-geklikt`, `gedeeld`, `taal-en`, `taal-nl`,
`vergelijk-gaspedaal`, `vergelijk-marktplaats`, `vergelijk-autoscout24` (clicks on the compare buttons).

## Data notes

- Value estimate = catalogue price × depreciation curve × brand/fuel/mileage adjustments. It is an estimate, not a valuation.
- APK history uses RDW datasets `sgfe-77wx` (inspections), `a34c-vvps` (defects found) and `hx2c-gt7k` (defect texts). RDW only publishes inspections from June 2022. Codes AC/RA/OP are advisories.
- Model pages: APK defects come from a sample of ~40 plates per model year (2012 to 4 years ago), refreshed monthly. Models with fewer than 120 inspected cars skip the section.
- Road tax is calibrated on 2026 rates for Noord-Brabant (87 opcenten). Other provinces: `OPCENTEN` in `model.js` (update each January). Opcenten are charged on the petrol base rate. EVs pay 70% in 2026.
- Province + own insurance premium are stored in the visitor's browser only (localStorage), never in share links.
- Fuel prices are constants in `model.js` (`FUEL_PRICE`); update roughly once a year.
