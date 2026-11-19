# AGENTS.md — `recipe/`

Document d'entrée pour tout agent de codage qui intervient sur ce repo.
Lecture obligatoire avant toute modification.

Pour le contexte global du projet et les conventions transverses, voir `../AGENTS.md` à la racine du workspace.

---

## 1. Rôle

`recipe/` est le **backend du domaine recettes** de Rekipe. Il détient les entités métier suivantes :

- recettes (`Recipe`), avec leurs étapes (`Step`), ingrédients utilisés (`RecipeIngredient`) et équipements utilisés (`RecipeEquipment`) ;
- ingrédients (`Ingredient`) avec groupes (`IngredientGroup`) et rayons (`IngredientRayon`) ;
- équipements / ustensiles (`Equipment`) ;
- tags (`Tag`).

Il expose ces entités via deux transports :

- **REST** (FastAPI) pour le frontend `gwel` ;
- **MCP** (FastMCP) pour les agents IA (`agent-recipe-creator`, etc.).

Le service est consommé par tout le reste du périmètre Rekipe : il est le **point de vérité unique** pour les données catalogue et recettes. Les autres services (`meal-planner`, `shopping`) référencent des recettes par UUID, ne les dupliquent jamais.

## 2. Stack et ports

| Élément | Valeur |
|---|---|
| Langage | Python 3.13 |
| Gestionnaire deps | `uv` (lock : `uv.lock`) |
| Framework de base | `arclith` (Entity, Repository, Service, Logger, FastAPI/FastMCP factories) |
| Web | FastAPI |
| MCP | FastMCP |
| Stockage prod | MongoDB (port `5971` en local) |
| Stockages alternatifs | `memory` (tests), `duckdb` (alt) |
| Auth | Keycloak (port `5990` en local) |
| REST | `8000` (proxy via pont `8301` pour `gwel`) |
| MCP HTTP | `8001` (proxy via pont `8302`) |
| Probes (health/ready/metrics) | `9000` |

Les ponts `83xx` sont gérés par `start_services.sh` à la racine du workspace.
**Ne jamais changer ces ports** sans mettre à jour en parallèle :

