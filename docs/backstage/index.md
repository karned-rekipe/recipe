# Rekipe Recipe

`recipe` détient les recettes et les catalogues d'ingrédients, d'équipements et
de tags. Les recettes ne dupliquent pas ces catalogues : elles stockent leurs
UUID et l'API hydrate les objets en lecture.

Le service expose une API REST sur le port `8000`, un MCP sur `8001` et les
probes d'administration sur `9000`. En préproduction, les processus REST et MCP
sont déployés séparément à partir de la même image.

Une recette sans ingrédient reste en brouillon et n'est pas éligible au meal
planner. Les suppressions de ressources référencées sont bloquées.
