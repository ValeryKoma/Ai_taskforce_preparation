# HORECA Competition Lens

Local Flask app + Quarto PDF report for the AI Taskforce prep assignment
(The Hague University of Applied Sciences).

Given an address and a category (café / restaurant / hotel), the app:
1. geocodes the address with **Nominatim**,
2. finds matching mapped establishments within 1 km using **Overpass**,
3. shows the 5 closest matches, and
4. generates a **Quarto PDF report** (typst backend) with a rule-based,
   transparent competition assessment.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

You also need [Quarto](https://quarto.org/docs/get-started/) installed and on your PATH.
Check it works:
```bash
quarto check
```

The report uses `format: typst`, so you normally don't need a full LaTeX
install. If rendering fails the first time, try:
```bash
quarto install tool typst
```
or switch `report.qmd`'s `format:` to `pdf` and run `quarto install tinytex` instead.

## Run

```bash
python app.py
```
Open http://127.0.0.1:5000, enter an address, pick a category, search,
then click "Download PDF report".

## Project structure

```
app.py            Flask routes (/, /search, /report/<id>)
osm_client.py     Nominatim + Overpass helpers, distance calculation
analysis.py       Rule-based competition assessment (shared, no LLM)
ai_narrative.py   Optional LLM narrative extension (disabled by default)
report.qmd        Quarto report template
templates/        HTML templates
data/             Per-search JSON + generated PDFs (gitignored)
```

## Responsible use of OSM

- Uses only public Nominatim/Overpass endpoints with a descriptive User-Agent
  (update the contact info in `osm_client.py` if you reuse this beyond the assignment).
- Avoid sending repeated identical requests while testing.
- Treat results as an indication only — OSM coverage can be incomplete or outdated.

## Known rough edges / things to iterate on

- Overpass sometimes returns `way`/relation results without a usable center
  under heavy load — these are currently skipped rather than retried.
- The public Overpass instance can rate-limit or time out under load; add
  retry/backoff if you hit this during testing.
- No caching yet: repeated identical searches re-hit both APIs.

## Reflection (fill this in for submission)

**What worked well?**
—

**What did not work at first?**
—

**What is one issue you solved by iterating with your coding harness?**
—

**What is one thing you still do not understand or want to discuss in the workshop?**
—
