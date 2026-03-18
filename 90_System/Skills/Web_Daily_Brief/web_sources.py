from __future__ import annotations

import argparse
import csv
import base64
import hashlib
import json
import sys
import tempfile
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Callable

try:
    from zoneinfo import ZoneInfo
    from zoneinfo import ZoneInfoNotFoundError
except ImportError:  # pragma: no cover (Python < 3.9)
    ZoneInfo = None  # type: ignore[assignment]
    ZoneInfoNotFoundError = Exception  # type: ignore[assignment]


DEFAULT_TZ = "Europe/Prague"
DEFAULT_TIMEOUT_S = 30
ECMWF_WEATHER_TIMES = ("07:00", "10:00", "13:00", "16:00", "19:00", "22:00")
ECMWF_LOCATIONS = (
    {
        "name": "Prague",
        "latitude": 50.0755,
        "longitude": 14.4378,
    },
    {
        "name": "Hradec Králové",
        "latitude": 50.2092,
        "longitude": 15.8328,
    },
)
STOOQ_MARKETS = (
    {"name": "S&P 500", "symbol": "^spx", "cnbc_symbol": ".SPX"},
    {"name": "NASDAQ-100", "symbol": "^ndx", "cnbc_symbol": ".NDX"},
    {"name": "DAX", "symbol": "^dax", "cnbc_symbol": ".GDAXI"},
    {"name": "Russell 2000", "symbol": "^rut", "cnbc_symbol": ".RUT"},
)


def _now_iso(tz_name: str) -> str:
    if ZoneInfo is None:
        return datetime.now().replace(microsecond=0).isoformat()
    try:
        return datetime.now(ZoneInfo(tz_name)).replace(microsecond=0).isoformat()
    except ZoneInfoNotFoundError:
        return datetime.now().replace(microsecond=0).isoformat()


def _today(tz_name: str) -> date:
    if ZoneInfo is None:
        return datetime.now().date()
    try:
        return datetime.now(ZoneInfo(tz_name)).date()
    except ZoneInfoNotFoundError:
        return datetime.now().date()


def _http_get(url: str, *, timeout_s: int, user_agent: str) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        status = getattr(resp, "status", 200)
        headers = {k.lower(): v for k, v in resp.headers.items()}
        body = resp.read()
        return int(status), headers, body


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _as_text(body: bytes, headers: dict[str, str]) -> str:
    content_type = headers.get("content-type", "")
    encoding = "utf-8"
    if "charset=" in content_type:
        encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _truncate_text(text: str, *, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n[truncated]\n", True


def _open_meteo_ecmwf_url(*, latitude: float, longitude: float, tz_name: str) -> str:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,precipitation_probability",
        "timezone": tz_name,
        "models": "ecmwf_ifs",
        "forecast_days": 1,
    }
    return "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)


def _open_meteo_ecmwf_weather(*, tz_name: str, timeout_s: int, user_agent: str) -> dict[str, Any]:
    target_date = _today(tz_name).isoformat()
    locations: list[dict[str, Any]] = []

    for location in ECMWF_LOCATIONS:
        url = _open_meteo_ecmwf_url(
            latitude=float(location["latitude"]),
            longitude=float(location["longitude"]),
            tz_name=tz_name,
        )
        status, headers, body = _http_get(url, timeout_s=timeout_s, user_agent=user_agent)
        text = _as_text(body, headers)
        data = json.loads(text)

        hourly = data.get("hourly", {}) if isinstance(data, dict) else {}
        times = hourly.get("time", []) if isinstance(hourly, dict) else []
        temperatures = hourly.get("temperature_2m", []) if isinstance(hourly, dict) else []
        precip_probs = hourly.get("precipitation_probability", []) if isinstance(hourly, dict) else []

        rows: list[dict[str, Any]] = []
        for time_label in ECMWF_WEATHER_TIMES:
            lookup = f"{target_date}T{time_label}"
            try:
                idx = times.index(lookup)
            except ValueError:
                rows.append(
                    {
                        "time": time_label,
                        "temperature_2m": None,
                        "precipitation_probability": None,
                        "available": False,
                    }
                )
                continue

            rows.append(
                {
                    "time": time_label,
                    "temperature_2m": temperatures[idx] if idx < len(temperatures) else None,
                    "precipitation_probability": precip_probs[idx] if idx < len(precip_probs) else None,
                    "available": True,
                }
            )

        locations.append(
            {
                "name": location["name"],
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "source_url": url,
                "status_code": status,
                "content_type": headers.get("content-type"),
                "sha256": _sha256_hex(body),
                "timezone": data.get("timezone"),
                "model": "ecmwf_ifs",
                "target_date": target_date,
                "rows": rows,
            }
        )

    return {
        "model": "ecmwf_ifs",
        "target_date": target_date,
        "times_local": list(ECMWF_WEATHER_TIMES),
        "locations": locations,
    }


