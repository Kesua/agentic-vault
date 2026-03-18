---
name: "regular_web_daily_brief"
description: "Regular Daily News sync: create/refresh the `# Daily News` header in today’s Daily Brief from deterministic `web_sources.py` output."
---

# Web Daily Brief

## What it does
- Uses `web_sources.py` as the only allowed data source for the Daily News block.
- Reads deterministic source payloads for:
  - ECMWF (IFS) weather (Prague + Hradec Králové) for today at fixed times
  - Anticipated / recap source feeds already fetched by `web_sources.py`
  - Markets (S&P 500, NASDAQ-100, DAX, Russell 2000)
- Writes the results as a readable `# Daily News` section into today’s Daily Brief:
  - `10_DailyBriefs/YYYY/MM/YYYY-MM-DD_Daily_Brief.md`
- Preserves the rest of the file (especially `# Tasks`, which is owned by the Todoist sync).

## Hard rule
- The agent must **not** do any ad-hoc web research when running this skill.
- The agent must **only** run `90_System/Skills/Web_Daily_Brief/web_sources.py fetch ...`, inspect that JSON output, and use it to construct the `# Daily News` block.
- If required data is missing from `web_sources.py` output, report the gap instead of browsing manually.

## Canonical path + ownership
- Daily Brief path: `10_DailyBriefs/YYYY/MM/YYYY-MM-DD_Daily_Brief.md`
- This skill owns only the `# Daily News` section.
- `90_System/Skills/daily_brief_todoist/` owns `# Tasks`.
- `.agents/skills/regular_day_start/SKILL.md` is the preferred morning wrapper when you want the full Daily Brief + Meetings flow.

## Output rules
- Timezone for “today / yesterday”: `Europe/Prague` (use explicit dates in the text)
- Keep it scannable:
  - Tables for weather + markets
  - Short bullets for events (1–2 sentences each)
  - Add 1–2 sources per item (markdown links)
- Replace only the `# Daily News` section if it exists; otherwise insert it above `# Tasks`.
- Sections to include (in this order):
  - Weather (ECMWF IFS): Prague + Hradec Králové (07:00/10:00/13:00/16:00/19:00/22:00)
  - Anticipated today (CZ): top 3
  - Anticipated today (World): top 3
  - Yesterday (CZ): top 3
  - Yesterday (World): top 3
  - Yesterday (AI): top 3
  - Trending yesterday (Czechia): top 5
  - Trending yesterday (World): top 5
  - Markets (last close): S&P 500, NASDAQ-100, DAX, Russell 2000

## Deterministic sources
Fetch “raw” inputs from fixed endpoints, then write the brief from those results:

- Fetch sources (JSON to stdout):
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_sources.py fetch --pretty`
- Save the fetched JSON to an intermediate file:
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_sources.py fetch --pretty > 70_Exports\sources.json`
- What you get back (high level):
  - `ecmwf_open_data_sample` (ECMWF Open Data, GRIB2 metadata + file path; decoding is separate)
  - `open_meteo_ecmwf_weather` (structured ECMWF IFS weather rows for Prague + Hradec Králové at 07:00/10:00/13:00/16:00/19:00/22:00)
  - `stooq_market_snapshot` (structured S&P 500, NASDAQ-100, DAX, Russell 2000 close + previous close + % change + as-of date)
  - `google_news_rss_cz` + `google_news_rss_world_proxy_us` (RSS items: title/link/pubDate)
  - `wikipedia_featured_news_cs` + `wikipedia_featured_news_en` (Wikimedia “featured” feed `news` array; sometimes empty)
  - `wikipedia_current_events_en_wikitext_yesterday` (Wikipedia “Portal:Current events/<yesterday>” wikitext via MediaWiki API)
  - `pytrends_top5_yesterday_cz` + `pytrends_top5_yesterday_world_proxy_us` (Top 5; can break if Google changes endpoints)
  - `pytrends_trending_searches_united_states` + `pytrends_trending_searches_japan` (examples of `pytrends.trending_searches(pn=...)`; “trending now”, not “yesterday”)
  - `google_trends_dailytrends_yesterday_cz` + `google_trends_dailytrends_yesterday_world_proxy_us` (Top 5 via Google Trends `dailytrends` endpoint; unofficial, may 404)
  - `google_trends_daily_rss_cz` + `google_trends_daily_rss_world_proxy_us` (Top 5 via Google Trends daily RSS; unofficial but often the most reliable “trending” input)

## Weather (ECMWF)
- Source recommendation (ECMWF model via Open‑Meteo):
  - Use Open‑Meteo forecast with `models=ecmwf_ifs`
  - Read `temperature_2m` and `precipitation_probability`
  - Time points (today): 07:00, 10:00, 13:00, 16:00, 19:00, 22:00 (local time)
- Locations (fixed):
  - Prague: 50.0755, 14.4378
  - Hradec Králové: 50.2092, 15.8328
- Direct API URLs (fast path)
  - Prague (ECMWF IFS, hourly temp + precip prob, Europe/Prague):
    - `https://api.open-meteo.com/v1/forecast?latitude=50.0755&longitude=14.4378&hourly=temperature_2m,precipitation_probability&timezone=Europe%2FPrague&models=ecmwf_ifs&forecast_days=1`
  - Hradec Králové (ECMWF IFS, hourly temp + precip prob, Europe/Prague):
    - `https://api.open-meteo.com/v1/forecast?latitude=50.2092&longitude=15.8328&hourly=temperature_2m,precipitation_probability&timezone=Europe%2FPrague&models=ecmwf_ifs&forecast_days=1`
