from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Annotated, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from arclith.adapters.input.fastapi.dependencies import make_inject_tenant_uri
from arclith.infrastructure.config import load_config_dir

_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config"
_http_bearer = HTTPBearer(auto_error=False)


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


async def _inject_from_tenant_header(request: Request) -> bool:
    config = _get_config()
    if not config.adapters.multitenant:
        return False

    tenant_id = request.headers.get("X-Tenant-URI") or request.headers.get("x-tenant-uri")
    if not tenant_id:
        return False

    from arclith.adapters.context import set_tenant_context

    set_tenant_context(await _get_header_tenant_resolver().resolve(tenant_id))
    return True


async def inject_tenant_uri(request: Request) -> None:
    if await _inject_from_tenant_header(request):
        return
    await _get_inject_fn()(request)


@cache
def _get_require_auth_fn() -> Callable:
    from arclith.adapters.input.fastapi.auth import make_require_auth
    from arclith.adapters.input.jwt.decoder import JWTDecoder
    from arclith.adapters.input.license.validator import RoleLicenseValidator
    from arclith.adapters.output.memory.cache_adapter import MemoryCacheAdapter

    config = _get_config()
    kc = config.keycloak
    if kc is None:
        raise RuntimeError("config.keycloak requis pour require_auth — ajouter la section dans config.yaml")
    decoder = JWTDecoder(
        jwks_uri=f"{kc.url}/realms/{kc.realm}/protocol/openid-connect/certs",
        audience=kc.audience,
        cache=MemoryCacheAdapter(),
        ttl_s=config.cache.jwks_ttl,
    )
    license_validator = RoleLicenseValidator(config.license.role) if config.license else None
    return make_require_auth(jwt_decoder=decoder, license_validator=license_validator)


async def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)],
) -> dict:
    return await _get_require_auth_fn()(credentials)