def _google_news_rss(url: str, *, timeout_s: int, user_agent: str, max_items: int) -> dict[str, Any]:
    status, headers, body = _http_get(url, timeout_s=timeout_s, user_agent=user_agent)
    text = _as_text(body, headers)

    root = ET.fromstring(text)
    channel = root.find("channel")
    items: list[dict[str, Any]] = []
    if channel is not None:
        for item in channel.findall("item")[:max_items]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            items.append({"title": title, "link": link, "pubDate": pub_date})

    return {
        "status_code": status,
        "content_type": headers.get("content-type"),
        "sha256": _sha256_hex(body),
        "items": items,
    }


def _parse_stooq_quote_line(text: str) -> dict[str, Any]:
    line = next((x.strip() for x in text.splitlines() if x.strip()), "")
    if not line:
        raise ValueError("empty Stooq quote response")

    row = next(csv.reader([line]))
    if len(row) < 7:
        raise ValueError(f"unexpected Stooq quote format: {row}")

    def _optional_float(value: str) -> float | None:
        value = (value or "").strip()
        if not value or value == "N/D":
            return None
        return float(value)

    def _optional_int(value: str) -> int | None:
        parsed = _optional_float(value)
        return int(parsed) if parsed is not None else None

    return {
        "symbol": row[0],
        "date": row[1] if len(row) > 1 else "N/D",
        "time": row[2] if len(row) > 2 else "N/D",
        "open": _optional_float(row[3]) if len(row) > 3 else None,
        "high": _optional_float(row[4]) if len(row) > 4 else None,
        "low": _optional_float(row[5]) if len(row) > 5 else None,
        "close": _optional_float(row[6]) if len(row) > 6 else None,
        "volume": _optional_int(row[7]) if len(row) > 7 else None,
    }


def _parse_stooq_history_csv(text: str) -> list[dict[str, Any]]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    reader = csv.DictReader(lines)
    rows: list[dict[str, Any]] = []
    for row in reader:
        try:
            rows.append(
                {
                    "date": str(row.get("Date") or "").strip(),
                    "open": float(row.get("Open") or 0),
                    "high": float(row.get("High") or 0),
                    "low": float(row.get("Low") or 0),
                    "close": float(row.get("Close") or 0),
                    "volume": int(float(row.get("Volume") or 0)),
                }
            )
        except ValueError:
            continue
    return rows


