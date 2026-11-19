"""Tests for adapters/input/fastmcp/dependencies.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import fastmcp


async def test_inject_tenant_uri_with_none_context():
    """Test inject_tenant_uri when context is None."""
    from adapters.input.fastmcp.dependencies import inject_tenant_uri
    
    # Should not raise
    await inject_tenant_uri(None)


async def test_inject_tenant_uri_with_context():
    """Test inject_tenant_uri with a valid context."""
    from adapters.input.fastmcp.dependencies import inject_tenant_uri
    
    ctx = MagicMock(spec=fastmcp.Context)
    cfg = MagicMock()
    cfg.adapters.multitenant = False
    
    with patch("adapters.input.fastmcp.dependencies._get_config", return_value=cfg):
        await inject_tenant_uri(ctx)


async def test_inject_tenant_uri_uses_local_tenant_when_auth_disabled(monkeypatch):
    from adapters.input.fastmcp.dependencies import inject_tenant_uri

    monkeypatch.setenv("REKIPE_AUTH_DISABLED", "true")
    monkeypatch.setenv("REKIPE_TENANT_URI", "foyer-demo")

    ctx = MagicMock(spec=fastmcp.Context)
    cfg = MagicMock()
    cfg.adapters.multitenant = True
    resolver = MagicMock()
    tenant_context = MagicMock()
    resolver.resolve = AsyncMock(return_value=tenant_context)

    with (
        patch("adapters.input.fastmcp.dependencies._get_config", return_value=cfg),
        patch("adapters.input.fastmcp.dependencies._get_header_tenant_resolver", return_value=resolver),
        patch("arclith.adapters.context.set_tenant_context") as set_tenant_context,
    ):
        await inject_tenant_uri(ctx)

    resolver.resolve.assert_awaited_once_with("foyer-demo")
    set_tenant_context.assert_called_once_with(tenant_context)


def test_inject_fn_is_cached():
    """Test that inject function is cached."""
    from adapters.input.fastmcp.dependencies import _get_inject_fn
    
    fn1 = _get_inject_fn()
    fn2 = _get_inject_fn()
    
    # Should return the same instance
    assert fn1 is fn2


def test_require_auth_mcp_fn_is_cached():
    """Test that require_auth_mcp function is cached."""
    mock_keycloak = MagicMock()
    mock_keycloak.url = "http://keycloak:8080"
    mock_keycloak.realm = "test"
    mock_keycloak.audience = "test-api"

    mock_cache_config = MagicMock()
    mock_cache_config.jwks_ttl = 3600

    mock_cfg = MagicMock()
    mock_cfg.keycloak = mock_keycloak
    mock_cfg.cache = mock_cache_config
    mock_cfg.license = None

    with patch("adapters.input.fastmcp.dependencies._get_config", return_value=mock_cfg):
        # Clear cache first
        from adapters.input.fastmcp.dependencies import _get_require_auth_mcp_fn
        _get_require_auth_mcp_fn.cache_clear()

        fn1 = _get_require_auth_mcp_fn()
        fn2 = _get_require_auth_mcp_fn()

        # Should return the same instance
        assert fn1 is fn2


async def test_require_auth_mcp_with_none_context_raises():
    """Test require_auth_mcp raises when context is None."""
    from adapters.input.fastmcp.dependencies import require_auth_mcp
    
    with pytest.raises(PermissionError, match="401: Authentification requise"):
        await require_auth_mcp(None)


async def test_require_auth_mcp_with_valid_context():
    """Test require_auth_mcp basic structure."""
    # This test validates that the function exists and has proper structure
    # Full integration testing with actual JWT is done in integration tests
    from adapters.input.fastmcp.dependencies import require_auth_mcp
    
    # The function should be defined
    assert callable(require_auth_mcp)


def test_require_auth_mcp_raises_without_keycloak_config():
    """Test that _get_require_auth_mcp_fn raises when keycloak is not configured."""
    mock_cfg = MagicMock()
    mock_cfg.keycloak = None

    with patch("adapters.input.fastmcp.dependencies._get_config", return_value=mock_cfg):
        # Clear cache
        from adapters.input.fastmcp.dependencies import _get_require_auth_mcp_fn
        _get_require_auth_mcp_fn.cache_clear()

        with pytest.raises(RuntimeError, match="config.keycloak requis"):
            _get_require_auth_mcp_fn()


async def test_require_auth_mcp_with_license_validator():
    """Test require_auth_mcp with license validation enabled."""
    # Setup mock config with license
    mock_keycloak = MagicMock()
    mock_keycloak.url = "http://keycloak:8080"
    mock_keycloak.realm = "test"
    mock_keycloak.audience = "test-api"

    mock_cache_config = MagicMock()
    mock_cache_config.jwks_ttl = 3600

    mock_license = MagicMock()
    mock_license.role = "premium"

    mock_cfg = MagicMock()
    mock_cfg.keycloak = mock_keycloak
    mock_cfg.cache = mock_cache_config
    mock_cfg.license = mock_license

    with patch("adapters.input.fastmcp.dependencies._get_config", return_value=mock_cfg):
        # Clear cache
        from adapters.input.fastmcp.dependencies import _get_require_auth_mcp_fn
        _get_require_auth_mcp_fn.cache_clear()

        # Should not raise during function creation
        fn = _get_require_auth_mcp_fn()
        assert callable(fn)
