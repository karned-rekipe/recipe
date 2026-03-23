# recipe — Copilot Instructions

Service REST+MCP production pour la gestion d'ingrédients, recettes, étapes et ustensiles. Lire `AGENTS.md` local.

## Règles spécifiques à ce repo

- Ports fixes : REST `:8301`, MCP `:8302` — ne pas changer sans mettre à jour `agent-recipe-creator/config.yaml`.
- MongoDB est le seul adaptateur de production — `memory` et `duckdb` uniquement pour les tests.
- Tout nouveau tool MCP doit être enregistré dans `adapters/input/fastmcp/tools.py` → `register_tools()`.
- Tests ≥ 80 % de coverage : `uv run --frozen pytest --cov-fail-under=80`.

