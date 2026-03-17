"""Tests for the 4-step email filtering pipeline."""

import pytest

from openclaw_mail.filters.pipeline import Email, FilterConfig, FilterPipeline, FilterResult


class TestStep1AddressRules:
    """Step 1: Address-based routing."""

    def test_exact_sender_match(self, vip_email, work_filter_config):
        pipeline = FilterPipeline(work_filter_config)
        result = pipeline.classify(vip_email)
        assert result.folder == "Executive"
        assert result.step == "address"
        assert result.confidence == 1.0

    def test_partial_sender_match(self, work_filter_config):
        email = Email(id="1", subject="PR merged", sender="bot@notifications.github.com")
        pipeline = FilterPipeline(work_filter_config)
        result = pipeline.classify(email)
        assert result.folder == "GitHub"
        assert result.step == "address"

    def test_case_insensitive(self, work_filter_config):
        email = Email(id="1", subject="Hello", sender="BOSS@COMPANY.COM")
        pipeline = FilterPipeline(work_filter_config)
        result = pipeline.classify(email)
        assert result.folder == "Executive"
        assert result.step == "address"

    def test_no_match_falls_through(self, sample_email, work_filter_config):
        pipeline = FilterPipeline(work_filter_config)
        result = pipeline.classify(sample_email)
        # Should NOT match address rules — billing@company.com is not in rules
        assert result.step != "address"


class TestStep2KeywordRules:
    """Step 2: Keyword regex matching."""

    def test_invoice_keyword(self, sample_email, work_filter_config):
        pipeline = FilterPipeline(work_filter_config)
        result = pipeline.classify(sample_email)
        assert result.folder == "Finance"
        assert result.step == "keyword"
        assert result.confidence == 0.90

    def test_newsletter_keyword(self, newsletter_email, work_filter_config):
        pipeline = FilterPipeline(work_filter_config)
        result = pipeline.classify(newsletter_email)
        assert result.folder == "Newsletters"
        assert result.step == "keyword"
        assert result.confidence == 0.95

    def test_best_match_wins(self, work_filter_config):
        """When multiple patterns match, highest confidence wins."""
        email = Email(id="1", subject="Security alert: invoice payment", sender="noreply@bank.com")
        pipeline = FilterPipeline(work_filter_config)
        result = pipeline.classify(email)
        # Both "security" (0.95) and "invoice" (0.90) and "no-reply" (0.95) match
        # Highest confidence should win
        assert result.confidence >= 0.90
        assert result.step == "keyword"

    def test_low_confidence_rejected(self, work_filter_config):
        """Keywords with confidence < 0.8 should not match."""
        config = FilterConfig(
            keyword_rules=[{"pattern": "test", "folder": "Test", "confidence": 0.5}],
            review_folder="Review",
        )
        email = Email(id="1", subject="test email", sender="a@b.com")
        pipeline = FilterPipeline(config)
        result = pipeline.classify(email)
        assert result.step == "review"  # Should fall through to review


class TestStep3AIScoring:
    """Step 3: AI-based folder scoring."""

    def test_high_score_matches(self, unclassifiable_email, work_filter_config):
        def mock_scorer(email, folder_defs):
            return {"Finance": 0.9, "HR": 0.3, "Newsletters": 0.1}

        pipeline = FilterPipeline(work_filter_config, ai_scorer=mock_scorer)
        result = pipeline.classify(unclassifiable_email)
        assert result.folder == "Finance"
        assert result.step == "ai"
        assert result.confidence == 0.9

    def test_below_threshold_rejected(self, unclassifiable_email, work_filter_config):
        def mock_scorer(email, folder_defs):
            return {"Finance": 0.7, "HR": 0.5}  # All below 0.8

        pipeline = FilterPipeline(work_filter_config, ai_scorer=mock_scorer)
        result = pipeline.classify(unclassifiable_email)
        assert result.step == "review"

    def test_no_folder_definitions_skips(self, unclassifiable_email, minimal_filter_config):
        pipeline = FilterPipeline(minimal_filter_config)
        result = pipeline.classify(unclassifiable_email)
        assert result.step == "review"


class TestStep4ReviewFallback:
    """Step 4: Unmatched emails go to Review."""

    def test_unclassifiable_goes_to_review(self, unclassifiable_email, work_filter_config):
        pipeline = FilterPipeline(work_filter_config)
        result = pipeline.classify(unclassifiable_email)
        assert result.folder == "Review"
        assert result.step == "review"
        assert result.confidence == 0.0

    def test_custom_review_folder(self, unclassifiable_email):
        config = FilterConfig(review_folder="NeedsAttention")
        pipeline = FilterPipeline(config)
        result = pipeline.classify(unclassifiable_email)
        assert result.folder == "NeedsAttention"

    def test_empty_config_all_to_review(self, sample_email, minimal_filter_config):
        pipeline = FilterPipeline(minimal_filter_config)
        result = pipeline.classify(sample_email)
        assert result.folder == "Review"
        assert result.step == "review"


class TestPipelineOrder:
    """Verify first-match-wins semantics."""

    def test_address_beats_keyword(self, work_filter_config):
        """Address match takes priority over keyword match."""
        # VIP email with "invoice" in subject — address should win
        email = Email(id="1", subject="Your invoice is ready", sender="boss@company.com")
        pipeline = FilterPipeline(work_filter_config)
        result = pipeline.classify(email)
        assert result.step == "address"
        assert result.folder == "Executive"

    def test_keyword_beats_ai(self, work_filter_config):
        """Keyword match takes priority over AI scoring."""
        def mock_scorer(email, folder_defs):
            return {"Projects": 0.99}

        email = Email(id="1", subject="Invoice #123", sender="accounting@vendor.com")
        pipeline = FilterPipeline(work_filter_config, ai_scorer=mock_scorer)
        result = pipeline.classify(email)
        assert result.step == "keyword"
        assert result.folder == "Finance"

    def test_ai_beats_review(self, unclassifiable_email, work_filter_config):
        """AI match prevents fallback to Review."""
        def mock_scorer(email, folder_defs):
            return {"Projects": 0.85}

        pipeline = FilterPipeline(work_filter_config, ai_scorer=mock_scorer)
        result = pipeline.classify(unclassifiable_email)
        assert result.step == "ai"
        assert result.folder == "Projects"


class TestFilterConfig:
    """Test FilterConfig parsing."""

    def test_from_yaml(self):
        data = {
            "ai_score_threshold": 0.9,
            "review_folder": "NeedsReview",
            "address_rules": [{"sender": "a@b.com", "folder": "VIP"}],
            "keyword_rules": [{"pattern": "test", "folder": "Test", "confidence": 0.8}],
            "folder_definitions": {"VIP": "Important people"},
        }
        config = FilterConfig.from_yaml(data)
        assert config.ai_score_threshold == 0.9
        assert config.review_folder == "NeedsReview"
        assert len(config.address_rules) == 1
        assert len(config.keyword_rules) == 1
        assert "VIP" in config.folder_definitions

    def test_defaults_on_empty(self):
        config = FilterConfig.from_yaml({})
        assert config.ai_score_threshold == 0.8
        assert config.review_folder == "Review"
        assert config.address_rules == []
        assert config.keyword_rules == []
        assert config.folder_definitions == {}

    def test_none_values_handled(self):
        data = {"address_rules": None, "keyword_rules": None, "folder_definitions": None}
        config = FilterConfig.from_yaml(data)
        assert config.address_rules == []
        assert config.keyword_rules == []
        assert config.folder_definitions == {}
