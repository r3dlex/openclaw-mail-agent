"""ARCH-003: Verify per-account config fallback mechanism.

Checks that:
1. _default.yaml exists with required keys
2. .gitignore blocks real account configs but allows _default and examples
3. Example files exist for documentation
"""

from __future__ import annotations

from pathlib import Path

import yaml


def check(project_root: Path) -> tuple[bool, str]:
    """Return (passed, message)."""
    errors: list[str] = []

    # 1. _default.yaml exists with required keys
    default_file = project_root / "config" / "filters" / "_default.yaml"
    if not default_file.exists():
        errors.append("config/filters/_default.yaml not found")
    else:
        data = yaml.safe_load(default_file.read_text()) or {}
        for key in ("ai_score_threshold", "review_folder", "folder_definitions"):
            if key not in data:
                errors.append(f"_default.yaml missing key: {key}")

    # 2. .gitignore protects real configs
    gitignore = project_root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        required = [
            "config/filters/*.yaml",
            "!config/filters/_default.yaml",
            "!config/filters/*.yaml.example",
        ]
        for pattern in required:
            if pattern not in content:
                errors.append(f".gitignore missing: {pattern}")
    else:
        errors.append(".gitignore not found")

    # 3. At least one .yaml.example exists
    examples = list((project_root / "config" / "filters").glob("*.yaml.example"))
    if not examples:
        errors.append("No .yaml.example files found in config/filters/")

    if errors:
        return False, "Config fallback issues:\n  " + "\n  ".join(errors)

    return True, f"Config fallback verified ({len(examples)} example files)"
