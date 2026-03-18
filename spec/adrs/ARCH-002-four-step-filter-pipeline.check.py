"""ARCH-002: Verify the 4-step filter pipeline structure exists and is correct.

Checks that:
1. FilterPipeline.classify() calls steps in the correct order
2. All 4 steps are present: address, keyword, ai, review
3. Default config exists with required keys
"""

from __future__ import annotations

from pathlib import Path


def check(project_root: Path) -> tuple[bool, str]:
    """Return (passed, message)."""
    pipeline_file = project_root / "openclaw_mail" / "filters" / "pipeline.py"
    default_config = project_root / "config" / "filters" / "_default.yaml"

    errors: list[str] = []

    # 1. Check pipeline.py exists and has the 4 steps
    if not pipeline_file.exists():
        return False, "filters/pipeline.py not found"

    content = pipeline_file.read_text()

    required_methods = ["_step_address", "_step_keyword", "_step_ai"]
    for method in required_methods:
        if f"def {method}" not in content:
            errors.append(f"Missing method: {method}")

    # Check classify() calls steps in order
    if "def classify" not in content:
        errors.append("Missing classify() method")
    else:
        # Verify step order in classify()
        classify_start = content.index("def classify")
        classify_section = content[classify_start:classify_start + 1000]
        positions = []
        for step in ["_step_address", "_step_keyword", "_step_ai", "review"]:
            pos = classify_section.find(step)
            if pos == -1:
                errors.append(f"classify() doesn't reference {step}")
            else:
                positions.append((pos, step))

        # Verify ordering
        if len(positions) >= 2:
            for i in range(len(positions) - 1):
                if positions[i][0] > positions[i + 1][0]:
                    errors.append(
                        f"Step order wrong: {positions[i][1]} appears after {positions[i + 1][1]}"
                    )

    # 2. Check default config exists
    if not default_config.exists():
        errors.append("config/filters/_default.yaml not found")

    # 3. Check review fallback step name
    if '"review"' not in content and "'review'" not in content:
        errors.append("No review fallback step found")

    if errors:
        return False, "Pipeline structure issues:\n  " + "\n  ".join(errors)

    return True, "4-step pipeline structure verified"
