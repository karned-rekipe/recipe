from pydantic import BaseModel, ConfigDict


class SourceSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"name": "Marmiton", "description": "Recette originale", "uri": "https://www.marmiton.org/recettes/recette_pizza.html"}]
        }
    )

    name: str
    description: str | None = None
    uri: str | None = None
