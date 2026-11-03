import pytest
from sqlalchemy import func, select

from src.scripts.import_exercise_translations import import_translations
from src.scripts.import_exercises import SOURCE, CatalogExercise
from src.workouts.models import Exercise, ExerciseTranslation


def record(source_id, name, instructions):
    return CatalogExercise.model_validate(
        {
            "id": source_id,
            "name": name,
            "force": "push",
            "level": "beginner",
            "mechanic": "compound",
            "equipment": "barbell",
            "primaryMuscles": ["chest"],
            "secondaryMuscles": ["triceps"],
            "instructions": instructions,
            "category": "strength",
            "images": [],
        }
    )


def seed_exercises(session_factory):
    with session_factory() as db, db.begin():
        for source_id, name in (("Bench_Press", "Bench Press"), ("Squat", "Squat")):
            db.add(
                Exercise(
                    source=SOURCE,
                    source_id=source_id,
                    name=name,
                    muscle_group="chest",
                    translations=[
                        ExerciseTranslation(
                            locale="en", name=name, instructions=["Original English"]
                        )
                    ],
                )
            )


def test_import_creates_and_idempotently_updates_translations(session_factory):
    seed_exercises(session_factory)
    records = [
        record("Bench_Press", "Supino", ["Deite-se no banco."]),
        record("Squat", "Agachamento", ["Fique em pé."]),
    ]

    with session_factory() as db, db.begin():
        result = import_translations(db, records)
        assert (result.created, result.updated, result.unchanged) == (2, 0, 0)
    with session_factory() as db:
        exercise = db.scalar(select(Exercise).where(Exercise.source_id == "Bench_Press"))
        translations = {item.locale: item for item in exercise.translations}
        assert exercise.name == "Bench Press"
        assert translations["en"].name == "Bench Press"
        assert translations["en"].instructions == ["Original English"]
        assert translations["pt-BR"].name == "Supino"
        assert translations["pt-BR"].instructions == ["Deite-se no banco."]

    with session_factory() as db, db.begin():
        result = import_translations(db, records)
        assert (result.created, result.updated, result.unchanged) == (0, 0, 2)

    updated_records = [record("Bench_Press", "Supino reto", ["Ajuste o banco."]), records[1]]
    with session_factory() as db, db.begin():
        result = import_translations(db, updated_records)
        assert (result.created, result.updated, result.unchanged) == (0, 1, 1)
    with session_factory() as db:
        exercise = db.scalar(select(Exercise).where(Exercise.source_id == "Bench_Press"))
        translations = {item.locale: item for item in exercise.translations}
        assert translations["pt-BR"].name == "Supino reto"
        assert translations["en"].instructions == ["Original English"]
        assert db.scalar(select(func.count()).select_from(ExerciseTranslation)) == 4


def test_import_requires_exact_database_catalog_coverage(session_factory):
    seed_exercises(session_factory)
    records = [record("Bench_Press", "Supino", ["Deite-se no banco."])]

    with session_factory() as db, pytest.raises(ValueError, match="exactly match"), db.begin():
        import_translations(db, records)

    with session_factory() as db:
        assert db.scalar(
            select(func.count())
            .select_from(ExerciseTranslation)
            .where(ExerciseTranslation.locale == "pt-BR")
        ) == 0


def test_import_rejects_unknown_database_ids(session_factory):
    seed_exercises(session_factory)
    records = [
        record("Bench_Press", "Supino", ["Deite-se no banco."]),
        record("Unknown", "Desconhecido", ["Texto."]),
    ]

    with (
        session_factory() as db,
        pytest.raises(ValueError, match="not found in database"),
        db.begin(),
    ):
        import_translations(db, records)
