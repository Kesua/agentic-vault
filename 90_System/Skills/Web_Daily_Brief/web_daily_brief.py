from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
    from zoneinfo import ZoneInfoNotFoundError
except ImportError:  # pragma: no cover (Python < 3.9)
    ZoneInfo = None  # type: ignore[assignment]
    ZoneInfoNotFoundError = Exception  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TZ = "Europe/Prague"
SOURCE_LINKS = (
    "[Stooq market snapshot](https://stooq.com/), "
    "[Open-Meteo](https://open-meteo.com/), "
    "[Google News RSS CZ](https://news.google.com/rss?hl=cs&gl=CZ&ceid=CZ:cs), "
    "[Google News RSS World](https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en), "
    "[Wikipedia featured news (cs)](https://cs.wikipedia.org/wiki/Wikipedie:Aktuality), "
    "[Wikipedia featured news (en)](https://en.wikipedia.org/wiki/Portal:Current_events)."
)
AI_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "machine learning",
    "llm",
    "chatgpt",
    "openai",
    "anthropic",
    "gemini",
    "claude",
    "copilot",
    "nvidia",
)


@dataclass(frozen=True)
class ApplyResult:
    path: Path
    existed: bool
    changed: bool


def _daily_brief_path(d: date) -> Path:
    return REPO_ROOT / "10_DailyBriefs" / f"{d:%Y}" / f"{d:%m}" / f"{d:%Y-%m-%d}_Daily_Brief.md"


def _today_in_timezone(tz_name: str) -> date:
    if ZoneInfo is None:
        return datetime.now().date()
    try:
        return datetime.now(ZoneInfo(tz_name)).date()
    except ZoneInfoNotFoundError:
        return datetime.now().date()


def _normalize_daily_news_block(text: str) -> str:
    text = text.replace("\r\n", "\n").strip("\n")
    if not text.lstrip().startswith("# Daily News"):
        text = "# Daily News\n" + text.lstrip("\n")
    return text.strip("\n") + "\n\n"


def _replace_or_insert_daily_news(existing: str, daily_news_block: str) -> tuple[str, bool]:
    existing_nl = existing.replace("\r\n", "\n")
    lines = existing_nl.splitlines(keepends=True)

    start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "# Daily News":
            start_idx = i
            break

    block_lines = _normalize_daily_news_block(daily_news_block).splitlines(keepends=True)

    if start_idx is None:
        prefix = "".join(block_lines)
        if existing_nl.startswith("\n"):
            existing_nl = existing_nl.lstrip("\n")
        return prefix + existing_nl, True

    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        if lines[j].startswith("# "):
            end_idx = j
            break

    new_lines = lines[:start_idx] + block_lines + lines[end_idx:]
    return "".join(new_lines), True


def apply_daily_news(*, day: date, daily_news_markdown: str, dry_run: bool) -> ApplyResult:
    path = _daily_brief_path(day)
    existed = path.exists()
    before = path.read_text(encoding="utf-8") if existed else ""
    after, changed = _replace_or_insert_daily_news(before, daily_news_markdown)

    if not existed and "# Tasks" not in after:
        if not after.endswith("\n\n"):
            after = after.rstrip("\n") + "\n\n"
        after += "# Tasks\n\n"
        changed = True

    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(after, encoding="utf-8")

    return ApplyResult(path=path, existed=existed, changed=changed)


def _read_content_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _get_source_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources = data.get("sources", [])
    out: dict[str, dict[str, Any]] = {}
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict) and isinstance(source.get("name"), str):
                out[str(source["name"])] = source
    return out


