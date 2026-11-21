from __future__ import annotations

from functools import cache
import os
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
        request_context = ctx.request_context
        if request_context is None:
            return {}
        request = request_context.request
        if request is None:
            return {}
        return dict(request.headers)
    except Exception:
        return {}


def _is_auth_disabled() -> bool:
    return os.getenv("REKIPE_AUTH_DISABLED", "").lower() in {"1", "true", "yes", "on"}


def _get_local_tenant_id() -> str | None:
    tenant_id = os.getenv("REKIPE_TENANT_URI")
    if _is_auth_disabled() and tenant_id:
        return tenant_id
    return None


async def _inject_from_tenant_id(tenant_id: str) -> None:
    from arclith.adapters.context import set_tenant_context

    set_tenant_context(await _get_header_tenant_resolver().resolve(tenant_id))


async def _inject_from_tenant_header(ctx: fastmcp.Context) -> bool:
    config = _get_config()
    if not config.adapters.multitenant or not _is_auth_disabled():
        return False

    headers = _extract_headers(ctx)
    tenant_id = headers.get("x-tenant-uri") or headers.get("X-Tenant-URI")
    if not tenant_id:
        return False

    await _inject_from_tenant_id(tenant_id)
    return True


async def _inject_from_local_tenant() -> bool:
    config = _get_config()
    if not config.adapters.multitenant:
        return False

    tenant_id = _get_local_tenant_id()
    if not tenant_id:
        return False

    await _inject_from_tenant_id(tenant_id)
    return True


async def inject_tenant_uri(ctx: fastmcp.Context | None) -> None:
    if ctx is not None:
        if await _inject_from_tenant_header(ctx):
            return
        if await _inject_from_local_tenant():
            return
        await _get_inject_fn()(ctx)
