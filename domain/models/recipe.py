from dataclasses import dataclass

from arclith import Entity


@dataclass
class Recipe(Entity):
    name: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        normalized_name = self.name.strip()
        if not normalized_name:
            raise ValueError("Recipe name cannot be empty")
        self.name = normalized_name
