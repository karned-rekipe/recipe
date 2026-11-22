# Architecture

Le domaine et les cas d'usage sont indépendants de FastAPI, FastMCP et MongoDB.
Les adapters d'entrée portent les contrats REST/MCP ; les repositories MongoDB
sont la persistance de production. Les adapters mémoire et DuckDB servent aux
tests.

`agent-recipe-creator` consomme les contrats du service pour rechercher,
créer ou mettre à jour les fiches. La génération d'image est orchestrée par
`recipe`, qui appelle `media` puis persiste l'URL publique de l'original dans
`main_image`.

Le service ne contacte jamais directement l'OCR ni le fournisseur LLM.
