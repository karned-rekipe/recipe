import pytest
import yaml
from arclith import Arclith

from infrastructure.agent_config import load_agent_settings
from infrastructure.container import build_ingredient_service, build_recipe_service, build_step_service, \
    build_ustensil_service


@pytest.fixture
def memory_arclith(tmp_path):
    config = {
        "adapters": {"repository": "memory"},
        "api": {"host": "0.0.0.0", "port": 8301, "reload": False},
        "mcp": {"host": "127.0.0.1", "port": 8302},
        "soft_delete": {"retention_days": 30},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    return Arclith(config_path)


def test_build_ingredient_service(memory_arclith):
    service, logger = build_ingredient_service(memory_arclith)
    assert service is not None
    assert logger is not None


def test_build_recipe_service(memory_arclith):
    service, logger = build_recipe_service(memory_arclith)
    assert service is not None


def test_build_step_service(memory_arclith):
    service, logger = build_step_service(memory_arclith)
    assert service is not None


def test_build_ustensil_service(memory_arclith):
    service, logger = build_ustensil_service(memory_arclith)
    assert service is not None


def test_load_agent_settings(tmp_path):
    config = {
        "agent": {
            "model_name": "gpt-4",
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
        }
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    settings = load_agent_settings(config_path)
    assert settings.model_name == "gpt-4"
    assert settings.base_url == "http://localhost:1234/v1"
    assert settings.api_key == "test-key"


def test_load_agent_settings_default_api_key(tmp_path):
    config = {"agent": {"model_name": "gpt-4", "base_url": "http://localhost/v1"}}
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    settings = load_agent_settings(config_path)
    assert settings.api_key == "local"
