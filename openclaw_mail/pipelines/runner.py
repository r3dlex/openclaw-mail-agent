"""Generic pipeline runner with first-match and sequential execution modes.

A pipeline is an ordered sequence of steps.  Each step receives a shared
context dict, performs its work, and returns a ``StepResult``.

Two execution modes are supported:

- **first_match** — stop at the first step that matches (email filtering).
- **sequential** — run every step regardless of matches (CI validation).

→ Full documentation: spec/PIPELINES.md
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Execution modes
# ---------------------------------------------------------------------------

class ExecutionMode(str, Enum):
    """How a pipeline processes its steps."""

    FIRST_MATCH = "first_match"
    SEQUENTIAL = "sequential"


# ---------------------------------------------------------------------------
# Step result
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Outcome of a single pipeline step.

    Attributes:
        step_name: Human-readable step identifier.
        matched: Whether this step produced a positive match / passed.
        output: Arbitrary data produced by the step.
        confidence: Confidence score (0.0–1.0) for the match.
        reason: Human-readable explanation.
        duration_ms: Execution time in milliseconds.
        skipped: Whether the step was skipped (e.g. not applicable).
    """

    step_name: str
    matched: bool = False
    output: Any = None
    confidence: float = 0.0
    reason: str = ""
    duration_ms: float = 0.0
    skipped: bool = False


# ---------------------------------------------------------------------------
# Step protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class PipelineStep(Protocol):
    """Interface that every pipeline step must satisfy.

    Steps are duck-typed — any object with a ``name`` attribute and an
    ``execute(context)`` method works.
    """

    name: str

    def execute(self, context: dict[str, Any]) -> StepResult:
        """Run this step against the given context.

        Args:
            context: Shared mutable dict carried across steps.

        Returns:
            A ``StepResult`` describing the outcome.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Aggregate outcome of running a full pipeline.

    Attributes:
        steps: Results from every step that was executed.
        mode: The execution mode that was used.
        matched: Whether the pipeline as a whole produced a match.
        final_result: In ``first_match`` mode, the winning step's result.
                      In ``sequential`` mode, the last step's result.
        all_passed: In ``sequential`` mode, True if every step matched.
        duration_ms: Total pipeline execution time in milliseconds.
    """

    steps: list[StepResult] = field(default_factory=list)
    mode: str = ExecutionMode.FIRST_MATCH.value
    matched: bool = False
    final_result: StepResult | None = None
    all_passed: bool = True
    duration_ms: float = 0.0

    @property
    def failed_steps(self) -> list[StepResult]:
        """Return steps that did not match (useful in sequential mode)."""
        return [s for s in self.steps if not s.matched and not s.skipped]

    @property
    def summary(self) -> str:
        """One-line human-readable summary."""
        total = len(self.steps)
        passed = sum(1 for s in self.steps if s.matched)
        skipped = sum(1 for s in self.steps if s.skipped)
        failed = total - passed - skipped
        return (
            f"{total} steps: {passed} passed, {failed} failed, "
            f"{skipped} skipped ({self.duration_ms:.0f}ms)"
        )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """Execute an ordered sequence of steps in a given mode.

    Args:
        name: Pipeline identifier (for logging / reports).
        steps: Ordered list of ``PipelineStep`` objects.
        mode: ``first_match`` or ``sequential``.
    """

    def __init__(
        self,
        name: str,
        steps: list[PipelineStep],
        mode: ExecutionMode = ExecutionMode.FIRST_MATCH,
    ) -> None:
        self.name = name
        self.steps = list(steps)
        self.mode = mode

    def run(self, context: dict[str, Any] | None = None) -> PipelineResult:
        """Execute the pipeline and return the aggregate result.

        Args:
            context: Shared mutable dict passed to every step.
                     A new dict is created if ``None``.

        Returns:
            ``PipelineResult`` with per-step results and aggregate metrics.
        """
        if context is None:
            context = {}

        result = PipelineResult(mode=self.mode.value)
        pipeline_start = time.monotonic()

        for step in self.steps:
            step_start = time.monotonic()
            step_result = step.execute(context)
            step_result.duration_ms = (time.monotonic() - step_start) * 1000
            step_result.step_name = step.name
            result.steps.append(step_result)

            if step_result.matched:
                result.matched = True
                result.final_result = step_result

                if self.mode == ExecutionMode.FIRST_MATCH:
                    break
            elif not step_result.skipped:
                result.all_passed = False

        # In sequential mode, final_result is the last step
        if self.mode == ExecutionMode.SEQUENTIAL and result.steps:
            result.final_result = result.steps[-1]

        result.duration_ms = (time.monotonic() - pipeline_start) * 1000
        return result

    def __repr__(self) -> str:
        return f"Pipeline({self.name!r}, steps={len(self.steps)}, mode={self.mode.value})"
