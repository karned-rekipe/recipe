import pytest
from uuid6 import uuid7

from application.services.recipe_service import RecipeComponentCycleError, RecipeComponentInUseError, RecipeService
from domain.models.recipe import Recipe
from domain.models.recipe_component import RecipeComponent
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.recipe_line_origin import RecipeLineOrigin
from domain.models.step import Step


@pytest.fixture
def service(repo, logger):
    return RecipeService(repo, logger)


async def test_create_and_read(service):
    recipe = await service.create(Recipe(name="Farine"))
    found = await service.read(recipe.uuid)
    assert found is not None
    assert found.name == "Farine"


async def test_update(service):
    recipe = await service.create(Recipe(name="Farine"))
    updated = await service.update(recipe.model_copy(update={"name": "Farine complète"}))
    assert updated.name == "Farine complète"
    assert updated.version == 2


async def test_delete_hides_from_read(service):
    recipe = await service.create(Recipe(name="Sel"))
    await service.delete(recipe.uuid)
    assert await service.read(recipe.uuid) is None


async def test_find_all(service):
    await service.create(Recipe(name="Farine"))
    await service.create(Recipe(name="Sel"))
    result = await service.find_all()
    assert len(result) == 2


async def test_find_by_name(service):
    await service.create(Recipe(name="Farine de blé"))
    await service.create(Recipe(name="Sel fin"))
    result = await service.find_by_name("farine")
    assert len(result) == 1
    assert result[0].name == "Farine de blé"


async def test_duplicate(service):
    recipe = await service.create(Recipe(name="Farine"))
    clone = await service.duplicate(recipe.uuid)
    assert clone.uuid != recipe.uuid
    assert clone.name == "Farine"


async def test_read_unknown_returns_none(service):
    assert await service.read(uuid7()) is None


async def test_find_by_name_no_results(service):
    await service.create(Recipe(name="Sel"))
    result = await service.find_by_name("farine")
    assert result == []


async def test_find_page_filtered_by_main_image(service):
    await service.create(Recipe(name="Sans image"))
    await service.create(Recipe(name="Avec image", main_image="https://example.com/recipe.jpg"))

    items, total = await service.find_page_filtered(has_main_image=False)

    assert total == 1
    assert [item.name for item in items] == ["Sans image"]


async def test_create_parent_projects_component_lines(service):
    ingredient_uuid = uuid7()
    child = await service.create(
        Recipe(
            name="Crème anglaise",
            ingredients=[RecipeIngredient(ingredient_uuid=ingredient_uuid, quantity=250, unit="ml")],
            steps=[Step(name="Cuire la crème", rank=1)],
        )
    )

    parent = await service.create(
        Recipe(
            name="Île flottante",
            components=[
                RecipeComponent(
                    recipe_uuid=child.uuid,
                    label="Crème anglaise",
                    rank=1,
                    servings_multiplier=2,
                )
            ],
        )
    )

    assert parent.status == "active"
    assert parent.ingredients[0].ingredient_uuid == ingredient_uuid
    assert parent.ingredients[0].quantity == 500
    assert parent.ingredients[0].line_origin == RecipeLineOrigin.component_projection
    assert parent.ingredients[0].source_recipe_uuid == child.uuid
    assert parent.steps[0].name == "Cuire la crème"
    assert parent.steps[0].line_origin == RecipeLineOrigin.component_projection


async def test_update_child_propagates_projection_to_parent(service):
    ingredient_uuid = uuid7()
    child = await service.create(
        Recipe(
            name="Meringue",
            ingredients=[RecipeIngredient(ingredient_uuid=ingredient_uuid, quantity=50, unit="g")],
        )
    )
    parent = await service.create(
        Recipe(
            name="Île flottante",
            components=[RecipeComponent(recipe_uuid=child.uuid, label="Meringue", rank=1, servings_multiplier=3)],
        )
    )

    await service.update(
        child.model_copy(
            update={
                "ingredients": [
                    RecipeIngredient(ingredient_uuid=ingredient_uuid, quantity=70, unit="g"),
                ]
            }
        )
    )
    updated_parent = await service.read(parent.uuid)

    assert updated_parent is not None
    assert updated_parent.version == parent.version + 1
    assert updated_parent.ingredients[0].quantity == 210


async def test_component_cycle_is_rejected(service):
    child = await service.create(Recipe(name="Caramel"))
    parent = await service.create(
        Recipe(
            name="Île flottante",
            components=[RecipeComponent(recipe_uuid=child.uuid, label="Caramel", rank=1)],
        )
    )

    with pytest.raises(RecipeComponentCycleError):
        await service.update(
            child.model_copy(
                update={"components": [RecipeComponent(recipe_uuid=parent.uuid, label="Parent", rank=1)]}
            )
        )


async def test_delete_component_in_use_is_rejected(service):
    child = await service.create(Recipe(name="Caramel"))
    await service.create(
        Recipe(
            name="Île flottante",
            components=[RecipeComponent(recipe_uuid=child.uuid, label="Caramel", rank=1)],
        )
    )

    with pytest.raises(RecipeComponentInUseError):
        await service.delete(child.uuid)
