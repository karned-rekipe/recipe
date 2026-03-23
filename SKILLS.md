# SKILLS.md — recipe/

## SK-R01 — Ajouter une entite metier complete (REST + MCP)

Contexte : ajouter une nouvelle entite avec CRUD REST + MCP.

### Etapes

1. domain/models/my_entity.py : sous-classer Entity, champs avec Field(description, examples) + field_validator
2. domain/ports/my_entity_repository.py : sous-classer Repository[MyEntity], methodes de requete specifiques
3. application/services/my_entity_service.py : sous-classer BaseService[MyEntity]
4. adapters/input/schemas/my_entity_schema.py : Pydantic model de serialisation
5. adapters/output/mongodb/my_entity_repository.py : copier ingredient_repository.py
6. adapters/output/memory/my_entity_repository.py : pour les tests
7. adapters/input/fastmcp/my_entity_tools.py : classe MyEntityMCP(service, logger, mcp) + _register_tools()
8. adapters/input/fastapi/my_entity_router.py : router FastAPI
9. infrastructure/my_entity_container.py : copier ingredient_container.py
10. Enregistrer dans : infrastructure/container.py, fastmcp/tools.py, fastapi/router.py
    Validation :
    uv run --frozen pytest -v -m "not e2e"
    uv run --frozen python main_mcp_sse.py

---

## SK-R02 — Lier deux entites (pattern Recipe-Ingredient)

Contexte : relation N:N entre deux entites existantes.

### Etapes

1. Modele source : ajouter list[TargetEntity] | None = Field(None) sur l entite porteuse
2. Service : implanter link(source_uuid, target_uuid) et unlink() dans le service source
3. MCP tools : creer adapters/input/fastmcp/source_target_tools.py avec SourceTargetMCP
    - link_target_to_source(source_uuid, target_uuid)
    - unlink_target_from_source(source_uuid, target_uuid)
    - list_source_targets(source_uuid)
4. Enregistrer dans tools.py register_tools()
   Validation : uv run --frozen pytest -v -k link

---

## SK-R03 — Ajouter un use case custom

Contexte : requete metier absente des 7 use cases standards de BaseService.

### Etapes

1. Port : ajouter la methode abstraite dans domain/ports/my_entity_repository.py
2. Implementations : implanter dans MongoDB, memory (et DuckDB si necessaire)
3. Use case : application/use_cases/find_by_my_field.py avec execute()
4. Service : injecter et exposer
   Validation : uv run --frozen pytest -v -k find_by

---

## SK-R04 — Tester un tool MCP en isolation

Contexte : valider un tool MCP sans serveur lance.

### Etapes

1. Instancier InMemoryMyEntityRepository() + MyEntityService(repo, NullLogger())
2. Creer FastMCP("test") factice
3. Instancier MyEntityMCP(service, logger, mcp)
4. Appeler le service directement dans le test
   Validation : uv run --frozen pytest -v tests/units/adapters/input/fastmcp/
