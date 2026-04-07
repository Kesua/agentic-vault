from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
API_KEY_PATH = SECRETS_DIR / "fireflies_api_key.txt"

MEETINGS_DIR = REPO_ROOT / "20_Meetings"

FIREFLIES_GRAPHQL_ENDPOINT = os.environ.get(
    "FIREFLIES_GRAPHQL_ENDPOINT", "https://api.fireflies.ai/graphql"
).strip()


def _configure_stdio() -> None:
    """
    Avoid UnicodeEncodeError on Windows consoles (cp1252/mbcs) when printing.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_stdio()


def _default_user_agent() -> str:
    # Some edge/WAF setups block Python's default urllib User-Agent.
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )


def _parse_csv_env_set(var_name: str) -> set[str]:
    raw = (os.environ.get(var_name) or "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


@dataclass(frozen=True)
class FirefliesSummary:
    overview: str | None
    short_summary: str | None
    bullet_gist: str | None
    action_items: str | None
    keywords: list[str] | None


@dataclass(frozen=True)
class FirefliesSentence:
    index: int | None
    speaker_name: str | None
    text: str | None
    start_time: float | None


@dataclass(frozen=True)
class FirefliesTranscript:
    id: str
    title: str | None
    transcript_url: str | None
    meeting_link: str | None
    calendar_id: str | None
    cal_id: str | None
    date_string: str | None
    date_ms: float | None
    summary: FirefliesSummary | None
    sentences: list[FirefliesSentence] | None = None


@dataclass(frozen=True)
class MeetingNoteMeta:
    path: Path
    start_local: datetime
    title: str
    meet_link: str | None
    uid: str | None
    gcal_cal_id: str | None


def _load_api_key() -> str:
    env = (os.environ.get("FIREFLIES_API_KEY") or "").strip()
    if env:
        return env
    if API_KEY_PATH.exists():
        val = API_KEY_PATH.read_text(encoding="utf-8").strip()
        if val:
            return val
    raise RuntimeError(
        "Missing Fireflies API key. Set env var FIREFLIES_API_KEY or create: "
        f"{API_KEY_PATH.relative_to(REPO_ROOT)}"
    )


def _to_utc_iso(dt: datetime) -> str:
    return (
        dt.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _date_range_to_iso(from_day: date, to_day: date) -> tuple[str, str]:
    if to_day < from_day:
        raise ValueError("--to must be >= --from")

    local_tz = datetime.now().astimezone().tzinfo
    start_local = datetime.combine(from_day, time.min).replace(tzinfo=local_tz)
    end_local_excl = datetime.combine(to_day + timedelta(days=1), time.min).replace(
        tzinfo=local_tz
    )
    return _to_utc_iso(start_local), _to_utc_iso(end_local_excl)


def _fireflies_graphql(api_key: str, query: str, variables: dict) -> dict:
    body = json.dumps(
        {"query": query, "variables": variables}, ensure_ascii=False
    ).encode("utf-8")

    api_key = api_key.strip()
    auth = api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
    req = Request(
        FIREFLIES_GRAPHQL_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, identity",
            "User-Agent": _default_user_agent(),
            "Authorization": auth,
        },
    )
    try:
        with urlopen(req, timeout=60) as resp:
            raw = resp.read()
            enc = (resp.headers.get("Content-Encoding") or "").lower().strip()
            if enc == "gzip":
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            payload = raw.decode("utf-8", errors="replace")
    except HTTPError as e:
        detail = ""
        cf = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        try:
            cf_ray = e.headers.get("cf-ray") or ""
            server = e.headers.get("server") or ""
            if cf_ray or server:
                cf = f" (server={server or '?'}, cf-ray={cf_ray or '?'})"
        except Exception:
            pass

        msg = detail or str(e.reason) or "Forbidden"
        if e.code == 403 and "error code: 1010" in msg:
            msg = (
                f"{msg}\n\n"
                "This looks like Cloudflare/WAF bot protection. If it persists:\n"
                "- Try again from a different network (no VPN/corporate proxy).\n"
                "- Confirm your API key is correct.\n"
                "- Contact Fireflies support and share the cf-ray from the error."
            )
        raise RuntimeError(f"Fireflies API HTTP {e.code}{cf}: {msg}") from e
    except URLError as e:
        raise RuntimeError(f"Fireflies API request failed: {e}") from e

    data = json.loads(payload)
    if data.get("errors"):
        raise RuntimeError(f"Fireflies API errors: {data['errors']}")
    return data.get("data") or {}


_Q_TRANSCRIPTS = """
query Transcripts($fromDate: DateTime, $toDate: DateTime, $limit: Int, $skip: Int) {
  transcripts(fromDate: $fromDate, toDate: $toDate, limit: $limit, skip: $skip) {
    id
    title
    transcript_url
    meeting_link
    calendar_id
    cal_id
    dateString
    date
    summary {
      overview
      short_summary
      bullet_gist
      action_items
      keywords
    }
  }
}
""".strip()

_Q_TRANSCRIPT_DETAIL = """
query Transcript($transcriptId: String!) {
  transcript(id: $transcriptId) {
    id
    sentences {
      index
      speaker_name
      text
      start_time
    }
  }
}
""".strip()


def _parse_summary(raw: dict | None) -> FirefliesSummary | None:
    if not raw:
        return None
    kws = raw.get("keywords")
    if isinstance(kws, list):
        keywords = [str(x) for x in kws if str(x).strip()]
    else:
        keywords = None
    return FirefliesSummary(
        overview=(raw.get("overview") or None),
        short_summary=(raw.get("short_summary") or None),
        bullet_gist=(raw.get("bullet_gist") or None),
        action_items=(raw.get("action_items") or None),
        keywords=keywords,
    )


def fetch_transcript_sentences(api_key: str, transcript_id: str) -> list[FirefliesSentence]:
    data = _fireflies_graphql(api_key, _Q_TRANSCRIPT_DETAIL, {"transcriptId": transcript_id})
    raw_sentences = (data.get("transcript") or {}).get("sentences") or []
    if not isinstance(raw_sentences, list):
        return []
    result: list[FirefliesSentence] = []
    for s in raw_sentences:
        if not isinstance(s, dict):
            continue
        text = (s.get("text") or "").strip()
        if not text:
            continue
        result.append(FirefliesSentence(
            index=s.get("index"),
            speaker_name=(s.get("speaker_name") or "").strip() or None,
            text=text,
            start_time=s.get("start_time"),
        ))
    return result


def fetch_transcripts(from_day: date, to_day: date) -> list[FirefliesTranscript]:
    api_key = _load_api_key()
    from_iso, to_iso = _date_range_to_iso(from_day, to_day)

    out: list[FirefliesTranscript] = []
    limit = 50
    skip = 0
    while True:
        data = _fireflies_graphql(
            api_key,
            _Q_TRANSCRIPTS,
            {"fromDate": from_iso, "toDate": to_iso, "limit": limit, "skip": skip},
        )
        items = data.get("transcripts") or []
        if not isinstance(items, list):
            break

        batch: list[FirefliesTranscript] = []
        for t in items:
            if not isinstance(t, dict):
                continue
            batch.append(
                FirefliesTranscript(
                    id=str(t.get("id") or ""),
                    title=(t.get("title") or None),
                    transcript_url=(t.get("transcript_url") or None),
                    meeting_link=(t.get("meeting_link") or None),
                    calendar_id=(t.get("calendar_id") or None),
                    cal_id=(t.get("cal_id") or None),
                    date_string=(t.get("dateString") or None),
                    date_ms=(t.get("date") if t.get("date") is not None else None),
                    summary=_parse_summary(t.get("summary")),
                )
            )

        out.extend(batch)
        if len(items) < limit:
            break
        skip += limit

    return [t for t in out if t.id]


def _normalize_meeting_url_loose(url: str) -> str:
    url = url.strip()
    parts = urlsplit(url)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = (parts.path or "").rstrip("/")
    return f"{scheme}://{netloc}{path}"


def _parse_note_meet_link(text: str) -> str | None:
    m = re.search(r"(?m)^\- Meet:\s*(.+?)\s*$", text)
    if not m:
        return None
    val = m.group(1).strip()
    return val or None


def _parse_note_uid(text: str) -> str | None:
    m = re.search(r"(?m)^\- UID:\s*(.+?)\s*$", text)
    if not m:
        return None
    val = m.group(1).strip()
    return val or None


def _parse_note_gcal_cal_id(text: str) -> str | None:
    m = re.search(r"(?m)^\- GCal cal_id:\s*(.+?)\s*$", text)
    if not m:
        return None
    val = m.group(1).strip()
    return val or None


_MEETING_NOTE_RE = re.compile(
    r"^(?P<hhmm>\d{4})\s+-\s+(?P<title>.+)\.md$", re.IGNORECASE
)


def _iter_meeting_notes(from_day: date, to_day: date) -> list[MeetingNoteMeta]:
    if to_day < from_day:
        raise ValueError("meeting note range invalid")

    local_tz = datetime.now().astimezone().tzinfo
    # local_tz = datetime(2026, 2, 1, 1, 0, 0).astimezone().tzinfo

    out: list[MeetingNoteMeta] = []
    cur = from_day
    while cur <= to_day:
        day_dir = (
            MEETINGS_DIR / cur.strftime("%Y") / cur.strftime("%m") / cur.strftime("%d")
        )
        if day_dir.exists():
            for p in sorted(day_dir.glob("*.md")):
                m = _MEETING_NOTE_RE.match(p.name)
                if not m:
                    continue
                hhmm = m.group("hhmm")
                title = m.group("title").strip()
                hour = int(hhmm[:2])
                minute = int(hhmm[2:])
                start_local = datetime.combine(
                    cur, time(hour=hour, minute=minute)
                ).replace(tzinfo=local_tz)
                text = p.read_text(encoding="utf-8", errors="replace")
                out.append(
                    MeetingNoteMeta(
                        path=p,
                        start_local=start_local,
                        title=title,
                        meet_link=_parse_note_meet_link(text),
                        uid=_parse_note_uid(text),
                        gcal_cal_id=_parse_note_gcal_cal_id(text),
                    )
                )
        cur += timedelta(days=1)
    return out


def _gcal_cal_id_match_score(
    note_gcal_cal_id: str, transcript: FirefliesTranscript
) -> int:
    if not note_gcal_cal_id:
        return 0
    tcal = (transcript.cal_id or "").strip()
    if not tcal:
        return 0
    if note_gcal_cal_id == tcal:
        return 110
    return 0


def _uid_match_score(note_uid: str, transcript: FirefliesTranscript) -> int:
    tid = (transcript.calendar_id or "").strip()
    tcal = (transcript.cal_id or "").strip()
    if not note_uid:
        return 0
    if note_uid == tid or note_uid == tcal:
        return 100

    # If the note UID is "iCalUID__originalStart", try prefix match on iCalUID.
    base = note_uid.split("__", 1)[0]
    if base and (base == tid or base == tcal):
        return 90

    for candidate in (tid, tcal):
        if not candidate:
            continue
        if note_uid.startswith(candidate) or candidate.startswith(note_uid):
            return 70
        if base and (base.startswith(candidate) or candidate.startswith(base)):
            return 60
    return 0


def _parse_transcript_datetime_local(t: FirefliesTranscript) -> datetime | None:
    if t.date_string:
        try:
            # Example: 2024-04-22T20:14:04.454Z
            ds = t.date_string.strip().replace("Z", "+00:00")
            return datetime.fromisoformat(ds).astimezone()
        except Exception:
            pass
    if t.date_ms is not None:
        try:
            ms = float(t.date_ms)
            seconds = ms / 1000.0 if ms > 1e12 else ms
            return datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone()
        except Exception:
            pass
    return None


def _choose_same_link_note_by_time(
    notes: list[MeetingNoteMeta], transcript: FirefliesTranscript
) -> MeetingNoteMeta | None:
    transcript_dt = _parse_transcript_datetime_local(transcript)
    if not transcript_dt:
        return None

    # Extension/manual captures may lack calendar identifiers. Fall back to time
    # only when one same-link note is clearly closest to the transcript start.
    max_distance_seconds = 2 * 60 * 60
    scored: list[tuple[float, MeetingNoteMeta]] = []
    for note in notes:
        dist = abs((note.start_local - transcript_dt).total_seconds())
        if dist <= max_distance_seconds:
            scored.append((dist, note))

    if len(scored) != 1:
        return None
    return scored[0][1]


def _choose_meeting_note(
    notes: list[MeetingNoteMeta], transcript: FirefliesTranscript
) -> MeetingNoteMeta | None:
    if not notes:
        return None

    t_meet = (transcript.meeting_link or "").strip()
    if t_meet:
        t_norm = _normalize_meeting_url_loose(t_meet)
        by_meet = [
            n
            for n in notes
            if n.meet_link and _normalize_meeting_url_loose(n.meet_link) == t_norm
        ]
        if len(by_meet) == 1:
            return by_meet[0]
        if len(by_meet) > 1:
            # Same link used for multiple notes (often recurring meetings).
            # Avoid guessing by time; require a strong identifier match to disambiguate.
            if transcript.cal_id:
                by_meet_cal_scored = [
                    (n, _gcal_cal_id_match_score(n.gcal_cal_id or "", transcript))
                    for n in by_meet
                    if n.gcal_cal_id
                ]
                by_meet_cal_scored = [x for x in by_meet_cal_scored if x[1] > 0]
                if by_meet_cal_scored:
                    by_meet_cal_scored.sort(key=lambda x: x[1], reverse=True)
                    if (
                        len(by_meet_cal_scored) == 1
                        or by_meet_cal_scored[0][1] > by_meet_cal_scored[1][1]
                    ):
                        return by_meet_cal_scored[0][0]

            by_meet_uid_scored = [
                (n, _uid_match_score(n.uid or "", transcript)) for n in by_meet if n.uid
            ]
            by_meet_uid_scored = [x for x in by_meet_uid_scored if x[1] > 0]
            if by_meet_uid_scored:
                by_meet_uid_scored.sort(key=lambda x: x[1], reverse=True)
                if (
                    len(by_meet_uid_scored) == 1
                    or by_meet_uid_scored[0][1] > by_meet_uid_scored[1][1]
                ):
                    return by_meet_uid_scored[0][0]

            by_meet_time = _choose_same_link_note_by_time(by_meet, transcript)
            if by_meet_time:
                return by_meet_time
            return None

    cal_scored = [
        (n, _gcal_cal_id_match_score(n.gcal_cal_id or "", transcript))
        for n in notes
        if n.gcal_cal_id
    ]
    cal_scored = [x for x in cal_scored if x[1] > 0]
    if cal_scored:
        cal_scored.sort(key=lambda x: x[1], reverse=True)
        if len(cal_scored) == 1 or cal_scored[0][1] > cal_scored[1][1]:
            return cal_scored[0][0]

    uid_scored = [
        (n, _uid_match_score(n.uid or "", transcript)) for n in notes if n.uid
    ]
    uid_scored = [x for x in uid_scored if x[1] > 0]
    if uid_scored:
        uid_scored.sort(key=lambda x: x[1], reverse=True)
        if len(uid_scored) == 1 or uid_scored[0][1] > uid_scored[1][1]:
            return uid_scored[0][0]

    return None


def _transcript_quality_score(t: FirefliesTranscript) -> int:
    score = 0
    if t.transcript_url:
        score += 5
    if t.summary:
        score += 2
        for val in (
            t.summary.short_summary,
            t.summary.overview,
            t.summary.bullet_gist,
            t.summary.action_items,
        ):
            if val and str(val).strip():
                score += 2
        if t.summary.keywords:
            score += min(3, len([k for k in t.summary.keywords if k.strip()]))
    return score


def _preferred_owner_score(t: FirefliesTranscript) -> int:
    # If multiple Fireflies bots joined the same meeting, prefer "my" recording.
    # Configure via env vars (comma-separated):
    # - FIREFLIES_PREFERRED_CALENDAR_IDS
    # - FIREFLIES_PREFERRED_CAL_IDS
    pref_calendar_ids = _parse_csv_env_set("FIREFLIES_PREFERRED_CALENDAR_IDS")
    pref_cal_ids = _parse_csv_env_set("FIREFLIES_PREFERRED_CAL_IDS")

    score = 0
    if t.calendar_id and t.calendar_id in pref_calendar_ids:
        score += 100
    if t.cal_id and t.cal_id in pref_cal_ids:
        score += 90
    return score


def _choose_best_transcript_for_note(
    note: MeetingNoteMeta, transcripts: list[FirefliesTranscript]
) -> FirefliesTranscript:
    if not transcripts:
        raise ValueError("no transcripts to choose from")

    def key(t: FirefliesTranscript) -> tuple[int, int, int, int, int, float, str]:
        uid_score = _uid_match_score(note.uid or "", t) if note.uid else 0
        meet_score = 0
        if note.meet_link and t.meeting_link:
            try:
                if _normalize_meeting_url_loose(
                    note.meet_link
                ) == _normalize_meeting_url_loose(t.meeting_link):
                    meet_score = 10
            except Exception:
                pass
        cal_score = (
            _gcal_cal_id_match_score(note.gcal_cal_id or "", t)
            if note.gcal_cal_id
            else 0
        )
        dt = _parse_transcript_datetime_local(t)
        dist = abs((note.start_local - dt).total_seconds()) if dt else float("inf")
        # Prefer: "my" recording > cal_id match > UID match > meet link match > richer content > closer time > id.
        return (
            _preferred_owner_score(t),
            cal_score,
            uid_score,
            meet_score,
            _transcript_quality_score(t),
            -dist,
            t.id,
        )

    return sorted(transcripts, key=key, reverse=True)[0]


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        s = re.sub(r"^\-+\s*", "", s)
        s = re.sub(r"^\d+\.\s*", "", s)
        lines.append(s)
    return lines


def _render_fireflies_block(t: FirefliesTranscript) -> str:
    lines: list[str] = []
    lines.append("## Fireflies (auto)\n")

    if t.transcript_url:
        lines.append(f"- Transcript: {t.transcript_url}\n")
    lines.append(f"- Fireflies ID: {t.id}\n")
    if t.meeting_link:
        lines.append(f"- Meeting link: {t.meeting_link}\n")
    if t.calendar_id:
        lines.append(f"- Calendar ID: {t.calendar_id}\n")
    if t.cal_id:
        lines.append(f"- cal_id: {t.cal_id}\n")

    if t.summary:
        summary_text = (t.summary.short_summary or t.summary.overview or "").strip()
        if summary_text:
            lines.append(f"- Summary: {summary_text}\n")

        actions = _clean_lines(t.summary.action_items or "")
        if actions:
            lines.append("- Action items:\n")
            for a in actions[:30]:
                lines.append(f"  - {a}\n")

        gist = _clean_lines(t.summary.bullet_gist or "")
        if gist and not actions:
            lines.append("- Key points:\n")
            for g in gist[:30]:
                lines.append(f"  - {g}\n")

        if t.summary.keywords:
            kw = ", ".join([k.strip() for k in t.summary.keywords if k.strip()])
            if kw:
                lines.append(f"- Keywords: {kw}\n")

    synced = datetime.now().astimezone().isoformat(timespec="seconds")
    lines.append(f"- Synced: {synced}\n")
    return "".join(lines).rstrip() + "\n"


def _upsert_fireflies_block(note_text: str, new_block: str) -> str:
    # Replace if already present.
    pattern = re.compile(r"(?ms)^##\s+Fireflies\s+\(auto\)\s*\n.*?(?=^##\s|\Z)")
    if pattern.search(note_text):
        out = pattern.sub(new_block.rstrip() + "\n\n", note_text, count=1)
        return out.rstrip() + "\n"

    # Insert before Meeting Notes (preferred; preserved area).
    m = re.search(r"(?m)^##\s+Meeting\s+Notes\s*$", note_text)
    if m:
        insert_at = m.start()
        before = note_text[:insert_at].rstrip() + "\n\n"
        after = note_text[insert_at:].lstrip()
        return (before + new_block.rstrip() + "\n\n" + after).rstrip() + "\n"

    # Otherwise append.
    return (note_text.rstrip() + "\n\n" + new_block.rstrip() + "\n").rstrip() + "\n"


def _format_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return "??:??:??"
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _render_transcript_block(sentences: list[FirefliesSentence]) -> str:
    lines: list[str] = ["## Fireflies Transcript (auto)\n\n"]
    for s in sentences:
        ts = _format_timestamp(s.start_time)
        speaker = s.speaker_name or "Unknown"
        lines.append(f"[{ts}] {speaker}: {s.text}\n")
    synced = datetime.now().astimezone().isoformat(timespec="seconds")
    lines.append(f"\n- Synced: {synced}\n")
    return "".join(lines).rstrip() + "\n"


def _upsert_transcript_block(note_text: str, new_block: str) -> str:
    # Replace if already present.
    pattern = re.compile(r"(?ms)^##\s+Fireflies\s+Transcript\s+\(auto\)\s*\n.*?(?=^##\s|\Z)")
    if pattern.search(note_text):
        return pattern.sub(new_block.rstrip() + "\n", note_text, count=1).rstrip() + "\n"

    # Always append at the end.
    return (note_text.rstrip() + "\n\n" + new_block.rstrip() + "\n").rstrip() + "\n"


def sync_transcripts_to_notes(from_day: date, to_day: date, dry_run: bool) -> None:
    api_key = _load_api_key()
    transcripts = fetch_transcripts(from_day, to_day)

    # Scan meeting notes a bit wider than transcript range (transcripts are created after meetings).
    notes_from = from_day - timedelta(days=14)
    notes_to = to_day
    notes = _iter_meeting_notes(notes_from, notes_to)

    unmatched: list[FirefliesTranscript] = []
    matched: dict[Path, tuple[MeetingNoteMeta, list[FirefliesTranscript]]] = {}

    for t in transcripts:
        note = _choose_meeting_note(notes, t)
        if not note:
            unmatched.append(t)
            continue

        slot = matched.get(note.path)
        if not slot:
            matched[note.path] = (note, [t])
        else:
            slot[1].append(t)

    updated: list[Path] = []
    multi_hits: list[tuple[Path, list[FirefliesTranscript]]] = []

    for note_path, (note, ts) in matched.items():
        if len(ts) > 1:
            multi_hits.append((note_path, ts))

        chosen = _choose_best_transcript_for_note(note, ts)
        text = note.path.read_text(encoding="utf-8", errors="replace")
        new_block = _render_fireflies_block(chosen)
        out = _upsert_fireflies_block(text, new_block)

        sentences: list[FirefliesSentence] = []
        try:
            sentences = fetch_transcript_sentences(api_key, chosen.id)
        except Exception as exc:
            print(f"  ! Could not fetch sentences for {chosen.id}: {exc}", file=sys.stderr)

        if sentences:
            transcript_block = _render_transcript_block(sentences)
            out = _upsert_transcript_block(out, transcript_block)

        if out == text:
            continue

        if not dry_run:
            note.path.write_text(out, encoding="utf-8")
        updated.append(note.path)

    print(
        f"Transcript window (created): {from_day.isoformat()} .. {to_day.isoformat()}"
    )
    print(f"Transcripts found: {len(transcripts)}")
    print(
        f"Meeting notes scanned: {len(notes)} ({notes_from.isoformat()} .. {notes_to.isoformat()})"
    )
    print(f"Updated notes: {len(updated)}")
    for p in updated[:25]:
        print(f"  ~ {p.relative_to(REPO_ROOT)}")
    if len(updated) > 25:
        print("  ...")

    print(f"Notes with multiple transcripts: {len(multi_hits)}")
    for p, ts in multi_hits[:25]:
        print(f"  ? {p.relative_to(REPO_ROOT)} ({len(ts)} transcripts)")
    if len(multi_hits) > 25:
        print("  ...")

    print(f"Unmatched transcripts: {len(unmatched)}")
    for t in unmatched[:25]:
        label = t.title or t.id
        print(f"  ! {label} ({t.transcript_url or 'no url'})")
    if len(unmatched) > 25:
        print("  ...")


def _days_back_value(raw_value: int | None, default_days: int) -> int:
    if raw_value is None:
        return default_days
    if raw_value < 1:
        raise ValueError("--days-back must be >= 1")
    return raw_value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fireflies_sync")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser(
        "sync", help="Fetch Fireflies transcripts and attach/link them to meeting notes"
    )
    p_sync.add_argument(
        "--from", dest="from_day", help="YYYY-MM-DD (default: today-30)", default=None
    )
    p_sync.add_argument(
        "--to", dest="to_day", help="YYYY-MM-DD (default: today)", default=None
    )
    p_sync.add_argument(
        "--days-back",
        type=int,
        default=None,
        help="Sync transcripts created in the last N days",
    )
    p_sync.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "sync":
        today = datetime.now().astimezone().date()
        if args.days_back is not None and (args.from_day or args.to_day):
            raise ValueError("--days-back cannot be combined with --from or --to")
        if args.days_back is not None:
            days_back = _days_back_value(args.days_back, default_days=30)
            from_day = today - timedelta(days=days_back)
            to_day = today
        else:
            from_day = (
                date.fromisoformat(args.from_day)
                if args.from_day
                else (today - timedelta(days=30))
            )
            to_day = date.fromisoformat(args.to_day) if args.to_day else today
        sync_transcripts_to_notes(
            from_day=from_day, to_day=to_day, dry_run=bool(args.dry_run)
        )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
