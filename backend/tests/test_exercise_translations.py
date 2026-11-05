import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.workouts.exercises.models import Exercise, ExerciseTranslation


def exercise():
    return Exercise(
        name="Bench Press",
        muscle_group="chest",
        source="free-exercise-db",
        source_id="Bench_Press",
        equipment="barbell",
        force="push",
        level="beginner",
        mechanic="compound",
        category="strength",
        primary_muscles=["chest"],
        secondary_muscles=["triceps", "shoulders"],
        images=["Bench_Press/0.jpg", "Bench_Press/1.jpg"],
        translations=[
            ExerciseTranslation(
                locale="en", name="Bench Press", instructions=["First step", "Second step"]
            ),
            ExerciseTranslation(
                locale="pt-BR", name="Supino reto", instructions=["Etapa 1", "Etapa 2"]
            ),
        ],
    )


def test_one_uuid_two_languages_and_ordered_json_fields(session_factory):
    with session_factory() as db:
        item = exercise()
        db.add(item)
        db.commit()
        item_id = item.id
        assert isinstance(item_id, uuid.UUID)
    with session_factory() as db:
        loaded = db.get(Exercise, item_id)
        assert loaded.source_id == "Bench_Press"
        assert loaded.primary_muscles == ["chest"]
        assert loaded.secondary_muscles == ["triceps", "shoulders"]
        assert loaded.images == ["Bench_Press/0.jpg", "Bench_Press/1.jpg"]
        texts = {t.locale: t for t in loaded.translations}
        assert texts["en"].instructions == ["First step", "Second step"]
        assert texts["pt-BR"].instructions == ["Etapa 1", "Etapa 2"]
        assert texts["en"].exercise is loaded
        assert db.scalar(select(func.count()).select_from(Exercise)) == 1


def test_same_source_identifier_cannot_be_imported_twice(session_factory):
    with session_factory() as db:
        db.add(exercise())
        db.commit()
        db.add(exercise())
        with pytest.raises(IntegrityError):
            db.commit()


def test_manual_exercises_need_no_source_or_translations(session_factory):
    with session_factory() as db:
        db.add_all(
            [
                Exercise(name="Custom", muscle_group="chest"),
                Exercise(name="Custom", muscle_group="chest"),
            ]
        )
        db.commit()
        assert db.scalar(select(func.count()).select_from(Exercise)) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"locale": "en"},
        {"locale": "pt"},
        {"locale": "pt-BR", "name": "  "},
    ],
)
def test_duplicate_locale_invalid_locale_and_empty_name_rejected(session_factory, changes):
    with session_factory() as db:
        item = exercise()
        if changes.get("name") == "  ":
            item.translations.clear()
        db.add(item)
        db.commit()
        item.translations.append(ExerciseTranslation(**{"name": "Test", **changes}))
        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize("source,source_id", [("free-exercise-db", None), (None, "external")])
def test_source_and_identifier_are_required_together(session_factory, source, source_id):
    with session_factory() as db:
        db.add(Exercise(name="Test", muscle_group="chest", source=source, source_id=source_id))
        with pytest.raises(IntegrityError):
            db.commit()


def test_deleting_exercise_cascades_translations(session_factory):
    with session_factory() as db:
        item = exercise()
        db.add(item)
        db.commit()
        item_id = item.id
    with session_factory() as db:
        item = db.get(Exercise, item_id)
        db.delete(item)
        db.commit()
        assert db.scalar(select(func.count()).select_from(ExerciseTranslation)) == 0