- `start_services.sh`
- `gwel/vite.config.ts` (proxies)
- `agent-recipe-creator/config.yaml` (clients MCP / REST de l'agent)

## 3. Architecture locale

Architecture hexagonale stricte :

```
domain/
  models/              # Entités métier (Recipe, Ingredient, Equipment, Tag, ...)
                       # Ne dépend que de pydantic et arclith.Entity
  ports/
    output/            # Interfaces des repositories (RecipeRepository, ...)

application/
  services/            # Orchestration métier (RecipeService, IngredientService, ...)
  use_cases/           # Cas d'usage spécifiques (find_by_name, find_ingredient_by_name, ...)

adapters/
  input/
    fastapi/
      routers/         # Routers REST par entité (recipe_router, ingredient_router, ...)
      register.py      # register_routers(app, arclith)
      dependencies.py
    fastmcp/
      tools/           # Tools MCP par entité (recipe_tools, ingredient_tools, ...)
      prompts/
      resources/
      register.py      # register_tools / register_prompts / register_resources
    schemas/           # Schémas pydantic d'entrée/sortie REST + MCP (par entité)
  output/
    mongodb/           # Adapter prod
      repositories/
    memory/            # Adapter tests
      repositories/
    duckdb/            # Adapter alternatif
      repositories/

infrastructure/
  containers/          # DI par entité (build_<entity>_service)
  container.py         # Façade qui ré-exporte les builders
  logging_setup.py
  purge_registry.py    # Soft-delete et purge

config/                # Configuration YAML par adapter (mongodb, fastapi, fastmcp, keycloak, ...)
tests/units/           # Tests unitaires par couche (domain, application, adapters, infrastructure)
main.py                # Entry point unique, MODE env var sélectionne le transport
```

### Modes de lancement

`main.py` lit la variable d'environnement `MODE` :

| MODE | Transports actifs | Ports |
|---|---|---|
| `api` (par défaut) | FastAPI REST + probes | `8000`, `9000` |
| `mcp_http` | MCP streamable-HTTP + probes | `8001`, `9000` |
| `mcp_sse` | MCP SSE + probes | `8001`, `9000` |
| `all` | API + MCP HTTP + probes (dev / POC) | `8000`, `8001`, `9000` |

## 4. Règles de développement

### Règles transverses (rappel — voir `../AGENTS.md` §4)

- Architecture hexagonale stricte. `domain/` ne dépend que de `arclith` + `pydantic`. **Aucun import framework dans `domain/`**.
- MongoDB est le seul adaptateur de production. `memory` et `duckdb` ne sont utilisés que pour les tests / dev local.
- Les recettes stockent des **UUID** vers ingrédients, équipements, tags. Hydratation à la lecture. Ne jamais dupliquer.
- Une recette sans ingrédients passe au statut `draft` et n'est pas exposée au meal planner (filtre API `meal_planner_eligible=true`).
- La suppression d'une ressource catalogue référencée par une recette doit être bloquée.

### Règles spécifiques à ce repo

- **Tout nouveau tool MCP** doit être enregistré dans `adapters/input/fastmcp/register.py` → `register_tools()`. Sinon il n'est pas exposé.
- **Toute nouvelle route REST** doit être enregistrée dans `adapters/input/fastapi/register.py` → `register_routers()`.
- **Toute nouvelle entité** doit être ajoutée dans les **trois** adaptateurs de persistence (`memory`, `mongodb`, `duckdb`) pour rester testable. Voir `docs/new-entity.md` pour le guide complet.
- **Couverture de tests ≥ 80 %** : `make coverage` (échec si `--cov-fail-under=80` n'est pas atteint).
- **Pre-commit** : `make precommit` (lint + typecheck + sécurité) avant tout push.
- **Jamais de secret** dans `config/*.yaml` versionné. Les secrets passent par Vault (cf. `docs/vault.md`).

### Qualité

```bash
make lint         # ruff check
make typecheck    # mypy
make security     # bandit
make complexity   # radon (échec si CC >= C)
make test         # pytest -v
make test-unit    # pytest -v -m "not e2e"
make test-e2e     # pytest -v -m "e2e"
make coverage     # pytest --cov ; échec si < 80 %
make quality      # lint + security + complexity + typecheck + coverage (CI complète)
make precommit    # lint + typecheck + security (pre-push rapide)
```

Hooks Git : `make setup` une fois pour activer `.githooks/`.

## 5. Commandes utiles

### Lancement local manuel

```bash
uv sync --frozen
MODE=all uv run --frozen python main.py
```

(Préférer `./start_services.sh up recipe` depuis la racine du workspace pour rester cohérent avec le reste de la stack.)

### Tester l'API authentifiée

```bash
TOKEN=$(curl -s -X POST "http://127.0.0.1:5990/realms/sample/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=sample" -d "username=test" -d "password=test" -d "grant_type=password" \
  | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/recipe/v1/
```

### Inspecter les tools MCP exposés

```bash
uv run --frozen python -c "
from adapters.input.fastmcp.register import register_tools
from arclith import Arclith
from pathlib import Path
import asyncio

a = Arclith(Path('config'))
mcp = a.fastmcp('inspect')
register_tools(mcp, a)
print([t.name for t in asyncio.run(mcp.list_tools())])
"
```

## 6. Fichiers à lire en premier

Pour comprendre l'architecture et les flux :

1. `main.py` — entry point, modes de lancement.
2. `domain/models/recipe.py` — modèle métier central.
3. `domain/ports/output/recipe_repository.py` — contrat du repository.
4. `application/services/recipe_service.py` — orchestration du domaine recette.
5. `adapters/input/fastapi/register.py` — câblage des routers REST.
6. `adapters/input/fastmcp/register.py` — câblage des tools MCP.
7. `adapters/output/mongodb/repositories/recipe_repository.py` — implémentation prod.
8. `infrastructure/containers/recipe_container.py` — DI du service recipe.
9. `infrastructure/container.py` — façade DI globale.
10. `config/adapters/adapters.yaml` + `config/app.yaml` — configuration.

Pour ajouter une fonctionnalité, lire en plus :

- `docs/new-entity.md` — guide complet pour ajouter une entité (référence canonique).
- `docs/http-conventions.md` — conventions HTTP partagées avec les autres backends.
- `docs/implementation.md` — détails d'implémentation.
- `docs/vault.md` — gestion des secrets.

Pour les recettes paramétriques de tâches récurrentes : `SKILLS.md` (ce repo).

## 7. Règle du journal — rappel

Toute modification non triviale doit être consignée dans `journal/YYYY-MM-DD-slug.md` à la **racine du workspace**. Voir `../AGENTS.md` §6 et `../journal/README.md`.

Cas spécifiques à ce repo qui exigent une entrée journal :

- ajout, suppression ou renommage d'une entité métier ;
- ajout d'un nouveau tool MCP ou d'une nouvelle route REST ;
- changement de port (REST, MCP, probes) ;
- changement de schéma de données (migration MongoDB) ;
- ajout / retrait d'un adapter de persistence ;
- évolution des conventions HTTP partagées (auquel cas mettre à jour `docs/http-conventions.md` et signaler dans le journal).

## 8. Hors scope

- Les **décisions produit** (vision, glossaire métier, ADR métier) vivent dans `recipe-project/docs/`. Ne pas les recopier ici.
- Le **frontend** vit dans `gwel/`. Les règles UI/UX y sont documentées localement.
- Les **agents IA** consommateurs (création de recette assistée, etc.) vivent dans `agent-recipe-creator/`. Ce repo ne contient **jamais** de logique LLM.
