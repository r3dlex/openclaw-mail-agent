"""Tests for the generic pipeline runner framework."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


from openclaw_mail.pipelines.runner import (
    ExecutionMode,
    Pipeline,
    PipelineResult,
    PipelineStep,
    StepResult,
)


# ---------------------------------------------------------------------------
# Test step implementations
# ---------------------------------------------------------------------------


@dataclass
class AlwaysMatchStep:
    """Step that always matches."""
    name: str = "always-match"
    confidence: float = 1.0

    def execute(self, context: dict[str, Any]) -> StepResult:
        return StepResult(step_name=self.name, matched=True, confidence=self.confidence, reason="Always matches")


@dataclass
class NeverMatchStep:
    """Step that never matches."""
    name: str = "never-match"

    def execute(self, context: dict[str, Any]) -> StepResult:
        return StepResult(step_name=self.name, matched=False, reason="Never matches")


@dataclass
class SkippedStep:
    """Step that skips itself."""
    name: str = "skipped"

    def execute(self, context: dict[str, Any]) -> StepResult:
        return StepResult(step_name=self.name, skipped=True, reason="Not applicable")


@dataclass
class ContextWriterStep:
    """Step that writes to the shared context."""
    name: str = "context-writer"
    key: str = "visited"

    def execute(self, context: dict[str, Any]) -> StepResult:
        context.setdefault("visits", []).append(self.name)
        return StepResult(step_name=self.name, matched=True, reason="Wrote to context")


@dataclass
class ConditionalStep:
    """Step that matches only if a context key is present."""
    name: str = "conditional"
    required_key: str = "trigger"

    def execute(self, context: dict[str, Any]) -> StepResult:
        if self.required_key in context:
            return StepResult(step_name=self.name, matched=True, reason="Key found")
        return StepResult(step_name=self.name, matched=False, reason="Key missing")


# ---------------------------------------------------------------------------
# StepResult tests
# ---------------------------------------------------------------------------


class TestStepResult:
    def test_defaults(self):
        r = StepResult(step_name="test")
        assert r.matched is False
        assert r.confidence == 0.0
        assert r.skipped is False

    def test_matched(self):
        r = StepResult(step_name="test", matched=True, confidence=0.95)
        assert r.matched is True
        assert r.confidence == 0.95


# ---------------------------------------------------------------------------
# PipelineResult tests
# ---------------------------------------------------------------------------


class TestPipelineResult:
    def test_failed_steps(self):
        r = PipelineResult(steps=[
            StepResult(step_name="a", matched=True),
            StepResult(step_name="b", matched=False),
            StepResult(step_name="c", matched=True),
            StepResult(step_name="d", skipped=True),
        ])
        assert len(r.failed_steps) == 1
        assert r.failed_steps[0].step_name == "b"

    def test_summary(self):
        r = PipelineResult(
            steps=[
                StepResult(step_name="a", matched=True),
                StepResult(step_name="b", matched=False),
                StepResult(step_name="c", skipped=True),
            ],
            duration_ms=42.5,
        )
        assert "3 steps" in r.summary
        assert "1 passed" in r.summary
        assert "1 failed" in r.summary
        assert "1 skipped" in r.summary


# ---------------------------------------------------------------------------
# Pipeline — first_match mode
# ---------------------------------------------------------------------------


class TestFirstMatchPipeline:
    def test_stops_at_first_match(self):
        pipeline = Pipeline(
            name="test",
            steps=[NeverMatchStep(), AlwaysMatchStep(name="winner"), AlwaysMatchStep(name="should-not-run")],
            mode=ExecutionMode.FIRST_MATCH,
        )
        result = pipeline.run()
        assert result.matched is True
        assert result.final_result.step_name == "winner"
        assert len(result.steps) == 2  # Third step never ran

    def test_no_match_returns_unmatched(self):
        pipeline = Pipeline(
            name="test",
            steps=[NeverMatchStep(), NeverMatchStep()],
            mode=ExecutionMode.FIRST_MATCH,
        )
        result = pipeline.run()
        assert result.matched is False
        assert len(result.steps) == 2

    def test_first_step_matches(self):
        pipeline = Pipeline(
            name="test",
            steps=[AlwaysMatchStep(), NeverMatchStep()],
            mode=ExecutionMode.FIRST_MATCH,
        )
        result = pipeline.run()
        assert result.matched is True
        assert len(result.steps) == 1

    def test_empty_pipeline(self):
        pipeline = Pipeline(name="empty", steps=[], mode=ExecutionMode.FIRST_MATCH)
        result = pipeline.run()
        assert result.matched is False
        assert len(result.steps) == 0

    def test_skipped_steps_dont_count_as_match(self):
        pipeline = Pipeline(
            name="test",
            steps=[SkippedStep(), AlwaysMatchStep()],
            mode=ExecutionMode.FIRST_MATCH,
        )
        result = pipeline.run()
        # Skipped step doesn't stop the pipeline
        assert result.final_result.step_name == "always-match"
        assert len(result.steps) == 2


# ---------------------------------------------------------------------------
# Pipeline — sequential mode
# ---------------------------------------------------------------------------


class TestSequentialPipeline:
    def test_runs_all_steps(self):
        pipeline = Pipeline(
            name="test",
            steps=[AlwaysMatchStep(name="a"), AlwaysMatchStep(name="b"), AlwaysMatchStep(name="c")],
            mode=ExecutionMode.SEQUENTIAL,
        )
        result = pipeline.run()
        assert len(result.steps) == 3
        assert result.all_passed is True
        assert result.matched is True

    def test_continues_after_failure(self):
        pipeline = Pipeline(
            name="test",
            steps=[AlwaysMatchStep(name="a"), NeverMatchStep(), AlwaysMatchStep(name="c")],
            mode=ExecutionMode.SEQUENTIAL,
        )
        result = pipeline.run()
        assert len(result.steps) == 3  # All ran
        assert result.all_passed is False
        assert result.matched is True  # At least one matched

    def test_all_fail(self):
        pipeline = Pipeline(
            name="test",
            steps=[NeverMatchStep(name="a"), NeverMatchStep(name="b")],
            mode=ExecutionMode.SEQUENTIAL,
        )
        result = pipeline.run()
        assert result.all_passed is False
        assert result.matched is False

    def test_final_result_is_last_step(self):
        pipeline = Pipeline(
            name="test",
            steps=[AlwaysMatchStep(name="first"), NeverMatchStep(name="last")],
            mode=ExecutionMode.SEQUENTIAL,
        )
        result = pipeline.run()
        assert result.final_result.step_name == "last"

    def test_skipped_steps_dont_affect_all_passed(self):
        pipeline = Pipeline(
            name="test",
            steps=[AlwaysMatchStep(), SkippedStep()],
            mode=ExecutionMode.SEQUENTIAL,
        )
        result = pipeline.run()
        assert result.all_passed is True  # Skipped doesn't count as failure


# ---------------------------------------------------------------------------
# Context sharing
# ---------------------------------------------------------------------------


class TestContextSharing:
    def test_context_passed_between_steps(self):
        pipeline = Pipeline(
            name="test",
            steps=[
                ContextWriterStep(name="step-1"),
                ContextWriterStep(name="step-2"),
            ],
            mode=ExecutionMode.SEQUENTIAL,
        )
        ctx: dict = {}
        pipeline.run(context=ctx)
        assert ctx["visits"] == ["step-1", "step-2"]

    def test_default_context_created(self):
        pipeline = Pipeline(
            name="test",
            steps=[ContextWriterStep()],
            mode=ExecutionMode.SEQUENTIAL,
        )
        result = pipeline.run()  # No context passed — should create one
        assert len(result.steps) == 1

    def test_conditional_step_uses_context(self):
        pipeline = Pipeline(
            name="test",
            steps=[ConditionalStep()],
            mode=ExecutionMode.FIRST_MATCH,
        )
        # Without trigger key
        result = pipeline.run(context={})
        assert result.matched is False

        # With trigger key
        result = pipeline.run(context={"trigger": True})
        assert result.matched is True


# ---------------------------------------------------------------------------
# PipelineStep protocol compliance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_protocol_check(self):
        """Verify our test steps satisfy the PipelineStep protocol."""
        assert isinstance(AlwaysMatchStep(), PipelineStep)
        assert isinstance(NeverMatchStep(), PipelineStep)
        assert isinstance(SkippedStep(), PipelineStep)

    def test_non_compliant_rejected(self):
        """Objects without name/execute don't satisfy PipelineStep."""

        class BadStep:
            pass

        assert not isinstance(BadStep(), PipelineStep)


# ---------------------------------------------------------------------------
# Duration tracking
# ---------------------------------------------------------------------------


class TestDuration:
    def test_step_duration_tracked(self):
        pipeline = Pipeline(
            name="test",
            steps=[AlwaysMatchStep()],
            mode=ExecutionMode.SEQUENTIAL,
        )
        result = pipeline.run()
        assert result.steps[0].duration_ms >= 0

    def test_pipeline_duration_tracked(self):
        pipeline = Pipeline(
            name="test",
            steps=[AlwaysMatchStep(), AlwaysMatchStep()],
            mode=ExecutionMode.SEQUENTIAL,
        )
        result = pipeline.run()
        assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# Pipeline repr
# ---------------------------------------------------------------------------


class TestPipelineRepr:
    def test_repr(self):
        pipeline = Pipeline(name="my-pipe", steps=[AlwaysMatchStep()], mode=ExecutionMode.FIRST_MATCH)
        r = repr(pipeline)
        assert "my-pipe" in r
        assert "1" in r
        assert "first_match" in r
