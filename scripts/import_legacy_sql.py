#!/usr/bin/env python3
"""Import the legacy cuisine SQL dump into the Rekipe MongoDB target."""

import argparse
import json
import os
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pymongo import MongoClient, ReplaceOne

from domain.models.equipment import Equipment
from domain.models.ingredient import Ingredient
from domain.models.ingredient_group import IngredientGroup
from domain.models.ingredient_rayon import IngredientRayon
from domain.models.recipe import Recipe, RecipeQualityStatus, RecipeStatus
from domain.models.recipe_equipment import RecipeEquipment
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.tag import Tag, TagCategory
from domain.models.step import Step

SqlValue = str | int | float | None
SqlRow = dict[str, SqlValue]
MongoDocument = dict[str, Any]

LEGACY_SOURCE_NAME = "cuisine.karned.bzh"
LEGACY_NAMESPACE = uuid5(NAMESPACE_URL, f"rekipe:{LEGACY_SOURCE_NAME}")
MEAL_PLAN_ENTRY_COLLECTION = "meal_plan_entry"
TARGET_TABLES = {
    "mkg_liste_choix",
    "mkg_recipe",
    "mkg_recipe__ingredient",
    "mkg_recipe__liaison_ingredient",
    "mkg_recipe__equipement",
    "mkg_recipe__liaison_equipement",
    "mkg_recipe__step",
    "mkg_recipe__liaison_step",
    "mkg_recipe__planner",
}
INSERT_RE = re.compile(r"^INSERT INTO `(?P<table>[^`]+)` \((?P<columns>.*?)\) VALUES (?P<values>.*);$")


@dataclass
class ImportReport:
    source_sql: str
    mongo_uri: str
    db_name: str
    dry_run: bool
    imported_at: str
    parsed_rows: dict[str, int] = field(default_factory=dict)
    documents: dict[str, int] = field(default_factory=dict)
    quality_status: dict[str, int] = field(default_factory=dict)
    planner_entry_types: dict[str, int] = field(default_factory=dict)
    warnings: dict[str, int] = field(default_factory=dict)
    mongo_result: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass
class ImportArtifacts:
    ingredient_group_docs: list[MongoDocument]
    ingredient_rayon_docs: list[MongoDocument]
    tag_docs: list[MongoDocument]
    ingredient_docs: list[MongoDocument]
    equipment_docs: list[MongoDocument]
    recipe_docs: list[MongoDocument]
    planner_docs: list[MongoDocument]
    report: ImportReport


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[2]
    default_sql = project_root / "dataset" / "databases" / "cuisine.karned.bzh" / "20240524094358_data.sql"
    default_report = Path(__file__).resolve().parents[1] / ".run" / "legacy_sql_import_report.json"

    parser = argparse.ArgumentParser(description="Import legacy cuisine.karned.bzh SQL data into MongoDB.")
    parser.add_argument("--data-sql", type=Path, default=default_sql, help="Path to the MySQL data dump.")
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI", "mongodb://127.0.0.1:5971"))
    parser.add_argument("--db-name", default=os.getenv("MONGODB_DB_NAME", "recipe"))
    parser.add_argument("--report-path", type=Path, default=default_report)
    parser.add_argument("--dry-run", action="store_true", help="Parse and transform only, without writing MongoDB.")
    parser.add_argument(
        "--delete-existing-legacy-docs",
        action="store_true",
        help="Delete previous documents imported from this legacy source before upserting.",
    )
    return parser.parse_args()


def load_sql_tables(sql_path: Path, target_tables: set[str]) -> dict[str, list[SqlRow]]:
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL dump not found: {sql_path}")

    tables: dict[str, list[SqlRow]] = {table: [] for table in target_tables}
    with sql_path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.startswith("INSERT INTO `"):
                continue

            match = INSERT_RE.match(line.rstrip("\n"))
            if match is None:
                continue

            table = match.group("table")
            if table not in target_tables:
                continue

            columns = re.findall(r"`([^`]+)`", match.group("columns"))
            for values in iter_value_groups(match.group("values")):
                parsed_values = [parse_sql_value(value) for value in split_sql_values(values)]
                if len(parsed_values) != len(columns):
                    raise ValueError(
                        f"Invalid value count for {table}: expected {len(columns)}, got {len(parsed_values)}"
                    )
                tables[table].append(dict(zip(columns, parsed_values, strict=True)))
    return tables


