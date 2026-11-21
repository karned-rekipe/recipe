from __future__ import annotations

import fastmcp
from fastmcp.exceptions import AuthorizationError
from fastmcp.server.dependencies import get_access_token

from adapters.input.fastmcp.authorization import secure_tool


class IdentityMCP:
    """Expose the stable identity represented by the current OAuth token."""

    def __init__(self, mcp: fastmcp.FastMCP) -> None:
        @secure_tool(
            mcp,
            meta={"openai/profile": True},
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "openWorldHint": False,
            },
        )
        async def get_profile() -> dict[str, str]:
            """Return the profile represented by the authenticated OAuth token."""

            access_token = get_access_token()
            if access_token is None:
                raise AuthorizationError("Authenticated profile unavailable")

            claims = access_token.claims
            profile = {"id": str(claims["sub"])}
            for source, target in (
                ("name", "name"),
                ("email", "email"),
                ("preferred_username", "nickname"),
            ):
                value = claims.get(source)
                if isinstance(value, str) and value.strip():
                    profile[target] = value
            return profile