- Extraction shortcut
  - In the returned JSON, use `hourly.time[]` to find today’s `07:00`, `10:00`, `13:00`, `16:00`, `19:00`, `22:00` entries, then pull the aligned values from:
    - `hourly.temperature_2m[]`
    - `hourly.precipitation_probability[]`

## Markets
- Indices:
  - S&P 500
  - NASDAQ-100
  - DAX
  - Russell 2000
- Output:
  - Last close and % change vs previous close
  - “As of” date (last trading day for that index)
- Fast sources (pick 1 and be consistent)
  - Stooq quote pages (easy last close + % change; verify “as of” date):
    - S&P 500: `https://stooq.com/q/?s=^spx`
    - NASDAQ-100: `https://stooq.com/q/?s=^ndx`
    - DAX: `https://stooq.com/q/?s=^dax`
    - Russell 2000: `https://stooq.com/q/?s=^rut`
  - If Stooq is unavailable, use a major finance source (e.g., exchange/operator pages or widely used market data sites) and compute `% chg = (close/prev_close - 1) * 100` if needed.

## Construction rule
- Use only the fetched JSON from `web_sources.py`.
- Do not open search engines, browse news sites manually, or add extra sources outside the JSON payload.
- When a source payload is `ok: false`, omit or clearly label that subsection instead of researching manually.

## Commands (Windows)
This skill is “agent-driven” in the sense that the agent summarizes deterministic JSON and writes markdown. It is **not** a free-form browsing task.

- Fetch deterministic sources:
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_sources.py fetch --pretty > 70_Exports\sources.json`
- Construct `70_Exports\daily_news.md` only from that JSON output:
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_daily_brief.py render --sources-file 70_Exports\sources.json --output-file 70_Exports\daily_news.md`
- Apply a prepared `# Daily News` block from a file:
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_daily_brief.py apply --content-file 70_Exports\daily_news.md`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_daily_brief.py apply --content-file 70_Exports\daily_news.md --dry-run`

## Daily News template (copy/paste)
Use this structure.

```markdown
# Daily News
- Updated: YYYY-MM-DDTHH:mm (Europe/Prague)
- Coverage: weather (ECMWF), events (CZ+World), yesterday (CZ+World+AI), trends (CZ+World), markets

## Weather (ECMWF IFS)

### Prague
| Time | Temp (°C) | Precip prob (%) |
|---:|---:|---:|
| 07:00 |  |  |
| 10:00 |  |  |
| 13:00 |  |  |
| 16:00 |  |  |
| 19:00 |  |  |
| 22:00 |  |  |
Source: [Open‑Meteo (ECMWF IFS)](https://open-meteo.com/)

### Hradec Králové
| Time | Temp (°C) | Precip prob (%) |
|---:|---:|---:|
| 07:00 |  |  |
| 10:00 |  |  |
| 13:00 |  |  |
| 16:00 |  |  |
| 19:00 |  |  |
| 22:00 |  |  |
Source: [Open‑Meteo (ECMWF IFS)](https://open-meteo.com/)

## Anticipated today (CZ) — YYYY-MM-DD
- **Event** — short context. ([source](https://example.com))
- **Event** — short context. ([source](https://example.com))
- **Event** — short context. ([source](https://example.com))

## Anticipated today (World) — YYYY-MM-DD
- **Event** — short context. ([source](https://example.com))
- **Event** — short context. ([source](https://example.com))
- **Event** — short context. ([source](https://example.com))

## Yesterday (CZ) — YYYY-MM-DD
- **Event** — short context. ([source](https://example.com))
- **Event** — short context. ([source](https://example.com))
- **Event** — short context. ([source](https://example.com))

## Yesterday (World) — YYYY-MM-DD
- **Event** — short context. ([source](https://example.com))
- **Event** — short context. ([source](https://example.com))
- **Event** — short context. ([source](https://example.com))

## Yesterday (AI) — YYYY-MM-DD
- **Item** — short context. ([source](https://example.com))
- **Item** — short context. ([source](https://example.com))
- **Item** — short context. ([source](https://example.com))

## Trending yesterday (Czechia) — YYYY-MM-DD
- **Trend** — (optional context). ([source](https://trends.google.com/))
- **Trend** — (optional context). ([source](https://trends.google.com/))
- **Trend** — (optional context). ([source](https://trends.google.com/))
- **Trend** — (optional context). ([source](https://trends.google.com/))
- **Trend** — (optional context). ([source](https://trends.google.com/))

## Trending yesterday (World) — YYYY-MM-DD
- **Trend** — (optional context). ([source](https://trends.google.com/))
- **Trend** — (optional context). ([source](https://trends.google.com/))
- **Trend** — (optional context). ([source](https://trends.google.com/))
- **Trend** — (optional context). ([source](https://trends.google.com/))
- **Trend** — (optional context). ([source](https://trends.google.com/))

## Markets (last close)
| Index | Close | % chg | As of |
|---|---:|---:|---|
| S&P 500 |  |  | YYYY-MM-DD |
| NASDAQ-100 |  |  | YYYY-MM-DD |
| DAX |  |  | YYYY-MM-DD |
| Russell 2000 |  |  | YYYY-MM-DD |
Sources: link the pages you used.
```
