from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
]

REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
EXPORT_ROOT = REPO_ROOT / "70_Exports"

OAUTH_CLIENT_PRIVATE_PATH = SECRETS_DIR / "gdrive_oauth_client_private.json"
OAUTH_CLIENT_PERSONAL_PATH = SECRETS_DIR / "gdrive_oauth_client_personal.json"
OAUTH_CLIENT_SHARED_PATH = SECRETS_DIR / "gdrive_oauth_client.json"
TOKEN_PRIVATE_PATH = SECRETS_DIR / "gdrive_token_private.json"
TOKEN_PERSONAL_PATH = SECRETS_DIR / "gdrive_token_personal.json"

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE_MIME = "application/vnd.google-apps.presentation"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"

MIME_TYPE_FILTERS = {
    "any": None,
    "folder": GOOGLE_FOLDER_MIME,
    "document": GOOGLE_DOC_MIME,
    "spreadsheet": GOOGLE_SHEET_MIME,
    "presentation": GOOGLE_SLIDE_MIME,
    "pdf": "application/pdf",
}

DEFAULT_EXPORT_MIME = {
    GOOGLE_DOC_MIME: "text/plain",
    GOOGLE_SHEET_MIME: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    GOOGLE_SLIDE_MIME: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_stdio()


def _json_dump(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _get_token_path(account: str) -> Path:
    if account == "private":
        return TOKEN_PRIVATE_PATH
    if account == "personal":
        return TOKEN_PERSONAL_PATH
    raise ValueError(f"Unknown account: {account}")


def _get_client_path(account: str) -> Path:
    if account == "private":
        preferred = OAUTH_CLIENT_PRIVATE_PATH
    elif account == "personal":
        preferred = OAUTH_CLIENT_PERSONAL_PATH
    else:
        raise ValueError(f"Unknown account: {account}")
    return preferred if preferred.exists() else OAUTH_CLIENT_SHARED_PATH


def _load_credentials(account: str) -> Credentials:
    token_path = _get_token_path(account)
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    if not creds or not creds.valid:
        raise RuntimeError(
            f"Missing/invalid token for account '{account}'. "
            f"Run: .\\.venv\\Scripts\\python.exe 90_System\\Skills\\google_drive_assistant\\google_drive_assistant.py auth --account {account}"
        )

    return creds


def auth_account(account: str) -> None:
    client_path = _get_client_path(account)
    if not client_path.exists():
        raise RuntimeError(
            "Missing OAuth client file. Create one of:\n"
            f"- {OAUTH_CLIENT_PRIVATE_PATH}\n"
            f"- {OAUTH_CLIENT_PERSONAL_PATH}\n"
            f"- {OAUTH_CLIENT_SHARED_PATH}\n"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = _get_token_path(account)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved token: {token_path}")


def _service(api: str, version: str, account: str):
    return build(api, version, credentials=_load_credentials(account), cache_discovery=False)


def _drive_service(account: str):
    return _service("drive", "v3", account)


def _docs_service(account: str):
    return _service("docs", "v1", account)


def _sheets_service(account: str):
    return _service("sheets", "v4", account)


def _slides_service(account: str):
    return _service("slides", "v1", account)


def _safe_execute(request: Any, *, label: str) -> dict[str, Any]:
    try:
        return request.execute()
    except HttpError as exc:
        detail = exc.reason or str(exc)
        raise RuntimeError(f"{label} failed: {detail}") from exc


def _iter_accounts(account: str) -> list[str]:
    if account == "both":
        return ["private", "personal"]
    return [account]


def _escape_query_term(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _search_tokens(query: str) -> list[str]:
    return [token.strip() for token in re.split(r"\s+", query.strip()) if token.strip()]


def _build_search_query(query: str, file_type: str, folder_id: str | None) -> str:
    parts = ["trashed = false"]
    mime_type = MIME_TYPE_FILTERS[file_type]
    if mime_type:
        parts.append(f"mimeType = '{mime_type}'")
    if folder_id:
        parts.append(f"'{folder_id}' in parents")
    for token in _search_tokens(query):
        safe = _escape_query_term(token)
        parts.append(f"(name contains '{safe}' or fullText contains '{safe}')")
    return " and ".join(parts)


def _extract_file_id(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise RuntimeError("Missing file identifier")
    for pattern in (
        r"/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
        r"/folders/([a-zA-Z0-9_-]+)",
    ):
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", value):
        return value
    raise RuntimeError(f"Unable to extract a Google file id from '{raw}'")


def _serialize_drive_file(account: str, payload: dict[str, Any]) -> dict[str, Any]:
    owners = []
    for owner in payload.get("owners") or []:
        owners.append(
            {
                "display_name": owner.get("displayName"),
                "email": owner.get("emailAddress"),
            }
        )
    last_modifying_user = payload.get("lastModifyingUser") or {}
    shortcut = payload.get("shortcutDetails") or {}
    return {
        "account": account,
        "id": payload.get("id"),
        "name": payload.get("name"),
        "mime_type": payload.get("mimeType"),
        "modified_time": payload.get("modifiedTime"),
        "modified_by_me": payload.get("modifiedByMe"),
        "modified_by_me_time": payload.get("modifiedByMeTime"),
        "last_modifying_user": {
            "display_name": last_modifying_user.get("displayName"),
            "email": last_modifying_user.get("emailAddress"),
        }
        if last_modifying_user
        else None,
        "created_time": payload.get("createdTime"),
        "viewed_by_me_time": payload.get("viewedByMeTime"),
        "size": payload.get("size"),
        "web_view_link": payload.get("webViewLink"),
        "icon_link": payload.get("iconLink"),
        "parents": payload.get("parents") or [],
        "owners": owners,
        "drive_id": payload.get("driveId"),
        "shortcut_target_id": shortcut.get("targetId"),
        "shortcut_target_mime_type": shortcut.get("targetMimeType"),
    }


def _file_fields() -> str:
    return (
        "nextPageToken, files("
        "id, name, mimeType, modifiedTime, modifiedByMe, modifiedByMeTime, "
        "lastModifyingUser(displayName,emailAddress), createdTime, viewedByMeTime, size, "
        "webViewLink, iconLink, parents, owners(displayName,emailAddress), "
        "driveId, shortcutDetails(targetId,targetMimeType)"
        ")"
    )


def _find_file_metadata(account: str, file_id: str) -> dict[str, Any]:
    service = _drive_service(account)
    payload = _safe_execute(
        service.files().get(
            fileId=file_id,
            fields=(
                "id, name, mimeType, modifiedTime, modifiedByMe, modifiedByMeTime, "
                "lastModifyingUser(displayName,emailAddress), createdTime, viewedByMeTime, size, "
                "webViewLink, iconLink, parents, owners(displayName,emailAddress), "
                "driveId, shortcutDetails(targetId,targetMimeType)"
            ),
            supportsAllDrives=True,
        ),
        label=f"Drive get metadata ({account})",
    )
    return _serialize_drive_file(account, payload)


def _print_or_raise_first_result(results: list[dict[str, Any]], missing_message: str) -> None:
    if not results:
        raise RuntimeError(missing_message)
    _json_dump(results[0] if len(results) == 1 else {"count": len(results), "items": results})


def command_auth(args: argparse.Namespace) -> None:
    auth_account(args.account)


def command_search(args: argparse.Namespace) -> None:
    folder_id = _extract_file_id(args.folder_id) if args.folder_id else None
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        service = _drive_service(account)
        token: str | None = None
        while len(results) < args.max_results:
            payload = _safe_execute(
                service.files().list(
                    q=_build_search_query(args.query, args.type, folder_id),
                    pageSize=min(args.max_results, 100),
                    pageToken=token,
                    orderBy="modifiedTime desc",
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    fields=_file_fields(),
                ),
                label=f"Drive search ({account})",
            )
            for item in payload.get("files") or []:
                serialized = _serialize_drive_file(account, item)
                if args.modified_by_me and not serialized.get("modified_by_me"):
                    continue
                results.append(serialized)
                if len(results) >= args.max_results:
                    break
            token = payload.get("nextPageToken")
            if not token:
                break
    _json_dump({"count": len(results), "files": results[: args.max_results]})


def command_recent(args: argparse.Namespace) -> None:
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        service = _drive_service(account)
        payload = _safe_execute(
            service.files().list(
                q="trashed = false",
                pageSize=min(args.max_results, 100),
                orderBy="modifiedTime desc",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields=_file_fields(),
            ),
            label=f"Drive recent ({account})",
        )
        for item in payload.get("files") or []:
            serialized = _serialize_drive_file(account, item)
            if args.modified_by_me and not serialized.get("modified_by_me"):
                continue
            results.append(serialized)
    results.sort(key=lambda item: str(item.get("modified_time") or ""), reverse=True)
    _json_dump({"count": min(len(results), args.max_results), "files": results[: args.max_results]})


def command_list_folder(args: argparse.Namespace) -> None:
    folder_id = _extract_file_id(args.folder_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        service = _drive_service(account)
        payload = _safe_execute(
            service.files().list(
                q=f"trashed = false and '{folder_id}' in parents",
                pageSize=min(args.max_results, 100),
                orderBy="folder,name",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields=_file_fields(),
            ),
            label=f"Drive list folder ({account})",
        )
        for item in payload.get("files") or []:
            results.append(_serialize_drive_file(account, item))
    _json_dump({"count": len(results), "files": results[: args.max_results]})


def command_get_metadata(args: argparse.Namespace) -> None:
    file_id = _extract_file_id(args.file_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_find_file_metadata(account, file_id))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"File '{file_id}' not found for account setting '{args.account}'")


def _doc_paragraph_text(paragraph: dict[str, Any]) -> str:
    parts: list[str] = []
    for element in paragraph.get("elements") or []:
        text_run = (element.get("textRun") or {}).get("content")
        if text_run:
            parts.append(text_run)
    text = "".join(parts).replace("\v", "\n")
    return text.strip()


def _walk_doc_content(elements: list[dict[str, Any]], lines: list[str]) -> None:
    for element in elements:
        paragraph = element.get("paragraph")
        if paragraph:
            text = _doc_paragraph_text(paragraph)
            if text:
                lines.append(text)
            continue

        table = element.get("table")
        if table:
            for row in table.get("tableRows") or []:
                cells: list[str] = []
                for cell in row.get("tableCells") or []:
                    cell_lines: list[str] = []
                    _walk_doc_content(cell.get("content") or [], cell_lines)
                    cells.append(" ".join(part.strip() for part in cell_lines if part.strip()))
                if any(cells):
                    lines.append(" | ".join(cells))
            continue

        toc = element.get("tableOfContents")
        if toc:
            _walk_doc_content(toc.get("content") or [], lines)


def _get_doc_text(account: str, document_id: str) -> dict[str, Any]:
    payload = _safe_execute(
        _docs_service(account).documents().get(documentId=document_id),
        label=f"Docs get ({account})",
    )
    lines: list[str] = []
    body = payload.get("body") or {}
    _walk_doc_content(body.get("content") or [], lines)
    return {
        "account": account,
        "document_id": payload.get("documentId"),
        "title": payload.get("title"),
        "text": "\n\n".join(line for line in lines if line.strip()).strip(),
    }


def command_get_doc_text(args: argparse.Namespace) -> None:
    document_id = _extract_file_id(args.document_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_get_doc_text(account, document_id))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Document '{document_id}' not found for account setting '{args.account}'")


def _get_sheet_metadata(account: str, spreadsheet_id: str) -> dict[str, Any]:
    payload = _safe_execute(
        _sheets_service(account).spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            includeGridData=False,
        ),
        label=f"Sheets get metadata ({account})",
    )
    sheets = []
    for sheet in payload.get("sheets") or []:
        props = sheet.get("properties") or {}
        grid = props.get("gridProperties") or {}
        sheets.append(
            {
                "sheet_id": props.get("sheetId"),
                "title": props.get("title"),
                "index": props.get("index"),
                "row_count": grid.get("rowCount"),
                "column_count": grid.get("columnCount"),
                "hidden": props.get("hidden"),
            }
        )
    return {
        "account": account,
        "spreadsheet_id": payload.get("spreadsheetId"),
        "title": payload.get("properties", {}).get("title"),
        "locale": payload.get("properties", {}).get("locale"),
        "time_zone": payload.get("properties", {}).get("timeZone"),
        "sheets": sheets,
    }


def command_get_sheet_metadata(args: argparse.Namespace) -> None:
    spreadsheet_id = _extract_file_id(args.spreadsheet_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_get_sheet_metadata(account, spreadsheet_id))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Spreadsheet '{spreadsheet_id}' not found for account setting '{args.account}'")


def _sheet_range(sheet_name: str | None, cell_range: str) -> str:
    if sheet_name:
        return f"{sheet_name}!{cell_range}"
    return cell_range


def _get_sheet_values(account: str, spreadsheet_id: str, sheet_name: str | None, cell_range: str, value_render_option: str | None) -> dict[str, Any]:
    payload = _safe_execute(
        _sheets_service(account).spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=_sheet_range(sheet_name, cell_range),
            valueRenderOption=value_render_option,
        ),
        label=f"Sheets get values ({account})",
    )
    return {
        "account": account,
        "spreadsheet_id": spreadsheet_id,
        "range": payload.get("range"),
        "major_dimension": payload.get("majorDimension"),
        "values": payload.get("values") or [],
    }


def command_get_sheet_values(args: argparse.Namespace) -> None:
    spreadsheet_id = _extract_file_id(args.spreadsheet_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(
                _get_sheet_values(
                    account,
                    spreadsheet_id,
                    args.sheet_name,
                    args.range,
                    args.value_render_option,
                )
            )
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Spreadsheet '{spreadsheet_id}' not found for account setting '{args.account}'")


def _slide_text(shape: dict[str, Any]) -> str:
    runs: list[str] = []
    text_content = (((shape.get("text") or {}).get("textElements")) or [])
    for element in text_content:
        text_run = (element.get("textRun") or {}).get("content")
        if text_run:
            runs.append(text_run)
    return "".join(runs).strip()


def _table_text(table: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for row in table.get("tableRows") or []:
        cells: list[str] = []
        for cell in row.get("tableCells") or []:
            parts: list[str] = []
            for text_element in cell.get("text", {}).get("textElements") or []:
                text_run = (text_element.get("textRun") or {}).get("content")
                if text_run:
                    parts.append(text_run.strip())
            cells.append(" ".join(part for part in parts if part))
        if any(cells):
            lines.append(" | ".join(cells))
    return lines


def _get_presentation_text(account: str, presentation_id: str) -> dict[str, Any]:
    payload = _safe_execute(
        _slides_service(account).presentations().get(presentationId=presentation_id),
        label=f"Slides get ({account})",
    )
    slides = []
    for index, slide in enumerate(payload.get("slides") or [], start=1):
        lines: list[str] = []
        for element in slide.get("pageElements") or []:
            shape = element.get("shape")
            if shape:
                text = _slide_text(shape)
                if text:
                    lines.append(text)
            table = element.get("table")
            if table:
                lines.extend(_table_text(table))
        slides.append(
            {
                "slide_number": index,
                "slide_object_id": slide.get("objectId"),
                "text": "\n\n".join(line for line in lines if line.strip()).strip(),
            }
        )
    return {
        "account": account,
        "presentation_id": payload.get("presentationId"),
        "title": payload.get("title"),
        "slides": slides,
    }


def command_get_presentation_text(args: argparse.Namespace) -> None:
    presentation_id = _extract_file_id(args.presentation_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_get_presentation_text(account, presentation_id))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Presentation '{presentation_id}' not found for account setting '{args.account}'")


def _default_export_dir() -> Path:
    today = datetime.now().astimezone()
    return EXPORT_ROOT / today.strftime("%Y") / today.strftime("%m") / today.strftime("%d")


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "-", name).strip()
    return cleaned or "gdrive-export"


def _download_to_path(request: Any, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=5)


def _export_file(account: str, file_id: str, output_path: Path, mime_type: str | None) -> dict[str, Any]:
    metadata = _find_file_metadata(account, file_id)
    service = _drive_service(account)
    native_mime = str(metadata.get("mime_type") or "")

    if native_mime.startswith("application/vnd.google-apps."):
        chosen_mime = mime_type or DEFAULT_EXPORT_MIME.get(native_mime)
        if not chosen_mime:
            raise RuntimeError(
                "Native Google file requires --mime-type for export. "
                "Example: text/plain, application/pdf, or Office export mime types."
            )
        request = service.files().export_media(fileId=file_id, mimeType=chosen_mime)
    else:
        chosen_mime = mime_type
        request = service.files().get_media(fileId=file_id)

    _download_to_path(request, output_path)
    return {
        "account": account,
        "file_id": file_id,
        "name": metadata.get("name"),
        "mime_type": metadata.get("mime_type"),
        "export_mime_type": chosen_mime,
        "output_path": str(output_path),
    }


def command_export_file(args: argparse.Namespace) -> None:
    file_id = _extract_file_id(args.file_id)
    target_metadata: dict[str, Any] | None = None
    target_account: str | None = None
    for account in _iter_accounts(args.account):
        try:
            target_metadata = _find_file_metadata(account, file_id)
            target_account = account
            break
        except RuntimeError:
            continue

    if not target_metadata or not target_account:
        raise RuntimeError(f"File '{file_id}' not found for account setting '{args.account}'")

    output_path = Path(args.output) if args.output else (_default_export_dir() / _safe_filename(str(target_metadata.get("name") or file_id)))
    result = _export_file(target_account, file_id, output_path, args.mime_type)
    _json_dump(result)




NAMED_STYLE_CHOICES = [
    "NORMAL_TEXT",
    "TITLE",
    "SUBTITLE",
    "HEADING_1",
    "HEADING_2",
    "HEADING_3",
    "HEADING_4",
    "HEADING_5",
    "HEADING_6",
]


def _doc_structural_elements(document: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    body = document.get("body") or {}
    for idx, element in enumerate(body.get("content") or []):
        if element.get("paragraph"):
            paragraph = element["paragraph"]
            text = _doc_paragraph_text(paragraph)
            style = (paragraph.get("paragraphStyle") or {}).get("namedStyleType")
            items.append(
                {
                    "type": "paragraph",
                    "block_index": idx,
                    "start_index": element.get("startIndex"),
                    "end_index": element.get("endIndex"),
                    "named_style": style,
                    "text": text,
                }
            )
        elif element.get("table"):
            rows = []
            for row in element["table"].get("tableRows") or []:
                row_cells = []
                for cell in row.get("tableCells") or []:
                    cell_lines: list[str] = []
                    _walk_doc_content(cell.get("content") or [], cell_lines)
                    row_cells.append(" ".join(part.strip() for part in cell_lines if part.strip()))
                rows.append(row_cells)
            items.append(
                {
                    "type": "table",
                    "block_index": idx,
                    "start_index": element.get("startIndex"),
                    "end_index": element.get("endIndex"),
                    "rows": rows,
                }
            )
    return items


def _get_doc_structure(account: str, document_id: str) -> dict[str, Any]:
    payload = _safe_execute(
        _docs_service(account).documents().get(documentId=document_id),
        label=f"Docs structure ({account})",
    )
    return {
        "account": account,
        "document_id": payload.get("documentId"),
        "title": payload.get("title"),
        "items": _doc_structural_elements(payload),
    }


def command_get_doc_structure(args: argparse.Namespace) -> None:
    document_id = _extract_file_id(args.document_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_get_doc_structure(account, document_id))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Document '{document_id}' not found for account setting '{args.account}'")


def _find_doc_text(account: str, document_id: str, query: str) -> dict[str, Any]:
    payload = _safe_execute(
        _docs_service(account).documents().get(documentId=document_id),
        label=f"Docs find text ({account})",
    )
    matches: list[dict[str, Any]] = []
    for item in _doc_structural_elements(payload):
        block_text = item.get("text") or ""
        start = 0
        while True:
            found = block_text.lower().find(query.lower(), start)
            if found == -1:
                break
            matches.append(
                {
                    "block_index": item.get("block_index"),
                    "start_index": item.get("start_index"),
                    "end_index": item.get("end_index"),
                    "text_offset": found,
                    "match_text": block_text[found:found + len(query)],
                    "block_text": block_text,
                }
            )
            start = found + len(query)
    return {
        "account": account,
        "document_id": payload.get("documentId"),
        "title": payload.get("title"),
        "query": query,
        "matches": matches,
    }


def command_find_doc_text(args: argparse.Namespace) -> None:
    document_id = _extract_file_id(args.document_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_find_doc_text(account, document_id, args.query))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Document '{document_id}' not found for account setting '{args.account}'")


def _replace_doc_range(account: str, document_id: str, start_index: int, end_index: int, text_value: str, named_style: str | None) -> dict[str, Any]:
    requests: list[dict[str, Any]] = [
        {
            "deleteContentRange": {
                "range": {
                    "startIndex": start_index,
                    "endIndex": end_index,
                }
            }
        },
        {
            "insertText": {
                "location": {"index": start_index},
                "text": text_value,
            }
        },
    ]
    if named_style:
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": start_index,
                        "endIndex": start_index + len(text_value),
                    },
                    "paragraphStyle": {"namedStyleType": named_style},
                    "fields": "namedStyleType",
                }
            }
        )
    payload = _safe_execute(
        _docs_service(account).documents().batchUpdate(
            documentId=document_id,
            body={"requests": requests},
        ),
        label=f"Docs replace range ({account})",
    )
    return {
        "account": account,
        "document_id": document_id,
        "start_index": start_index,
        "end_index": end_index,
        "inserted_text_length": len(text_value),
        "named_style": named_style,
        "replies": len(payload.get("replies") or []),
    }


def command_replace_doc_range(args: argparse.Namespace) -> None:
    document_id = _extract_file_id(args.document_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_replace_doc_range(account, document_id, args.start_index, args.end_index, args.text, args.named_style))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Document '{document_id}' not found for account setting '{args.account}'")


def _append_doc_table(account: str, document_id: str, rows: list[list[str]]) -> dict[str, Any]:
    if not rows or not rows[0]:
        raise RuntimeError("rows-json must contain at least one row and one column")
    document = _safe_execute(
        _docs_service(account).documents().get(documentId=document_id),
        label=f"Docs get before append table ({account})",
    )
    end_index = (document.get("body") or {}).get("content", [])[-1].get("endIndex", 1) - 1
    requests: list[dict[str, Any]] = [
        {"insertTable": {"rows": len(rows), "columns": len(rows[0]), "location": {"index": end_index}}}
    ]
    insertion_index = end_index + 4
    for row in rows:
        for cell in row:
            if cell:
                requests.append(
                    {
                        "insertText": {
                            "location": {"index": insertion_index},
                            "text": cell,
                        }
                    }
                )
            insertion_index += len(cell) + 2
    payload = _safe_execute(
        _docs_service(account).documents().batchUpdate(
            documentId=document_id,
            body={"requests": requests},
        ),
        label=f"Docs append table ({account})",
    )
    return {
        "account": account,
        "document_id": document_id,
        "rows": len(rows),
        "columns": len(rows[0]),
        "replies": len(payload.get("replies") or []),
    }


def command_append_doc_table(args: argparse.Namespace) -> None:
    document_id = _extract_file_id(args.document_id)
    rows = json.loads(args.rows_json)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_append_doc_table(account, document_id, rows))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Document '{document_id}' not found for account setting '{args.account}'")


