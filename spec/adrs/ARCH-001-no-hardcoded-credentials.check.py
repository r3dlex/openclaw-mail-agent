"""ARCH-001: Verify no hardcoded credentials in Python source files.

Scans all .py files for password/secret/key assignments that aren't
environment variable references.
"""

from __future__ import annotations

import re
from pathlib import Path

# Patterns that indicate hardcoded credentials
CREDENTIAL_PATTERNS = [
    (r'(?i)password\s*=\s*["\'][^"\']{4,}["\']', "hardcoded password"),
    (r'(?i)api[_-]?key\s*=\s*["\'][^"\']{8,}["\']', "hardcoded API key"),
    (r'(?i)secret\s*=\s*["\'][^"\']{8,}["\']', "hardcoded secret"),
    (r'(?i)token\s*=\s*["\'][^"\']{8,}["\']', "hardcoded token"),
]

# Lines containing these strings are env references (safe)
ENV_MARKERS = [
    "os.getenv", "os.environ", "get_env(", "getenv(",
    "_env", "ENV", "env_key", "#", "example", "test",
    "mock", "fixture", "placeholder", "dummy",
]

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "artifacts", ".openclaw"}


def check(project_root: Path) -> tuple[bool, str]:
    """Return (passed, message)."""
    violations: list[str] = []

    for py_file in project_root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in py_file.parts):
            continue
        # Skip test files — they contain intentional hardcoded values for testing
        if py_file.name.startswith("test_") or py_file.name == "conftest.py":
            continue

        try:
            content = py_file.read_text(errors="ignore")
        except OSError:
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            # Skip lines that are env references
            if any(marker in line for marker in ENV_MARKERS):
                continue

            for pattern, desc in CREDENTIAL_PATTERNS:
                if re.search(pattern, line):
                    rel = py_file.relative_to(project_root)
                    violations.append(f"  {rel}:{line_num}: {desc}")

    if violations:
        detail = "\n".join(violations[:10])
        return False, f"Found {len(violations)} hardcoded credentials:\n{detail}"

    return True, "No hardcoded credentials found"