def _stooq_market_snapshot(*, timeout_s: int, user_agent: str) -> dict[str, Any]:
    markets: list[dict[str, Any]] = []

    for market in STOOQ_MARKETS:
        symbol = str(market["symbol"])
        symbol_encoded = urllib.parse.quote(symbol)
        quote_url = f"https://stooq.com/q/l/?s={symbol_encoded}&i=d"
        history_url = f"https://stooq.com/q/d/l/?s={symbol_encoded}&i=d"
        page_url = f"https://stooq.com/q/?s={symbol_encoded}"

        quote_status, quote_headers, quote_body = _http_get(quote_url, timeout_s=timeout_s, user_agent=user_agent)
        quote_text = _as_text(quote_body, quote_headers)
        quote = _parse_stooq_quote_line(quote_text)

        history_status, history_headers, history_body = _http_get(history_url, timeout_s=timeout_s, user_agent=user_agent)
        history_text = _as_text(history_body, history_headers)
        history_rows = _parse_stooq_history_csv(history_text)
        latest_history = history_rows[-1] if history_rows else None

        previous_close: float | None = None
        close_value = quote["close"] if quote["close"] is not None else (float(latest_history["close"]) if latest_history else None)
        as_of_date_raw = quote["date"] if quote["date"] != "N/D" else (str(latest_history["date"]).replace("-", "") if latest_history else None)
        as_of_time_utc = quote["time"] if quote["time"] != "N/D" else None
        open_value = quote["open"] if quote["open"] is not None else (float(latest_history["open"]) if latest_history else None)
        high_value = quote["high"] if quote["high"] is not None else (float(latest_history["high"]) if latest_history else None)
        low_value = quote["low"] if quote["low"] is not None else (float(latest_history["low"]) if latest_history else None)

        if len(history_rows) >= 2 and close_value is not None:
            last_row = history_rows[-1]
            prior_row = history_rows[-2]
            if as_of_date_raw and last_row["date"].replace("-", "") == as_of_date_raw:
                previous_close = float(prior_row["close"])
            else:
                previous_close = float(last_row["close"])

        pct_change = None
        if previous_close not in (None, 0) and close_value is not None:
            pct_change = round(((float(close_value) / float(previous_close)) - 1.0) * 100.0, 4)

        fallback_used = False
        fallback_payload: dict[str, Any] | None = None
        if close_value is None and market.get("cnbc_symbol"):
            fallback_payload = _cnbc_market_quote(
                cnbc_symbol=str(market["cnbc_symbol"]),
                timeout_s=timeout_s,
                user_agent=user_agent,
            )
            if fallback_payload.get("close") is not None:
                fallback_used = True
                close_value = fallback_payload.get("close")
                previous_close = fallback_payload.get("previous_close")
                pct_change = fallback_payload.get("pct_change_vs_previous_close")
                open_value = open_value if open_value is not None else close_value
                high_value = high_value if high_value is not None else None
                low_value = low_value if low_value is not None else None
                as_of_date_raw = (str(fallback_payload.get("as_of_date") or "") or None)
                as_of_time_utc = None

        markets.append(
            {
                "name": market["name"],
                "symbol": symbol,
                "provider": fallback_payload.get("provider") if fallback_used and fallback_payload else "Stooq",
                "quote_url": page_url,
                "quote_csv_url": quote_url,
                "history_csv_url": history_url,
                "as_of_date": (
                    f"{as_of_date_raw[0:4]}-{as_of_date_raw[4:6]}-{as_of_date_raw[6:8]}"
                    if as_of_date_raw and len(as_of_date_raw) == 8
                    else as_of_date_raw
                ),
                "as_of_time_utc": as_of_time_utc,
                "close": close_value,
                "previous_close": previous_close,
                "pct_change_vs_previous_close": pct_change,
                "open": open_value,
                "high": high_value,
                "low": low_value,
                "volume": quote["volume"],
                "fallback_used": fallback_used,
                "fallback_payload": fallback_payload,
                "status_code": quote_status,
                "content_type": quote_headers.get("content-type"),
                "quote_sha256": _sha256_hex(quote_body),
                "history_status_code": history_status,
                "history_content_type": history_headers.get("content-type"),
                "history_sha256": _sha256_hex(history_body),
            }
        )

    return {
        "provider": "Stooq",
        "markets": markets,
    }


def _cnbc_market_quote(*, cnbc_symbol: str, timeout_s: int, user_agent: str) -> dict[str, Any]:
    url = f"https://www.cnbc.com/quotes/{urllib.parse.quote(cnbc_symbol)}"
    status, headers, body = _http_get(url, timeout_s=timeout_s, user_agent=user_agent)
    text = _as_text(body, headers)

    def _extract(pattern: str) -> str | None:
        import re

        match = re.search(pattern, text)
        return match.group(1) if match else None

    last_raw = _extract(r'"last":"([^"]+)"')
    change_raw = _extract(r'"change":"([^"]+)"')
    change_pct_raw = _extract(r'"change_pct":"([^"]+)"')
    last_time = _extract(r'"last_time":"([^"]+)"')
    name = _extract(r'"name":"([^"]+)"')

    def _parse_number(value: str | None) -> float | None:
        if not value:
            return None
        cleaned = value.replace(",", "").replace("%", "").strip()
        if not cleaned:
            return None
        return float(cleaned)

    last_value = _parse_number(last_raw)
    change_value = _parse_number(change_raw)
    previous_close = None
    if last_value is not None and change_value is not None:
        previous_close = round(last_value - change_value, 6)

    return {
        "name": name,
        "symbol": cnbc_symbol,
        "provider": "CNBC",
        "quote_url": url,
        "as_of_date": last_time,
        "close": last_value,
        "previous_close": previous_close,
        "pct_change_vs_previous_close": _parse_number(change_pct_raw),
        "change": change_value,
        "status_code": status,
        "content_type": headers.get("content-type"),
        "sha256": _sha256_hex(body),
    }