def _find_sheet_rows(account: str, spreadsheet_id: str, range_name: str, query: str) -> dict[str, Any]:
    payload = _safe_execute(
        _sheets_service(account).spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name,
        ),
        label=f"Sheets find rows ({account})",
    )
    rows = payload.get("values") or []
    matches = []
    for index, row in enumerate(rows, start=1):
        joined = " | ".join(str(cell) for cell in row)
        if query.lower() in joined.lower():
            matches.append({"row_number": index, "values": row})
    return {
        "account": account,
        "spreadsheet_id": spreadsheet_id,
        "range": payload.get("range"),
        "query": query,
        "matches": matches,
    }


def command_find_sheet_rows(args: argparse.Namespace) -> None:
    spreadsheet_id = _extract_file_id(args.spreadsheet_id)
    range_name = _sheet_range(args.sheet_name, args.range)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_find_sheet_rows(account, spreadsheet_id, range_name, args.query))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Spreadsheet '{spreadsheet_id}' not found for account setting '{args.account}'")


def _update_sheet_values(account: str, spreadsheet_id: str, range_name: str, values: list[list[Any]], value_input_option: str) -> dict[str, Any]:
    payload = _safe_execute(
        _sheets_service(account).spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=value_input_option,
            body={"values": values},
        ),
        label=f"Sheets update values ({account})",
    )
    return {
        "account": account,
        "spreadsheet_id": spreadsheet_id,
        "updated_range": payload.get("updatedRange"),
        "updated_rows": payload.get("updatedRows"),
        "updated_columns": payload.get("updatedColumns"),
        "updated_cells": payload.get("updatedCells"),
    }


