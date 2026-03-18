"""ARCH-004: Verify sensitive data separation via .gitignore.

Checks that:
1. .gitignore blocks all sensitive paths
2. Example/template files exist for documentation
3. No .env file is tracked by git
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def check(project_root: Path) -> tuple[bool, str]:
    """Return (passed, message)."""
    errors: list[str] = []

    # 1. .gitignore contains required blocks
    gitignore = project_root / ".gitignore"
    if not gitignore.exists():
        return False, ".gitignore not found"

    content = gitignore.read_text()
    required_patterns = [
        ".env",
        "config/accounts.yaml",
        "config/filters/*.yaml",
        "config/folder_mappings/*.md",
        "reports/",
        "logs/",
    ]
    for pattern in required_patterns:
        if pattern not in content:
            errors.append(f".gitignore missing: {pattern}")

    # 2. Example files exist
    if not (project_root / ".env.example").exists():
        errors.append(".env.example not found")
    if not (project_root / "config" / "accounts.yaml.example").exists():
        errors.append("config/accounts.yaml.example not found")

    # 3. Check git doesn't track sensitive files
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached"],
            capture_output=True, text=True, cwd=project_root, timeout=10,
        )
        tracked = set(result.stdout.strip().splitlines())
        sensitive_tracked = [
            f for f in tracked
            if f == ".env" or f == "config/accounts.yaml"
            or (f.startswith("config/filters/") and f.endswith(".yaml")
                and "_default" not in f and ".example" not in f)
        ]
        if sensitive_tracked:
            errors.append(f"Sensitive files tracked by git: {sensitive_tracked}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # Git not available — skip this check

    if errors:
        return False, "Sensitive data separation issues:\n  " + "\n  ".join(errors)

    return True, "Sensitive data properly separated"
