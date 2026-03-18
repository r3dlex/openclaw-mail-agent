"""ARCH-005: Verify the pipeline step protocol is properly implemented.

Checks that:
1. PipelineStep protocol exists with name + execute
2. Pipeline supports both first_match and sequential modes
3. StepResult and PipelineResult dataclasses exist
"""

from __future__ import annotations

from pathlib import Path


def check(project_root: Path) -> tuple[bool, str]:
    """Return (passed, message)."""
    errors: list[str] = []

    runner_file = project_root / "openclaw_mail" / "pipelines" / "runner.py"
    if not runner_file.exists():
        return False, "openclaw_mail/pipelines/runner.py not found"

    content = runner_file.read_text()

    # 1. PipelineStep protocol
    if "class PipelineStep" not in content:
        errors.append("PipelineStep class not found")
    if "def execute" not in content:
        errors.append("execute() method not found in PipelineStep")
    if "name: str" not in content:
        errors.append("name attribute not found in PipelineStep")

    # 2. Execution modes
    if "FIRST_MATCH" not in content:
        errors.append("FIRST_MATCH execution mode not found")
    if "SEQUENTIAL" not in content:
        errors.append("SEQUENTIAL execution mode not found")

    # 3. Data classes
    for cls in ("StepResult", "PipelineResult"):
        if f"class {cls}" not in content:
            errors.append(f"{cls} class not found")

    # 4. Pipeline class
    if "class Pipeline" not in content:
        errors.append("Pipeline class not found")
    if "def run" not in content:
        errors.append("Pipeline.run() method not found")

    if errors:
        return False, "Pipeline protocol issues:\n  " + "\n  ".join(errors)

    return True, "Pipeline step protocol verified"
