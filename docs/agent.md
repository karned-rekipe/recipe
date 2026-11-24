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
- `normalize_origin_country` : normaliser un code pays IA sans bloquer une
  recette lorsque le code est inconnu ;
- `update_recipe` : remplacer une recette ;
- `patch_recipe` : modifier partiellement une recette ;
- `generate_recipe_image` : générer et rattacher l'image principale via le
  service `media`, sans exposer ce service au client MCP ;
- `generate_ingredient_image` : générer une image d'ingrédient et créer une
  suggestion `media_profile` validable via l'agent interne ;
- `generate_equipment_image` : générer et rattacher individuellement l'image
  principale d'un ustensile ou équipement ;
- `ai_enrich_recipe` : enrichir et reclasser une fiche existante via le MCP
  interne de l'agent, sans exposer cet agent au client ;
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

## Générer l'image d'une recette

Après avoir sélectionné une recette sans image, appeler le tool MCP
`generate_recipe_image` :

```json
{
  "uuid": "01951234-5678-7abc-def0-123456789abc"
}
```

Le service `recipe` charge le nom et les ingrédients, construit le brief métier,
demande à l'API générique de `media` de générer et stocker l'image, puis persiste
l'URL obtenue dans `main_image`. Le
client MCP ne doit donc pas appeler `media` directement. La réponse contient
la recette mise à jour, les métadonnées de l'image et le fournisseur utilisé.

La même façade est disponible pour les clients REST authentifiés :

```http
POST /v1/recipes/{uuid}/main-image
Content-Type: application/json

{
  "replace_existing": false
}
```

Le frontend appelle cette route de `recipe` ; il ne doit ni orchestrer `media`
directement, ni persister lui-même l'URL retournée.

Par sécurité, le tool refuse de remplacer une image existante. Le paramètre
`replace_existing=true` doit être fourni explicitement pour régénérer une
image. Aucun prompt libre n'est accepté : `recipe` construit toujours le brief
depuis la fiche faisant autorité et ses ingrédients hydratés.

Une réservation atomique temporaire est portée par MongoDB pendant la
génération. Elle empêche deux appels REST/MCP concurrents de déclencher deux
générations payantes et la finalisation ne modifie que `main_image`, afin de
ne pas écraser une édition concurrente du reste de la recette.

Le tool est une opération authentifiée susceptible de consommer un fournisseur
payant. La connexion interne à `media` se configure sans secret :

```dotenv
RECIPE_MEDIA_API_BASE_URL=http://127.0.0.1:8030
RECIPE_MEDIA_API_TIMEOUT_SECONDS=120
```

## Générer l'image d'un équipement

Le catalogue équipement suit la même frontière : `recipe` possède la fiche,
compose un brief depuis son nom et sa description, appelle le contrat générique
de `media`, puis attache l'URL à `main_image`.

Le tool MCP est `generate_equipment_image`. La façade REST authentifiée est :

```http
POST /v1/equipment/{uuid}/main-image
Content-Type: application/json

{
  "replace_existing": false
}
```

La réservation atomique et le remplacement explicite suivent les mêmes règles
que pour les recettes. `media` ne connaît ni recette, ni ingrédient, ni
équipement : il reçoit uniquement un `brief`, un `bucket` et un
`object_prefix` techniques. Le brief ne peut pas être remplacé par le client
REST ou MCP.

## Générer l'image d'un ingrédient

Le catalogue ingrédient possède la même façade publique :

```http
POST /v1/ingredients/{uuid}/main-image
Content-Type: application/json

{}
```

Le tool MCP public équivalent est `generate_ingredient_image(uuid)`. `recipe`
vérifie l'existence de l'ingrédient puis délègue au MCP interne de
`ingredient-enrichment-agent`, configuré par :

```dotenv
INGREDIENT_ENRICHMENT_AGENT_MCP_URL=http://127.0.0.1:8034/mcp
INGREDIENT_ENRICHMENT_AGENT_MCP_TIMEOUT_SECONDS=180
```

En développement local, l'adapter transmet aussi le tenant configuré par
`REKIPE_TENANT_URI` dans `X-Tenant-URI`. Les deux API conservent ainsi leur
propre résolution multitenant sans partager de coordonnées MongoDB.

L'agent construit le brief, appelle le contrat générique de `media` et crée une
suggestion limitée à `media_profile`. Contrairement aux recettes et
équipements, l'image n'est pas appliquée automatiquement : elle reste soumise
à validation humaine. Le navigateur et les clients IA ne contactent jamais
directement l'agent d'enrichissement pour cette opération.

Les lectures REST et MCP d'un ingrédient exposent aussi
`suggested_media_profile` lorsque la dernière suggestion image n'est ni
appliquée ni rejetée. Ce profil sert uniquement d'aperçu durable : il reste
séparé de `media_profile`, survit à un rechargement du client et disparaît après
rejet. Après application, l'image est portée par `media_profile` et l'aperçu
n'est plus renvoyé.

## Enrichir une recette via l'IA

Le tool public `ai_enrich_recipe` délègue au MCP interne de
`agent-recipe-creator`. L'agent n'a donc pas besoin d'un Ingress public et le
client Codex conserve un seul serveur MCP, celui de `recipe` :

```json
{
  "uuid": "01951234-5678-7abc-def0-123456789abc",
  "generate_image": true
}
```

La même façade existe en REST avec
`POST /v1/recipes/{uuid}/ai-enrich`. La réponse contient le résultat de
l'agent et la recette hydratée après mise à jour. Le service interne se
configure par `RECIPE_AGENT_MCP_URL` et
`RECIPE_AGENT_MCP_TIMEOUT_SECONDS` ; le délai par défaut est de 300 secondes.

Lors de l'enrichissement, l'agent reçoit le catalogue de tags courant, choisit
uniquement des noms existants et les résout vers leurs UUID. Les tags détectés
sont ajoutés aux tags déjà présents ; aucun tag humain n'est retiré et aucun
nouveau tag n'est créé implicitement.

Le catalogue curaté peut être chargé de manière idempotente avec
`scripts/seed_recipe_tags.py`. Le script compare casse, accents et espaces
avant toute création et propose un mode lecture seule par défaut.

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
`create_recipe`, `patch_recipe`, `generate_recipe_image`, `ai_enrich_recipe`,
`generate_ingredient_image`, `generate_equipment_image`,
`normalize_origin_country`
et `delete_recipe`.
