# SKILLS.md — `recipe/`

Recettes paramétriques pour les tâches récurrentes sur le backend `recipe`.
Pour les tâches cross-repo, voir `../SKILLS.md` à la racine du workspace.

Format : chaque skill est identifiée `SK-R##` (R = Recipe), avec contexte, étapes, validation.

---

## SK-R01 — Ajouter une nouvelle entité métier

**Contexte :** ajouter une entité de domaine (ex. `Allergen`, `Cuisine`, `Source`) avec persistence et exposition REST + MCP complète.

### Référence canonique

`docs/new-entity.md` est le guide pas-à-pas complet. À suivre intégralement, dans l'ordre des couches.

### Checklist synthétique

1. **Domain**
    - `domain/models/<entity>.py` — modèle pydantic héritant de `arclith.Entity`.
    - `domain/ports/output/<entity>_repository.py` — port du repository.

2. **Application**
    - `application/use_cases/<verbe>_<entity>.py` — si use cases spécifiques.
    - `application/services/<entity>_service.py` — service métier.

3. **Adapters output (les trois)**
    - `adapters/output/memory/repositories/<entity>_repository.py`
    - `adapters/output/mongodb/repositories/<entity>_repository.py`
    - `adapters/output/duckdb/repositories/<entity>_repository.py`

4. **Adapters input**
    - `adapters/input/schemas/<entity>_schema.py` — `Create`, `Patch`, `Update`, `Read`.
    - `adapters/input/fastapi/routers/<entity>_router.py` + enregistrement dans `register.py`.
    - `adapters/input/fastmcp/tools/<entity>_tools.py` + enregistrement dans `register.py`.

5. **Infrastructure**
    - `infrastructure/containers/<entity>_container.py` — DI.
    - Ré-export dans `infrastructure/container.py`.

6. **Tests**
    - `tests/units/domain/test_<entity>.py`
    - `tests/units/adapters/output/memory/test_<entity>_repository.py`
    - Coverage globale doit rester ≥ 80 %.

7. **Documentation**
    - Mettre à jour `docs/http-conventions.md` si l'entité introduit une convention spécifique.
    - Entrée dans `journal/` à la racine du workspace.

### Validation

```bash
make precommit
make coverage
MODE=all uv run --frozen python main.py
# Vérifier dans Swagger : http://127.0.0.1:8000/docs
# Vérifier les tools MCP exposés (cf. AGENTS.md §5)
```

---

## SK-R02 — Ajouter un tool MCP

**Contexte :** exposer une nouvelle opération via MCP (consommée par `agent-recipe-creator` ou autre agent).

### Étapes

1. **`adapters/input/fastmcp/tools/<entity>_tools.py`** — ajouter la méthode dans la classe MCP de l'entité concernée :

   ```python
   class RecipeMCP:
       def __init__(self, service: RecipeService, logger: Logger, mcp: FastMCP) -> None:
           self._service = service
           self._logger = logger

           @mcp.tool()
           async def my_new_tool(arg1: str, arg2: int | None = None) -> dict:
               """Docstring exposée à l'agent — soigner la formulation."""
               result = await service.do_something(arg1, arg2)
               return result.model_dump()
   ```

2. **Vérifier l'enregistrement** : la classe `<Entity>MCP` doit déjà être instanciée dans `adapters/input/fastmcp/register.py` → `register_tools()`. Si l'entité est nouvelle, voir SK-R01.

3. **Schéma d'entrée/sortie** : si le tool prend ou renvoie un objet structuré, définir les schémas dans `adapters/input/schemas/<entity>_schema.py` et les utiliser plutôt que des `dict` libres.

4. **Test** :
    - `tests/units/adapters/input/fastmcp/test_<entity>_tools.py` — appeler le tool en mode in-memory.

### Validation

```bash
make test-unit
MODE=mcp_http uv run --frozen python main.py
# Inspecter les tools (cf. AGENTS.md §5) — le nouveau tool doit apparaître.
```