def iter_value_groups(values_block: str) -> Iterable[str]:
    in_string = False
    escape = False
    depth = 0
    start: int | None = None

    for index, char in enumerate(values_block):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "'":
                in_string = False
            continue

        if char == "'":
            in_string = True
        elif char == "(":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                if start is None:
                    raise ValueError("Malformed SQL values block")
                yield values_block[start:index]
                start = None


def split_sql_values(group: str) -> list[str]:
    values: list[str] = []
    in_string = False
    escape = False
    start = 0

    for index, char in enumerate(group):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "'":
                in_string = False
            continue

        if char == "'":
            in_string = True
        elif char == ",":
            values.append(group[start:index].strip())
            start = index + 1

    values.append(group[start:].strip())
    return values


def parse_sql_value(token: str) -> SqlValue:
    if token.upper() == "NULL":
        return None
    if len(token) >= 2 and token[0] == "'" and token[-1] == "'":
        return unescape_mysql_string(token[1:-1])
    if "." in token:
        return float(token)
    return int(token)


def unescape_mysql_string(value: str) -> str:
    escapes = {
        "0": "\0",
        "'": "'",
        '"': '"',
        "b": "\b",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "Z": "\x1a",
        "\\": "\\",
    }
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            next_char = value[index + 1]
            result.append(escapes.get(next_char, next_char))
            index += 2
            continue
        result.append(char)
        index += 1
    return "".join(result)


def build_artifacts(tables: dict[str, list[SqlRow]], args: argparse.Namespace) -> ImportArtifacts:
    imported_at = datetime.now(UTC)
    report = ImportReport(
        source_sql=str(args.data_sql),
        mongo_uri=args.mongo_uri,
        db_name=args.db_name,
        dry_run=args.dry_run,
        imported_at=imported_at.isoformat(),
        parsed_rows={table: len(rows) for table, rows in sorted(tables.items())},
    )

    choices = build_choice_lookup(tables["mkg_liste_choix"])
    ingredients_by_id = index_by_legacy_id(tables["mkg_recipe__ingredient"])
    equipment_by_id = index_by_legacy_id(tables["mkg_recipe__equipement"])
    steps_by_id = index_by_legacy_id(tables["mkg_recipe__step"])
    recipe_uuid_by_legacy_id = {
        require_int(recipe["id"]): legacy_uuid("mkg_recipe", require_int(recipe["id"]))
        for recipe in tables["mkg_recipe"]
    }
    ingredient_uuid_by_legacy_id = {
        require_int(ingredient["id"]): legacy_uuid("mkg_recipe__ingredient", require_int(ingredient["id"]))
        for ingredient in tables["mkg_recipe__ingredient"]
    }
    equipment_uuid_by_legacy_id = {
        require_int(equipment["id"]): legacy_uuid("mkg_recipe__equipement", require_int(equipment["id"]))
        for equipment in tables["mkg_recipe__equipement"]
    }
    ingredient_group_docs, group_uuid_by_name = build_ingredient_group_docs(
        tables["mkg_recipe__ingredient"],
        choices,
        imported_at,
    )
    ingredient_rayon_docs, rayon_uuid_by_name = build_ingredient_rayon_docs(
        tables["mkg_recipe__ingredient"],
        choices,
        imported_at,
    )
    tag_docs = build_default_tag_docs(imported_at)

    ingredient_docs = build_ingredient_docs(
        tables["mkg_recipe__ingredient"],
        choices,
        group_uuid_by_name,
        rayon_uuid_by_name,
        imported_at,
        report,
    )
    ingredient_season_by_uuid = {
        str(doc["_id"]): {int(month): int(score) for month, score in doc.get("season_months", {}).items()}
        for doc in ingredient_docs
    }
    equipment_docs = build_equipment_docs(
        tables["mkg_recipe__equipement"],
        imported_at,
        report,
    )
    recipe_docs = build_recipe_docs(
        recipe_rows=tables["mkg_recipe"],
        ingredient_links=tables["mkg_recipe__liaison_ingredient"],
        equipment_links=tables["mkg_recipe__liaison_equipement"],
        step_links=tables["mkg_recipe__liaison_step"],
        ingredients_by_id=ingredients_by_id,
        equipment_by_id=equipment_by_id,
        steps_by_id=steps_by_id,
        ingredient_uuid_by_legacy_id=ingredient_uuid_by_legacy_id,
        equipment_uuid_by_legacy_id=equipment_uuid_by_legacy_id,
        ingredient_season_by_uuid=ingredient_season_by_uuid,
        choices=choices,
        imported_at=imported_at,
        report=report,
    )
    planner_docs = build_planner_docs(
        tables["mkg_recipe__planner"],
        recipe_uuid_by_legacy_id,
        ingredient_uuid_by_legacy_id,
        imported_at,
        report,
    )

    report.documents = {
        "ingredient_group": len(ingredient_group_docs),
        "ingredient_rayon": len(ingredient_rayon_docs),
        "tag": len(tag_docs),
        "ingredient": len(ingredient_docs),
        "equipment": len(equipment_docs),
        "recipe": len(recipe_docs),
        MEAL_PLAN_ENTRY_COLLECTION: len(planner_docs),
    }
    return ImportArtifacts(ingredient_group_docs, ingredient_rayon_docs, tag_docs, ingredient_docs, equipment_docs, recipe_docs, planner_docs, report)