def _google_trends_dailytrends_yesterday(*, geo: str, d: date, timeout_s: int, user_agent: str, max_items: int) -> dict[str, Any]:
    """
    Fetch Google Trends 'dailytrends' for a specific end-date (ed=YYYYMMDD).

    This is an unofficial endpoint (commonly used by pytrends) but tends to be more stable than scraping.
    """
    # Note: This endpoint is unofficial and sometimes returns 404 when parameters change.
    ed = d.strftime("%Y%m%d")
    urls = [
        f"https://trends.google.com/trends/api/dailytrends?hl=en-US&tz=0&geo={urllib.parse.quote(geo)}&ns=15&ed={ed}",
        f"https://trends.google.com/trends/api/dailytrends?hl=en-US&tz=0&geo={urllib.parse.quote(geo)}&ns=15",
    ]

    last_error: str | None = None
    status = 0
    headers: dict[str, str] = {}
    body = b""
    data: dict[str, Any] = {}

    for url in urls:
        try:
            status, headers, body = _http_get(url, timeout_s=timeout_s, user_agent=user_agent)
            text = _as_text(body, headers).lstrip()
            if text.startswith(")]}'"):
                text = text.split("\n", 1)[1] if "\n" in text else ""
            data = json.loads(text) if text else {}
            last_error = None
            break
        except Exception as e:
            last_error = f"{e.__class__.__name__}: {e}"
            continue

    days = data.get("default", {}).get("trendingSearchesDays", [])
    searches = days[0].get("trendingSearches", []) if (days and isinstance(days[0], dict)) else []

    items: list[dict[str, Any]] = []
    for s in searches[:max_items]:
        title_obj = s.get("title")
        query = (title_obj.get("query") if isinstance(title_obj, dict) else title_obj) or ""
        traffic = s.get("formattedTraffic")
        articles = s.get("articles", [])
        article_summaries: list[dict[str, str]] = []
        if isinstance(articles, list):
            for a in articles[:3]:
                if not isinstance(a, dict):
                    continue
                source_obj = a.get("source")
                source_name = (source_obj.get("name") if isinstance(source_obj, dict) else source_obj) or ""
                article_summaries.append(
                    {"title": str(a.get("title") or ""), "url": str(a.get("url") or ""), "source": str(source_name)}
                )
        items.append({"query": str(query).strip(), "traffic": traffic, "articles": article_summaries})

    return {
        "urls_tried": urls,
        "status_code": status,
        "content_type": headers.get("content-type"),
        "sha256": _sha256_hex(body) if body else None,
        "items": [x for x in items if x.get("query")][:max_items],
        "note": "Unofficial Google Trends endpoint; may change.",
        **({"error": last_error} if last_error else {}),
    }


def _xml_item_text(item: ET.Element, local_name: str) -> str:
    for child in list(item):
        if _strip_xml_namespace(child.tag) == local_name:
            return (child.text or "").strip()
    return ""