def command_update_sheet_values(args: argparse.Namespace) -> None:
    spreadsheet_id = _extract_file_id(args.spreadsheet_id)
    values = json.loads(args.values_json)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_update_sheet_values(account, spreadsheet_id, args.range, values, args.value_input_option))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Spreadsheet '{spreadsheet_id}' not found for account setting '{args.account}'")


def _append_sheet_rows(account: str, spreadsheet_id: str, range_name: str, rows: list[list[Any]], value_input_option: str) -> dict[str, Any]:
    payload = _safe_execute(
        _sheets_service(account).spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=value_input_option,
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ),
        label=f"Sheets append rows ({account})",
    )
    updates = payload.get("updates") or {}
    return {
        "account": account,
        "spreadsheet_id": spreadsheet_id,
        "updated_range": updates.get("updatedRange"),
        "updated_rows": updates.get("updatedRows"),
        "updated_columns": updates.get("updatedColumns"),
        "updated_cells": updates.get("updatedCells"),
    }


def command_append_sheet_rows(args: argparse.Namespace) -> None:
    spreadsheet_id = _extract_file_id(args.spreadsheet_id)
    rows = json.loads(args.rows_json)
    range_name = f"{args.sheet_name}!A1" if args.sheet_name else "A1"
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_append_sheet_rows(account, spreadsheet_id, range_name, rows, args.value_input_option))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Spreadsheet '{spreadsheet_id}' not found for account setting '{args.account}'")


