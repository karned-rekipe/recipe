from infrastructure.containers.ingredient_enrichment_agent_container import (
    build_ingredient_enrichment_agent,
)

# Backward-compatible builder name for callers outside this repository.
build_ingredient_image_generation_agent = build_ingredient_enrichment_agent
