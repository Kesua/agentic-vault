from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: list[str], *, cwd: Path, dry_run: bool) -> int:
    rendered = " ".join(cmd)
    print(f"$ {rendered}")
    if dry_run:
        return 0
    proc = subprocess.run(cmd, cwd=str(cwd))
    return proc.returncode


def _ensure_git_repo(repo_root: Path) -> None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git not found on PATH") from exc

    if proc.returncode != 0 or proc.stdout.strip().lower() != "true":
        raise RuntimeError(f"Not a git repo: {repo_root}")


def sync(*, repo_root: Path, mode: str, dry_run: bool) -> None:
    _ensure_git_repo(repo_root)

    gitmodules_path = repo_root / ".gitmodules"
    if not gitmodules_path.exists():
        print("No .gitmodules found; nothing to do.")
        return

    # Keep submodule URLs and config consistent with .gitmodules.
    rc = _run(["git", "submodule", "sync", "--recursive"], cwd=repo_root, dry_run=dry_run)
    if rc != 0:
        raise RuntimeError("git submodule sync failed")

    # Ensure the submodule working trees exist.
    rc = _run(["git", "submodule", "update", "--init", "--recursive"], cwd=repo_root, dry_run=dry_run)
    if rc != 0:
        raise RuntimeError("git submodule update --init failed")

    if mode == "remote":
        # Update each submodule to its configured remote branch (optionally set per-submodule in .gitmodules).
        rc = _run(
            ["git", "submodule", "update", "--remote", "--merge", "--recursive"],
            cwd=repo_root,
            dry_run=dry_run,
        )
        if rc != 0:
            raise RuntimeError("git submodule update --remote failed")

    # Helpful summary for what changed.
    _run(["git", "submodule", "status", "--recursive"], cwd=repo_root, dry_run=dry_run)
    _run(["git", "status", "-sb"], cwd=repo_root, dry_run=dry_run)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize and refresh all git submodules in this repo.")
    sub = parser.add_subparsers(dest="command", required=True)

    sync_p = sub.add_parser("sync", help="Sync and update all submodules.")
    sync_p.add_argument(
        "--mode",
        choices=("remote", "pinned"),
        default="remote",
        help="remote: update to latest remote commits; pinned: checkout SHAs recorded in the superproject.",
    )
    sync_p.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    sync_p.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repo root to operate on (defaults to this vault repo).",
    )

    return parser


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "sync":
            sync(repo_root=args.repo_root, mode=args.mode, dry_run=args.dry_run)
            return 0
        raise RuntimeError(f"Unknown command: {args.command}")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

