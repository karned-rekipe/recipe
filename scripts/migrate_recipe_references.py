#!/usr/bin/env python3
"""Migrate embedded recipe ingredients/equipment to UUID references."""

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pymongo import MongoClient, ReplaceOne

from domain.models.equipment import Equipment
from domain.models.ingredient_group import IngredientGroup
from domain.models.ingredient_rayon import IngredientRayon
from domain.models.tag import Tag, TagCategory

MongoDocument = dict[str, Any]
LEGACY_SOURCE_NAME = "rekipe.reference_migration"
MIGRATION_NAMESPACE = uuid5(NAMESPACE_URL, "rekipe:catalog-reference-migration")


@dataclass
class MigrationReport:
    mongo_uri: str
    db_name: str
    dry_run: bool
    migrated_at: str
    recipes_seen: int = 0
    recipes_to_update: int = 0
    ingredients_to_update: int = 0
    equipment_to_create: int = 0
    ingredient_groups_to_create: int = 0
    ingredient_rayons_to_create: int = 0
    tags_to_create: int = 0
    warnings: dict[str, int] = field(default_factory=dict)
    ambiguous_ingredients: dict[str, list[str]] = field(default_factory=dict)
    missing_ingredients: list[str] = field(default_factory=list)
    mongo_result: dict[str, dict[str, int]] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    default_report = Path(__file__).resolve().parents[1] / ".run" / "recipe_reference_migration_report.json"
    parser = argparse.ArgumentParser(description="Migrate embedded recipe catalog data to UUID references.")
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI", "mongodb://127.0.0.1:5971"))
    parser.add_argument("--db-name", default=os.getenv("MONGODB_DB_NAME", "recipe"))
    parser.add_argument("--report-path", type=Path, default=default_report)
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, without writing MongoDB.")
    return parser.parse_args()


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def entity_to_doc(entity: Any) -> MongoDocument:
    doc = entity.model_dump(mode="json", exclude_computed_fields=True)
    doc["_id"] = str(doc.pop("uuid"))
    return doc


def named_uuid(kind: str, name: str) -> str:
    return str(uuid5(MIGRATION_NAMESPACE, f"{kind}:{normalize_name(name)}"))


def increment(mapping: dict[str, int], key: str) -> None:
    mapping[key] = mapping.get(key, 0) + 1


def build_ingredient_lookup(docs: list[MongoDocument], report: MigrationReport) -> dict[str, str]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for doc in docs:
        name = doc.get("name")
        if isinstance(name, str) and name.strip():
            grouped[normalize_name(name)].append(str(doc["_id"]))

    lookup: dict[str, str] = {}
    for normalized_name, uuids in grouped.items():
        unique_uuids = sorted(set(uuids))
        if len(unique_uuids) == 1:
            lookup[normalized_name] = unique_uuids[0]
            continue
        report.ambiguous_ingredients[normalized_name] = unique_uuids
        increment(report.warnings, "ambiguous_ingredient_name")
    return lookup


def build_equipment_lookup(docs: list[MongoDocument]) -> dict[str, MongoDocument]:
    lookup: dict[str, MongoDocument] = {}
    for doc in docs:
        name = doc.get("name")
        if isinstance(name, str) and name.strip():
            lookup[normalize_name(name)] = doc
    return lookup


def build_setting_docs(
    ingredient_docs: list[MongoDocument],
    migrated_at: datetime,
) -> tuple[list[MongoDocument], dict[str, str], list[MongoDocument], dict[str, str]]:
    group_names = sorted({
        name.strip()
        for doc in ingredient_docs
        if isinstance((name := doc.get("group")), str) and name.strip()
    })
    rayon_names = sorted({
        name.strip()
        for doc in ingredient_docs
        if isinstance((name := doc.get("rayon")), str) and name.strip()
    })
    group_docs: list[MongoDocument] = []
    group_lookup: dict[str, str] = {}
    for index, name in enumerate(group_names, start=1):
        doc = entity_to_doc(IngredientGroup(uuid=named_uuid("ingredient_group", name), name=name, sort_order=index, created_at=migrated_at, updated_at=migrated_at))
        group_docs.append(doc)
        group_lookup[normalize_name(name)] = doc["_id"]

    rayon_docs: list[MongoDocument] = []
    rayon_lookup: dict[str, str] = {}
    for index, name in enumerate(rayon_names, start=1):
        doc = entity_to_doc(IngredientRayon(uuid=named_uuid("ingredient_rayon", name), name=name, sort_order=index, created_at=migrated_at, updated_at=migrated_at))
        rayon_docs.append(doc)
        rayon_lookup[normalize_name(name)] = doc["_id"]
    return group_docs, group_lookup, rayon_docs, rayon_lookup


