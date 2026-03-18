# ARCH-005: Pipeline Step Protocol

**Status:** Accepted
**Date:** 2026-03-19

## Context

The project needs pipelines for two distinct purposes:
1. Email filtering (first-match-wins, per-email classification)
2. CI validation (sequential, all-must-pass compliance checks)

Duplicating pipeline infrastructure for each use case creates maintenance
overhead.

## Decision

A generic `Pipeline` framework in `openclaw_mail/pipelines/` provides:

- **`PipelineStep` protocol** — any object with `name: str` and
  `execute(context: dict) -> StepResult`
- **`StepResult`** — matched, confidence, reason, output, duration
- **`Pipeline`** — ordered step execution in `first_match` or `sequential` mode
- **`PipelineResult`** — aggregate with per-step results and summary

Both the email filter pipeline and the CI validation pipeline can be built
on this foundation.

## Consequences

- New pipeline types are trivial to add (just implement `PipelineStep`)
- Steps are independently testable
- CI validation uses `sequential` mode (all steps must pass)
- Email filtering uses `first_match` mode (first step wins)
- GitHub Actions runs `poetry run validate` to execute the validation pipeline

## Validation

Machine-checkable: `spec/adrs/ARCH-005-pipeline-step-protocol.check.py`
