from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
FIREFLIES_SKILL_DIR = REPO_ROOT / "90_System" / "Skills" / "fireflies_sync"
if str(FIREFLIES_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(FIREFLIES_SKILL_DIR))

import fireflies_sync as ff_base


def _normalize_transcript(t: ff_base.FirefliesTranscript) -> dict[str, Any]:
    summary = t.summary
    return {
        "id": t.id,
        "title": t.title,
        "transcript_url": t.transcript_url,
        "meeting_link": t.meeting_link,
        "calendar_id": t.calendar_id,
        "cal_id": t.cal_id,
        "date": t.date_string,
        "summary": {
            "short_summary": summary.short_summary if summary else None,
            "overview": summary.overview if summary else None,
            "action_items": summary.action_items if summary else None,
            "bullet_gist": summary.bullet_gist if summary else None,
            "keywords": summary.keywords if summary else None,
        },
        "transcript_text_available": False,
    }


def _fetch_window(from_day: str | None, to_day: str | None, default_days: int) -> tuple[date, date, list[ff_base.FirefliesTranscript]]:
    today = datetime.now().astimezone().date()
    start = date.fromisoformat(from_day) if from_day else (today - timedelta(days=default_days))
    end = date.fromisoformat(to_day) if to_day else today
    transcripts = ff_base.fetch_transcripts(start, end)
    return start, end, transcripts


def _matches_query(t: ff_base.FirefliesTranscript, query: str) -> bool:
    q = query.casefold()
    haystacks = [
        t.id,
        t.title or "",
        t.transcript_url or "",
        t.meeting_link or "",
        t.calendar_id or "",
        t.cal_id or "",
        t.date_string or "",
    ]
    if t.summary:
        haystacks.extend(
            [
                t.summary.short_summary or "",
                t.summary.overview or "",
                t.summary.action_items or "",
                t.summary.bullet_gist or "",
                " ".join(t.summary.keywords or []),
            ]
        )
    return any(q in text.casefold() for text in haystacks if text)


def command_search(args: argparse.Namespace) -> None:
    from_day, to_day, transcripts = _fetch_window(args.from_day, args.to_day, default_days=args.days)
    filtered = transcripts
    if args.query:
        filtered = [t for t in filtered if _matches_query(t, args.query)]
    if args.has_summary:
        filtered = [t for t in filtered if t.summary]
    payload = {
        "window": {"from": from_day.isoformat(), "to": to_day.isoformat()},
        "count": len(filtered),
        "transcripts": [_normalize_transcript(t) for t in filtered[: args.limit]],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def command_show(args: argparse.Namespace) -> None:
    from_day, to_day, transcripts = _fetch_window(args.from_day, args.to_day, default_days=args.days)
    wanted = next((t for t in transcripts if t.id == args.transcript_id), None)
    if not wanted:
        raise RuntimeError(
            f"Transcript '{args.transcript_id}' not found in window {from_day.isoformat()} .. {to_day.isoformat()}"
        )
    payload = {
        "window": {"from": from_day.isoformat(), "to": to_day.isoformat()},
        "transcript": _normalize_transcript(wanted),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="adhoc_fireflies",
        description="Ad-hoc Fireflies assistant: search transcripts and retrieve summaries/details.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search Fireflies transcripts in a date window")
    p_search.add_argument("--from", dest="from_day")
    p_search.add_argument("--to", dest="to_day")
    p_search.add_argument("--days", type=int, default=30)
    p_search.add_argument("--query")
    p_search.add_argument("--has-summary", action="store_true")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.set_defaults(func=command_search)

    p_show = sub.add_parser("show", help="Show one transcript by ID within a date window")
    p_show.add_argument("--transcript-id", required=True)
    p_show.add_argument("--from", dest="from_day")
    p_show.add_argument("--to", dest="to_day")
    p_show.add_argument("--days", type=int, default=30)
    p_show.set_defaults(func=command_show)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
