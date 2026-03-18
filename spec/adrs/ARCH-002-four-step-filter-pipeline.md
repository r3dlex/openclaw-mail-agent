# ARCH-002: Four-Step Filter Pipeline

**Status:** Accepted
**Date:** 2026-03-18

## Context

Emails need to be classified into folders automatically. A single approach
(regex only, or AI only) is insufficient — regex can't handle nuance, and
AI is slow/expensive for obvious matches.

## Decision

Every email passes through exactly 4 steps in order. **First match wins** —
the email stops at the step that classifies it:

1. **Address rules** — exact sender matching (confidence 1.0)
2. **Keyword rules** — regex on subject+sender (confidence ≥ 0.8)
3. **AI scoring** — score against folder definitions (threshold configurable)
4. **Review fallback** — unmatched → Review folder

## Consequences

- Simple cases are fast (Step 1–2), complex cases use AI (Step 3)
- New accounts get a default pipeline via `config/filters/_default.yaml`
- The pipeline is deterministic — same email always gets same result
- `FilterPipeline.classify()` implements this exact flow

## Validation

Machine-checkable: `spec/adrs/ARCH-002-four-step-filter-pipeline.check.py`
