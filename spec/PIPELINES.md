# Pipelines — Openclaw Mail Agent

## Overview

The pipeline runner framework (`openclaw_mail/pipelines/`) provides a generic,
testable abstraction for executing ordered sequences of steps. It powers both
the email filtering pipeline and the CI validation pipeline.

→ Pipeline step protocol: `spec/adrs/ARCH-005-pipeline-step-protocol.md`
→ Architecture decisions: `spec/adrs/`

## Core Concepts

### Pipeline Step Protocol

Any object with a `name` attribute and an `execute(context)` method:

```python
from openclaw_mail.pipelines import PipelineStep, StepResult

class MyStep:
    name = "my-check"

    def execute(self, context: dict) -> StepResult:
        # Do work...
        return StepResult(
            step_name=self.name,
            matched=True,
            confidence=0.95,
            reason="Check passed",
        )
```

### Execution Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `first_match` | Stop at first matching step | Email filtering |
| `sequential` | Run all steps regardless | CI validation |

### Pipeline Result

```python
from openclaw_mail.pipelines import Pipeline, ExecutionMode

pipeline = Pipeline(
    name="my-pipeline",
    steps=[step1, step2, step3],
    mode=ExecutionMode.SEQUENTIAL,
)

result = pipeline.run(context={"project_root": Path(".")})

print(result.summary)       # "3 steps: 2 passed, 1 failed, 0 skipped (42ms)"
print(result.all_passed)    # False
print(result.failed_steps)  # [StepResult(...)]
```

## Available Pipelines

### 1. Validation Pipeline (CI)

**Mode:** Sequential (all must pass)
**Trigger:** `poetry run validate` or GitHub Actions CI

Steps:
1. **Sensitive data scan** — no hardcoded passwords, API keys, or PII
2. **Gitignore check** — all sensitive paths covered by `.gitignore`
3. **ADR compliance** — all `spec/adrs/*.check.py` scripts pass

```bash
# Run locally
poetry run validate

# Run in CI (GitHub Actions)
# Automatically triggered on push/PR to main
```

### 2. Email Filter Pipeline

**Mode:** First-match (first step wins)
**Trigger:** `poetry run mail-tidy`

Steps:
1. **Address rules** — exact sender matching
2. **Keyword rules** — regex on subject+sender
3. **AI scoring** — score against folder definitions
4. **Review fallback** — unmatched → Review

→ Full details: `spec/ARCHITECTURE.md`

## ADR System

Architecture Decision Records live in `spec/adrs/`. Each ADR has:
- `ARCH-NNN-<name>.md` — human-readable decision document
- `ARCH-NNN-<name>.check.py` — machine-executable validation script

### Current ADRs

| ID | Decision | Check |
|----|----------|-------|
| ARCH-001 | No Hardcoded Credentials | Scans `.py` files for password/key assignments |
| ARCH-002 | Four-Step Filter Pipeline | Verifies pipeline structure and step order |
| ARCH-003 | Per-Account Config Fallback | Checks `_default.yaml` and `.gitignore` rules |
| ARCH-004 | Sensitive Data Separation | Verifies `.gitignore` and git tracking |
| ARCH-005 | Pipeline Step Protocol | Verifies runner module structure |

### Adding a New ADR

1. Create `spec/adrs/ARCH-NNN-<name>.md` with Context / Decision / Consequences
2. Create `spec/adrs/ARCH-NNN-<name>.check.py` with a `check(project_root) -> (bool, str)` function
3. The validation pipeline picks it up automatically — no registration needed

```python
# spec/adrs/ARCH-006-my-decision.check.py
from pathlib import Path

def check(project_root: Path) -> tuple[bool, str]:
    # Return (True, "message") if the check passes
    # Return (False, "message") if the check fails
    return True, "All good"
```

## GitHub Actions

CI runs automatically on every push to `main` and on pull requests:

```
.github/workflows/ci.yml
├── lint       — ruff check
├── test       — pytest + coverage (≥70%)
└── validate   — validation pipeline + secret scanning
```

### What CI Checks

1. **Lint** — code style via ruff
2. **Test** — all pytest tests pass, ≥70% coverage
3. **Validate** — runs `poetry run validate`:
   - Sensitive data scan (no hardcoded credentials)
   - Gitignore verification (sensitive paths blocked)
   - ADR compliance (all `.check.py` scripts pass)
4. **Secret scanning** — git-level check for tracked `.env` or `accounts.yaml`

### Local Pre-Push Verification

```bash
# Run the same checks CI runs
poetry run ruff check openclaw_mail/ tests/
poetry run pytest -v --cov=openclaw_mail --cov-fail-under=55
poetry run validate
```

## Creating a New Pipeline

1. Create step classes implementing `PipelineStep`:
   ```python
   from openclaw_mail.pipelines import PipelineStep, StepResult

   class MyCustomStep:
       name = "custom-check"
       def execute(self, context: dict) -> StepResult:
           ...
   ```

2. Assemble into a pipeline:
   ```python
   from openclaw_mail.pipelines import Pipeline, ExecutionMode

   pipeline = Pipeline(
       name="custom",
       steps=[MyCustomStep(), AnotherStep()],
       mode=ExecutionMode.SEQUENTIAL,
   )
   result = pipeline.run()
   ```

3. Add tests in `tests/test_<pipeline>.py`
4. Optionally add a CLI entrypoint in `pyproject.toml`

## File Structure

```
openclaw_mail/pipelines/
├── __init__.py         # Public API
├── runner.py           # Pipeline, PipelineStep, StepResult, PipelineResult
└── validation.py       # CI validation steps (sensitive data, gitignore, ADR)

spec/adrs/
├── ARCH-001-*.md       # Decision: No Hardcoded Credentials
├── ARCH-001-*.check.py # Machine-checkable validation
├── ARCH-002-*.md       # Decision: Four-Step Filter Pipeline
├── ARCH-002-*.check.py
├── ARCH-003-*.md       # Decision: Per-Account Config Fallback
├── ARCH-003-*.check.py
├── ARCH-004-*.md       # Decision: Sensitive Data Separation
├── ARCH-004-*.check.py
├── ARCH-005-*.md       # Decision: Pipeline Step Protocol
└── ARCH-005-*.check.py

.github/workflows/
└── ci.yml              # Lint + Test + Validate
```
