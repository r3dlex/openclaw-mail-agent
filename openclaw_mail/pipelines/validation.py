"""Validation pipeline — runs ADR compliance checks and sensitive data scans.

Used by GitHub Actions CI and local ``poetry run validate`` to ensure the
codebase stays compliant with architecture decisions.

→ ADR definitions: spec/adrs/
→ Full documentation: spec/PIPELINES.md
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openclaw_mail.pipelines.runner import (
    ExecutionMode,
    Pipeline,
    StepResult,
)

# ---------------------------------------------------------------------------
# Project root (works from any CWD)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Sensitive data scanner step
# ---------------------------------------------------------------------------

# Patterns that should NEVER appear in committed files
_SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)password\s*=\s*['\"][^'\"]+['\"]", "Hardcoded password assignment"),
    (r"(?i)api[_-]?key\s*=\s*['\"][^'\"]+['\"]", "Hardcoded API key"),
    (r"(?i)secret\s*=\s*['\"][^'\"]+['\"]", "Hardcoded secret"),
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "Email address"),
]

# Files/dirs to skip when scanning
_SKIP_PATTERNS: set[str] = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    "artifacts", ".openclaw", ".env", "reports", "logs", "memory",
}

# Extensions to scan
_SCAN_EXTENSIONS: set[str] = {".py", ".yaml", ".yml", ".toml", ".md", ".sh", ".json"}

# Files where email patterns are expected (test fixtures, examples, docs)
_EMAIL_ALLOWED_FILES: set[str] = {
    "conftest.py", "test_pipeline.py", "test_himalaya.py", "test_mq.py", "test_calendar.py",
    "accounts.yaml.example", "_default.yaml",
    "work_main.yaml.example", "personal_main.yaml.example",
    "system_account.yaml.example", "r3dtuxedo.yaml.example", "_example.md",
    "ARCHITECTURE.md", "AGENTS.md", "CLAUDE.md", "README.md",
    "TROUBLESHOOTING.md", "TESTING.md", "PIPELINES.md",
    "validation.py",  # this file contains patterns
    "pyproject.toml",  # contains author email potentially
}


@dataclass
class SensitiveDataStep:
    """Scan committed files for hardcoded credentials and PII."""

    name: str = "sensitive-data-scan"

    def execute(self, context: dict[str, Any]) -> StepResult:
        root = context.get("project_root", PROJECT_ROOT)
        violations: list[str] = []

        for path in _iter_files(root):
            rel = path.relative_to(root)
            try:
                content = path.read_text(errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue

            is_test = _is_test_file(path)
            for pattern, desc in _SENSITIVE_PATTERNS:
                if desc == "Email address" and rel.name in _EMAIL_ALLOWED_FILES:
                    continue
                # Test files may contain intentional hardcoded values for testing
                if is_test and desc != "Email address":
                    continue
                for match in re.finditer(pattern, content):
                    # Skip env-variable references (os.getenv, get_env, etc.)
                    line = _get_line(content, match.start())
                    if _is_env_reference(line):
                        continue
                    violations.append(f"{rel}:{_line_number(content, match.start())}: {desc}")

        if violations:
            return StepResult(
                step_name=self.name,
                matched=False,
                reason=f"Found {len(violations)} sensitive data violations",
                output=violations[:20],  # Cap output
            )
        return StepResult(
            step_name=self.name,
            matched=True,
            reason="No sensitive data found in committed files",
        )


def _iter_files(root: Path):
    """Yield git-tracked files eligible for scanning.

    Uses ``git ls-files`` to only scan files that would be committed.
    Falls back to rglob if git is unavailable.
    """
    tracked = _git_tracked_files(root)
    if tracked is not None:
        for rel_path in tracked:
            path = root / rel_path
            if path.suffix in _SCAN_EXTENSIONS and path.is_file():
                yield path
    else:
        # Fallback: scan all files, skipping known dirs
        for path in root.rglob("*"):
            if any(part in _SKIP_PATTERNS for part in path.parts):
                continue
            if path.is_file() and path.suffix in _SCAN_EXTENSIONS:
                yield path


def _git_tracked_files(root: Path) -> list[str] | None:
    """Return list of git-tracked file paths, or None if git unavailable."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached"],
            capture_output=True, text=True, cwd=root, timeout=10,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().splitlines() if f]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _get_line(content: str, pos: int) -> str:
    """Get the full line containing the character at ``pos``."""
    start = content.rfind("\n", 0, pos) + 1
    end = content.find("\n", pos)
    return content[start:end] if end != -1 else content[start:]


def _line_number(content: str, pos: int) -> int:
    return content[:pos].count("\n") + 1


