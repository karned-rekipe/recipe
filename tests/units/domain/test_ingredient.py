import pytest

from domain.models.ingredient import Ingredient

GROUP_UUID = "01951234-5678-7abc-def0-000000000201"
RAYON_UUID = "01951234-5678-7abc-def0-000000000202"
SUPPLIER_UUID = "01951234-5678-7abc-def0-000000000203"
SECONDARY_SUPPLIER_UUID = "01951234-5678-7abc-def0-000000000204"


def make_ingredient(**kwargs) -> Ingredient:
    kwargs.setdefault("name", "Tomate")
    return Ingredient(**kwargs)


# --- name validation ---

def test_name_is_stripped():
    ingredient = make_ingredient(name="  Tomate  ")
    assert ingredient.name == "Tomate"


def test_empty_name_raises():
    with pytest.raises(ValueError, match="cannot be empty"):
        make_ingredient(name="   ")


def test_name_required():
    with pytest.raises(Exception):
        Ingredient()  # type: ignore[call-arg]


# --- season_months validation ---

def test_season_months_defaults_empty():
    ingredient = make_ingredient()
    assert ingredient.season_months == {}


def test_season_months_valid():
    ingredient = make_ingredient(season_months={6: 2, 7: 3, 8: 3, 9: 2})
    assert ingredient.season_months == {6: 2, 7: 3, 8: 3, 9: 2}


def test_season_months_string_keys_coerced():
    ingredient = make_ingredient(season_months={"6": 2, "7": 3})
    assert ingredient.season_months == {6: 2, 7: 3}


def test_season_months_invalid_month_raises():
    with pytest.raises(ValueError, match="Month key must be between 1 and 12"):
        make_ingredient(season_months={0: 2})


def test_season_months_month_too_high_raises():
    with pytest.raises(ValueError, match="Month key must be between 1 and 12"):
        make_ingredient(season_months={13: 1})


def test_season_months_invalid_score_raises():
    with pytest.raises(ValueError, match="Season score must be between 1 and 3"):
        make_ingredient(season_months={6: 4})


def test_season_months_score_zero_raises():
    with pytest.raises(ValueError, match="Season score must be between 1 and 3"):
        make_ingredient(season_months={6: 0})


# --- optional fields ---

def test_optional_fields_default_none():
    ingredient = make_ingredient()
    assert ingredient.rayon_uuid is None
    assert ingredient.group_uuid is None
    assert ingredient.main_supplier_uuid is None
    assert ingredient.secondary_supplier_uuids == []
    assert ingredient.green_score is None
    assert ingredient.unit is None
    assert ingredient.quantity is None


def test_all_fields():
    ingredient = make_ingredient(
        rayon_uuid=RAYON_UUID,
        group_uuid=GROUP_UUID,
        main_supplier_uuid=SUPPLIER_UUID,
        secondary_supplier_uuids=[SECONDARY_SUPPLIER_UUID],
        green_score=80,
        unit="g",
        quantity=100.0,
        season_months={7: 3, 8: 3},
    )
    assert str(ingredient.rayon_uuid) == RAYON_UUID
    assert str(ingredient.group_uuid) == GROUP_UUID
    assert str(ingredient.main_supplier_uuid) == SUPPLIER_UUID
    assert [str(uuid) for uuid in ingredient.secondary_supplier_uuids] == [SECONDARY_SUPPLIER_UUID]
    assert ingredient.green_score == 80
    assert ingredient.unit == "g"
    assert ingredient.quantity == 100.0
    assert ingredient.season_months == {7: 3, 8: 3}


def test_entity_has_uuid():
    ingredient = make_ingredient()
    assert ingredient.uuid is not None


def test_entity_has_version():
    ingredient = make_ingredient()
    assert ingredient.version is not None