def build_choice_lookup(rows: list[SqlRow]) -> dict[int, str]:
    choices: dict[int, str] = {}
    for row in rows:
        legacy_id = optional_int(row.get("id"))
        name = clean_text(row.get("nom"))
        if legacy_id is not None and name is not None:
            choices[legacy_id] = name
    return choices


def index_by_legacy_id(rows: list[SqlRow]) -> dict[int, SqlRow]:
    indexed: dict[int, SqlRow] = {}
    for row in rows:
        legacy_id = optional_int(row.get("id"))
        if legacy_id is not None:
            indexed[legacy_id] = row
    return indexed


def build_ingredient_group_docs(
    rows: list[SqlRow],
    choices: dict[int, str],
    imported_at: datetime,
) -> tuple[list[MongoDocument], dict[str, str]]:
    names = sorted({
        name
        for row in rows
        if (name := choice_name(choices, row.get("mls__groupe"))) is not None
    })
    docs: list[MongoDocument] = []
    uuid_by_name: dict[str, str] = {}
    for index, name in enumerate(names, start=1):
        group = IngredientGroup(
            uuid=named_legacy_uuid("ingredient_group", name),
            created_at=imported_at,
            updated_at=imported_at,
            name=name,
            sort_order=index,
        )
        doc = entity_to_doc(group)
        doc["migration_metadata"] = {
            "source_name": LEGACY_SOURCE_NAME,
            "source_table": "mkg_liste_choix",
            "imported_at": imported_at.isoformat(),
        }
        docs.append(doc)
        uuid_by_name[name] = doc["_id"]
    return docs, uuid_by_name


def build_ingredient_rayon_docs(
    rows: list[SqlRow],
    choices: dict[int, str],
    imported_at: datetime,
) -> tuple[list[MongoDocument], dict[str, str]]:
    names = sorted({
        name
        for row in rows
        if (name := choice_name(choices, row.get("mls__rayon"))) is not None
    })
    docs: list[MongoDocument] = []
    uuid_by_name: dict[str, str] = {}
    for index, name in enumerate(names, start=1):
        rayon = IngredientRayon(
            uuid=named_legacy_uuid("ingredient_rayon", name),
            created_at=imported_at,
            updated_at=imported_at,
            name=name,
            sort_order=index,
        )
        doc = entity_to_doc(rayon)
        doc["migration_metadata"] = {
            "source_name": LEGACY_SOURCE_NAME,
            "source_table": "mkg_liste_choix",
            "imported_at": imported_at.isoformat(),
        }
        docs.append(doc)
        uuid_by_name[name] = doc["_id"]
    return docs, uuid_by_name


