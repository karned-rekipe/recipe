from enum import Enum


class RecipeLineOrigin(str, Enum):
    manual = "manual"
    component_projection = "component_projection"