def default_tag_docs(migrated_at: datetime) -> list[MongoDocument]:
    defaults = [
        ("végan", TagCategory.diet, "#34c759"),
        ("végétarien", TagCategory.diet, "#30d158"),
        ("grande tablée", TagCategory.occasion, "#ff9f0a"),
        ("à l'assiette", TagCategory.service, "#007aff"),
    ]
    return [
        entity_to_doc(Tag(uuid=named_uuid("tag", name), name=name, category=category, color=color, created_at=migrated_at, updated_at=migrated_at))
        for name, category, color in defaults
    ]


def migrate_ingredient_doc(
    ingredient: MongoDocument,
    group_lookup: dict[str, str],
    rayon_lookup: dict[str, str],
) -> MongoDocument | None:
    updated = dict(ingredient)
    changed = False
    group = ingredient.get("group")
    if isinstance(group, str) and group.strip() and not ingredient.get("group_uuid"):
        updated["group_uuid"] = group_lookup.get(normalize_name(group))
        changed = True
    rayon = ingredient.get("rayon")
    if isinstance(rayon, str) and rayon.strip() and not ingredient.get("rayon_uuid"):
        updated["rayon_uuid"] = rayon_lookup.get(normalize_name(rayon))
        changed = True
    if "group" in updated:
        updated.pop("group", None)
        changed = True
    if "rayon" in updated:
        updated.pop("rayon", None)
        changed = True
    return updated if changed else None


def calculate_recipe_season(
    ingredients: list[MongoDocument],
    ingredient_season_by_uuid: dict[str, dict[int, int]],
) -> dict[int, int]:
    ingredient_seasons = [
        season
        for line in ingredients
        if (season := ingredient_season_by_uuid.get(str(line.get("ingredient_uuid"))))
    ]
    if not ingredient_seasons:
        return {month: 1 for month in range(1, 13)}
    aggregated: dict[int, int] = {}
    for month in range(1, 13):
        scores = [season[month] for season in ingredient_seasons if month in season]
        if scores:
            score = round(sum(scores) / len(scores))
            aggregated[month] = max(1, min(3, score))
    return aggregated


def migrate_recipe(
    recipe: MongoDocument,
    ingredient_lookup: dict[str, str],
    ingredient_season_by_uuid: dict[str, dict[int, int]],
    equipment_lookup: dict[str, MongoDocument],
    new_equipment: dict[str, MongoDocument],
    report: MigrationReport,
    migrated_at: datetime,
) -> MongoDocument | None:
    changed = False
    ingredients: list[MongoDocument] = []
    for line in recipe.get("ingredients", []):
        if not isinstance(line, dict):
            increment(report.warnings, "invalid_ingredient_line")
            continue

        ingredient_uuid = line.get("ingredient_uuid")
        if ingredient_uuid is None:
            name = line.get("name")
            if not isinstance(name, str) or not name.strip():
                increment(report.warnings, "ingredient_line_missing_name")
                continue
            normalized_name = normalize_name(name)
            ingredient_uuid = ingredient_lookup.get(normalized_name)
            if ingredient_uuid is None:
                report.missing_ingredients.append(name)
                increment(report.warnings, "missing_ingredient_match")
                continue
            changed = True

        ingredients.append(
            {
                "ingredient_uuid": str(ingredient_uuid),
                "quantity": float(line.get("quantity") or 1),
                "unit": str(line.get("unit") or "x").strip() or "x",
            }
        )

    equipment: list[MongoDocument] = []
    for line in recipe.get("equipment", []):
        if not isinstance(line, dict):
            increment(report.warnings, "invalid_equipment_line")
            continue

        equipment_uuid = line.get("equipment_uuid")
        if equipment_uuid is None:
            name = line.get("name")
            if not isinstance(name, str) or not name.strip():
                increment(report.warnings, "equipment_line_missing_name")
                continue
            normalized_name = normalize_name(name)
            doc = equipment_lookup.get(normalized_name) or new_equipment.get(normalized_name)
            if doc is None:
                equipment_entity = Equipment(
                    uuid=str(uuid5(MIGRATION_NAMESPACE, f"equipment:{normalized_name}")),
                    name=name.strip(),
                    created_at=migrated_at,
                    updated_at=migrated_at,
                )
                doc = entity_to_doc(equipment_entity)
                doc["migration_metadata"] = {
                    "source_name": LEGACY_SOURCE_NAME,
                    "source_table": "recipe.embedded_equipment",
                    "imported_at": migrated_at.isoformat(),
                }
                new_equipment[normalized_name] = doc
            equipment_uuid = doc["_id"]
            changed = True

        quantity = line.get("quantity")
        equipment.append(
            {
                "equipment_uuid": str(equipment_uuid),
                "quantity": float(quantity) if quantity is not None else None,
            }
        )

    season_months = calculate_recipe_season(ingredients, ingredient_season_by_uuid)
    if recipe.get("tag_uuids") is None:
        changed = True
    if recipe.get("season_months") != season_months:
        changed = True

    if not changed:
        return None

    updated = dict(recipe)
    updated["ingredients"] = ingredients
    updated["equipment"] = equipment
    updated["tag_uuids"] = list(recipe.get("tag_uuids") or [])
    updated["season_months"] = {str(month): score for month, score in season_months.items()}
    updated["updated_at"] = migrated_at.isoformat()
    return updated