def build_default_tag_docs(imported_at: datetime) -> list[MongoDocument]:
    defaults = [
        ("végan", TagCategory.diet, "#34c759"),
        ("végétarien", TagCategory.diet, "#30d158"),
        ("grande tablée", TagCategory.occasion, "#ff9f0a"),
        ("à l'assiette", TagCategory.service, "#007aff"),
    ]
    docs: list[MongoDocument] = []
    for name, category, color in defaults:
        tag = Tag(
            uuid=named_legacy_uuid("tag", name),
            created_at=imported_at,
            updated_at=imported_at,
            name=name,
            category=category,
            color=color,
        )
        doc = entity_to_doc(tag)
        doc["migration_metadata"] = {
            "source_name": LEGACY_SOURCE_NAME,
            "source_table": "default_tags",
            "imported_at": imported_at.isoformat(),
        }
        docs.append(doc)
    return docs


def build_ingredient_docs(
    rows: list[SqlRow],
    choices: dict[int, str],
    group_uuid_by_name: dict[str, str],
    rayon_uuid_by_name: dict[str, str],
    imported_at: datetime,
    report: ImportReport,
) -> list[MongoDocument]:
    docs: list[MongoDocument] = []
    for row in sorted(rows, key=lambda item: require_int(item["id"])):
        legacy_id = require_int(row["id"])
        name = clean_text(row.get("nom"))
        if name is None:
            name = f"Ingredient legacy {legacy_id}"
            increment(report.warnings, "ingredient_missing_name")

        created_at = parse_datetime(row.get("dc")) or imported_at
        updated_at = parse_datetime(row.get("dm")) or created_at
        group_name = choice_name(choices, row.get("mls__groupe"))
        rayon_name = choice_name(choices, row.get("mls__rayon"))
        ingredient = Ingredient(
            uuid=legacy_uuid("mkg_recipe__ingredient", legacy_id),
            created_at=created_at,
            updated_at=updated_at,
            name=name,
            rayon_uuid=rayon_uuid_by_name.get(rayon_name) if rayon_name is not None else None,
            group_uuid=group_uuid_by_name.get(group_name) if group_name is not None else None,
            unit=choice_name(choices, row.get("mls__unite")),
            quantity=positive_float(row.get("portion")),
            season_months=season_months(row),
        )
        doc = entity_to_doc(ingredient)
        doc.update(
            {
                "legacy_id": legacy_id,
                "status": legacy_status(row),
                "created_at_legacy": datetime_to_json(parse_datetime(row.get("dc"))),
                "updated_at_legacy": datetime_to_json(parse_datetime(row.get("dm"))),
                "migration_metadata": {
                    "source_name": LEGACY_SOURCE_NAME,
                    "source_table": "mkg_recipe__ingredient",
                    "source_keygen": clean_text(row.get("keygen")),
                    "imported_at": imported_at.isoformat(),
                },
            }
        )
        docs.append(doc)
    return docs


def build_equipment_docs(
    rows: list[SqlRow],
    imported_at: datetime,
    report: ImportReport,
) -> list[MongoDocument]:
    docs: list[MongoDocument] = []
    for row in sorted(rows, key=lambda item: require_int(item["id"])):
        legacy_id = require_int(row["id"])
        name = clean_text(row.get("nom"))
        if name is None:
            name = f"Equipment legacy {legacy_id}"
            increment(report.warnings, "equipment_missing_name")

        created_at = parse_datetime(row.get("dc")) or imported_at
        updated_at = parse_datetime(row.get("dm")) or created_at
        equipment = Equipment(
            uuid=legacy_uuid("mkg_recipe__equipement", legacy_id),
            created_at=created_at,
            updated_at=updated_at,
            name=name,
        )
        doc = entity_to_doc(equipment)
        doc.update(
            {
                "legacy_id": legacy_id,
                "status": legacy_status(row),
                "created_at_legacy": datetime_to_json(parse_datetime(row.get("dc"))),
                "updated_at_legacy": datetime_to_json(parse_datetime(row.get("dm"))),
                "migration_metadata": {
                    "source_name": LEGACY_SOURCE_NAME,
                    "source_table": "mkg_recipe__equipement",
                    "source_keygen": clean_text(row.get("keygen")),
                    "imported_at": imported_at.isoformat(),
                },
            }
        )
        docs.append(doc)
    return docs


