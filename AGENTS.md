# AGENTS.md — `recipe/`

## Contexte global

`recipe/` est le service de production de Rekipe. Il expose les entités métier (`Ingredient`, `Recipe`, `Step`,
`Ustensil`) via REST (`:8301`) et MCP (`:8302`). Il est la seule source de vérité des données — `agent-recipe-creator/`
interagit exclusivement via son interface MCP.

## Rôle

- CRUD complet sur 4 entités métier
- Exposition des tools MCP consommés par l'agent IA
- Persistance MongoDB en production (memory/DuckDB en dev/test)
- Support du soft-delete avec rétention configurable (défaut 30 jours)

## Règles de développement

- Architecture hexagonale stricte : `domain → application → adapters → infrastructure`
- `domain/` n'importe que `arclith` (Entity) et `pydantic` — zéro dépendance framework web
- Chaque entité a son propre container dans `infrastructure/`
- Tests ≥ 80 % — `uv run --frozen pytest --cov-fail-under=80`
- Pre-commit : `uv run --frozen ruff check` + `uv run --frozen mypy`

## Entités de domaine

| Entité       | Champs principaux                                                                   | Port                   |
|--------------|-------------------------------------------------------------------------------------|------------------------|
| `Ingredient` | `name` (normalisé), `unit?`                                                         | `IngredientRepository` |
| `Recipe`     | `name`, `description?`, `nutriscore?`, `ingredients[]?`, `ustensils[]?`, `steps[]?` | `RecipeRepository`     |
| `Step`       | `recipe_uuid`, `name` (max 80 car.), `description?`                                 | `StepRepository`       |
| `Ustensil`   | `name` (normalisé)                                                                  | `UstensilRepository`   |

`Recipe` agrège `Ingredient`, `Ustensil` et `Step` par référence UUID — les liens sont gérés via les tools MCP dédiés.

## Architecture locale

```
domain/
  models/         ingredient.py, recipe.py, step.py, ustensil.py
  ports/          *_repository.py (sous-classes de Repository[T])

application/
  use_cases/      use cases custom (ex. find_by_recipe pour Step)
  services/       *_service.py (sous-classes de BaseService[T])

adapters/
  input/
    fastapi/      router.py + *_router.py (REST :8301)
    fastmcp/      tools.py + *_tools.py (MCP :8302)
    schemas/      *_schema.py (sérialisation API)
  output/
    mongodb/      *_repository.py
    duckdb/       *_repository.py
    memory/       *_repository.py

infrastructure/
  container.py            re-exporte tous les build_*_service
  ingredient_container.py
  recipe_container.py
  step_container.py
  ustensil_container.py
```

### Flux de données (MCP)

```
MCP client → fastmcp tool → inject_tenant_uri() → *Service.method() → *Repository → MongoDB
```

### Flux de données (REST)

```
HTTP → FastAPI router → *Service.method() → *Repository → MongoDB
```

## Tools MCP exposés (`:8302`)

### Ingrédients (`IngredientMCP`)

| Tool                                   | Description                           |
|----------------------------------------|---------------------------------------|
| `create_ingredient(name, unit?)`       | Crée un ingrédient réutilisable       |
| `get_ingredient(uuid)`                 | Récupère par UUID                     |
| `update_ingredient(uuid, name, unit?)` | Remplace name + unit                  |
| `delete_ingredient(uuid)`              | Soft-delete                           |
| `list_ingredients(name?)`              | Liste tous (filtre optionnel par nom) |
| `duplicate_ingredient(uuid)`           | Duplique avec nouveau UUID            |

### Ustensiles (`UstensilMCP`)

| Tool                          | Description                    |
|-------------------------------|--------------------------------|
| `create_ustensil(name)`       | Crée un ustensile réutilisable |
| `get_ustensil(uuid)`          | Récupère par UUID              |
| `update_ustensil(uuid, name)` | Renomme                        |
| `delete_ustensil(uuid)`       | Soft-delete                    |
| `list_ustensils(name?)`       | Liste tous                     |
| `duplicate_ustensil(uuid)`    | Duplique                       |

### Recettes (`RecipeMCP`)

| Tool                                                   | Description                                 |
|--------------------------------------------------------|---------------------------------------------|
| `create_recipe(name, description?, nutriscore?)`       | Crée une recette vide                       |
| `get_recipe(uuid)`                                     | Récupère avec steps, ingredients, ustensils |
| `update_recipe(uuid, name, description?, nutriscore?)` | Met à jour les métadonnées                  |
| `delete_recipe(uuid)`                                  | Soft-delete                                 |
| `list_recipes(name?)`                                  | Liste toutes                                |

### Étapes (`StepMCP`)

| Tool                                           | Description                       |
|------------------------------------------------|-----------------------------------|
| `create_step(recipe_uuid, name, description?)` | Crée une étape liée à une recette |
| `get_step(uuid)`                               | Récupère par UUID                 |
| `update_step(uuid, name, description?)`        | Met à jour                        |
| `delete_step(uuid)`                            | Soft-delete                       |
| `list_steps(recipe_uuid)`                      | Liste les étapes d'une recette    |

### Liens recette-ingrédients (`RecipeIngredientMCP`)

| Tool                                                          | Description                         |
|---------------------------------------------------------------|-------------------------------------|
| `link_ingredient_to_recipe(recipe_uuid, ingredient_uuid)`     | Attache un ingrédient à une recette |
| `unlink_ingredient_from_recipe(recipe_uuid, ingredient_uuid)` | Détache                             |
| `list_recipe_ingredients(recipe_uuid)`                        | Liste les ingrédients liés          |

### Liens recette-ustensiles (`RecipeUstensilMCP`)

| Tool                                                      | Description               |
|-----------------------------------------------------------|---------------------------|
| `link_ustensil_to_recipe(recipe_uuid, ustensil_uuid)`     | Attache un ustensile      |
| `unlink_ustensil_from_recipe(recipe_uuid, ustensil_uuid)` | Détache                   |
| `list_recipe_ustensils(recipe_uuid)`                      | Liste les ustensiles liés |

### Prompts et Resources MCP

- `suggest_recipe` — prompt : suggère une recette à partir des ingrédients disponibles
- `how_to_use(ingredient_name)` — prompt : explique comment utiliser un ingrédient
- `ingredients://all` — resource : liste complète des ingrédients en JSON
- `ingredient://{uuid}` — resource : un ingrédient par UUID

## Configuration (`config.yaml`)

```yaml
adapters:
  repository: mongodb   # memory | mongodb | duckdb
  multitenant: false
  mongodb:
    uri: mongodb://localhost:5971
    db_name: recipe
api:
  port: 8301
mcp:
  port: 8302
soft_delete:
  retention_days: 30
```

## Commandes utiles

```bash
# Démarrage
uv run --frozen python main_api.py        # REST :8301
uv run --frozen python main_mcp_sse.py    # MCP SSE :8302
uv run --frozen python main_mcp_http.py   # MCP HTTP :8302

# Qualité
uv run --frozen ruff check domain adapters application infrastructure
uv run --frozen pytest -v
uv run --frozen pytest -v -m "not e2e"
```

## Fichiers à lire en premier

1. `domain/models/recipe.py` — modèle central
2. `adapters/input/fastmcp/tools.py` — point d'entrée de l'exposition MCP
3. `infrastructure/container.py` — DI et câblage
4. `adapters/input/fastmcp/ingredient_tools.py` — pattern de référence pour un tool MCP
5. `infrastructure/ingredient_container.py` — pattern de référence pour un container

