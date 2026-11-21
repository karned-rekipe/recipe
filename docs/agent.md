# Connecter une IA au serveur MCP `recipe`

Le service `recipe` expose son catalogue et ses opérations métier avec
FastMCP, via la factory MCP d'Arclith. Il n'embarque pas de logique LLM : une
IA ou un agent externe se connecte au serveur MCP et appelle les tools exposés.

## Démarrer le serveur

Depuis le repo `recipe` :

```bash
uv sync --frozen
MODE=mcp_http uv run --frozen python main.py
```

Le transport streamable HTTP est alors disponible sur :

```text
http://127.0.0.1:8001/mcp
```

Pour lancer simultanément l'API REST et le MCP pendant le développement :

```bash
MODE=all uv run --frozen python main.py
```

Depuis la racine du workspace, la commande recommandée reste :

```bash
./rekipe_dev.sh up recipe-stack
```

Elle charge la configuration locale, prépare le tenant de développement et
démarre les dépendances nécessaires sans placer de secret dans Git.

## Tools recettes

Le serveur expose notamment :

- `create_recipe` : créer un agrégat recette complet ;
- `get_recipe` : lire une recette par UUID ;
- `update_recipe` : remplacer une recette ;
- `patch_recipe` : modifier partiellement une recette ;
- `delete_recipe` : supprimer logiquement une recette ;
- `list_recipes` : lister et filtrer les recettes ;
- `duplicate_recipe` : dupliquer une recette.

Les tools des catalogues ingrédients, équipements et tags sont enregistrés sur
le même serveur. Le prompt MCP `mcp_help` fournit la liste des capacités à un
client qui les découvre dynamiquement.

## Lister les recettes sans image

Appeler `list_recipes` avec le filtre suivant :

```json
{
  "has_main_image": false,
  "offset": 0,
  "limit": 50
}
```

Le filtre cible l'image principale. Les valeurs absentes, nulles, vides ou
composées uniquement d'espaces sont considérées comme une image manquante.

Les filtres sont combinés avec une logique `AND`. Un agent peut par exemple
limiter son lot aux recettes actives et favorites :

```json
{
  "has_main_image": false,
  "status": "active",
  "favorite": true,
  "offset": 0,
  "limit": 20
}
```

`list_recipes` conserve une réponse sous forme de liste pour rester compatible
avec les agents existants. `offset` et `limit` permettent de traiter le
catalogue par lots ; `limit` est plafonné à 200.

## Filtres disponibles

Les filtres optionnels sont :

- `name` ;
- `ingredient_uuid`, `equipment_uuid`, `tag_uuid` ;
- `difficulty`, `origin_country`, `price` ;
- `favorite`, `season_month`, `status` ;
- `meal_planner_eligible` ;
- `has_main_image` ;
- `offset`, `limit` pour la pagination.

## Tenant et authentification

Tous les tools injectent le contexte tenant avant d'accéder aux données. En
développement local, `rekipe_dev.sh` configure le tenant `foyer-demo` lorsque
l'authentification est explicitement désactivée. Un client HTTP peut aussi
transmettre `X-Tenant-URI` dans ce mode uniquement.

Hors développement local, le client MCP doit transmettre un jeton Bearer
valide. Le tenant est alors résolu depuis le contexte authentifié ; un en-tête
fourni arbitrairement par le client ne doit pas permettre de changer de foyer.

## Vérifier les tools enregistrés

```bash
uv run --frozen python -c "
from adapters.input.fastmcp.register import register_tools
from arclith import Arclith
from pathlib import Path
import asyncio

arclith = Arclith(Path('config'))
mcp = arclith.fastmcp('inspect')
register_tools(mcp, arclith)
print([tool.name for tool in asyncio.run(mcp.list_tools())])
"
```

La liste doit contenir au minimum `list_recipes`, `get_recipe`,
`create_recipe`, `patch_recipe` et `delete_recipe`.
