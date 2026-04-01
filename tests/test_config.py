"""Tests for the config module — get_env, load_accounts, find_account, etc."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# get_env
# ---------------------------------------------------------------------------

class TestGetEnv:
    def test_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR_XYZ", "hello")
        from openclaw_mail.config import get_env
        assert get_env("TEST_VAR_XYZ") == "hello"

    def test_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_UNSET_VAR", raising=False)
        from openclaw_mail.config import get_env
        assert get_env("TEST_UNSET_VAR", "fallback") == "fallback"

    def test_returns_empty_string_when_no_default(self, monkeypatch):
        monkeypatch.delenv("TEST_EMPTY_VAR", raising=False)
        from openclaw_mail.config import get_env
        assert get_env("TEST_EMPTY_VAR") == ""

    def test_raises_on_required_missing(self, monkeypatch):
        monkeypatch.delenv("REQUIRED_VAR_MISSING", raising=False)
        from openclaw_mail.config import get_env
        with pytest.raises(EnvironmentError, match="REQUIRED_VAR_MISSING"):
            get_env("REQUIRED_VAR_MISSING", required=True)

    def test_no_raise_when_required_is_set(self, monkeypatch):
        monkeypatch.setenv("REQUIRED_VAR_SET", "value")
        from openclaw_mail.config import get_env
        result = get_env("REQUIRED_VAR_SET", required=True)
        assert result == "value"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_project_root_is_a_directory(self):
        from openclaw_mail.config import PROJECT_ROOT
        assert PROJECT_ROOT.is_dir()

    def test_config_dir_path(self):
        from openclaw_mail.config import CONFIG_DIR, PROJECT_ROOT
        assert CONFIG_DIR == PROJECT_ROOT / "config"

    def test_log_dir_path(self):
        from openclaw_mail.config import LOG_DIR, PROJECT_ROOT
        # Default is PROJECT_ROOT/logs
        assert "logs" in str(LOG_DIR)

    def test_report_dir_path(self):
        from openclaw_mail.config import REPORT_DIR, PROJECT_ROOT
        assert "reports" in str(REPORT_DIR)

    def test_davmail_port_defaults(self):
        from openclaw_mail.config import DAVMAIL_IMAP_PORT, DAVMAIL_SMTP_PORT
        assert DAVMAIL_IMAP_PORT == 1143
        assert DAVMAIL_SMTP_PORT == 1025

    def test_gmail_host_default(self):
        from openclaw_mail.config import GMAIL_HOST
        assert GMAIL_HOST == "imap.gmail.com"


# ---------------------------------------------------------------------------
# load_accounts
# ---------------------------------------------------------------------------

class TestLoadAccounts:
    def _write_accounts_yaml(self, tmp_path: Path, data: dict) -> Path:
        accounts_dir = tmp_path / "config"
        accounts_dir.mkdir(parents=True, exist_ok=True)
        accounts_file = accounts_dir / "accounts.yaml"
        accounts_file.write_text(yaml.dump(data))
        return accounts_dir

    def test_raises_when_file_missing(self, tmp_path):
        missing_dir = tmp_path / "no_config"
        missing_dir.mkdir()
        from openclaw_mail.config import load_accounts
        with patch("openclaw_mail.config.CONFIG_DIR", missing_dir):
            with pytest.raises(FileNotFoundError):
                load_accounts()

    def test_loads_basic_accounts(self, tmp_path, monkeypatch):
        config_dir = self._write_accounts_yaml(tmp_path, {
            "accounts": [
                {"id": "acc1", "name": "Account 1", "active": True},
            ]
        })
        from openclaw_mail.config import load_accounts
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            accounts = load_accounts()

        assert len(accounts) == 1
        assert accounts[0]["id"] == "acc1"

    def test_resolves_user_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_USER_EMAIL", "user@example.com")
        config_dir = self._write_accounts_yaml(tmp_path, {
            "accounts": [
                {"id": "acc1", "name": "Account 1", "user_env": "MY_USER_EMAIL", "active": True},
            ]
        })
        from openclaw_mail.config import load_accounts
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            accounts = load_accounts()

        assert accounts[0]["_user"] == "user@example.com"

    def test_resolves_password_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_PASS", "secret123")
        config_dir = self._write_accounts_yaml(tmp_path, {
            "accounts": [
                {"id": "acc1", "name": "Account 1", "password_env": "MY_PASS", "active": True},
            ]
        })
        from openclaw_mail.config import load_accounts
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            accounts = load_accounts()

        assert accounts[0]["_password"] == "secret123"

    def test_no_user_env_uses_user_field(self, tmp_path):
        config_dir = self._write_accounts_yaml(tmp_path, {
            "accounts": [
                {"id": "acc1", "name": "Account 1", "user": "direct@example.com", "active": True},
            ]
        })
        from openclaw_mail.config import load_accounts
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            accounts = load_accounts()

        assert accounts[0]["_user"] == "direct@example.com"

    def test_resolves_calendar_env_keys(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CAL_TOKEN_VAR", "/path/to/token.json")
        config_dir = self._write_accounts_yaml(tmp_path, {
            "accounts": [
                {
                    "id": "acc1",
                    "name": "Account 1",
                    "active": True,
                    "calendar": {
                        "provider": "google",
                        "token_env": "CAL_TOKEN_VAR",
                    }
                },
            ]
        })
        from openclaw_mail.config import load_accounts
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            accounts = load_accounts()

        assert accounts[0]["calendar"]["_token"] == "/path/to/token.json"

    def test_empty_accounts_list(self, tmp_path):
        config_dir = self._write_accounts_yaml(tmp_path, {"accounts": []})
        from openclaw_mail.config import load_accounts
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            accounts = load_accounts()
        assert accounts == []


# ---------------------------------------------------------------------------
# find_account
# ---------------------------------------------------------------------------

class TestFindAccount:
    def _write_accounts(self, tmp_path, accounts_list):
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "accounts.yaml").write_text(yaml.dump({"accounts": accounts_list}))
        return config_dir

    def test_find_by_id(self, tmp_path):
        config_dir = self._write_accounts(tmp_path, [
            {"id": "personal", "name": "Personal", "nickname": "pers", "active": True}
        ])
        from openclaw_mail.config import find_account
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            acc = find_account("personal")
        assert acc is not None
        assert acc["id"] == "personal"

    def test_find_by_nickname(self, tmp_path):
        config_dir = self._write_accounts(tmp_path, [
            {"id": "personal", "name": "Personal", "nickname": "pers", "active": True}
        ])
        from openclaw_mail.config import find_account
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            acc = find_account("pers")
        assert acc is not None

    def test_find_by_himalaya_name(self, tmp_path):
        config_dir = self._write_accounts(tmp_path, [
            {"id": "personal", "name": "Personal", "himalaya_name": "PersonalGmail", "active": True}
        ])
        from openclaw_mail.config import find_account
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            acc = find_account("PersonalGmail")
        assert acc is not None

    def test_returns_none_when_not_found(self, tmp_path):
        config_dir = self._write_accounts(tmp_path, [
            {"id": "personal", "name": "Personal", "active": True}
        ])
        from openclaw_mail.config import find_account
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            acc = find_account("nonexistent")
        assert acc is None


# ---------------------------------------------------------------------------
# get_active_accounts
# ---------------------------------------------------------------------------

class TestGetActiveAccounts:
    def _write_accounts(self, tmp_path, accounts_list):
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "accounts.yaml").write_text(yaml.dump({"accounts": accounts_list}))
        return config_dir

    def test_filters_inactive_accounts(self, tmp_path):
        config_dir = self._write_accounts(tmp_path, [
            {"id": "active", "name": "Active", "active": True},
            {"id": "inactive", "name": "Inactive", "active": False},
        ])
        from openclaw_mail.config import get_active_accounts
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            accounts = get_active_accounts()

        assert len(accounts) == 1
        assert accounts[0]["id"] == "active"

    def test_returns_empty_when_all_inactive(self, tmp_path):
        config_dir = self._write_accounts(tmp_path, [
            {"id": "inactive", "name": "Inactive", "active": False},
        ])
        from openclaw_mail.config import get_active_accounts
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            accounts = get_active_accounts()

        assert accounts == []


# ---------------------------------------------------------------------------
# load_filter_config
# ---------------------------------------------------------------------------

class TestLoadFilterConfig:
    def test_returns_empty_when_no_file(self, tmp_path):
        config_dir = tmp_path / "config"
        (config_dir / "filters").mkdir(parents=True)
        from openclaw_mail.config import load_filter_config
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            result = load_filter_config("nonexistent_account")
        assert result == {}

    def test_returns_config_when_file_exists(self, tmp_path):
        config_dir = tmp_path / "config"
        filters_dir = config_dir / "filters"
        filters_dir.mkdir(parents=True)
        (filters_dir / "myaccount.yaml").write_text(yaml.dump({
            "review_folder": "Review",
            "address_rules": [],
        }))
        from openclaw_mail.config import load_filter_config
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            result = load_filter_config("myaccount")

        assert result["review_folder"] == "Review"

    def test_returns_empty_on_blank_yaml(self, tmp_path):
        config_dir = tmp_path / "config"
        filters_dir = config_dir / "filters"
        filters_dir.mkdir(parents=True)
        (filters_dir / "emptyacc.yaml").write_text("")
        from openclaw_mail.config import load_filter_config
        with patch("openclaw_mail.config.CONFIG_DIR", config_dir):
            result = load_filter_config("emptyacc")
        assert result == {}
