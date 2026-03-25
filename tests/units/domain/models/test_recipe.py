import pytest
from typing import Literal
from uuid6 import UUID

from domain.models.ingredient import Ingredient
from domain.models.recipe import Recipe
from domain.models.step import Step
from domain.models.ustensil import Ustensil


def test_valid_recipe():
    r = Recipe(name = "Pizza")
    assert r.name == "Pizza"
    assert r.description is None
    assert r.ingredients is None
    assert r.ustensils is None
    assert r.steps is None
    assert r.nutriscore is None


def test_name_stripped():
    r = Recipe(name = "  Tarte  ")
    assert r.name == "Tarte"


def test_empty_name_raises():
    with pytest.raises(Exception):
        Recipe(name = "")


def test_blank_name_raises():
    with pytest.raises(Exception):
        Recipe(name = "   ")


@pytest.mark.parametrize("score", ["A", "B", "C", "D", "E", "F"])
def test_nutriscore_valid(score: Literal["A", "B", "C", "D", "E", "F"]):
    r = Recipe(name = "Pizza", nutriscore = score)
    assert r.nutriscore == score


def test_nutriscore_invalid():
    with pytest.raises(Exception):
        Recipe(name = "Pizza", nutriscore = "Z")  # type: ignore[arg-type]


def test_with_ingredients():
    i = Ingredient(name = "Farine")
    r = Recipe(name = "Pizza", ingredients = [i])
    assert len(r.ingredients) == 1


def test_with_ustensils():
    u = Ustensil(name = "Fouet")
    r = Recipe(name = "Pizza", ustensils = [u])
    assert len(r.ustensils) == 1


def test_model_post_init_assigns_recipe_uuid_to_steps():
    s = Step(name = "Pétrir")
    r = Recipe(name = "Pizza", steps = [s])
    assert r.steps[0].recipe_uuid == r.uuid


def test_model_post_init_does_not_overwrite_existing_recipe_uuid():
    from uuid6 import uuid7
    rid = uuid7()
    s = Step(name = "Pétrir", recipe_uuid = rid)
    r = Recipe(name = "Pizza", steps = [s])
    assert r.steps[0].recipe_uuid == rid


def test_inherits_entity_fields():
    r = Recipe(name = "Pizza")
    assert isinstance(r.uuid, UUID)
    assert r.version == 1
    assert not r.is_deleted
