#!/usr/bin/env python3
"""
01_requirements / update_requirements.py
-----------------------------------------
Step 1 of installation: automatically scan all Python files in the project
and update requirements.txt based on detected import statements.

Features
--------
- Detects both ``import X`` and ``from X import Y``
- Maps module names to PyPI package names (e.g. PIL -> Pillow)
- Ignores the Python standard library and local project packages
- Avoids duplicate entries
- Preserves existing version pins when present
- Adds newly discovered packages with sensible minimum-version constraints

Usage (from project root)
-------------------------
    python 01_requirements/update_requirements.py

Dry-run (show changes without writing the file)
-----------------------------------------------
    python 01_requirements/update_requirements.py --dry-run
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Dict, Set

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Local project packages that must never be written to requirements.txt
LOCAL_PACKAGES: Set[str] = {
    "auth",
    "tabs",
    "db",
    "static",
    "docker",
}

# Module name (as written in import statements) -> PyPI package name
MODULE_TO_PACKAGE: Dict[str, str] = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil",
    "dotenv": "python-dotenv",
    "jwt": "PyJWT",
    "Crypto": "pycryptodome",
    "OpenSSL": "pyOpenSSL",
    "gi": "PyGObject",
    "wx": "wxPython",
    "serial": "pyserial",
    "usb": "pyusb",
    "MySQLdb": "mysqlclient",
    "psycopg2": "psycopg2-binary",
    "matplotlib": "matplotlib",
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "requests": "requests",
    "flask": "Flask",
    "django": "Django",
    "shiny": "shiny",
    "plotly": "plotly",
    "seaborn": "seaborn",
    "bokeh": "bokeh",
    "dash": "dash",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "alembic",
    "celery": "celery",
    "redis": "redis",
    "boto3": "boto3",
    "botocore": "botocore",
    "tensorflow": "tensorflow",
    "torch": "torch",
    "transformers": "transformers",
}

# Recommended minimum versions for commonly used packages
DEFAULT_MIN_VERSIONS: Dict[str, str] = {
    "shiny": ">=1.4",
    "Pillow": ">=10.0",
    "numpy": ">=1.24",
    "matplotlib": ">=3.7",
    "pandas": ">=2.0",
    "scipy": ">=1.10",
    "requests": ">=2.28",
}

# File extensions to scan
PY_EXTENSIONS = {".py"}

# Directory names that are skipped during the scan
IGNORE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".tox",
}


def find_project_root() -> Path:
    """Locate the project root (directory that contains requirements.txt or app.py)."""
    script_dir = Path(__file__).resolve().parent
    if script_dir.name == "01_requirements":
        candidate = script_dir.parent
        if (candidate / "requirements.txt").exists() or (candidate / "app.py").exists():
            return candidate
    if (script_dir / "requirements.txt").exists() or (script_dir / "app.py").exists():
        return script_dir
    cwd = Path.cwd()
    if (cwd / "requirements.txt").exists() or (cwd / "app.py").exists():
        return cwd
    return script_dir.parent if script_dir.name == "01_requirements" else script_dir


def get_stdlib_names() -> Set[str]:
    """Return the set of Python standard-library module names."""
    names: Set[str] = set(sys.builtin_module_names)
    if hasattr(sys, "stdlib_module_names"):
        names |= set(sys.stdlib_module_names)
    names.add("__future__")
    return names


def is_local_or_relative(module_name: str, project_root: Path) -> bool:
    """Return True if the module belongs to this project."""
    top = module_name.split(".")[0]
    if top in LOCAL_PACKAGES:
        return True
    if (project_root / top).is_dir() or (project_root / f"{top}.py").is_file():
        return True
    return False


def extract_imports_from_file(filepath: Path) -> Set[str]:
    """Extract top-level module names from a Python source file using AST."""
    imports: Set[str] = set()
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # import numpy as np  ->  numpy
                # import matplotlib.pyplot  ->  matplotlib
                top = alias.name.split(".")[0]
                imports.add(top)
        elif isinstance(node, ast.ImportFrom):
            # from matplotlib import pyplot  ->  matplotlib
            # from . import something         ->  relative (ignored)
            # from auth.core import x         ->  auth
            if node.module is None or node.level > 0:
                continue
            top = node.module.split(".")[0]
            imports.add(top)
    return imports


def collect_all_imports(project_root: Path) -> Set[str]:
    """Walk the project tree and collect every top-level import."""
    all_imports: Set[str] = set()
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in PY_EXTENSIONS:
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        file_imports = extract_imports_from_file(path)
        all_imports |= file_imports
    return all_imports


def resolve_package_name(module: str) -> str:
    """Map an import name to the corresponding PyPI package name."""
    return MODULE_TO_PACKAGE.get(module, module)


def parse_existing_requirements(req_path: Path) -> Dict[str, str]:
    """
    Parse an existing requirements.txt file.

    Returns a dictionary mapping package name (lower-case) to the full
    requirement line (including any version specifier).
    """
    existing: Dict[str, str] = {}
    if not req_path.exists():
        return existing
    for line in req_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for sep in (">=", "<=", "==", "~=", ">", "<", "!="):
            if sep in stripped:
                name = stripped.split(sep)[0].strip()
                existing[name.lower()] = stripped
                break
        else:
            existing[stripped.lower()] = stripped
    return existing


def update_requirements(
    project_root: Path,
    dry_run: bool = False,
) -> list[str]:
    """
    Core logic: scan -> filter -> merge with existing requirements -> write.

    Returns the list of newly added requirement lines.
    """
    stdlib = get_stdlib_names()
    all_modules = collect_all_imports(project_root)

    third_party: Set[str] = set()
    for mod in sorted(all_modules):
        if mod in stdlib:
            continue
        if is_local_or_relative(mod, project_root):
            continue
        if mod.startswith("_"):
            continue
        pkg = resolve_package_name(mod)
        third_party.add(pkg)

    req_path = project_root / "requirements.txt"
    existing = parse_existing_requirements(req_path)

    final_lines: list[str] = []
    seen: Set[str] = set()

    # Keep existing entries (and their original order / version pins)
    if req_path.exists():
        for line in req_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                final_lines.append(line)
                continue
            name = stripped
            for sep in (">=", "<=", "==", "~=", ">", "<", "!="):
                if sep in stripped:
                    name = stripped.split(sep)[0].strip()
                    break
            key = name.lower()
            if key not in seen:
                final_lines.append(stripped)
                seen.add(key)

    # Append any newly discovered packages
    newly_added: list[str] = []
    for pkg in sorted(third_party):
        key = pkg.lower()
        if key in seen:
            continue
        if pkg in DEFAULT_MIN_VERSIONS:
            line = f"{pkg}{DEFAULT_MIN_VERSIONS[pkg]}"
        else:
            line = pkg
        final_lines.append(line)
        seen.add(key)
        newly_added.append(line)

    content = "\n".join(final_lines).rstrip() + "\n"
    if not dry_run:
        req_path.write_text(content, encoding="utf-8")

    return newly_added


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan Python files and automatically update requirements.txt"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing the file",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Project root path (default: auto-detect)",
    )
    args = parser.parse_args()

    project_root = Path(args.root).resolve() if args.root else find_project_root()
    print(f"Project root : {project_root}")
    print(f"requirements : {project_root / 'requirements.txt'}")
    print("-" * 50)

    all_mods = collect_all_imports(project_root)
    stdlib = get_stdlib_names()
    print("Modules found:")
    for m in sorted(all_mods):
        if m in stdlib:
            tag = "(stdlib)"
        elif is_local_or_relative(m, project_root):
            tag = "(local)"
        else:
            tag = f"-> {resolve_package_name(m)}"
        print(f"   * {m:20s} {tag}")
    print("-" * 50)

    newly = update_requirements(project_root, dry_run=args.dry_run)

    if newly:
        print("Newly added packages:")
        for line in newly:
            print(f"   + {line}")
    else:
        print("No new packages needed (all already present).")

    if args.dry_run:
        print("\n[DRY-RUN] File was NOT modified.")
    else:
        print("\nrequirements.txt updated successfully.")
        print("\nCurrent content:")
        print((project_root / "requirements.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
