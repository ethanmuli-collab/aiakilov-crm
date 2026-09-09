"""Optional Supabase integration.

The demo runs on local SQLite so it never depends on network configuration.
This module is the drop-in path to a real Supabase backend: it builds a client
from environment variables only - no credential is ever hard-coded or logged.
"""

from __future__ import annotations

import os

_client = None


def is_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))


def get_client():
    """Return a cached Supabase client, or None when unavailable."""
    global _client
    if _client is not None:
        return _client
    if not is_configured():
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    return _client


def status() -> dict:
    """Non-secret status summary, safe to render in the Settings page."""
    url = os.getenv("SUPABASE_URL", "")
    return {
        "configured": is_configured(),
        "url_host": url.split("//")[-1].split(".")[0] if url else None,
        "anon_key_present": bool(os.getenv("SUPABASE_ANON_KEY")),
        "client_ready": get_client() is not None,
    }


def fetch(table: str, limit: int = 100) -> list[dict]:
    """Read rows from an aiakilov_* table. Guarded against unrelated tables."""
    if not table.startswith("aiakilov_"):
        raise ValueError("this service may only read aiakilov_* tables")
    client = get_client()
    if client is None:
        return []
    return client.table(table).select("*").limit(limit).execute().data
