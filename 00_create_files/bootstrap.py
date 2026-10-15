#!/usr/bin/env python3
"""
00_create_files / bootstrap.py
------------------------------
Step 0 of installation: prepare the runtime environment for a clean first run.

What this script does
---------------------
1. Ensures the ``db/`` directory exists.
2. Removes any leftover ``db/auth.db`` (the database must be created on first
   run by ``auth.core.init_db()``, never shipped).
3. Creates ``docker/.env`` from ``docker/.env.example`` if it does not exist.
4. Performs a few basic sanity checks on the project layout.
5. Prints clear next-step instructions.

Usage (from project root)
-------------------------
    python 00_create_files/bootstrap.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def find_project_root() -> Path:
    """Locate the project root (directory that contains app.py)."""
    script_dir = Path(__file__).resolve().parent
    if script_dir.name == "00_create_files":
        candidate = script_dir.parent
        if (candidate / "app.py").exists():
            return candidate
    cwd = Path.cwd()
    if (cwd / "app.py").exists():
        return cwd
    return script_dir.parent if script_dir.name == "00_create_files" else script_dir


def ensure_db_directory(root: Path) -> None:
    """Create the db/ directory if it is missing."""
    db_dir = root / "db"
    if not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)
        print("[ok] Created directory: db/")
    else:
        print("[ok] Directory already exists: db/")


def remove_shipped_database(root: Path) -> None:
    """
    Delete db/auth.db if present.

    The database is generated automatically on first run. Shipping a pre-seeded
    file is undesirable (stale password hashes, default accounts, etc.).
    """
    db_file = root / "db" / "auth.db"
    if db_file.exists():
        db_file.unlink()
        print("[ok] Removed leftover file: db/auth.db")
    else:
        print("[ok] No shipped database found (good)")


def ensure_docker_env(root: Path) -> None:
    """Copy docker/.env.example -> docker/.env when the latter is missing."""
    example = root / "docker" / ".env.example"
    target = root / "docker" / ".env"

    if not example.exists():
        print("[warn] docker/.env.example not found – skipped")
        return

    if target.exists():
        print("[ok] docker/.env already exists")
        return

    shutil.copy2(example, target)
    print("[ok] Created docker/.env from .env.example")


def sanity_checks(root: Path) -> list[str]:
    """Return a list of missing critical paths (empty list = all good)."""
    required = [
        "app.py",
        "i18n.py",
        "requirements.txt",
        "auth/__init__.py",
        "auth/core.py",
        "auth/captcha.py",
        "tabs",
        "static/css/styles.css",
        "static/js/custom.js",
        "docker/Dockerfile",
        "01_requirements/update_requirements.py",
    ]
    missing = []
    for rel in required:
        if not (root / rel).exists():
            missing.append(rel)
    return missing


def main() -> int:
    root = find_project_root()
    print(f"Project root : {root}")
    print("-" * 50)

    ensure_db_directory(root)
    remove_shipped_database(root)
    ensure_docker_env(root)

    print("-" * 50)
    missing = sanity_checks(root)
    if missing:
        print("[error] Some critical files are missing:")
        for m in missing:
            print(f"        - {m}")
        print("\nPlease make sure you extracted the full project archive.")
        return 1

    print("[ok] All critical project files are present")
    print()
    print("=" * 50)
    print("Bootstrap finished successfully.")
    print()
    print("Next steps:")
    print("  1. python 01_requirements/update_requirements.py")
    print("  2. pip install -r requirements.txt")
    print("  3. shiny run app.py --reload")
    print()
    print("Or use Docker:")
    print("  cd docker && docker compose up --build -d")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
