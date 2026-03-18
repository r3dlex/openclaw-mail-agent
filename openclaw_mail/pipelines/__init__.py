"""Generic pipeline runner framework.

Provides reusable Pipeline/PipelineStep/StepResult abstractions that can be
used for email filtering, CI validation, ADR compliance checks, and more.

→ Full documentation: spec/PIPELINES.md
"""

from openclaw_mail.pipelines.runner import (
    ExecutionMode,
    Pipeline,
    PipelineResult,
    PipelineStep,
    StepResult,
)

__all__ = [
    "ExecutionMode",
    "Pipeline",
    "PipelineResult",
    "PipelineStep",
    "StepResult",
]
