from pathlib import Path

from arclith import Arclith

from adapters.input.fastmcp.register import register_tools

arclith = Arclith(Path(__file__).parent / "config.yaml")
mcp = arclith.fastmcp("Rekipe")
register_tools(mcp, arclith)

if __name__ == "__main__":
    arclith.run_mcp_stdio(mcp)
