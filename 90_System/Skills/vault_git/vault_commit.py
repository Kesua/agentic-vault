#!/usr/bin/env python3
"""Commit routine-owned vault folders and optionally push to an allow-listed private remote.

Uses only the Python standard library and the local git CLI. It never pulls,
merges, rebases or force-pushes; a rejected push is reported for manual
reconciliation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATHS = (
    "00_Mailbox",
    "10_DailyBriefs",
    "20_Meetings",
    "30_Projects/Journal",
    "30_Projects/_Projects.md",
    "40_People",
)
ALLOWED_PUSH_URL_KEY = "agenticvault.pushUrl"

EXIT_OK = 0
EXIT_GIT_ERROR = 1
EXIT_PUSH_REFUSED = 2
EXIT_PUSH_REJECTED = 3


class GitError(RuntimeError):
    """Raised when a git command fails."""


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise GitError(f"git {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url.lower()


def existing_paths(repo: Path, paths: Sequence[str]) -> List[str]:
    return [path for path in paths if (repo / path).exists()]


def commit_routine_outputs(
    repo: Path,
    routine: str,
    date: str,
    paths: Sequence[str],
    *,
    dry_run: bool = False,
) -> Optional[str]:
    """Commit only the given paths. Returns the new commit hash, or None if nothing changed."""
    present = existing_paths(repo, paths)
    if not present:
        return None

    changes = _git(repo, "status", "--porcelain", "--untracked-files=all", "--", *present).stdout
    if not changes.strip():
        return None
    if dry_run:
        print(changes.rstrip())
        return "dry-run"

    _git(repo, "add", "--all", "--", *present)
    message = f"routine: {routine} {date}"
    # Pathspec commit: other staged or dirty files stay untouched.
    _git(repo, "commit", "--only", "-m", message, "--", *present)
    return _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()


def push_current_branch(repo: Path, *, dry_run: bool = False) -> int:
    branch = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).stdout.strip()
    if not branch:
        print("Push refused: HEAD is detached.")
        return EXIT_PUSH_REFUSED

    remote = _git(repo, "config", "--get", f"branch.{branch}.remote", check=False).stdout.strip() or "origin"
    remote_url = _git(repo, "remote", "get-url", remote, check=False).stdout.strip()
    allowed_url = _git(repo, "config", "--get", ALLOWED_PUSH_URL_KEY, check=False).stdout.strip()

    if not remote_url:
        print(f"Push refused: remote '{remote}' is not configured.")
        return EXIT_PUSH_REFUSED
    if not allowed_url:
        print(
            "Push refused: no private remote is allow-listed. After confirming the remote is private, run:\n"
            f"  git config --local {ALLOWED_PUSH_URL_KEY} <url of your private vault repository>"
        )
        return EXIT_PUSH_REFUSED
    if _normalize_url(remote_url) != _normalize_url(allowed_url):
        print(f"Push refused: remote '{remote}' does not match the allow-listed {ALLOWED_PUSH_URL_KEY}.")
        return EXIT_PUSH_REFUSED

    if dry_run:
        print(f"Would push {branch} to {remote}.")
        return EXIT_OK

    result = _git(repo, "push", remote, f"HEAD:refs/heads/{branch}", check=False)
    if result.returncode == 0:
        print(f"Pushed {branch} to {remote}.")
        return EXIT_OK

    _git(repo, "fetch", remote, branch, check=False)
    counts = _git(repo, "rev-list", "--left-right", "--count", f"HEAD...{remote}/{branch}", check=False).stdout.split()
    divergence = f" Local is ahead {counts[0]} and behind {counts[1]}." if len(counts) == 2 else ""
    print(
        f"Push rejected by {remote}.{divergence} Nothing was pulled, merged or forced; "
        "reconcile manually before the next push."
    )
    return EXIT_PUSH_REJECTED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--routine", required=True, help="Routine name used in the commit message, e.g. day-start")
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="Date for the commit message (YYYY-MM-DD)")
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Vault-relative path to include; repeatable. Defaults to the routine-owned folders.",
    )
    parser.add_argument("--push", action="store_true", help="Push afterwards, only to the allow-listed private remote")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be committed and pushed")
    parser.add_argument("--repo", default=str(REPO_ROOT), help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo)
    paths = args.paths or list(DEFAULT_PATHS)

    try:
        commit = commit_routine_outputs(repo, args.routine, args.date, paths, dry_run=args.dry_run)
        if commit is None:
            print("Nothing to commit in routine-owned paths.")
        elif commit != "dry-run":
            print(f"Committed {commit}: routine: {args.routine} {args.date}")
        if args.push:
            return push_current_branch(repo, dry_run=args.dry_run)
    except GitError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_GIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