def _create_presentation(account: str, title: str) -> dict[str, Any]:
    payload = _safe_execute(
        _slides_service(account).presentations().create(body={"title": title}),
        label=f"Slides create ({account})",
    )
    return {
        "account": account,
        "presentation_id": payload.get("presentationId"),
        "title": payload.get("title"),
    }


def command_create_presentation(args: argparse.Namespace) -> None:
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_create_presentation(account, args.title))
            if args.account != "both":
                break
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, "Could not create presentation")


def _replace_slide_text(account: str, presentation_id: str, find_text: str, replace_text: str) -> dict[str, Any]:
    payload = _safe_execute(
        _slides_service(account).presentations().batchUpdate(
            presentationId=presentation_id,
            body={
                "requests": [
                    {
                        "replaceAllText": {
                            "containsText": {"text": find_text, "matchCase": False},
                            "replaceText": replace_text,
                        }
                    }
                ]
            },
        ),
        label=f"Slides replace text ({account})",
    )
    matches = payload.get("replies", [{}])[0].get("replaceAllText", {}).get("occurrencesChanged")
    return {
        "account": account,
        "presentation_id": presentation_id,
        "find": find_text,
        "replace": replace_text,
        "occurrences_changed": matches,
    }


def command_replace_slide_text(args: argparse.Namespace) -> None:
    presentation_id = _extract_file_id(args.presentation_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_replace_slide_text(account, presentation_id, args.find, args.replace))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Presentation '{presentation_id}' not found for account setting '{args.account}'")


