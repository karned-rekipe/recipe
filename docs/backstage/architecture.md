# Architecture

Le domaine et les cas d'usage sont indépendants de FastAPI, FastMCP et MongoDB.
Les adapters d'entrée portent les contrats REST/MCP ; les repositories MongoDB
sont la persistance de production. Les adapters mémoire et DuckDB servent aux
tests.

`agent-recipe-creator` consomme les contrats du service pour rechercher,
créer ou mettre à jour les fiches. La génération d'image est orchestrée par
`recipe`, qui construit un brief métier pour une recette ou un équipement,
appelle le contrat générique de `media`, puis persiste l'URL publique de
l'original dans `main_image`. Pour un ingrédient, `recipe` délègue au MCP
interne de `ingredient-enrichment-agent`; l'agent crée une suggestion
`media_profile` que l'utilisateur doit valider avant application.

Les MCP clients se connectent à `recipe` et utilisent les tools spécifiques.
Le MCP générique de `media` est une primitive d'infrastructure interne et ne
fait pas partie des capacités confiées à une IA métier.

Le service ne contacte jamais directement l'OCR ni le fournisseur LLM.
