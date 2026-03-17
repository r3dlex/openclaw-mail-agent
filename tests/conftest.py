"""Shared test fixtures."""

import pytest

from openclaw_mail.filters.pipeline import Email, FilterConfig


@pytest.fixture
def sample_email():
    return Email(
        id="123",
        subject="Your invoice #4521 is ready",
        sender="billing@company.com",
        sender_name="Billing Dept",
        snippet="Please find attached your invoice for March 2026.",
    )


@pytest.fixture
def newsletter_email():
    return Email(
        id="456",
        subject="Weekly Tech Digest - March 17",
        sender="no-reply@newsletter.tech",
        sender_name="Tech Weekly",
        snippet="Top stories this week in technology...",
    )


@pytest.fixture
def vip_email():
    return Email(
        id="789",
        subject="Meeting tomorrow at 10am",
        sender="boss@company.com",
        sender_name="The Boss",
        snippet="Let's discuss the Q2 roadmap.",
    )


@pytest.fixture
def unclassifiable_email():
    return Email(
        id="999",
        subject="Hey",
        sender="random@unknown.org",
        sender_name="Random Person",
        snippet="Just wanted to check in.",
    )


@pytest.fixture
def work_filter_config():
    return FilterConfig(
        ai_score_threshold=0.8,
        review_folder="Review",
        address_rules=[
            {"sender": "boss@company.com", "folder": "Executive"},
            {"sender": "@notifications.github.com", "folder": "GitHub"},
        ],
        keyword_rules=[
            {"pattern": "(invoice|receipt|payment|bill)", "folder": "Finance", "confidence": 0.90},
            {"pattern": "(newsletter|marketing|digest|no-reply)", "folder": "Newsletters", "confidence": 0.95},
            {"pattern": "(hr|vacation|sick|personnel)", "folder": "HR", "confidence": 0.90},
            {"pattern": "(security|alert|verify|login)", "folder": "Security", "confidence": 0.95},
        ],
        folder_definitions={
            "Finance": "Banking, invoices, payments, receipts",
            "HR": "Human resources, vacation, personnel matters",
            "Newsletters": "Marketing emails, subscriptions",
            "Security": "Security alerts, verification codes",
            "Projects": "Project-related communications",
        },
    )


@pytest.fixture
def minimal_filter_config():
    return FilterConfig(
        ai_score_threshold=0.8,
        review_folder="Review",
        address_rules=[],
        keyword_rules=[],
        folder_definitions={},
    )