def build_recipe_docs(
    recipe_rows: list[SqlRow],
    ingredient_links: list[SqlRow],
    equipment_links: list[SqlRow],
    step_links: list[SqlRow],
    ingredients_by_id: dict[int, SqlRow],
    equipment_by_id: dict[int, SqlRow],
    steps_by_id: dict[int, SqlRow],
    ingredient_uuid_by_legacy_id: dict[int, str],
    equipment_uuid_by_legacy_id: dict[int, str],
    ingredient_season_by_uuid: dict[str, dict[int, int]],
    choices: dict[int, str],
    imported_at: datetime,
    report: ImportReport,
) -> list[MongoDocument]:
    ingredient_lines = group_recipe_ingredients(
        ingredient_links,
        ingredients_by_id,
        ingredient_uuid_by_legacy_id,
        choices,
        report,
    )
    equipment_lines = group_recipe_equipment(equipment_links, equipment_by_id, equipment_uuid_by_legacy_id, report)
    step_lines = group_recipe_steps(step_links, steps_by_id)

    docs: list[MongoDocument] = []
    for row in sorted(recipe_rows, key=lambda item: require_int(item["id"])):
        legacy_id = require_int(row["id"])
        name = clean_text(row.get("nom"))
        if name is None:
            name = f"Recette legacy {legacy_id}"
            increment(report.warnings, "recipe_missing_name")

        ingredients = ingredient_lines.get(legacy_id, [])
        equipment = equipment_lines.get(legacy_id, [])
        steps = step_lines.get(legacy_id, [])
        created_at = parse_datetime(row.get("dc")) or imported_at
        updated_at = parse_datetime(row.get("dm")) or created_at
        quality_status = recipe_quality_status(row, ingredients, steps)
        increment(report.quality_status, quality_status.value)

        recipe = Recipe(
            uuid=legacy_uuid("mkg_recipe", legacy_id),
            created_at=created_at,
            updated_at=updated_at,
            name=name,
            description=clean_text(row.get("description")),
            servings=positive_int(row.get("nb_personne")),
            unit_count=positive_int(row.get("nb_portion")),
            difficulty=level_1_to_5(row.get("niveau_difficulte")),
            price=level_1_to_5(row.get("niveau_prix")),
            favorite=yes_no(row.get("favori")),
            tag_uuids=[],
            season_months=calculate_recipe_season(ingredients, ingredient_season_by_uuid),
            status=RecipeStatus.archived if legacy_status(row) == "archived" else RecipeStatus.active,
            quality_status=quality_status,
            legacy_id=legacy_id,
            created_at_legacy=parse_datetime(row.get("dc")),
            updated_at_legacy=parse_datetime(row.get("dm")),
            migration_metadata={
                "source_name": LEGACY_SOURCE_NAME,
                "source_table": "mkg_recipe",
                "source_keygen": clean_text(row.get("keygen")),
                "legacy_classement": clean_text(row.get("classement")),
                "legacy_repas": clean_text(row.get("repas")),
                "legacy_rang": clean_text(row.get("rang")),
                "source_corbeille": clean_text(row.get("corbeille")),
                "imported_at": imported_at.isoformat(),
            },
            ingredients=ingredients,
            equipment=equipment,
            steps=steps,
        )
        docs.append(entity_to_doc(recipe))
    return docs


def group_recipe_ingredients(
    links: list[SqlRow],
    ingredients_by_id: dict[int, SqlRow],
    ingredient_uuid_by_legacy_id: dict[int, str],
    choices: dict[int, str],
    report: ImportReport,
) -> dict[int, list[RecipeIngredient]]:
    grouped: dict[int, list[RecipeIngredient]] = defaultdict(list)
    sorted_links = sorted(links, key=lambda item: (optional_int(item.get("recipe_id")) or 0, require_int(item["id"])))
    for link in sorted_links:
        if legacy_status(link) == "archived":
            continue

        recipe_id = positive_int(link.get("recipe_id"))
        ingredient_id = positive_int(link.get("recipe__ingredient"))
        if recipe_id is None or ingredient_id is None:
            increment(report.warnings, "recipe_ingredient_link_missing_reference")
            continue

        ingredient_row = ingredients_by_id.get(ingredient_id)
        ingredient_uuid = ingredient_uuid_by_legacy_id.get(ingredient_id)
        if ingredient_uuid is None:
            ingredient_uuid = legacy_uuid("mkg_recipe__ingredient", ingredient_id)
            increment(report.warnings, "recipe_ingredient_link_unknown_ingredient_uuid")

        if ingredient_row is None:
            increment(report.warnings, "recipe_ingredient_link_unknown_ingredient")
            unit = "x"
        else:
            unit = choice_name(choices, ingredient_row.get("mls__unite")) or "x"

        quantity = positive_float(link.get("nb_unite"))
        if quantity is None:
            quantity = 1.0
            increment(report.warnings, "recipe_ingredient_quantity_defaulted")

        grouped[recipe_id].append(
            RecipeIngredient(
                ingredient_uuid=ingredient_uuid,
                quantity=quantity,
                unit=unit,
            )
        )
    return grouped