def _update_slide_shape_text(account: str, presentation_id: str, shape_id: str, text_value: str) -> dict[str, Any]:
    payload = _safe_execute(
        _slides_service(account).presentations().batchUpdate(
            presentationId=presentation_id,
            body={
                "requests": [
                    {"deleteText": {"objectId": shape_id, "textRange": {"type": "ALL"}}},
                    {"insertText": {"objectId": shape_id, "insertionIndex": 0, "text": text_value}},
                ]
            },
        ),
        label=f"Slides update shape text ({account})",
    )
    return {
        "account": account,
        "presentation_id": presentation_id,
        "shape_id": shape_id,
        "replies": len(payload.get("replies") or []),
    }


def command_update_slide_shape_text(args: argparse.Namespace) -> None:
    presentation_id = _extract_file_id(args.presentation_id)
    results: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        try:
            results.append(_update_slide_shape_text(account, presentation_id, args.shape_id, args.text))
        except RuntimeError:
            continue
    _print_or_raise_first_result(results, f"Presentation '{presentation_id}' not found for account setting '{args.account}'")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="google_drive_assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    p_auth = sub.add_parser("auth", help="Authenticate and store a token for an account")
    p_auth.add_argument("--account", choices=["private", "personal"], required=True)
    p_auth.set_defaults(func=command_auth)

    p_search = sub.add_parser("search", help="Search Drive files")
    p_search.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--type", choices=sorted(MIME_TYPE_FILTERS.keys()), default="any")
    p_search.add_argument("--folder-id", help="Optional folder id or folder URL to constrain the search")
    p_search.add_argument("--modified-by-me", action="store_true", help="Keep only files last modified by the authenticated user")
    p_search.add_argument("--max-results", type=int, default=10)
    p_search.set_defaults(func=command_search)

    p_recent = sub.add_parser("recent", help="List recently modified files")
    p_recent.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_recent.add_argument("--modified-by-me", action="store_true", help="Keep only files last modified by the authenticated user")
    p_recent.add_argument("--max-results", type=int, default=10)
    p_recent.set_defaults(func=command_recent)

    p_list_folder = sub.add_parser("list-folder", help="List one Drive folder")
    p_list_folder.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_list_folder.add_argument("--folder-id", required=True)
    p_list_folder.add_argument("--max-results", type=int, default=50)
    p_list_folder.set_defaults(func=command_list_folder)

    p_meta = sub.add_parser("get-metadata", help="Get Drive file metadata")
    p_meta.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_meta.add_argument("--file-id", required=True)
    p_meta.set_defaults(func=command_get_metadata)

    p_doc = sub.add_parser("get-doc-text", help="Read Google Docs text")
    p_doc.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_doc.add_argument("--document-id", required=True)
    p_doc.set_defaults(func=command_get_doc_text)

    p_doc_structure = sub.add_parser("get-doc-structure", help="Read Google Docs structure with indexes")
    p_doc_structure.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_doc_structure.add_argument("--document-id", required=True)
    p_doc_structure.set_defaults(func=command_get_doc_structure)

    p_doc_find = sub.add_parser("find-doc-text", help="Find text occurrences inside a Google Doc")
    p_doc_find.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_doc_find.add_argument("--document-id", required=True)
    p_doc_find.add_argument("--query", required=True)
    p_doc_find.set_defaults(func=command_find_doc_text)

    p_doc_replace = sub.add_parser("replace-doc-range", help="Replace a Google Doc range with new text")
    p_doc_replace.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_doc_replace.add_argument("--document-id", required=True)
    p_doc_replace.add_argument("--start-index", type=int, required=True)
    p_doc_replace.add_argument("--end-index", type=int, required=True)
    p_doc_replace.add_argument("--text", required=True)
    p_doc_replace.add_argument("--named-style", choices=NAMED_STYLE_CHOICES)
    p_doc_replace.set_defaults(func=command_replace_doc_range)

    p_doc_table = sub.add_parser("append-doc-table", help="Append a table to the end of a Google Doc")
    p_doc_table.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_doc_table.add_argument("--document-id", required=True)
    p_doc_table.add_argument("--rows-json", required=True)
    p_doc_table.set_defaults(func=command_append_doc_table)

    p_sheet_meta = sub.add_parser("get-sheet-metadata", help="Read Google Sheets metadata")
    p_sheet_meta.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_sheet_meta.add_argument("--spreadsheet-id", required=True)
    p_sheet_meta.set_defaults(func=command_get_sheet_metadata)

    p_sheet_values = sub.add_parser("get-sheet-values", help="Read Google Sheets values")
    p_sheet_values.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_sheet_values.add_argument("--spreadsheet-id", required=True)
    p_sheet_values.add_argument("--sheet-name")
    p_sheet_values.add_argument("--range", required=True)
    p_sheet_values.add_argument("--value-render-option", choices=["FORMATTED_VALUE", "UNFORMATTED_VALUE", "FORMULA"], default=None)
    p_sheet_values.set_defaults(func=command_get_sheet_values)

    p_sheet_find = sub.add_parser("find-sheet-rows", help="Find matching rows inside a Google Sheet range")
    p_sheet_find.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_sheet_find.add_argument("--spreadsheet-id", required=True)
    p_sheet_find.add_argument("--sheet-name")
    p_sheet_find.add_argument("--range", required=True)
    p_sheet_find.add_argument("--query", required=True)
    p_sheet_find.set_defaults(func=command_find_sheet_rows)

    p_sheet_update = sub.add_parser("update-sheet-values", help="Update a Google Sheet range")
    p_sheet_update.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_sheet_update.add_argument("--spreadsheet-id", required=True)
    p_sheet_update.add_argument("--range", required=True)
    p_sheet_update.add_argument("--values-json", required=True)
    p_sheet_update.add_argument("--value-input-option", choices=["RAW", "USER_ENTERED"], default="USER_ENTERED")
    p_sheet_update.set_defaults(func=command_update_sheet_values)

    p_sheet_append = sub.add_parser("append-sheet-rows", help="Append rows to a Google Sheet")
    p_sheet_append.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_sheet_append.add_argument("--spreadsheet-id", required=True)
    p_sheet_append.add_argument("--sheet-name", required=True)
    p_sheet_append.add_argument("--rows-json", required=True)
    p_sheet_append.add_argument("--value-input-option", choices=["RAW", "USER_ENTERED"], default="USER_ENTERED")
    p_sheet_append.set_defaults(func=command_append_sheet_rows)

    p_slides = sub.add_parser("get-presentation-text", help="Read Google Slides text")
    p_slides.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_slides.add_argument("--presentation-id", required=True)
    p_slides.set_defaults(func=command_get_presentation_text)

    p_create_presentation = sub.add_parser("create-presentation", help="Create a Google Slides presentation")
    p_create_presentation.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_create_presentation.add_argument("--title", required=True)
    p_create_presentation.set_defaults(func=command_create_presentation)

    p_replace_slide_text = sub.add_parser("replace-slide-text", help="Replace text across a presentation")
    p_replace_slide_text.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_replace_slide_text.add_argument("--presentation-id", required=True)
    p_replace_slide_text.add_argument("--find", required=True)
    p_replace_slide_text.add_argument("--replace", required=True)
    p_replace_slide_text.set_defaults(func=command_replace_slide_text)

    p_update_slide_shape = sub.add_parser("update-slide-shape-text", help="Replace one text shape by object id")
    p_update_slide_shape.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_update_slide_shape.add_argument("--presentation-id", required=True)
    p_update_slide_shape.add_argument("--shape-id", required=True)
    p_update_slide_shape.add_argument("--text", required=True)
    p_update_slide_shape.set_defaults(func=command_update_slide_shape_text)

    p_export = sub.add_parser("export-file", help="Export or download a Drive file into the vault")
    p_export.add_argument("--account", choices=["private", "personal", "both"], default="both")
    p_export.add_argument("--file-id", required=True)
    p_export.add_argument("--mime-type")
    p_export.add_argument("--output", help="Absolute or repo-relative output path")
    p_export.set_defaults(func=command_export_file)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
