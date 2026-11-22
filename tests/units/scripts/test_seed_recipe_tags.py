from scripts.seed_recipe_tags import CURATED_TAGS, normalized_name, seed_tags


class _Seeder:
    def __init__(self, existing: list[dict]) -> None:
        self.existing = existing
        self.created = []

    def list_tags(self) -> list[dict]:
        return self.existing

    def create_tag(self, seed):
        self.created.append(seed)
        return {"name": seed.name}


def test_normalized_name_ignores_case_accents_and_spaces():
    assert normalized_name("  GOÛTER ") == normalized_name("gouter")


def test_seed_is_idempotent_for_normalized_existing_names():
    seeder = _Seeder([{"name": "GOUTER"}, {"name": "plat principal"}])

    kept, created = seed_tags(seeder, apply=True)

    assert "GOUTER" in kept
    assert "plat principal" in kept
    assert "goûter" not in created
    assert len(created) == len(CURATED_TAGS) - 2
    assert len(seeder.created) == len(CURATED_TAGS) - 2


def test_dry_run_does_not_create_tags():
    seeder = _Seeder([])

    _, missing = seed_tags(seeder, apply=False)

    assert len(missing) == len(CURATED_TAGS)
    assert seeder.created == []
