"""Tests for adapters/input/fastmcp/dependencies.py."""

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