def _google_trends_daily_rss(*, geo: str, timeout_s: int, user_agent: str, max_items: int) -> dict[str, Any]:
    """
    Fetch Google Trends daily trending searches RSS (unofficial but simple and often stable).
    """
    url = f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={urllib.parse.quote(geo)}"
    status, headers, body = _http_get(url, timeout_s=timeout_s, user_agent=user_agent)
    text = _as_text(body, headers)

    root = ET.fromstring(text)
    channel = root.find("channel")
    items: list[dict[str, Any]] = []
    if channel is not None:
        for item in channel.findall("item")[:max_items]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            approx_traffic = _xml_item_text(item, "approx_traffic")
            items.append(
                {
                    "title": title,
                    "link": link,
                    "pubDate": pub_date,
                    "approx_traffic": approx_traffic or None,
                }
            )

    return {
        "url": url,
        "status_code": status,
        "content_type": headers.get("content-type"),
        "sha256": _sha256_hex(body),
        "items": items,
        "note": "Unofficial RSS feed; typically represents the last completed day for the region.",
    }


def _wikipedia_current_events_wikitext_en(*, d: date, timeout_s: int, user_agent: str) -> dict[str, Any]:
    # Daily pages exist as: Portal:Current events/YYYY Month D (e.g., 2026 February 25)
    title = f"Portal:Current events/{d:%Y} {d:%B} {d.day}"
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    }
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    status, headers, body = _http_get(url, timeout_s=timeout_s, user_agent=user_agent)
    text = _as_text(body, headers)
    data = json.loads(text) if text else {}
    wikitext = ((data.get("parse") or {}).get("wikitext") or "") if isinstance(data, dict) else ""
    return {
        "url": url,
        "status_code": status,
        "content_type": headers.get("content-type"),
        "sha256": _sha256_hex(body),
        "page": title,
        "wikitext": wikitext,
    }


def _wikimedia_featured(lang: str, d: date, *, timeout_s: int, user_agent: str) -> dict[str, Any]:
    url = f"https://api.wikimedia.org/feed/v1/wikipedia/{lang}/featured/{d:%Y}/{d:%m}/{d:%d}"
    status, headers, body = _http_get(url, timeout_s=timeout_s, user_agent=user_agent)
    text = _as_text(body, headers)
    data = json.loads(text)
    news = data.get("news", [])
    normalized_news: list[dict[str, Any]] = []
    for item in news:
        normalized_news.append(
            {
                "story": item.get("story"),
                "links": item.get("links", []),
            }
        )

    return {
        "url": url,
        "status_code": status,
        "content_type": headers.get("content-type"),
        "sha256": _sha256_hex(body),
        "news": normalized_news,
    }


def _pytrends_top5_yesterday(*, geo: str, tz_name: str) -> dict[str, Any]:
    try:
        from pytrends.request import TrendReq  # type: ignore[import-not-found]
    except Exception as e:  # pragma: no cover
        return {
            "error": f"pytrends import failed: {e.__class__.__name__}: {e}",
            "install_hint": "pip install -U pytrends",
        }

    yday = _today(tz_name) - timedelta(days=1)
    pytrends = TrendReq(hl="en-US", tz=0)

    # Try to fetch a date-specific daily trends report if supported by the installed pytrends.
    methods_tried: list[dict[str, Any]] = []

    def _df_to_list(df: Any) -> list[str]:
        # DataFrame-like: use first column, drop empty, keep order.
        try:
            col = df.iloc[:, 0].tolist()  # type: ignore[attr-defined]
        except Exception:
            try:
                col = list(df[df.columns[0]].values)  # type: ignore[attr-defined]
            except Exception:
                return []
        out: list[str] = []
        for x in col:
            s = str(x).strip()
            if s and s not in out:
                out.append(s)
        return out

    if hasattr(pytrends, "daily_trends"):
        daily_trends: Callable[..., Any] = getattr(pytrends, "daily_trends")
        # Try several common signatures (pytrends has changed over time).
        candidates = [
            {"year": yday.year, "month": yday.month, "day": yday.day, "geo": geo},
            {"date": yday.strftime("%Y%m%d"), "geo": geo},
            {"date": yday.strftime("%Y-%m-%d"), "geo": geo},
        ]
        for kwargs in candidates:
            try:
                df = daily_trends(**kwargs)
                values = _df_to_list(df)
                methods_tried.append({"method": "daily_trends", "kwargs": kwargs, "result_count": len(values)})
                if values:
                    return {
                        "date": yday.isoformat(),
                        "geo": geo,
                        "method": "daily_trends",
                        "method_kwargs": kwargs,
                        "items": values[:5],
                        "methods_tried": methods_tried,
                    }
            except Exception as e:
                methods_tried.append(
                    {"method": "daily_trends", "kwargs": kwargs, "error": f"{e.__class__.__name__}: {e}"}
                )

    # Fallback: trending_searches (not guaranteed to be "yesterday", depends on endpoint behavior).
    if hasattr(pytrends, "trending_searches"):
        trending_searches: Callable[..., Any] = getattr(pytrends, "trending_searches")
        pn_candidates = [geo, geo.lower(), "czech_republic" if geo.upper() == "CZ" else None, "united_states" if geo.upper() == "US" else None]  # type: ignore[list-item]
        pn_candidates = [x for x in pn_candidates if x]
        for pn in pn_candidates:
            try:
                df = trending_searches(pn=pn)
                values = _df_to_list(df)
                methods_tried.append({"method": "trending_searches", "kwargs": {"pn": pn}, "result_count": len(values)})
                if values:
                    return {
                        "date": yday.isoformat(),
                        "geo": geo,
                        "method": "trending_searches",
                        "method_kwargs": {"pn": pn},
                        "items": values[:5],
                        "methods_tried": methods_tried,
                        "note": "Fallback method; may not strictly be 'yesterday' depending on Trends endpoint.",
                    }
            except Exception as e:
                methods_tried.append(
                    {"method": "trending_searches", "kwargs": {"pn": pn}, "error": f"{e.__class__.__name__}: {e}"}
                )

    return {"error": "pytrends did not provide daily trends via available methods", "methods_tried": methods_tried}


