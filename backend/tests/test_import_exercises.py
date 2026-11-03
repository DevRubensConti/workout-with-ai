import json

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from src.auth.models import User
from src.scripts.import_exercises import SOURCE, import_catalog, load_catalog
from src.workouts.models import Exercise, ExerciseTranslation


def record(source_id="Bench_Press"):
    return {
        "id": source_id,
        "name": "Bench Press",
        "force": "push",
        "level": "beginner",
        "mechanic": None,
        "equipment": None,
        "primaryMuscles": ["chest", "shoulders"],
        "secondaryMuscles": ["triceps"],
        "instructions": ["First step", "Second step"],
        "category": "strength",
        "images": ["Bench_Press/0.jpg", "Bench_Press/1.jpg"],
    }


def catalog(tmp_path, rows):
    path = tmp_path / "exercises.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return load_catalog(path)


def test_import_matches_all_fields_and_is_idempotent(session_factory, tmp_path):
    records = catalog(tmp_path, [record()])
    with session_factory() as db, db.begin():
        result = import_catalog(db, records)
        assert (result.created, result.updated, result.unchanged) == (1, 0, 0)
    with session_factory() as db:
        item = db.scalar(select(Exercise))
        item_id, english_id = item.id, item.translations[0].id
        assert item.source == SOURCE and item.source_id == records[0].id
        assert item.owner_user_id is None
        assert item.name == records[0].name
        assert item.muscle_group == "chest"
        assert item.primary_muscles == ["chest", "shoulders"]
        assert item.secondary_muscles == ["triceps"]
        assert item.images == records[0].images
        assert item.force == "push" and item.category == "strength"
        assert item.equipment is None and item.mechanic is None
        assert item.level == "beginner"
        assert item.translations[0].locale == "en"
        assert item.translations[0].instructions == records[0].instructions
    with session_factory() as db, db.begin():
        result = import_catalog(db, records)
        assert (result.created, result.updated, result.unchanged) == (0, 0, 1)
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Exercise)) == 1
        assert db.scalar(select(func.count()).select_from(ExerciseTranslation)) == 1
        item = db.get(Exercise, item_id)
        assert item.translations[0].id == english_id


def test_reimport_updates_english_without_changing_other_languages_or_manual_data(
    session_factory, tmp_path
):
    records = catalog(tmp_path, [record()])
    with session_factory() as db, db.begin():
        import_catalog(db, records)
        item = db.scalar(select(Exercise))
        original_id = item.id
        item.video_url = "https://example.com/video"
        item.description = "Manually edited"
        item.translations.append(
            ExerciseTranslation(locale="pt-BR", name="Supino", instructions=["Passo 1"])
        )
        db.add(Exercise(name="Custom", muscle_group="chest"))
    changed = record()
    changed["name"], changed["instructions"] = "Updated name", ["Updated step"]
    with session_factory() as db, db.begin():
        result = import_catalog(db, catalog(tmp_path, [changed]))
        assert (result.created, result.updated, result.unchanged) == (0, 1, 0)
    with session_factory() as db:
        item = db.get(Exercise, original_id)
        texts = {t.locale: t for t in item.translations}
        assert item.name == texts["en"].name == "Updated name"
        assert texts["en"].instructions == ["Updated step"]
        assert texts["pt-BR"].name == "Supino"
        assert item.description == "Manually edited"
        assert item.video_url == "https://example.com/video"
        assert db.scalar(select(func.count()).select_from(Exercise)) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"name": " "},
        {"name": "x" * 161},
        {"primaryMuscles": []},
        {"primaryMuscles": [""]},
        {"instructions": "not a list"},
        {"instructions": [1]},
        {"images": ["../private.jpg"]},
        {"images": ["https://example.com/img.jpg"]},
        {"level": 1},
        {"unknown": "extra"},
    ],
)
def test_bad_input_rejected_before_import(tmp_path, change):
    with pytest.raises(ValidationError):
        catalog(tmp_path, [record(), {**record("Second"), **change}])


def test_duplicate_ids_rejected(tmp_path):
    with pytest.raises(ValueError, match="Duplicate source IDs"):
        catalog(tmp_path, [record(), record()])


def test_empty_or_malformed_json_rejected(tmp_path):
    with pytest.raises(ValidationError):
        catalog(tmp_path, [])
    path = tmp_path / "malformed.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_catalog(path)


@pytest.mark.parametrize("steps", [[], ["First", "", "Third"]])
def test_incomplete_source_instructions_are_preserved(session_factory, tmp_path, steps):
    with session_factory() as db, db.begin():
        import_catalog(db, catalog(tmp_path, [{**record(), "instructions": steps}]))
    with session_factory() as db:
        assert db.scalar(select(ExerciseTranslation)).instructions == steps


def test_private_source_id_collision_aborts_without_changing_owner(session_factory, tmp_path):
    with session_factory() as db, db.begin():
        user = User(name="Ana", email="ana@example.com", password_hash="test")
        db.add(user)
        db.flush()
        db.add(
            Exercise(
                name="Private",
                muscle_group="chest",
                owner_user_id=user.id,
                source=SOURCE,
                source_id="Bench_Press",
            )
        )
    with session_factory() as db, pytest.raises(ValueError, match="private exercise"), db.begin():
        import_catalog(db, catalog(tmp_path, [record("New"), record()]))
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Exercise)) == 1
        assert db.scalar(select(Exercise)).name == "Private"


def test_database_failure_rolls_back_entire_import(session_factory, tmp_path):
    records = catalog(tmp_path, [record(), record("Second")])
    with session_factory() as db:

        @event.listens_for(db, "before_flush")
        def inject_invalid_translation(session, *_):
            for item in list(session.new):
                if isinstance(item, ExerciseTranslation):
                    item.locale = "invalid"

        with pytest.raises(IntegrityError), db.begin():
            import_catalog(db, records)
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Exercise)) == 0
        assert db.scalar(select(func.count()).select_from(ExerciseTranslation)) == 0
