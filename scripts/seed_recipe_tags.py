#!/usr/bin/env python3
"""Idempotently seed the curated recipe-tag catalogue through the Recipe API."""

from __future__ import annotations

import argparse
import json
import os
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TagSeed:
    name: str
    category: str


CURATED_TAGS = (
    TagSeed("plat principal", "service"),
    TagSeed("accompagnement", "service"),
    TagSeed("petit déjeuner", "service"),
    TagSeed("déjeuner", "service"),
    TagSeed("goûter", "service"),
    TagSeed("dîner", "service"),
    TagSeed("entrée", "service"),
    TagSeed("dessert", "service"),
    TagSeed("apéritif", "service"),
    TagSeed("brunch", "service"),
    TagSeed("rapide", "other"),
    TagSeed("healthy", "diet"),
    TagSeed("végétarien", "diet"),
    TagSeed("vegan", "diet"),
    TagSeed("sans gluten", "diet"),
    TagSeed("soupe", "other"),
    TagSeed("sandwich", "other"),
    TagSeed("street food", "other"),
    TagSeed("salade", "other"),
    TagSeed("épicé", "other"),
    TagSeed("parfumé", "other"),
    TagSeed("familial", "occasion"),
    TagSeed("batch cooking", "technique"),
    TagSeed("réconfortant", "occasion"),
)


def normalized_name(value: str) -> str:
    folded = value.casefold().replace("œ", "oe").replace("æ", "ae")
    without_accents = "".join(
        character
        for character in unicodedata.normalize("NFKD", folded)
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.split())


class RecipeTagSeeder:
    def __init__(self, base_url: str, tenant_uri: str, token: str | None = None) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Tenant-URI": tenant_uri,
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def list_tags(self) -> list[dict]:
        tags: list[dict] = []
        page = 1
        while True:
            payload = self._request("GET", f"v1/tags/?{urlencode({'page': page, 'per_page': 100})}")
            items = payload.get("data", [])
            tags.extend(items)
            pagination = payload.get("pagination") or {}
            if not items or page >= int(pagination.get("total_pages") or page):
                return tags
            page += 1

    def create_tag(self, seed: TagSeed) -> dict:
        payload = self._request(
            "POST",
            "v1/tags/",
            {"name": seed.name, "category": seed.category},
        )
        return payload["data"]

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        request = Request(
            urljoin(self._base_url, path),
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers=self._headers,
            method=method,
        )
        with urlopen(request, timeout=30) as response:  # nosec B310 - operator-supplied HTTP(S) API
            return json.loads(response.read())


def seed_tags(seeder: RecipeTagSeeder, *, apply: bool) -> tuple[list[str], list[str]]:
    existing = seeder.list_tags()
    existing_by_name: dict[str, dict] = {}
    duplicates: set[str] = set()
    for tag in existing:
        key = normalized_name(tag["name"])
        if key in existing_by_name:
            duplicates.add(key)
        else:
            existing_by_name[key] = tag
    if duplicates:
        names = ", ".join(sorted(duplicates))
        raise RuntimeError(f"Duplicate normalized tags already exist: {names}")

    kept: list[str] = []
    created: list[str] = []
    for seed in CURATED_TAGS:
        key = normalized_name(seed.name)
        if key in existing_by_name:
            kept.append(existing_by_name[key]["name"])
        elif apply:
            seeder.create_tag(seed)
            created.append(seed.name)
        else:
            created.append(seed.name)
    return kept, created


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Recipe API base URL, e.g. http://127.0.0.1:8301/")
    parser.add_argument("--tenant-uri", required=True, help="Tenant URI sent through X-Tenant-URI")
    parser.add_argument("--apply", action="store_true", help="Create missing tags; otherwise only print the plan")
    args = parser.parse_args()

    seeder = RecipeTagSeeder(
        args.base_url,
        args.tenant_uri,
        token=os.getenv("REKIPE_TAG_SEED_BEARER_TOKEN"),
    )
    kept, missing_or_created = seed_tags(seeder, apply=args.apply)
    action = "created" if args.apply else "missing"
    print(json.dumps({"kept": kept, action: missing_or_created}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