def group_recipe_equipment(
    links: list[SqlRow],
    equipment_by_id: dict[int, SqlRow],
    equipment_uuid_by_legacy_id: dict[int, str],
    report: ImportReport,
) -> dict[int, list[RecipeEquipment]]:
    grouped: dict[int, list[RecipeEquipment]] = defaultdict(list)
    sorted_links = sorted(links, key=lambda item: (optional_int(item.get("recipe_id")) or 0, require_int(item["id"])))
    for link in sorted_links:
        if legacy_status(link) == "archived":
            continue

        recipe_id = positive_int(link.get("recipe_id"))
        equipment_id = positive_int(link.get("recipe__equipement_id"))
        if recipe_id is None or equipment_id is None:
            increment(report.warnings, "recipe_equipment_link_missing_reference")
            continue

        if equipment_by_id.get(equipment_id) is None:
            increment(report.warnings, "recipe_equipment_link_unknown_equipment")

        grouped[recipe_id].append(
            RecipeEquipment(
                equipment_uuid=equipment_uuid_by_legacy_id.get(
                    equipment_id,
                    legacy_uuid("mkg_recipe__equipement", equipment_id),
                ),
                quantity=positive_float(link.get("nb_unite")),
            )
        )
    return grouped


def group_recipe_steps(
    links: list[SqlRow],
    steps_by_id: dict[int, SqlRow],
) -> dict[int, list[Step]]:
    grouped_rows: dict[int, list[tuple[SqlRow, SqlRow]]] = defaultdict(list)
    for link in links:
        if legacy_status(link) == "archived":
            continue

        recipe_id = positive_int(link.get("recipe_id"))
        step_id = positive_int(link.get("recipe__step_id"))
        if recipe_id is None or step_id is None:
            continue

        step_row = steps_by_id.get(step_id)
        if step_row is not None:
            grouped_rows[recipe_id].append((link, step_row))

    grouped_steps: dict[int, list[Step]] = {}
    for recipe_id, rows in grouped_rows.items():
        ordered = sorted(rows, key=lambda item: (optional_int(item[0].get("ordre")) or 0, require_int(item[0]["id"])))
        grouped_steps[recipe_id] = [step_from_legacy(row, index + 1) for index, (_, row) in enumerate(ordered)]
    return grouped_steps


def step_from_legacy(row: SqlRow, rank: int) -> Step:
    name = clean_text(row.get("nom")) or f"Etape {rank}"
    return Step(
        uuid=legacy_uuid("mkg_recipe__step", require_int(row["id"])),
        created_at=parse_datetime(row.get("dc")) or datetime.now(UTC),
        updated_at=parse_datetime(row.get("dm")) or parse_datetime(row.get("dc")) or datetime.now(UTC),
        name=name,
        description=clean_text(row.get("description")),
        preparation_time=time_to_minutes(row.get("temps_preparation")),
        rest_time=time_to_minutes(row.get("temps_repos")),
        cooking_time=time_to_minutes(row.get("temps_cuisson")),
        rank=rank,
    )


