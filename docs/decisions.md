# docs/decisions.md — `recipe/`

## ADR-001 — MongoDB comme adaptateur de production

**Contexte :** Choix du backend de persistance pour les entités métier en production.

**Décision :** MongoDB via `motor` (async). `memory` et `duckdb` réservés au dev/test.

**Pourquoi pas l'alternative évidente (PostgreSQL/SQLite) :**
Les entités métier (`Recipe`, `Ingredient`) ont une structure flexible (ingrédients, étapes embeddées). MongoDB permet
de stocker ces structures sans migration de schéma. Motor est nativement async et s'intègre directement avec
FastAPI/asyncio.

**Conséquence sur le code :**

- `infrastructure/*_container.py` : le `case "mongodb"` instancie le repo custom `MongoDB<Entity>Repository`.
- En test : `adapters.repository: memory` dans `config.yaml` — aucune connexion réseau requise.
- `config.yaml` de prod doit définir `adapters.mongodb.uri`.

---

## ADR-002 — MCP SSE sur port dédié `:8302` (séparé de l'API REST `:8301`)

**Contexte :** Choix d'architecture pour l'exposition des tools MCP.

**Décision :** Deux processus séparés — `main_api.py` (`:8301`) et `main_mcp_sse.py` (`:8302`). Ports distincts
configurés dans `config.yaml`.

**Pourquoi pas l'alternative évidente (même port, même serveur) :**
FastMCP et FastAPI utilisent des cycles de vie différents. Séparer les transports permet de scaler indépendamment le
service REST et le service MCP, et de redémarrer l'un sans couper l'autre.

**Conséquence sur le code :**

- `agent-recipe-creator/config.yaml` référence `mcp_registry.url: http://127.0.0.1:8302/mcp`.
- Si le port change dans `recipe/config.yaml`, il faut aussi changer `agent-recipe-creator/config.yaml`.

---

## ADR-003 — Liens Recipe-Ingredient/Ustensil via copie snapshot (pas par référence pure)

**Contexte :** Comment stocker la relation entre `Recipe` et `Ingredient` / `Ustensil`.

**Décision :** Lorsqu'un ingrédient est lié à une recette (`link_ingredient_to_recipe`), une copie snapshot de
l'ingrédient (avec son UUID) est stockée dans `Recipe.ingredients`. L'UUID original est conservé pour la traçabilité.

**Pourquoi pas l'alternative évidente (référence UUID pure + join) :**
Le service n'a pas de couche ORM. Un join MongoDB nécessiterait un `$lookup` à chaque lecture de recette. La copie
snapshot évite les I/O supplémentaires et rend la recette auto-contenue. Si l'ingrédient évolue, la recette reflète
l'état au moment du lien.

**Conséquence sur le code :**

- `link_ingredient_to_recipe` est **idempotent** : si l'ingrédient est déjà lié, l'appel est silencieusement ignoré.
- `get_recipe` retourne les ingrédients embeddés sans requête additionnelle.
- `unlink_ingredient_from_recipe` retire l'ingrédient de la liste en filtrant par UUID.

---

## ADR-004 — Pattern classe `*MCP` pour enregistrer les tools FastMCP

**Contexte :** Organisation du code pour les tools MCP.

**Décision :** Chaque entité a sa propre classe `MyEntityMCP(service, logger, mcp)` qui enregistre ses tools dans son
constructeur via `@self._mcp.tool`.

**Pourquoi pas l'alternative évidente (fonctions top-level avec `@mcp.tool`) :**
Les fonctions top-level ne peuvent pas recevoir le service en injection de dépendance sans closure ou global. La classe
permet d'encapsuler l'injection et de garder le service typé sans `Depends` FastAPI.

**Conséquence sur le code :**

- `register_tools()` dans `tools.py` instancie les classes dans l'ordre.
- Les tools sont des closures qui capturent `service` et `logger` depuis `self`.
- Le constructeur de `FastMCP` est partagé entre toutes les classes `*MCP`.

---

## ADR-005 — `Step` comme entité indépendante (pas embedded dans `Recipe`)

**Contexte :** Comment modéliser les étapes d'une recette.

**Décision :** `Step` est une entité autonome avec son propre UUID, son propre repository et ses own tools MCP.
`Recipe.steps` est peuplée à la lecture via `step_service.find_by_recipe(recipe_uuid)`.

**Pourquoi pas l'alternative évidente (steps embedded dans Recipe) :**
Les steps embedded ne peuvent pas être adressées individuellement (pas d'UUID propre), ce qui complique le CRUD
granulaire. L'agent IA crée les steps une à une via `create_step` — une collection autonome est indispensable.

**Conséquence sur le code :**

- `get_recipe` appelle `step_service.find_by_recipe(uuid)` pour hydrater `Recipe.steps`.
- `StepMCP` et `StepService` sont instanciés séparément dans `recipe_container.py`.
- `RecipeMCP.__init__` reçoit à la fois `recipe_service` et `step_service`.