def _source_payload(source_map: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    source = source_map.get(name, {})
    payload = source.get("payload", {})
    return payload if isinstance(payload, dict) else {}


def _source_meta(source_map: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    source = source_map.get(name, {})
    meta = source.get("meta", {})
    return meta if isinstance(meta, dict) else {}


def _format_value(value: Any, *, decimals: int = 1) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def _news_bullet(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "Untitled").strip()
    link = str(item.get("link") or "").strip()
    return f"- **{title}**. ([source]({link}))" if link else f"- **{title}**."


def _featured_bullet(item: dict[str, Any]) -> str:
    story = " ".join(str(item.get("story") or "").split())
    links = item.get("links", [])
    href = ""
    if isinstance(links, list) and links:
        first = links[0]
        if isinstance(first, dict):
            href = str(first.get("content_urls", {}).get("desktop", {}).get("page") or "").strip()
            if not href:
                href = str(first.get("content_urls", {}).get("mobile", {}).get("page") or "").strip()
    return f"- {story} ([source]({href}))" if href else f"- {story}"


def _trend_bullet(item: Any) -> str:
    if isinstance(item, str):
        return f"- {item}"
    if not isinstance(item, dict):
        return f"- {item}"
    title = str(item.get("title") or "").strip()
    traffic = str(item.get("approx_traffic") or "").strip()
    link = str(item.get("link") or "").strip()
    suffix = f" ({traffic})" if traffic else ""
    return f"- {title}{suffix} ([source]({link}))" if link else f"- {title}{suffix}"


def _append_fallback(lines: list[str], label: str, fallback_reason: str) -> None:
    lines.append(f"- {label} (`{fallback_reason}`).")
    lines.append("")


def _render_weather(lines: list[str], source_map: dict[str, dict[str, Any]]) -> None:
    payload = _source_payload(source_map, "open_meteo_ecmwf_weather")
    locations = payload.get("locations", [])

    lines.append("## Weather (ECMWF IFS)")
    lines.append("")

    if not isinstance(locations, list) or not locations:
        lines.append("- Weather data unavailable in deterministic source payload.")
        lines.append("")
        return

    for location in locations:
        if not isinstance(location, dict):
            continue
        lines.append(f"### {location.get('name', 'Unknown')}")
        lines.append("| Time | Temp (°C) | Precip prob (%) |")
        lines.append("|---:|---:|---:|")
        rows = location.get("rows", [])
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"| {row.get('time', '')} | "
                    f"{_format_value(row.get('temperature_2m'), decimals=1)} | "
                    f"{_format_value(row.get('precipitation_probability'), decimals=0)} |"
                )
        lines.append("Source: [Open-Meteo (ECMWF IFS)](https://open-meteo.com/)")
        lines.append("")


def _render_news_section(
    lines: list[str],
    title: str,
    source_map: dict[str, dict[str, Any]],
    source_name: str,
    date_label: str,
) -> None:
    payload = _source_payload(source_map, source_name)
    items = payload.get("items", [])
    lines.append(f"## {title} - {date_label}")
    if isinstance(items, list) and items:
        for item in items[:3]:
            if isinstance(item, dict):
                lines.append(_news_bullet(item))
    else:
        lines.append("- No deterministic items available in source payload.")
    lines.append("")


def _render_featured_section(
    lines: list[str],
    title: str,
    source_map: dict[str, dict[str, Any]],
    source_name: str,
    date_label: str,
) -> None:
    payload = _source_payload(source_map, source_name)
    items = payload.get("news", [])
    lines.append(f"## {title} - {date_label}")
    if isinstance(items, list) and items:
        for item in items[:3]:
            if isinstance(item, dict):
                lines.append(_featured_bullet(item))
    else:
        lines.append("- No deterministic items available in source payload.")
    lines.append("")


def _render_ai_section(lines: list[str], source_map: dict[str, dict[str, Any]], date_label: str) -> None:
    payload_cz = _source_payload(source_map, "google_news_rss_cz")
    payload_world = _source_payload(source_map, "google_news_rss_world_proxy_us")
    items: list[dict[str, Any]] = []
    for payload in (payload_cz, payload_world):
        source_items = payload.get("items", [])
        if isinstance(source_items, list):
            for item in source_items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").lower()
                if any(keyword in title for keyword in AI_KEYWORDS):
                    items.append(item)
    lines.append(f"## Yesterday (AI) - {date_label}")
    if items:
        seen: set[str] = set()
        count = 0
        for item in items:
            title = str(item.get("title") or "")
            if title in seen:
                continue
            seen.add(title)
            lines.append(_news_bullet(item))
            count += 1
            if count >= 3:
                break
    else:
        lines.append("- No AI-specific deterministic items available in source payload.")
    lines.append("")


def _render_trends_section(
    lines: list[str],
    title: str,
    source_map: dict[str, dict[str, Any]],
    primary_name: str,
    fallback_name: str,
    date_label: str,
) -> None:
    lines.append(f"## {title} - {date_label}")

    primary = _source_payload(source_map, primary_name)
    items = primary.get("items", [])
    if isinstance(items, list) and items:
        for item in items[:5]:
            lines.append(_trend_bullet(item))
        lines.append("")
        return

    fallback = _source_payload(source_map, fallback_name)
    fallback_items = fallback.get("items", [])
    if isinstance(fallback_items, list) and fallback_items:
        for item in fallback_items[:5]:
            lines.append(_trend_bullet(item))
        lines.append("")
        return

    error = str(primary.get("error") or fallback.get("error") or "ok: false")
    _append_fallback(lines, "Trends data unavailable in deterministic source payload", error)


def _render_markets(lines: list[str], source_map: dict[str, dict[str, Any]]) -> None:
    payload = _source_payload(source_map, "stooq_market_snapshot")
    markets = payload.get("markets", [])

    lines.append("## Markets (last close)")
    lines.append("| Index | Close | % chg | As of |")
    lines.append("|---|---:|---:|---|")

    if isinstance(markets, list) and markets:
        for market in markets:
            if not isinstance(market, dict):
                continue
            pct = market.get("pct_change_vs_previous_close")
            pct_str = f"{float(pct):.2f}%" if isinstance(pct, (int, float)) else ""
            close = market.get("close")
            close_str = f"{float(close):.2f}" if isinstance(close, (int, float)) else ""
            lines.append(
                f"| {market.get('name', '')} | {close_str} | {pct_str} | {market.get('as_of_date', '')} |"
            )
    else:
        lines.append("| Markets unavailable |  |  |  |")

    lines.append(f"Sources: {SOURCE_LINKS}")
    lines.append("")


def render_daily_news(data: dict[str, Any]) -> str:
    source_map = _get_source_map(data)
    updated_at = str(data.get("fetched_at") or "")
    today = str(data.get("today") or "")
    yesterday = str(data.get("yesterday") or "")

    lines: list[str] = [
        "# Daily News",
        f"- Updated: {updated_at}",
        "- Coverage: weather (ECMWF), events (CZ+World), yesterday (CZ+World+AI), trends (CZ+World), markets",
        "",
    ]

    _render_weather(lines, source_map)
    _render_news_section(lines, "Anticipated today (CZ)", source_map, "google_news_rss_cz", today)
    _render_news_section(lines, "Anticipated today (World)", source_map, "google_news_rss_world_proxy_us", today)
    _render_featured_section(lines, "Yesterday (CZ)", source_map, "wikipedia_featured_news_cs", yesterday)
    _render_featured_section(lines, "Yesterday (World)", source_map, "wikipedia_featured_news_en", yesterday)
    _render_ai_section(lines, source_map, yesterday)
    _render_trends_section(lines, "Trending yesterday (Czechia)", source_map, "google_trends_daily_rss_cz", "pytrends_top5_yesterday_cz", yesterday)
    _render_trends_section(
        lines,
        "Trending yesterday (World)",
        source_map,
        "google_trends_daily_rss_world_proxy_us",
        "pytrends_top5_yesterday_world_proxy_us",
        yesterday,
    )
    _render_markets(lines, source_map)
    return "\n".join(lines).rstrip() + "\n"


def _write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="web_daily_brief")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_render = sub.add_parser("render", help="Render `# Daily News` markdown from fetched JSON.")
    p_render.add_argument("--sources-file", required=True, help="Path to JSON produced by `web_sources.py fetch`.")
    p_render.add_argument("--output-file", help="Optional output path for rendered markdown.")

    p_apply = sub.add_parser("apply", help="Insert/replace `# Daily News` in today’s Daily Brief")
    p_apply.add_argument("--date", dest="date_str", help="Target date (YYYY-MM-DD). Default: today in Europe/Prague.")
    p_apply.add_argument("--tz", default=DEFAULT_TZ, help=f"Timezone for default date (default: {DEFAULT_TZ}).")
    p_apply.add_argument("--content-file", required=True, help="Path to a markdown file containing the Daily News block.")
    p_apply.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "render":
        data = json.loads(Path(args.sources_file).read_text(encoding="utf-8"))
        rendered = render_daily_news(data if isinstance(data, dict) else {})
        if args.output_file:
            _write_output(Path(args.output_file), rendered)
            print(f"rendered: {Path(args.output_file)}")
        else:
            print(rendered, end="")
        return 0

    if args.cmd == "apply":
        if args.date_str:
            target_day = date.fromisoformat(args.date_str)
        else:
            target_day = _today_in_timezone(args.tz)

        daily_news = _read_content_file(Path(args.content_file))
        result = apply_daily_news(day=target_day, daily_news_markdown=daily_news, dry_run=bool(args.dry_run))

        action = "updated" if result.existed else "created"
        if args.dry_run:
            print(f"[dry-run] Would write: {result.path}")
        else:
            print(f"{action}: {result.path}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