def build_planner_docs(
    rows: list[SqlRow],
    recipe_uuid_by_legacy_id: dict[int, str],
    ingredient_uuid_by_legacy_id: dict[int, str],
    imported_at: datetime,
    report: ImportReport,
) -> list[MongoDocument]:
    docs: list[MongoDocument] = []
    for row in sorted(rows, key=lambda item: require_int(item["id"])):
        legacy_id = require_int(row["id"])
        recipe_id = positive_int(row.get("recipe_id"))
        ingredient_id = positive_int(row.get("ingredient_id"))
        note = clean_text(row.get("commentaire"))
        entry_type = planner_entry_type(recipe_id, ingredient_id, note)
        increment(report.planner_entry_types, entry_type)

        doc = {
            "_id": legacy_uuid("mkg_recipe__planner", legacy_id),
            "document_type": "legacy_entry",
            "legacy_id": legacy_id,
            "date": clean_text(row.get("date")),
            "headcount": positive_int(row.get("nb_personne")),
            "entry_type": entry_type,
            "recipe_legacy_id": recipe_id,
            "recipe_uuid": recipe_uuid_by_legacy_id.get(recipe_id) if recipe_id is not None else None,
            "ingredient_legacy_id": ingredient_id,
            "ingredient_uuid": ingredient_uuid_by_legacy_id.get(ingredient_id) if ingredient_id is not None else None,
            "note": note,
            "meal_slot_code_legacy": clean_text(row.get("repas")),
            "legacy_rank": clean_text(row.get("rang")),
            "status": legacy_status(row),
            "created_at": datetime_to_json(parse_datetime(row.get("dc")) or imported_at),
            "updated_at": datetime_to_json(parse_datetime(row.get("dm")) or parse_datetime(row.get("dc")) or imported_at),
            "created_at_legacy": datetime_to_json(parse_datetime(row.get("dc"))),
            "updated_at_legacy": datetime_to_json(parse_datetime(row.get("dm"))),
            "migration_metadata": {
                "source_name": LEGACY_SOURCE_NAME,
                "source_table": "mkg_recipe__planner",
                "source_keygen": clean_text(row.get("keygen")),
                "imported_at": imported_at.isoformat(),
            },
        }
        docs.append(doc)
    return docs


def import_into_mongo(artifacts: ImportArtifacts, args: argparse.Namespace) -> None:
    client: MongoClient[dict[str, Any]] = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")

    db = client[args.db_name]
    collections = {
        "ingredient_group": artifacts.ingredient_group_docs,
        "ingredient_rayon": artifacts.ingredient_rayon_docs,
        "tag": artifacts.tag_docs,
        "ingredient": artifacts.ingredient_docs,
        "equipment": artifacts.equipment_docs,
        "recipe": artifacts.recipe_docs,
        MEAL_PLAN_ENTRY_COLLECTION: artifacts.planner_docs,
    }

    for collection_name, docs in collections.items():
        collection = db[collection_name]
        if args.delete_existing_legacy_docs:
            collection.delete_many({"migration_metadata.source_name": LEGACY_SOURCE_NAME})

        result = bulk_replace(collection, docs)
        artifacts.report.mongo_result[collection_name] = result

    db["ingredient"].create_index("legacy_id", unique=True, sparse=True, name="legacy_id_unique")
    db["ingredient"].create_index("group_uuid", name="group_uuid")
    db["ingredient"].create_index("rayon_uuid", name="rayon_uuid")
    db["ingredient_group"].create_index("slug", unique=True, name="slug_unique")
    db["ingredient_rayon"].create_index("slug", unique=True, name="slug_unique")
    db["equipment"].create_index("legacy_id", unique=True, sparse=True, name="legacy_id_unique")
    db["tag"].create_index("slug", unique=True, name="slug_unique")
    db["recipe"].create_index("legacy_id", unique=True, sparse=True, name="legacy_id_unique")
    db["recipe"].create_index("ingredients.ingredient_uuid", name="ingredients_ingredient_uuid")
    db["recipe"].create_index("equipment.equipment_uuid", name="equipment_equipment_uuid")
    db["recipe"].create_index("tag_uuids", name="tag_uuids")
    db["recipe"].create_index("season_months", name="season_months")
    db[MEAL_PLAN_ENTRY_COLLECTION].create_index("legacy_id", unique=True, sparse=True, name="legacy_id_unique")
    db[MEAL_PLAN_ENTRY_COLLECTION].create_index("date", name="date")
    db[MEAL_PLAN_ENTRY_COLLECTION].create_index("document_type", name="document_type")
    db[MEAL_PLAN_ENTRY_COLLECTION].create_index(
        [("document_type", 1), ("date", 1)],
        name="document_type_date",
    )


def bulk_replace(collection: Any, docs: list[MongoDocument]) -> dict[str, int]:
    if not docs:
        return {"matched": 0, "modified": 0, "upserted": 0}

    operations = [ReplaceOne({"_id": doc["_id"]}, doc, upsert=True) for doc in docs]
    result = collection.bulk_write(operations, ordered=False)
    return {
        "matched": result.matched_count,
        "modified": result.modified_count,
        "upserted": result.upserted_count,
    }