def _pytrends_trending_searches_top5(*, pn: str) -> dict[str, Any]:
    """
    Fetch Google Trends "trending searches" for a region (real-time-ish), via pytrends.

    Note: This is not guaranteed to represent "yesterday"; treat it as "trending now / latest list".
    """
    try:
        from pytrends.request import TrendReq  # type: ignore[import-not-found]
    except Exception as e:  # pragma: no cover
        return {
            "error": f"pytrends import failed: {e.__class__.__name__}: {e}",
            "install_hint": "pip install -U pytrends",
        }

    pytrends = TrendReq(hl="en-US", tz=0)

    def _df_to_list(df: Any) -> list[str]:
        try:
            col = df.iloc[:, 0].tolist()  # type: ignore[attr-defined]
        except Exception:
            try:
                col = list(df[df.columns[0]].values)  # type: ignore[attr-defined]
            except Exception:
                return []
        out: list[str] = []
        for x in col:
            s = str(x).strip()
            if s and s not in out:
                out.append(s)
        return out

    try:
        df = pytrends.trending_searches(pn=pn)
        items = _df_to_list(df)[:5]
        return {
            "pn": pn,
            "items": items,
            "note": "pytrends.trending_searches (not a dated 'yesterday' list).",
        }
    except Exception as e:
        return {"pn": pn, "error": f"{e.__class__.__name__}: {e}"}


def _ecmwf_open_data_sample(*, tz_name: str) -> dict[str, Any]:
    """
    Fetch a *small* ECMWF Open Data sample.

    Note: ECMWF Open Data is typically delivered as GRIB2. This function downloads a small file and returns metadata.
    Decoding GRIB2 into point forecasts requires extra native deps (eccodes/cfgrib/xarray) that are not assumed here.
    """
    try:
        from ecmwf.opendata import Client  # type: ignore[import-not-found]
    except Exception as e:  # pragma: no cover
        return {
            "error": f"ecmwf-opendata import failed: {e.__class__.__name__}: {e}",
            "install_hint": "pip install ecmwf-opendata",
        }

    # Pick "latest" available run. The library handles availability internally.
    # Keep the request intentionally small.
    request = {
        "source": "ecmwf",
        "model": "ifs",
        "type": "fc",
        "param": "2t",
        "step": 0,
        "time": 0,
    }

    # The ECMWF client may print portal notices to stdout; capture it so our program output stays valid JSON.
    buf_out = StringIO()
    buf_err = StringIO()
    with redirect_stdout(buf_out), redirect_stderr(buf_err):
        client = Client(source=request["source"])
    tmp_dir = Path(tempfile.gettempdir()) / "ecmwf-open-data"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"ecmwf_ifs_2t_step0_{_today(tz_name).isoformat()}.grib2"

    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            client.retrieve(
                request={k: v for k, v in request.items() if k not in {"source"}},
                target=str(out_path),
            )
    except Exception as e:
        return {"request": request, "error": f"retrieve failed: {e.__class__.__name__}: {e}"}

    data = out_path.read_bytes()
    head_b64 = base64.b64encode(data[:256]).decode("ascii")
    return {
        "request": request,
        "file_path": str(out_path),
        "bytes": len(data),
        "sha256": _sha256_hex(data),
        "head_base64_256": head_b64,
        "content_note": "GRIB2 binary; decode separately to extract point values.",
        "portal_notice_stdout": buf_out.getvalue().strip() or None,
        "portal_notice_stderr": buf_err.getvalue().strip() or None,
    }


