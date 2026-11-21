from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import fastmcp
import pytest
from authlib.jose import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastmcp.server.auth import AccessToken, AuthContext, RemoteAuthProvider, TokenVerifier
from fastmcp.server.auth.authorization import run_auth_checks
from httpx import ASGITransport, AsyncClient

from adapters.input.fastmcp.authorization import (
    ADMIN_SCOPE,
    DELETE_SCOPE,
    IMAGE_GENERATE_SCOPE,
    MCP_SCOPES,
    READ_SCOPE,
    WRITE_SCOPE,
    KeycloakJWTVerifier,
    build_mcp_auth_provider,
    secure_tool,
)

ISSUER = "https://keycloak.example.test/realms/rekipe"
RESOURCE = "https://rekipe.example.test/api/recipe-mcp/mcp"
METADATA_PATH = "/.well-known/oauth-protected-resource/api/recipe-mcp/mcp"


@pytest.fixture(scope="module")
def signing_keys() -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def _token(private_key: bytes, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": RESOURCE,
        "sub": "user-123",
        "azp": "rekipe-mcp-codex",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "scope": f"openid {READ_SCOPE} {WRITE_SCOPE}",
        "realm_access": {"roles": ["rekipe:mcp-access"]},
    }
    claims.update(overrides)
    encoded = jwt.encode({"alg": "RS256"}, claims, private_key)
    return encoded.decode()


def _verifier(public_key: bytes) -> KeycloakJWTVerifier:
    return KeycloakJWTVerifier(
        public_key=public_key.decode(),
        issuer=ISSUER,
        audience=RESOURCE,
        algorithm="RS256",
        required_scopes=[READ_SCOPE],
        required_role="rekipe:mcp-access",
    )


async def test_keycloak_verifier_accepts_bound_authorized_token(signing_keys) -> None:
    private_key, public_key = signing_keys

    access_token = await _verifier(public_key).verify_token(_token(private_key))

    assert access_token is not None
    assert access_token.client_id == "rekipe-mcp-codex"
    assert READ_SCOPE in access_token.scopes
    assert access_token.claims["sub"] == "user-123"


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "https://another-resource.example.test/mcp"},
        {"scope": "openid profile"},
        {"realm_access": {"roles": []}},
        {"nbf": int(time.time()) + 3600},
        {"iat": int(time.time()) + 3600},
        {"exp": int(time.time()) - 60},
        {"sub": ""},
    ],
)
async def test_keycloak_verifier_rejects_unbound_or_unauthorized_token(signing_keys, overrides) -> None:
    private_key, public_key = signing_keys

    access_token = await _verifier(public_key).verify_token(_token(private_key, **overrides))

    assert access_token is None


