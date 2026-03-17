"""Centralized configuration loader.

Loads all settings from environment variables and config/accounts.yaml.
No hardcoded credentials or local paths.
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Resolve project root (one level up from this file: openclaw_mail/config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_env(key: str, default: str | None = None, required: bool = False) -> str:
    val = os.getenv(key, default)
    if required and not val:
        raise EnvironmentError(f"Required environment variable {key} is not set. Check your .env file.")
    return val or ""


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------
DAVMAIL_HOST = get_env("DAVMAIL_HOST", "localhost")
DAVMAIL_IMAP_PORT = int(get_env("DAVMAIL_IMAP_PORT", "1143"))
DAVMAIL_SMTP_PORT = int(get_env("DAVMAIL_SMTP_PORT", "1025"))
DAVMAIL_CALDAV_PORT = int(get_env("DAVMAIL_CALDAV_PORT", "1080"))
GMAIL_HOST = get_env("GMAIL_HOST", "imap.gmail.com")
GMAIL_PORT = int(get_env("GMAIL_PORT", "993"))

# ---------------------------------------------------------------------------
# Azure DevOps
# ---------------------------------------------------------------------------
ADO_PAT = get_env("ADO_PAT")
ADO_ORG = get_env("ADO_ORG")
ADO_PROJECT = get_env("ADO_PROJECT")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
LOG_DIR = PROJECT_ROOT / get_env("LOG_DIR", "logs")
REPORT_DIR = PROJECT_ROOT / get_env("REPORT_DIR", "reports")
CONFIG_DIR = PROJECT_ROOT / "config"
LOG_LEVEL = get_env("LOG_LEVEL", "INFO")


def load_accounts() -> list[dict]:
    """Load account definitions from config/accounts.yaml.

    Resolves user and password from environment variables.
    Supports lookup by id, nickname, or himalaya_name.
    """
    accounts_file = CONFIG_DIR / "accounts.yaml"
    if not accounts_file.exists():
        raise FileNotFoundError(f"Accounts config not found: {accounts_file}")
    with open(accounts_file) as f:
        data = yaml.safe_load(f)
    accounts = data.get("accounts", [])
    for acc in accounts:
        # Resolve user from env
        user_env_key = acc.get("user_env")
        if user_env_key:
            acc["_user"] = get_env(user_env_key, acc.get("user", ""))
        else:
            acc["_user"] = acc.get("user", "")
        # Resolve password from env
        pass_env_key = acc.get("password_env")
        if pass_env_key:
            acc["_password"] = get_env(pass_env_key, "")
        # Resolve calendar credentials from env (if present)
        cal = acc.get("calendar")
        if cal:
            for key in ("url_env", "user_env", "password_env", "client_secrets_env", "token_env"):
                env_key = cal.get(key)
                if env_key:
                    resolved_key = "_" + key.replace("_env", "")
                    cal[resolved_key] = get_env(env_key, "")
    return accounts


def find_account(identifier: str) -> dict | None:
    """Find an account by id, nickname, or himalaya_name."""
    for acc in load_accounts():
        if identifier in (acc.get("id"), acc.get("nickname"), acc.get("himalaya_name")):
            return acc
    return None


def load_filter_config(account_id: str) -> dict:
    """Load per-account filter configuration from config/filters/<account_id>.yaml."""
    filter_file = CONFIG_DIR / "filters" / f"{account_id}.yaml"
    if not filter_file.exists():
        return {}
    with open(filter_file) as f:
        return yaml.safe_load(f) or {}


def get_active_accounts() -> list[dict]:
    """Return only active accounts."""
    return [a for a in load_accounts() if a.get("active", False)]
