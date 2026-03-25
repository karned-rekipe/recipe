import pytest
from uuid6 import UUID, uuid7

from domain.models.step import Step


def test_valid_step():
    s = Step(name = "Préparer la pâte")
    assert s.name == "Préparer la pâte"
    assert s.recipe_uuid is None
    assert s.description is None


def test_name_stripped():
    s = Step(name = "  Cuire  ")
    assert s.name == "Cuire"


def test_empty_name_raises():
    with pytest.raises(Exception):
        Step(name = "")


def test_blank_name_raises():
    with pytest.raises(Exception):
        Step(name = "   ")


def test_name_max_length():
    Step(name = "A" * 80)
    with pytest.raises(Exception):
        Step(name = "A" * 81)


def test_recipe_uuid_set():
    rid = uuid7()
    s = Step(name = "Cuire", recipe_uuid = rid)
    assert s.recipe_uuid == rid


def test_description_set():
    s = Step(name = "Cuire", description = "Cuire au four 20 min")
    assert s.description == "Cuire au four 20 min"


def test_inherits_entity_fields():
    s = Step(name = "Cuire")
    assert isinstance(s.uuid, UUID)
    assert s.version == 1
    assert not s.is_deleted
