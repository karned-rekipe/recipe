# API et MCP

La documentation OpenAPI active est disponible sous `/api/recipe/docs` en
préproduction. Le contrat REST fournit les CRUD des recettes et catalogues, la
pagination, les filtres de saison, d'éligibilité et de présence d'image, ainsi
que la façade de génération d'image principale.
La façade `POST /v1/recipes/{uuid}/ai-enrich` déclenche l'agent interne puis
renvoie la fiche hydratée, sans exposer directement le MCP de l'agent.

Le MCP public est exposé sous `/api/recipe-mcp/mcp`. Il exige OAuth 2.1, PKCE,
le rôle `rekipe:mcp-access` et des scopes adaptés à l'opération. Les appels sans
jeton ou avec un jeton invalide renvoient `401` avec la metadata de ressource
protégée.

`list_recipes` conserve la compatibilité avec la recherche par nom et accepte
les filtres du catalogue, dont `has_main_image`, avec une pagination bornée à
200 éléments.

`normalize_origin_country` normalise un code pays non fiable produit par une
IA. Une valeur incompatible est renvoyée à `null` avec un avertissement, sans
faire échouer l'enrichissement de la recette.

`ai_enrich_recipe` requiert les scopes `recipes:write` et
`recipes:image:generate`. Il sélectionne les tags uniquement dans le catalogue
Recipe existant et conserve les associations déjà présentes.
