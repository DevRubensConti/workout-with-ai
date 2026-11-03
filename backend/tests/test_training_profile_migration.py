import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def test_training_profile_migration_preserves_existing_tables(tmp_path, monkeypatch):
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0009_training_profiles.py"
    spec = importlib.util.spec_from_file_location("training_profile_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users (id UUID PRIMARY KEY)")
            connection.exec_driver_sql(
                "CREATE TABLE muscle_targets (id UUID PRIMARY KEY, code VARCHAR(80))"
            )
            connection.exec_driver_sql("CREATE TABLE exercise_muscle_effects (id UUID PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO muscle_targets VALUES ('test', 'chest')")
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            inspector = inspect(connection)
            assert "training_profiles" in inspector.get_table_names()
            assert {column["name"] for column in inspector.get_columns("training_profiles")} == {
                "user_id",
                "age",
                "weight_kg",
                "height_cm",
                "updated_at",
            }
            assert len(inspector.get_check_constraints("training_profiles")) == 3
            assert (
                inspector.get_foreign_keys("training_profiles")[0]["options"]["ondelete"]
                == "CASCADE"
            )
            assert connection.exec_driver_sql("SELECT code FROM muscle_targets").scalar() == "chest"
            migration.downgrade()
            assert "training_profiles" not in inspect(connection).get_table_names()
            assert connection.exec_driver_sql("SELECT code FROM muscle_targets").scalar() == "chest"
            assert "exercise_muscle_effects" in inspect(connection).get_table_names()
    finally:
        engine.dispose()