def bulk_replace(collection: Any, docs: list[MongoDocument]) -> dict[str, int]:
    if not docs:
        return {"matched": 0, "modified": 0, "upserted": 0}
    result = collection.bulk_write([ReplaceOne({"_id": doc["_id"]}, doc, upsert=True) for doc in docs], ordered=False)
    return {
        "matched": result.matched_count,
        "modified": result.modified_count,
        "upserted": result.upserted_count,
    }


def write_report(report: MigrationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.__dict__ | {
        "missing_ingredients": [
            name for name, _ in Counter(report.missing_ingredients).most_common()
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    migrated_at = datetime.now(UTC)
    report = MigrationReport(
        mongo_uri=args.mongo_uri,
        db_name=args.db_name,
        dry_run=args.dry_run,
        migrated_at=migrated_at.isoformat(),
    )

    client: MongoClient[dict[str, Any]] = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    db = client[args.db_name]

    ingredient_docs = list(db["ingredient"].find({"deleted_at": None}))
    equipment_docs = list(db["equipment"].find({"deleted_at": None}))
    recipes = list(db["recipe"].find({"deleted_at": None}))
    report.recipes_seen = len(recipes)

    group_docs, group_lookup, rayon_docs, rayon_lookup = build_setting_docs(ingredient_docs, migrated_at)
    tag_docs = default_tag_docs(migrated_at)
    ingredients_to_update = [
        updated
        for doc in ingredient_docs
        if (updated := migrate_ingredient_doc(doc, group_lookup, rayon_lookup)) is not None
    ]
    updated_ingredient_by_uuid = {str(doc["_id"]): doc for doc in ingredient_docs}
    updated_ingredient_by_uuid.update({str(doc["_id"]): doc for doc in ingredients_to_update})
    ingredient_season_by_uuid = {
        uuid: {int(month): int(score) for month, score in doc.get("season_months", {}).items()}
        for uuid, doc in updated_ingredient_by_uuid.items()
    }
    ingredient_lookup = build_ingredient_lookup(ingredient_docs, report)
    equipment_lookup = build_equipment_lookup(equipment_docs)
    new_equipment: dict[str, MongoDocument] = {}
    recipes_to_update: list[MongoDocument] = []

    for recipe in recipes:
        updated = migrate_recipe(
            recipe=recipe,
            ingredient_lookup=ingredient_lookup,
            ingredient_season_by_uuid=ingredient_season_by_uuid,
            equipment_lookup=equipment_lookup,
            new_equipment=new_equipment,
            report=report,
            migrated_at=migrated_at,
        )
        if updated is not None:
            recipes_to_update.append(updated)

    report.recipes_to_update = len(recipes_to_update)
    report.ingredients_to_update = len(ingredients_to_update)
    report.equipment_to_create = len(new_equipment)
    report.ingredient_groups_to_create = len(group_docs)
    report.ingredient_rayons_to_create = len(rayon_docs)
    report.tags_to_create = len(tag_docs)
    has_blockers = bool(report.missing_ingredients)

    if not args.dry_run and has_blockers:
        write_report(report, args.report_path)
        print(json.dumps(report.__dict__, ensure_ascii=False, indent=2, sort_keys=True))
        return 2

    if not args.dry_run:
        report.mongo_result["ingredient_group"] = bulk_replace(db["ingredient_group"], group_docs)
        report.mongo_result["ingredient_rayon"] = bulk_replace(db["ingredient_rayon"], rayon_docs)
        report.mongo_result["tag"] = bulk_replace(db["tag"], tag_docs)
        report.mongo_result["ingredient"] = bulk_replace(db["ingredient"], ingredients_to_update)
        report.mongo_result["equipment"] = bulk_replace(db["equipment"], list(new_equipment.values()))
        report.mongo_result["recipe"] = bulk_replace(db["recipe"], recipes_to_update)
        db["ingredient"].create_index("group_uuid", name="group_uuid")
        db["ingredient"].create_index("rayon_uuid", name="rayon_uuid")
        db["ingredient_group"].create_index("slug", unique=True, name="slug_unique")
        db["ingredient_rayon"].create_index("slug", unique=True, name="slug_unique")
        db["tag"].create_index("slug", unique=True, name="slug_unique")
        db["recipe"].create_index("ingredients.ingredient_uuid", name="ingredients_ingredient_uuid")
        db["recipe"].create_index("equipment.equipment_uuid", name="equipment_equipment_uuid")
        db["recipe"].create_index("tag_uuids", name="tag_uuids")

    write_report(report, args.report_path)
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
