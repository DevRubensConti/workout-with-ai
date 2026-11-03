"""Import the English free-exercise-db catalog in a single transaction."""

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.workouts.models import Exercise, ExerciseTranslation

SOURCE = "free-exercise-db"
NonEmptyText = Annotated[str, Field(min_length=1)]


class CatalogExercise(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    force: str | None = Field(max_length=40)
    level: str = Field(min_length=1, max_length=40)
    mechanic: str | None = Field(max_length=40)
    equipment: str | None = Field(max_length=80)
    primaryMuscles: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(min_length=1)
    secondaryMuscles: list[Annotated[str, Field(min_length=1, max_length=60)]]
    instructions: list[str]
    category: str = Field(min_length=1, max_length=60)
    images: list[NonEmptyText]

    @field_validator("id", "name", "level", "category")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be blank.")
        return value

    @field_validator("primaryMuscles", "secondaryMuscles")
    @classmethod
    def reject_blank_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("List items must not be blank.")
        return values

    @field_validator("images")
    @classmethod
    def validate_image_paths(cls, paths: list[str]) -> list[str]:
        for value in paths:
            path = PurePosixPath(value)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in value
                or ":" in value
                or not value.strip()
            ):
                raise ValueError("Images must be relative source paths without traversal.")
        return paths


CATALOG = TypeAdapter(Annotated[list[CatalogExercise], Field(min_length=1)])


def load_catalog(path: Path) -> list[CatalogExercise]:
    records = CATALOG.validate_json(path.read_text(encoding="utf-8-sig"))
    validate_identifiers(records)
    return records


def validate_identifiers(records: list[CatalogExercise]) -> None:
    duplicates = sorted(key for key, count in Counter(r.id for r in records).items() if count > 1)
    if duplicates:
        raise ValueError(f"Duplicate source IDs: {', '.join(duplicates)}")


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0


def import_catalog(session: Session, records: list[CatalogExercise]) -> ImportResult:
    """Caller owns the transaction; no commits or deletions are performed here."""
    validate_identifiers(records)
    existing = {
        item.source_id: item
        for item in session.scalars(select(Exercise).where(Exercise.source == SOURCE))
    }
    for row in records:
        if row.id in existing and existing[row.id].owner_user_id is not None:
            raise ValueError(f"Source ID belongs to a private exercise: {row.id}")

    result = ImportResult()
    for row in records:
        item = existing.get(row.id)
        is_new = item is None
        if item is None:
            item = Exercise(source=SOURCE, source_id=row.id)
            session.add(item)

        values = {
            "name": row.name,
            "muscle_group": row.primaryMuscles[0],
            "equipment": row.equipment,
            "force": row.force,
            "level": row.level,
            "mechanic": row.mechanic,
            "category": row.category,
            "primary_muscles": row.primaryMuscles,
            "secondary_muscles": row.secondaryMuscles,
            "images": row.images,
        }
        changed = is_new
        for key, value in values.items():
            if getattr(item, key) != value:
                setattr(item, key, value)
                changed = True

        english = next((t for t in item.translations if t.locale == "en"), None)
        if english is None:
            item.translations.append(
                ExerciseTranslation(locale="en", name=row.name, instructions=row.instructions)
            )
            changed = True
        elif english.name != row.name or english.instructions != row.instructions:
            english.name = row.name
            english.instructions = row.instructions
            changed = True

        if is_new:
            result.created += 1
        elif changed:
            result.updated += 1
        else:
            result.unchanged += 1

    session.flush()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Local English exercises.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; no DB connection")
    args = parser.parse_args()
    try:
        records = load_catalog(args.path)
    except (OSError, ValidationError, ValueError) as error:
        raise SystemExit(f"Catalog validation failed: {error}") from error
    print(f"Validated {len(records)} English exercises from {SOURCE}.")
    missing = [row.id for row in records if not row.instructions]
    blank_steps = [row.id for row in records if any(not s.strip() for s in row.instructions)]
    if missing:
        print(f"WARNING: no instructions in source: {', '.join(missing)}")
    if blank_steps:
        print(f"WARNING: blank instruction steps preserved: {', '.join(blank_steps)}")
    if args.dry_run:
        return
    try:
        with SessionLocal.begin() as session:
            result = import_catalog(session, records)
    except (SQLAlchemyError, ValueError) as error:
        raise SystemExit(
            f"Import aborted ({type(error).__name__}); transaction rolled back. "
            "Check database availability, migration version and source ID ownership."
        ) from None
    print(
        f"Committed: created={result.created}, updated={result.updated}, "
        f"unchanged={result.unchanged}."
    )


if __name__ == "__main__":
    main()
