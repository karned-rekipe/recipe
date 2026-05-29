from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Callable

import fastmcp

from arclith.adapters.input.fastmcp.dependencies import make_inject_tenant_uri
from arclith.infrastructure.config import load_config_dir

_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config"


@cache
def _get_config():
    return load_config_dir(_CONFIG_PATH)


@cache
def _get_inject_fn() -> Callable:
    return make_inject_tenant_uri(_get_config())


@cache
def _get_header_tenant_resolver():
    from arclith.adapters.output.memory.cache_adapter import MemoryCacheAdapter
    from arclith.adapters.output.vault.tenant_adapter import VaultTenantResolver

    config = _get_config()
    if config.tenant is None:
        raise RuntimeError("config.tenant requis en mode multitenant")
    return VaultTenantResolver(
        adapter_name="mongodb",
        addr=config.tenant.vault_addr,
        mount=config.tenant.vault_mount,
        path_prefix=config.tenant.vault_path_prefix,
        cache=MemoryCacheAdapter(),
        ttl_s=config.cache.tenant_uri_ttl,
    )


def _extract_headers(ctx: fastmcp.Context) -> dict[str, str]:
    try:
        request = ctx.request_context.request
        if request is None:
            return {}
        return dict(request.headers)
    except Exception:
        return {}


async def _inject_from_tenant_header(ctx: fastmcp.Context) -> bool:
    config = _get_config()
    if not config.adapters.multitenant:
        return False

    headers = _extract_headers(ctx)
    tenant_id = headers.get("x-tenant-uri") or headers.get("X-Tenant-URI")
    if not tenant_id:
        return False

    from arclith.adapters.context import set_tenant_context

    set_tenant_context(await _get_header_tenant_resolver().resolve(tenant_id))
    return True


async def inject_tenant_uri(ctx: fastmcp.Context | None) -> None:
    if ctx is not None:
        if await _inject_from_tenant_header(ctx):
            return
        await _get_inject_fn()(ctx)


@cache
def _get_require_auth_mcp_fn() -> Callable:
    from arclith.adapters.input.fastmcp.auth import make_require_auth_tool
    from arclith.adapters.input.jwt.decoder import JWTDecoder
    from arclith.adapters.input.license.validator import RoleLicenseValidator
    from arclith.adapters.output.memory.cache_adapter import MemoryCacheAdapter

    config = _get_config()
    kc = config.keycloak
    if kc is None:
        raise RuntimeError("config.keycloak requis pour require_auth_mcp — ajouter la section dans config.yaml")
    decoder = JWTDecoder(
        jwks_uri=f"{kc.url}/realms/{kc.realm}/protocol/openid-connect/certs",
        audience=kc.audience,
        cache=MemoryCacheAdapter(),
        ttl_s=config.cache.jwks_ttl,
    )
    license_validator = RoleLicenseValidator(config.license.role) if config.license else None
    return make_require_auth_tool(jwt_decoder=decoder, license_validator=license_validator)


async def require_auth_mcp(ctx: fastmcp.Context | None) -> dict:
    if ctx is None:
        raise PermissionError("401: Authentification requise (transport stdio non supporté)")
    return await _get_require_auth_mcp_fn()(ctx)