### Notes

- Le **nom du tool** est consommé tel quel par les agents (ex. `agent-recipe-creator/_mcp_registry.py`). Ne jamais le renommer sans coordonner avec les agents consommateurs.
- Garder les docstrings claires et orientées agent : c'est ce que le LLM lit pour décider d'appeler le tool.

---

## SK-R03 — Ajouter une route REST à une entité existante

**Contexte :** exposer une opération métier via FastAPI (consommée par `gwel`).

### Étapes

1. **`application/services/<entity>_service.py`** — ajouter la méthode si elle n'existe pas. Garder le service ignorant de FastAPI (pas de `Request`, pas de `Depends`).

2. **`adapters/input/schemas/<entity>_schema.py`** — schémas d'entrée (`Patch`, `Update`...) et de sortie si différents de l'existant.

3. **`adapters/input/fastapi/routers/<entity>_router.py`** — ajouter la route dans la classe `<Entity>Router` :

   ```python
   class RecipeRouter:
       def __init__(self, service: RecipeService, logger: Logger) -> None:
           self.router = APIRouter(prefix="/recipe/v1", tags=["recipe"])

           @self.router.post("/{recipe_id}:duplicate", response_model=RecipeSchema)
           async def duplicate(recipe_id: UUID) -> Recipe:
               return await service.duplicate(recipe_id)
   ```