def test_build_auth_provider_uses_public_resource_and_internal_jwks(monkeypatch) -> None:
    config = MagicMock()
    config.keycloak.url = "http://keycloak.keycloak.svc.cluster.local"
    config.keycloak.realm = "rekipe"
    monkeypatch.delenv("REKIPE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("REKIPE_MCP_PUBLIC_BASE_URL", "https://rekipe.example.test/api/recipe-mcp")
    monkeypatch.setenv("REKIPE_MCP_AUTH_ISSUER_URL", ISSUER)
    monkeypatch.setenv("REKIPE_MCP_AUTH_REQUIRED_ROLE", "rekipe:mcp-access")

    with patch("adapters.input.fastmcp.authorization.load_config_dir", return_value=config):
        provider = build_mcp_auth_provider()

    assert isinstance(provider, RemoteAuthProvider)
    assert str(provider.base_url) == "https://rekipe.example.test/api/recipe-mcp"
    assert provider.token_verifier.issuer == ISSUER
    assert provider.token_verifier.audience == RESOURCE
    assert provider.token_verifier.jwks_uri == (
        "http://keycloak.keycloak.svc.cluster.local/realms/rekipe/protocol/openid-connect/certs"
    )
    assert provider.token_verifier.required_scopes == [READ_SCOPE]
    assert provider.token_verifier.required_role == "rekipe:mcp-access"


def test_build_auth_provider_can_only_be_disabled_explicitly(monkeypatch) -> None:
    monkeypatch.setenv("REKIPE_AUTH_DISABLED", "true")

    assert build_mcp_auth_provider() is None


class _StaticTokenVerifier(TokenVerifier):
    def __init__(self) -> None:
        super().__init__(required_scopes=[READ_SCOPE])

    async def verify_token(self, token: str) -> AccessToken | None:
        if token != "valid-token":
            return None
        return AccessToken(
            token=token,
            client_id="test-client",
            scopes=[READ_SCOPE],
            expires_at=int(time.time()) + 300,
            claims={"sub": "test-user"},
        )


@pytest.fixture
def protected_mcp_app():
    auth = RemoteAuthProvider(
        token_verifier=_StaticTokenVerifier(),
        authorization_servers=[ISSUER],
        base_url="https://rekipe.example.test/api/recipe-mcp",
        scopes_supported=MCP_SCOPES,
        resource_name="Rekipe Recipe MCP",
    )
    mcp = fastmcp.FastMCP("protected-test", auth=auth)

    @secure_tool(mcp)
    async def read_recipe() -> dict[str, bool]:
        return {"ok": True}

    return mcp.http_app(path="/mcp", stateless_http=True, json_response=True)


async def test_protected_resource_metadata_is_public_and_complete(protected_mcp_app) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=protected_mcp_app),
        base_url="https://rekipe.example.test",
    ) as client:
        response = await client.get(METADATA_PATH)

    assert response.status_code == 200
    assert response.json() == {
        "resource": RESOURCE,
        "authorization_servers": [ISSUER],
        "scopes_supported": [
            READ_SCOPE,
            WRITE_SCOPE,
            IMAGE_GENERATE_SCOPE,
            DELETE_SCOPE,
            ADMIN_SCOPE,
        ],
        "bearer_methods_supported": ["header"],
        "resource_name": "Rekipe Recipe MCP",
    }


async def test_mcp_transport_rejects_anonymous_request_with_discovery_challenge(protected_mcp_app) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=protected_mcp_app),
        base_url="https://rekipe.example.test",
    ) as client:
        response = await client.post("/mcp", json={})

    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith("Bearer ")
    assert f'resource_metadata="https://rekipe.example.test{METADATA_PATH}"' in challenge


async def test_mcp_transport_rejects_invalid_bearer_token(protected_mcp_app) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=protected_mcp_app),
        base_url="https://rekipe.example.test",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer invalid-token"},
            json={},
        )

    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


async def test_tool_scope_is_advertised_and_enforced() -> None:
    auth = RemoteAuthProvider(
        token_verifier=_StaticTokenVerifier(),
        authorization_servers=[ISSUER],
        base_url="https://rekipe.example.test/api/recipe-mcp",
        scopes_supported=MCP_SCOPES,
    )
    mcp = fastmcp.FastMCP("scope-test", auth=auth)

    @secure_tool(mcp, WRITE_SCOPE)
    async def write_recipe() -> dict[str, bool]:
        return {"ok": True}

    tool = await mcp._local_provider.get_tool("write_recipe")
    assert tool is not None
    assert tool.meta["securitySchemes"] == [
        {"type": "oauth2", "scopes": [READ_SCOPE, WRITE_SCOPE]},
    ]
    assert tool.auth is not None

    read_token = AccessToken(
        token="read",
        client_id="reader",
        scopes=[READ_SCOPE],
        claims={"sub": "reader"},
    )
    write_token = AccessToken(
        token="write",
        client_id="writer",
        scopes=[READ_SCOPE, WRITE_SCOPE],
        claims={"sub": "writer"},
    )
    assert await run_auth_checks(tool.auth, AuthContext(token=read_token, component=tool)) is False
    assert await run_auth_checks(tool.auth, AuthContext(token=write_token, component=tool)) is True
