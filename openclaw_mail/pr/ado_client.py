"""Azure DevOps REST API client."""

from __future__ import annotations

import base64

import requests

from openclaw_mail.config import ADO_ORG, ADO_PAT, ADO_PROJECT
from openclaw_mail.utils.logging import get_logger

log = get_logger("ado")

BASE_URL = f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis"


def _headers() -> dict:
    if not ADO_PAT:
        log.warning("ADO_PAT not set — API calls will fail")
        return {}
    auth = base64.b64encode(f":{ADO_PAT}".encode()).decode()
    return {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}


def get_data(endpoint: str, params: dict | None = None) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"ADO GET {endpoint}: {e}")
        return {}


def post_data(endpoint: str, params: dict | None = None, data: dict | None = None) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = requests.post(url, headers=_headers(), params=params, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"ADO POST {endpoint}: {e}")
        return {"error": str(e)}