4. Le router est déjà enregistré dans `adapters/input/fastapi/register.py` (rien à faire si l'entité existe).

5. **Test** :
    - `tests/units/adapters/input/fastapi/test_<entity>_router.py` — utiliser `httpx.AsyncClient` + `app` en mode `memory`.

### Validation

```bash
make test-unit
MODE=api uv run --frozen python main.py
# Swagger : http://127.0.0.1:8000/docs — la route doit apparaître.
```

### Notes

- Suivre les conventions de `docs/http-conventions.md` (codes d'erreur, format de réponse, en-têtes).
- Pour une opération non-CRUD, préférer `:verbe` à un sous-chemin (ex. `:duplicate`, `:merge`) — convention REST cohérente avec le reste du projet.

---

## SK-R04 — Ajouter un use case applicatif

**Contexte :** logique métier qui dépasse un simple CRUD (recherche, fusion, validation cross-entité).

### Quand créer un use case plutôt qu'une méthode de service

- Le use case implique **plusieurs étapes** ou **plusieurs ports** (ex. lire un repo, en écrire un autre, logger, émettre un évènement).
- Il a une **valeur métier nommable** ("Find Ingredient By Name", "Merge Duplicate Equipment").
- Il bénéficie d'être testé **isolément** du service.

Sinon : ajouter une méthode au service suffit.

### Étapes

1. **`application/use_cases/<verbe>_<entity>.py`** :

   ```python
   from arclith.domain.ports.logger import Logger
   from domain.models.recipe import Recipe
   from domain.ports.output.recipe_repository import RecipeRepository


   class FindRecipeByNameUseCase:
       def __init__(self, repository: RecipeRepository, logger: Logger) -> None:
           self._repo = repository
           self._logger = logger

       async def execute(self, name: str) -> list[Recipe]:
           self._logger.info("🔍 Finding recipes by name", name=name)
           result = [r for r in await self._repo.find_by_name(name) if not r.is_deleted]
           self._logger.info("✅ Recipes found", count=len(result))
           return result
   ```

2. **Exposer** dans `application/use_cases/__init__.py`.

3. **Câbler** dans le service : injecter le use case dans le constructeur, exposer une méthode `find_by_name` qui appelle `_uc.execute()`.

4. **Test** :
    - `tests/units/application/use_cases/test_<verbe>_<entity>.py` — repository in-memory + assertions.

### Validation

```bash
make test-unit
make typecheck
```

---

## SK-R05 — Changer d'adapter de persistence (dev local)

**Contexte :** basculer entre `memory`, `duckdb`, `mongodb` pour debug / test rapide / démo offline.

### Étapes

1. **`config/adapters/adapters.yaml`** — modifier la clé `repository` :

   ```yaml
   adapters:
     repository: memory   # memory | duckdb | mongodb
   ```

2. **Pour `mongodb`** : `config/adapters/output/mongodb.yaml` — vérifier `uri` et `db_name`.

3. **Pour `duckdb`** : `config/adapters/output/duckdb.yaml` — vérifier `path`.

### Validation

```bash
MODE=api uv run --frozen python main.py
curl -fsS http://127.0.0.1:9000/health
# Faire un POST puis un GET pour vérifier que le repo répond.
```

### Notes

- **Production = MongoDB obligatoire**. Ne jamais déployer avec `memory` ou `duckdb`.
- En cas de doute, vérifier les logs au démarrage : le service log l'adapter actif.

---

## SK-R06 — Diagnostiquer un échec d'auth Keycloak

**Contexte :** appel API renvoie `401` ou Swagger ne se connecte pas.

### Étapes

1. Vérifier que Keycloak est accessible :

   ```bash
   curl -fsS http://127.0.0.1:5990/realms/sample/.well-known/openid-configuration | jq .issuer
   # Doit retourner : "http://127.0.0.1:5990/realms/sample"
   ```

2. Vérifier que le realm `sample` et le client `sample` existent. Si non :

   ```bash
   # Depuis la racine du workspace
   python scripts/seed_keycloak.py
   ```

3. Vérifier `config/adapters/input/keycloak.yaml` :
    - `realm` correspond à celui de Keycloak ;
    - `client_id` correspond ;
    - les `redirect_uris` incluent `http://127.0.0.1:8000/docs/oauth2-redirect`.

4. Obtenir un token et inspecter :

   ```bash
   curl -X POST "http://127.0.0.1:5990/realms/sample/protocol/openid-connect/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "client_id=sample" -d "username=test" -d "password=test" -d "grant_type=password" \
     | jq
   ```

   Si le token est obtenu mais l'API renvoie quand même `401`, le souci vient du service `recipe` (audience, issuer, signature).

### Validation

Swagger UI authentifié, et :

```bash
TOKEN=$(...)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/recipe/v1/  # doit renvoyer 200
```

---

## SK-R07 — Vérifier que les tools MCP attendus sont exposés

**Contexte :** un agent (ex. `agent-recipe-creator`) ne trouve pas un tool — vérifier côté serveur.

### Étapes

1. Lancer le service en mode MCP :

   ```bash
   MODE=mcp_http uv run --frozen python main.py
   ```

2. Lister les tools enregistrés :

   ```bash
   uv run --frozen python -c "
   from adapters.input.fastmcp.register import register_tools
   from arclith import Arclith
   from pathlib import Path
   import asyncio

   a = Arclith(Path('config'))
   mcp = a.fastmcp('inspect')
   register_tools(mcp, a)
   tools = asyncio.run(mcp.list_tools())
   for t in tools:
       print(f'{t.name:40s}  {t.description[:60] if t.description else \"\"}')"
   ```

3. Comparer avec ce qu'attend l'agent :
    - Pour `agent-recipe-creator`, voir `agent-recipe-creator/adapters/output/recipe_agent/_mcp_registry.py` — chaque méthode publique doit correspondre à un tool listé ici.

### Si un tool manque

- Vérifier que la classe `<Entity>MCP` correspondante est bien instanciée dans `adapters/input/fastmcp/register.py` → `register_tools()`.
- Vérifier que le décorateur `@mcp.tool()` est présent sur la méthode.

---

## SK-R08 — Restaurer ou exporter la base MongoDB locale

**Contexte :** repartir d'un état connu, partager un dump avec un collègue.

Voir `../SKILLS.md` SK-W03 — la procédure est cross-repo.

Spécifique à ce repo : la base par défaut est `recipe` (cf. `config/adapters/output/mongodb.yaml`).