def _is_env_reference(line: str) -> bool:
    """Return True if the line is an env variable reference, not a hardcoded value."""
    env_patterns = [
        "os.getenv", "os.environ", "get_env(", "getenv(",
        "_env", "ENV", "env_key", "env:",
        "#", "example", "template", "placeholder",
        "user@", "noreply@", "a@b.com", "boss@company.com",
        "ceo@company.com", "@company.com", "@notifications.",
        "@vendor.", "@bank.", "@newsletter.", "@unknown.",
        "billing@", "accounting@", "bot@",
        "@example.com", "@example.org",
    ]
    return any(p in line for p in env_patterns)


def _is_test_file(path: Path) -> bool:
    """Return True if the file is a test file where hardcoded values are expected."""
    return path.name.startswith("test_") or path.name == "conftest.py"


# ---------------------------------------------------------------------------
# ADR compliance step
# ---------------------------------------------------------------------------

@dataclass
class ADRComplianceStep:
    """Run all ADR .check.py scripts and report results."""

    name: str = "adr-compliance"

    def execute(self, context: dict[str, Any]) -> StepResult:
        root = context.get("project_root", PROJECT_ROOT)
        adr_dir = root / "spec" / "adrs"

        if not adr_dir.exists():
            return StepResult(
                step_name=self.name,
                matched=True,
                reason="No ADR directory found — skipping",
                skipped=True,
            )

        check_files = sorted(adr_dir.glob("*.check.py"))
        if not check_files:
            return StepResult(
                step_name=self.name,
                matched=True,
                reason="No ADR checks found — skipping",
                skipped=True,
            )

        results: list[dict] = []
        all_passed = True

        for check_file in check_files:
            adr_name = check_file.stem.replace(".check", "")
            try:
                passed, message = _run_adr_check(check_file, root)
                results.append({
                    "adr": adr_name,
                    "passed": passed,
                    "message": message,
                })
                if not passed:
                    all_passed = False
            except Exception as e:
                results.append({
                    "adr": adr_name,
                    "passed": False,
                    "message": f"Check crashed: {e}",
                })
                all_passed = False

        total = len(results)
        passed_count = sum(1 for r in results if r["passed"])

        return StepResult(
            step_name=self.name,
            matched=all_passed,
            confidence=passed_count / total if total else 1.0,
            reason=f"ADR checks: {passed_count}/{total} passed",
            output=results,
        )


def _run_adr_check(check_file: Path, project_root: Path) -> tuple[bool, str]:
    """Import and execute an ADR check module.

    Each check module must define a ``check(project_root: Path) -> tuple[bool, str]``
    function that returns ``(passed, message)``.
    """
    spec = importlib.util.spec_from_file_location(check_file.stem, check_file)
    if spec is None or spec.loader is None:
        return False, f"Could not load {check_file}"

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    check_fn = getattr(module, "check", None)
    if check_fn is None:
        return False, f"No check() function in {check_file.name}"

    return check_fn(project_root)


# ---------------------------------------------------------------------------
# Gitignore verification step
# ---------------------------------------------------------------------------

@dataclass
class GitignoreStep:
    """Verify that sensitive paths are covered by .gitignore."""

    name: str = "gitignore-check"

    REQUIRED_PATTERNS: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.REQUIRED_PATTERNS is None:
            self.REQUIRED_PATTERNS = [
                ".env",
                "config/accounts.yaml",
                "config/filters/*.yaml",
                "config/folder_mappings/*.md",
                "reports/",
                "logs/",
                "memory/",
                "artifacts/",
            ]

    def execute(self, context: dict[str, Any]) -> StepResult:
        root = context.get("project_root", PROJECT_ROOT)
        gitignore = root / ".gitignore"

        if not gitignore.exists():
            return StepResult(
                step_name=self.name,
                matched=False,
                reason="No .gitignore found",
            )

        content = gitignore.read_text()
        missing: list[str] = []

        for pattern in self.REQUIRED_PATTERNS:
            if pattern not in content:
                missing.append(pattern)

        if missing:
            return StepResult(
                step_name=self.name,
                matched=False,
                reason=f"Missing {len(missing)} required .gitignore patterns",
                output=missing,
            )
        return StepResult(
            step_name=self.name,
            matched=True,
            reason="All required patterns present in .gitignore",
        )


# ---------------------------------------------------------------------------
# Factory — build the full validation pipeline
# ---------------------------------------------------------------------------

def build_validation_pipeline() -> Pipeline:
    """Create the standard validation pipeline used by CI.

    Steps (sequential — all must pass):
      1. Sensitive data scan
      2. Gitignore verification
      3. ADR compliance checks
    """
    return Pipeline(
        name="validation",
        steps=[
            SensitiveDataStep(),
            GitignoreStep(),
            ADRComplianceStep(),
        ],
        mode=ExecutionMode.SEQUENTIAL,
    )
