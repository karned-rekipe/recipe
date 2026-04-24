# Quickstart

## Prérequis

- Python 3.13
- [uv](https://docs.astral.sh/uv/) installé (`pip install uv` ou `curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Installation

### 1. Créer ton projet depuis le template

Ce dépôt est un **template GitHub**. Ne le clone pas directement.

Sur GitHub, clique sur **"Use this template"** → **"Create a new repository"**, choisis ton nom de projet, puis clone ton nouveau dépôt :

```bash
git clone <url-de-ton-repo> mon-projet
cd mon-projet
```

### 2. Installer les dépendances

```bash
uv sync
```

`uv sync` crée automatiquement le `.venv` et installe toutes les dépendances déclarées dans `pyproject.toml`, dont `arclith` depuis PyPI.

## Lancer l'application

### API (FastAPI)

```bash
uv run python main_api.py
```

### MCP — SSE

```bash
uv run python main_mcp_sse.py
```

## Importer le legacy SQL cuisine

Le script d'import lit l'export SQL historique et importe dans MongoDB :

- le catalogue `ingredient` ;
- les agrégats `recipe` avec ingrédients, équipements, étapes et métadonnées legacy ;
- l'historique de planification dans la collection de transition `legacy_meal_plan_entry`.

Dry-run :

```bash
uv run python scripts/import_legacy_sql.py --dry-run
```

Import local par défaut :

```bash
uv run python scripts/import_legacy_sql.py
```

Pour servir ces recettes via l'API, l'adapter actif doit être MongoDB et l'URI locale doit être déclarée dans `secrets.yaml` :

```yaml
adapters:
  mongodb:
    uri: mongodb://localhost:5971
```

Options utiles :

```bash
uv run python scripts/import_legacy_sql.py \
  --mongo-uri mongodb://localhost:5971 \
  --db-name recipe \
  --delete-existing-legacy-docs
```

Le rapport est écrit dans `.run/legacy_sql_import_report.json`.
