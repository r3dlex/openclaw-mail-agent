"""4-step email filtering pipeline.

Pipeline order (first match wins):
  Step 1: Address rules   — emails from specific senders go to specific folders
  Step 2: Keyword rules   — regex patterns on subject+sender match to folders
  Step 3: AI scoring      — score email content against folder definitions (0.0–1.0)
  Step 4: Fallback        — unmatched emails go to the Review folder
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

import yaml

from openclaw_mail.config import CONFIG_DIR


@dataclass
class FilterResult:
    """Result of running an email through the filter pipeline."""

    folder: str
    step: str  # "address", "keyword", "ai", "review"
    confidence: float
    reason: str
    matched: bool = True


@dataclass
class Email:
    """Minimal email representation for filtering."""

    id: str
    subject: str
    sender: str
    sender_name: str = ""
    snippet: str = ""  # first ~200 chars of body for AI scoring


# Type alias for the AI scorer callback.
# Signature: (email, folder_definitions) -> dict[folder_name, score]
AIScorer = Callable[[Email, dict[str, str]], dict[str, float]]


def _default_ai_scorer(email: Email, folder_definitions: dict[str, str]) -> dict[str, float]:
    """Placeholder scorer — always returns 0. Replace with openclaw agent call."""
    return {folder: 0.0 for folder in folder_definitions}


@dataclass
class FilterConfig:
    """Parsed filter configuration for one account."""

    ai_score_threshold: float = 0.8
    review_folder: str = "Review"
    address_rules: list[dict] = field(default_factory=list)
    keyword_rules: list[dict] = field(default_factory=list)
    folder_definitions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, data: dict) -> FilterConfig:
        return cls(
            ai_score_threshold=data.get("ai_score_threshold", 0.8),
            review_folder=data.get("review_folder", "Review"),
            address_rules=data.get("address_rules", []) or [],
            keyword_rules=data.get("keyword_rules", []) or [],
            folder_definitions=data.get("folder_definitions", {}) or {},
        )

    @classmethod
    def load(cls, account_id: str) -> FilterConfig:
        """Load filter config for an account, falling back to _default.yaml."""
        # Try account-specific first
        account_file = CONFIG_DIR / "filters" / f"{account_id}.yaml"
        default_file = CONFIG_DIR / "filters" / "_default.yaml"

        if account_file.exists():
            with open(account_file) as f:
                data = yaml.safe_load(f) or {}
        elif default_file.exists():
            with open(default_file) as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        return cls.from_yaml(data)


class FilterPipeline:
    """Executes the 4-step email filtering pipeline."""

    def __init__(self, config: FilterConfig, ai_scorer: AIScorer | None = None):
        self.config = config
        self.ai_scorer = ai_scorer or _default_ai_scorer

    def classify(self, email: Email) -> FilterResult:
        """Run email through the full pipeline. Returns first match."""

        # Step 1: Address rules
        result = self._step_address(email)
        if result:
            return result

        # Step 2: Keyword rules
        result = self._step_keyword(email)
        if result:
            return result

        # Step 3: AI scoring
        result = self._step_ai(email)
        if result:
            return result

        # Step 4: Fallback to Review
        return FilterResult(
            folder=self.config.review_folder,
            step="review",
            confidence=0.0,
            reason="No filter matched — moved to review",
        )

    def _step_address(self, email: Email) -> FilterResult | None:
        """Step 1: Match sender address against address rules."""
        sender_lower = email.sender.lower()
        for rule in self.config.address_rules:
            pattern = rule.get("sender", "").lower()
            if not pattern:
                continue
            if pattern in sender_lower:
                return FilterResult(
                    folder=rule["folder"],
                    step="address",
                    confidence=1.0,
                    reason=f"Sender matches address rule: {pattern}",
                )
        return None

    def _step_keyword(self, email: Email) -> FilterResult | None:
        """Step 2: Match subject+sender against keyword regex patterns."""
        text = f"{email.subject} {email.sender}".lower()

        best_match: FilterResult | None = None
        best_confidence = 0.0

        for rule in self.config.keyword_rules:
            pattern = rule.get("pattern", "")
            confidence = rule.get("confidence", 0.5)
            if not pattern:
                continue
            if re.search(pattern, text, re.IGNORECASE):
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = FilterResult(
                        folder=rule["folder"],
                        step="keyword",
                        confidence=confidence,
                        reason=f"Keyword match: /{pattern}/",
                    )

        # Only return if confidence >= 0.8
        if best_match and best_match.confidence >= 0.8:
            return best_match
        return None

    def _step_ai(self, email: Email) -> FilterResult | None:
        """Step 3: Score email against folder definitions using AI."""
        if not self.config.folder_definitions:
            return None

        scores = self.ai_scorer(email, self.config.folder_definitions)
        if not scores:
            return None

        best_folder = max(scores, key=scores.get)
        best_score = scores[best_folder]

        if best_score >= self.config.ai_score_threshold:
            return FilterResult(
                folder=best_folder,
                step="ai",
                confidence=best_score,
                reason=f"AI scored {best_score:.2f} for '{best_folder}'",
            )
        return None