def write_report(report: ImportReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.__dict__, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def print_summary(report: ImportReport) -> None:
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2, sort_keys=True))


def entity_to_doc(entity: Any) -> MongoDocument:
    doc = entity.model_dump(mode="json", exclude_computed_fields=True)
    doc["_id"] = str(doc.pop("uuid"))
    return doc


def recipe_quality_status(
    row: SqlRow,
    ingredients: list[RecipeIngredient],
    steps: list[Step],
) -> RecipeQualityStatus:
    if ingredients and steps:
        return RecipeQualityStatus.structured
    if clean_text(row.get("description")) is not None:
        return RecipeQualityStatus.text_only
    return RecipeQualityStatus.minimal


def planner_entry_type(recipe_id: int | None, ingredient_id: int | None, note: str | None) -> str:
    if recipe_id is not None and ingredient_id is not None:
        return "mixed"
    if recipe_id is not None:
        return "recipe"
    if ingredient_id is not None:
        return "ingredient"
    if note is None:
        return "note"

    note_lower = note.lower()
    if note_lower.startswith(("préparer", "preparer", "décongeler", "decongeler", "mettre à", "mettre a")):
        return "prep_task"
    return "note"


def legacy_status(row: SqlRow) -> str:
    return "archived" if clean_text(row.get("corbeille")) == "OUI" else "active"


def legacy_uuid(table: str, legacy_id: int) -> str:
    return str(uuid5(LEGACY_NAMESPACE, f"{table}:{legacy_id}"))


def named_legacy_uuid(kind: str, name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.strip().casefold())
    return str(uuid5(LEGACY_NAMESPACE, f"{kind}:{normalized}"))


def calculate_recipe_season(
    ingredients: list[RecipeIngredient],
    ingredient_season_by_uuid: dict[str, dict[int, int]],
) -> dict[int, int]:
    ingredient_seasons = [
        season
        for ingredient in ingredients
        if (season := ingredient_season_by_uuid.get(str(ingredient.ingredient_uuid)))
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


def require_int(value: SqlValue) -> int:
    parsed = optional_int(value)
    if parsed is None:
        raise ValueError(f"Expected int, got {value!r}")
    return parsed


def optional_int(value: SqlValue) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if value.strip() == "":
        return None
    return int(value)


def positive_int(value: SqlValue) -> int | None:
    parsed = optional_int(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def positive_float(value: SqlValue) -> float | None:
    if value is None:
        return None
    parsed = float(value)
    if parsed <= 0:
        return None
    return parsed


def level_1_to_5(value: SqlValue) -> int | None:
    parsed = optional_int(value)
    if parsed is None or not 1 <= parsed <= 5:
        return None
    return parsed


def clean_text(value: SqlValue) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def choice_name(choices: dict[int, str], value: SqlValue) -> str | None:
    legacy_id = optional_int(value)
    if legacy_id is None:
        return None
    return choices.get(legacy_id)


def yes_no(value: SqlValue) -> bool:
    return clean_text(value) == "OUI"


def parse_datetime(value: SqlValue) -> datetime | None:
    text = clean_text(value)
    if text is None:
        return None
    return datetime.fromisoformat(text)


def time_to_minutes(value: SqlValue) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    hours, minutes, seconds = [int(part) for part in text.split(":", maxsplit=2)]
    total = hours * 60 + minutes + (1 if seconds >= 30 else 0)
    return total or None


def datetime_to_json(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def season_months(row: SqlRow) -> dict[int, int]:
    months: dict[int, int] = {}
    for month in range(1, 13):
        score = optional_int(row.get(f"dispo_{month:02d}"))
        if score is not None and 1 <= score <= 3:
            months[month] = score
    return months


def increment(mapping: dict[str, int], key: str) -> None:
    mapping[key] = mapping.get(key, 0) + 1


def main() -> int:
    args = parse_args()
    tables = load_sql_tables(args.data_sql, TARGET_TABLES)
    artifacts = build_artifacts(tables, args)

    if not args.dry_run:
        import_into_mongo(artifacts, args)

    write_report(artifacts.report, args.report_path)
    print_summary(artifacts.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
