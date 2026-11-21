"""OAuth 2.1 authorization policy for the Recipe MCP transport.

The MCP endpoint is an OAuth resource server. Keycloak remains responsible
for authenticating users and issuing access tokens; this module only verifies
those tokens and declares the scopes required by MCP components.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import fastmcp
from fastmcp.server.auth import (
    AccessToken,
    AuthCheck,
    JWTVerifier,
    RemoteAuthProvider,
    require_scopes,
)
from pydantic import AnyHttpUrl

from arclith.infrastructure.config import load_config_dir

READ_SCOPE = "recipes:read"
WRITE_SCOPE = "recipes:write"
IMAGE_GENERATE_SCOPE = "recipes:image:generate"
DELETE_SCOPE = "recipes:delete"
ADMIN_SCOPE = "recipes:admin"

MCP_SCOPES = [
    READ_SCOPE,
    WRITE_SCOPE,
    IMAGE_GENERATE_SCOPE,
    DELETE_SCOPE,
    ADMIN_SCOPE,
]

_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_CLOCK_SKEW_SECONDS = 30


def _is_auth_disabled() -> bool:
    return os.getenv("REKIPE_AUTH_DISABLED", "").strip().lower() in _TRUE_VALUES


class KeycloakJWTVerifier(JWTVerifier):
    """JWT verifier with Keycloak realm-role and time-bound checks."""

    def __init__(self, *, required_role: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.required_role = required_role

    async def load_access_token(self, token: str) -> AccessToken | None:
        access_token = await super().load_access_token(token)
        if access_token is None:
            return None

        claims = access_token.claims
        now = int(time.time())
        if not _valid_expiration_numeric_date(claims.get("exp"), now):
            return None
        if not _valid_future_numeric_date(claims.get("nbf"), now + _CLOCK_SKEW_SECONDS):
            return None
        if not _valid_future_numeric_date(claims.get("iat"), now + _CLOCK_SKEW_SECONDS):
            return None
        if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
            return None

        if self.required_role:
            realm_access = claims.get("realm_access")
            roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
            if not isinstance(roles, list) or self.required_role not in roles:
                return None

        return access_token


def _valid_future_numeric_date(value: Any, latest: int) -> bool:
    """Validate optional JWT NumericDate claims without accepting booleans."""

    if value is None:
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value <= latest


def _valid_expiration_numeric_date(value: Any, now: int) -> bool:
    """Require a numeric expiration strictly later than the current time."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value > now


def build_mcp_auth_provider() -> RemoteAuthProvider | None:
    """Build the transport-level OAuth provider used by the HTTP MCP server."""

    if _is_auth_disabled():
        return None

    config = load_config_dir(_CONFIG_PATH)
    keycloak = config.keycloak
    if keycloak is None:
        raise RuntimeError("config.keycloak requis pour protéger le transport MCP")

    public_base_url = os.getenv(
        "REKIPE_MCP_PUBLIC_BASE_URL",
        "http://127.0.0.1:8001",
    ).rstrip("/")
    issuer_url = os.getenv(
        "REKIPE_MCP_AUTH_ISSUER_URL",
        f"{keycloak.url.rstrip('/')}/realms/{keycloak.realm}",
    ).rstrip("/")
    jwks_uri = os.getenv(
        "REKIPE_MCP_AUTH_JWKS_URI",
        f"{keycloak.url.rstrip('/')}/realms/{keycloak.realm}/protocol/openid-connect/certs",
    )
    required_role = os.getenv("REKIPE_MCP_AUTH_REQUIRED_ROLE", "rekipe:mcp-access").strip()
    if not required_role:
        raise RuntimeError("REKIPE_MCP_AUTH_REQUIRED_ROLE ne peut pas être vide")
    resource_url = f"{public_base_url}/mcp"

    verifier = KeycloakJWTVerifier(
        jwks_uri=jwks_uri,
        issuer=issuer_url,
        audience=resource_url,
        algorithm="RS256",
        required_scopes=[READ_SCOPE],
        required_role=required_role,
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[AnyHttpUrl(issuer_url)],
        base_url=public_base_url,
        scopes_supported=MCP_SCOPES,
        resource_name="Rekipe Recipe MCP",
    )


def _declared_scopes(scopes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((READ_SCOPE, *scopes)))


def _component_auth(mcp: fastmcp.FastMCP, scopes: tuple[str, ...]) -> AuthCheck | None:
    if mcp.auth is None:
        return None
    return require_scopes(*_declared_scopes(scopes))


def _oauth_meta(scopes: tuple[str, ...], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(meta or {})
    merged["securitySchemes"] = [
        {"type": "oauth2", "scopes": list(_declared_scopes(scopes))},
    ]
    return merged


def secure_tool(
    mcp: fastmcp.FastMCP,
    *scopes: str,
    meta: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Callable:
    """Register a tool with matching runtime and advertised OAuth scopes."""

    return mcp.tool(
        auth=_component_auth(mcp, scopes),
        meta=_oauth_meta(scopes, meta),
        **kwargs,
    )


def secure_resource(
    mcp: fastmcp.FastMCP,
    uri: str,
    *scopes: str,
    meta: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Callable:
    """Register an OAuth-protected MCP resource."""

    return mcp.resource(
        uri,
        auth=_component_auth(mcp, scopes),
        meta=_oauth_meta(scopes, meta),
        **kwargs,
    )


def secure_prompt(
    mcp: fastmcp.FastMCP,
    *scopes: str,
    meta: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Callable:
    """Register an OAuth-protected MCP prompt."""

    return mcp.prompt(
        auth=_component_auth(mcp, scopes),
        meta=_oauth_meta(scopes, meta),
        **kwargs,
    )
