"""Import Portuguese exercise translations by their canonical source IDs."""

import argparse
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from src.database import SessionLocal
from src.scripts.import_exercises import SOURCE, CatalogExercise, load_catalog, validate_identifiers
from src.workouts.exercises.models import Exercise, ExerciseTranslation

LOCALE = "pt-BR"


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0


def import_translations(session: Session, records: list[CatalogExercise]) -> ImportResult:
    """Upsert pt-BR text only; the caller owns the transaction."""
    validate_identifiers(records)
    exercises = list(
        session.scalars(
            select(Exercise)
            .options(selectinload(Exercise.translations))
            .where(Exercise.source == SOURCE)
        )
    )
    exercises_by_id: dict[str, Exercise] = {}
    for exercise in exercises:
        source_id = exercise.source_id
        if source_id is None:
            raise ValueError(f"Source exercise has no source ID: {exercise.id}")
        if exercise.owner_user_id is not None:
            raise ValueError(f"Source ID belongs to a private exercise: {source_id}")
        exercises_by_id[source_id] = exercise

    records_by_id = {record.id: record for record in records}
    missing = sorted(exercises_by_id.keys() - records_by_id.keys())
    unknown = sorted(records_by_id.keys() - exercises_by_id.keys())
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing from translation file: {', '.join(missing)}")
        if unknown:
            details.append(f"not found in database: {', '.join(unknown)}")
        raise ValueError(
            "Translation file IDs must exactly match the database catalog; " + "; ".join(details)
        )

    result = ImportResult()
    for source_id, row in records_by_id.items():
        exercise = exercises_by_id[source_id]
        translation = next((item for item in exercise.translations if item.locale == LOCALE), None)
        if translation is None:
            exercise.translations.append(
                ExerciseTranslation(locale=LOCALE, name=row.name, instructions=row.instructions)
            )
            result.created += 1
        elif translation.name != row.name or translation.instructions != row.instructions:
            translation.name = row.name
            translation.instructions = row.instructions
            result.updated += 1
        else:
            result.unchanged += 1

    session.flush()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Full exercise catalog with Portuguese names/text")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check database ID coverage and report changes without committing",
    )
    args = parser.parse_args()
    try:
        records = load_catalog(args.path)
    except (OSError, ValidationError, ValueError) as error:
        raise SystemExit(f"Translation validation failed: {error}") from error

    try:
        with SessionLocal() as session:
            if args.dry_run:
                result = import_translations(session, records)
                session.rollback()
                print(
                    f"Dry run for {len(records)} pt-BR translations: "
                    f"created={result.created}, updated={result.updated}, "
                    f"unchanged={result.unchanged}."
                )
            else:
                with session.begin():
                    result = import_translations(session, records)
                print(
                    f"Committed pt-BR translations: created={result.created}, "
                    f"updated={result.updated}, unchanged={result.unchanged}."
                )
    except (SQLAlchemyError, ValueError) as error:
        raise SystemExit(
            f"Import aborted ({type(error).__name__}); transaction rolled back. "
            "Check database availability, catalog ID coverage and source ownership."
        ) from None


if __name__ == "__main__":
    main()
