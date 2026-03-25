import pytest
from uuid6 import UUID

from domain.models.ustensil import Ustensil


def test_valid_ustensil():
    u = Ustensil(name = "Fouet")
    assert u.name == "Fouet"


def test_name_stripped():
    u = Ustensil(name = "  Spatule  ")
    assert u.name == "Spatule"


def test_empty_name_raises():
    with pytest.raises(Exception):
        Ustensil(name = "")


def test_blank_name_raises():
    with pytest.raises(Exception):
        Ustensil(name = "   ")


def test_inherits_entity_fields():
    u = Ustensil(name = "Fouet")
    assert isinstance(u.uuid, UUID)
    assert u.version == 1
    assert not u.is_deleted


def test_model_copy_update():
    u = Ustensil(name = "Fouet")
    copy = u.model_copy(update = {"name": "Spatule"})
    assert copy.name == "Spatule"
    assert copy.uuid == u.uuid