def _make_source(name: str, *, ok: bool, payload: Any, fetched_at: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"name": name, "ok": ok, "fetched_at": fetched_at, "payload": payload}
    if meta:
        out["meta"] = meta
    return out


def fetch_all(
    *,
    tz_name: str,
    timeout_s: int,
    user_agent: str,
    max_chars: int,
    rss_max_items: int,
) -> dict[str, Any]:
    fetched_at = _now_iso(tz_name)
    today = _today(tz_name)
    yesterday = today - timedelta(days=1)

    sources: list[dict[str, Any]] = []

    def _safe(name: str, fn: Callable[[], Any], *, meta: dict[str, Any] | None = None) -> None:
        try:
            payload = fn()
            ok = not (isinstance(payload, dict) and "error" in payload)
            sources.append(_make_source(name, ok=ok, payload=payload, fetched_at=fetched_at, meta=meta))
        except Exception as e:
            sources.append(
                _make_source(
                    name,
                    ok=False,
                    payload={"error": f"{e.__class__.__name__}: {e}"},
                    fetched_at=fetched_at,
                    meta=meta,
                )
            )

    # Weather: ECMWF Open Data (binary GRIB2 sample + metadata).
    _safe("ecmwf_open_data_sample", lambda: _ecmwf_open_data_sample(tz_name=tz_name))
    _safe(
        "open_meteo_ecmwf_weather",
        lambda: _open_meteo_ecmwf_weather(tz_name=tz_name, timeout_s=timeout_s, user_agent=user_agent),
        meta={"date": today.isoformat(), "times_local": list(ECMWF_WEATHER_TIMES)},
    )

    # Markets: Stooq index snapshots + previous-close comparison.
    _safe(
        "stooq_market_snapshot",
        lambda: _stooq_market_snapshot(timeout_s=timeout_s, user_agent=user_agent),
        meta={"indices": [market["name"] for market in STOOQ_MARKETS]},
    )

    # Google News RSS (CZ + US proxy).
    _safe(
        "google_news_rss_cz",
        lambda: _google_news_rss(
            "https://news.google.com/rss?hl=cs&gl=CZ&ceid=CZ:cs",
            timeout_s=timeout_s,
            user_agent=user_agent,
            max_items=rss_max_items,
        ),
    )
    _safe(
        "google_news_rss_world_proxy_us",
        lambda: _google_news_rss(
            "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
            timeout_s=timeout_s,
            user_agent=user_agent,
            max_items=rss_max_items,
        ),
    )

    # Wikipedia Current Events (Wikimedia Featured Content 'news' list) — CZ + EN.
    _safe(
        "wikipedia_featured_news_cs",
        lambda: _wikimedia_featured("cs", yesterday, timeout_s=timeout_s, user_agent=user_agent),
        meta={"date": yesterday.isoformat()},
    )
    _safe(
        "wikipedia_featured_news_en",
        lambda: _wikimedia_featured("en", yesterday, timeout_s=timeout_s, user_agent=user_agent),
        meta={"date": yesterday.isoformat()},
    )

    # Wikipedia Current events daily page (EN) — wikitext for yesterday.
    _safe(
        "wikipedia_current_events_en_wikitext_yesterday",
        lambda: _wikipedia_current_events_wikitext_en(d=yesterday, timeout_s=timeout_s, user_agent=user_agent),
        meta={"date": yesterday.isoformat()},
    )

    # Google Trends (pytrends) — yesterday top 5, CZ + World proxy (US).
    _safe(
        "pytrends_top5_yesterday_cz",
        lambda: _pytrends_top5_yesterday(geo="CZ", tz_name=tz_name),
        meta={"date": yesterday.isoformat()},
    )
    _safe(
        "pytrends_top5_yesterday_world_proxy_us",
        lambda: _pytrends_top5_yesterday(geo="US", tz_name=tz_name),
        meta={"date": yesterday.isoformat()},
    )

    # Google Trends (pytrends) — trending searches (real-time-ish), explicit pn examples.
    _safe(
        "pytrends_trending_searches_united_states",
        lambda: _pytrends_trending_searches_top5(pn="united_states"),
    )
    _safe(
        "pytrends_trending_searches_japan",
        lambda: _pytrends_trending_searches_top5(pn="japan"),
    )

    # Google Trends (unofficial dailytrends endpoint) — yesterday top 5, CZ + World proxy (US).
    _safe(
        "google_trends_dailytrends_yesterday_cz",
        lambda: _google_trends_dailytrends_yesterday(
            geo="CZ", d=yesterday, timeout_s=timeout_s, user_agent=user_agent, max_items=5
        ),
        meta={"date": yesterday.isoformat()},
    )
    _safe(
        "google_trends_dailytrends_yesterday_world_proxy_us",
        lambda: _google_trends_dailytrends_yesterday(
            geo="US", d=yesterday, timeout_s=timeout_s, user_agent=user_agent, max_items=5
        ),
        meta={"date": yesterday.isoformat()},
    )

    # Google Trends (RSS) — often more reliable than the JSON endpoint.
    _safe(
        "google_trends_daily_rss_cz",
        lambda: _google_trends_daily_rss(geo="CZ", timeout_s=timeout_s, user_agent=user_agent, max_items=5),
        meta={"date": yesterday.isoformat()},
    )
    _safe(
        "google_trends_daily_rss_world_proxy_us",
        lambda: _google_trends_daily_rss(geo="US", timeout_s=timeout_s, user_agent=user_agent, max_items=5),
        meta={"date": yesterday.isoformat()},
    )

    # Truncate any large string values in-place (keep output safe for LLMs).
    def _truncate_obj(o: Any) -> Any:
        if isinstance(o, str):
            t, truncated = _truncate_text(o, max_chars=max_chars)
            return {"text": t, "truncated": truncated} if truncated else o
        if isinstance(o, list):
            return [_truncate_obj(x) for x in o]
        if isinstance(o, dict):
            return {k: _truncate_obj(v) for k, v in o.items()}
        return o

    return {
        "fetched_at": fetched_at,
        "tz": tz_name,
        "today": today.isoformat(),
        "yesterday": yesterday.isoformat(),
        "sources": _truncate_obj(sources),
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="web_sources")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="Fetch deterministic endpoints for Web Daily Brief")
    p_fetch.add_argument("--tz", default=DEFAULT_TZ)
    p_fetch.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    p_fetch.add_argument(
        "--user-agent",
        default="ChiefOfStuffVault-WebDailyBrief/1.0",
        help="User-Agent for HTTP calls (some endpoints may block default urllib UA).",
    )
    p_fetch.add_argument("--max-chars", type=int, default=30_000, help="Max chars for any single text field in output.")
    p_fetch.add_argument("--rss-max-items", type=int, default=30)
    p_fetch.add_argument("--pretty", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "fetch":
        try:
            data = fetch_all(
                tz_name=str(args.tz),
                timeout_s=int(args.timeout),
                user_agent=str(args.user_agent),
                max_chars=int(args.max_chars),
                rss_max_items=int(args.rss_max_items),
            )
        except urllib.error.URLError as e:
            print(json.dumps({"ok": False, "error": f"network error: {e}"}, ensure_ascii=False))
            return 1
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"{e.__class__.__name__}: {e}"}, ensure_ascii=False))
            return 1

        if args.pretty:
            print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(json.dumps(data, ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
