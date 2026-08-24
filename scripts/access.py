"""Legal institutional-access state resolution without handling credentials."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts import utc_now


@dataclass
class AccessState:
    provider: str
    access_type: str = "institutional"
    authenticated: bool = False
    session_valid: bool = False
    subscription: str = "unknown"
    methods: list[str] = field(default_factory=list)
    next_action: str = "user_login"
    checked_at: str = field(default_factory=utc_now)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AccessResolver:
    """Resolve only non-secret session metadata and environment presence.

    Passwords, API keys, cookies, and token values are never read or returned.
    A provider session marker is a user-created JSON file containing metadata such
    as ``status`` and ``expires_at``; it is not an authentication credential.
    """

    CONFIG = {
        "WRDS": {"session_env": "WRDS_SESSION_FILE", "methods": ["institutional", "campus_ip", "vpn", "mfa"]},
        "CSMAR": {"session_env": "CSMAR_SESSION_FILE", "methods": ["institutional", "campus_ip", "carsi", "mfa"]},
        "RESSET": {"session_env": "RESSET_SESSION_FILE", "methods": ["institutional", "campus_ip", "vpn", "carsi", "mfa", "browser_session"]},
    }

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self.environ = dict(environ or os.environ)

    def resolve(self, provider: str) -> AccessState:
        normalized = provider.upper()
        config = self.CONFIG.get(normalized)
        if config is None:
            return AccessState(provider=normalized, next_action="configure_provider", details={"known_provider": False})
        marker_value = self.environ.get(config["session_env"])
        base = {"provider": normalized, "methods": list(config["methods"])}
        base_details = {"session_marker_configured": bool(marker_value)}
        if not marker_value:
            return AccessState(**base, details=base_details)
        marker = self._read_marker(marker_value)
        if marker is None:
            return AccessState(**base, next_action="repair_session_marker", details={**base_details, "marker_valid": False})
        status = str(marker.get("status", "authenticated")).lower()
        if status in {"no_subscription", "not_subscribed"}:
            return AccessState(**base, subscription="none", next_action="contact_library", details={**base_details, "marker_valid": True})
        if bool(marker.get("mfa_required")) or status == "mfa_required":
            return AccessState(**base, next_action="complete_mfa", details={**base_details, "marker_valid": True})
        if status in {"expired", "session_expired"} or self._expired(marker.get("expires_at")):
            return AccessState(**base, next_action="refresh_session", details={**base_details, "marker_valid": True})
        if status == "authenticated":
            return AccessState(**base, authenticated=True, session_valid=True, subscription="present", next_action="none", details={**base_details, "marker_valid": True})
        return AccessState(**base, next_action="repair_session_marker", details={**base_details, "marker_valid": True, "status": status})

    def resolve_api_key(self, provider: str, env_var: str) -> AccessState:
        """Check API-key presence without reading, logging, or returning its value."""
        present = bool(self.environ.get(env_var))
        return AccessState(
            provider=provider.upper(),
            access_type="api_key",
            authenticated=present,
            session_valid=present,
            subscription="unknown",
            methods=["api_key"],
            next_action="none" if present else "configure_api_key",
            details={"api_key_env": env_var, "api_key_present": present},
        )

    def _read_marker(self, value: str) -> dict[str, Any] | None:
        path = Path(value)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return {key: payload[key] for key in ("status", "expires_at", "mfa_required") if key in payload}

    @staticmethod
    def _expired(value: Any) -> bool:
        if not value:
            return False
        try:
            expiry = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return True
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry <= datetime.now(timezone.utc)
