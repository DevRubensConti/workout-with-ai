"""Empty assessment and review structure for external catalog imports.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exercise_biomechanical_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("scale_version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("assessment_method", sa.String(10), nullable=False),
        sa.Column("assessment_source", sa.String(500), nullable=False),
        sa.Column("execution_context", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "exercise_id", name="uq_biomechanical_assessment_exercise"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["scale_version"], ["biomechanical_scale_versions.version"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["supersedes_id", "exercise_id"],
            [
                "exercise_biomechanical_assessments.id",
                "exercise_biomechanical_assessments.exercise_id",
            ],
            ondelete="RESTRICT",
            name="fk_biomechanical_assessment_predecessor",
        ),
        sa.CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id != id",
            name="ck_biomechanical_assessment_predecessor",
        ),
        sa.CheckConstraint(
            "assessment_method IN ('manual', 'ai', 'rule')",
            name="ck_biomechanical_assessment_method",
        ),
        sa.CheckConstraint(
            "length(trim(assessment_source)) > 0", name="ck_biomechanical_assessment_source"
        ),
        sa.CheckConstraint(
            "length(trim(execution_context)) > 0", name="ck_biomechanical_assessment_context"
        ),
    )
    op.create_index(
        "ix_biomechanical_assessment_exercise_created",
        "exercise_biomechanical_assessments",
        ["exercise_id", "created_at"],
    )
    op.create_index(
        "ix_biomechanical_assessment_scale", "exercise_biomechanical_assessments", ["scale_version"]
    )
    op.create_table(
        "exercise_region_demands",
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("region_code", sa.String(30), nullable=False),
        sa.Column("assessment_status", sa.String(15), nullable=False),
        sa.Column("demand_score", sa.Integer(), nullable=True),
        sa.Column("demand_role", sa.String(20), nullable=True),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("assessment_id", "region_code"),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["exercise_biomechanical_assessments.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "region_code IN ('shoulder', 'lumbar_spine', 'cervical_spine', 'knee', 'elbow')",
            name="ck_exercise_region_demand_region",
        ),
        sa.CheckConstraint(
            "(assessment_status = 'assessed' AND demand_score IS NOT NULL "
            "AND demand_score BETWEEN 0 AND 5 AND demand_role IS NOT NULL "
            "AND demand_role IN ('direct', 'secondary', 'stabilizing')) OR "
            "(assessment_status = 'unassessed' AND demand_score IS NULL AND demand_role IS NULL)",
            name="ck_exercise_region_demand_result",
        ),
        sa.CheckConstraint(
            "length(trim(justification)) > 0", name="ck_exercise_region_demand_reason"
        ),
    )
    op.create_table(
        "biomechanical_assessment_reviews",
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(15), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column(
            "reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["exercise_biomechanical_assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "decision IN ('reviewed', 'rejected')", name="ck_biomechanical_review_decision"
        ),
        sa.CheckConstraint("length(trim(notes)) > 0", name="ck_biomechanical_review_notes"),
    )
    if op.get_context().dialect.name == "postgresql":
        for table in (
            "exercise_biomechanical_assessments",
            "exercise_region_demands",
            "biomechanical_assessment_reviews",
        ):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # Deferred validation allows external imports to insert a header and five rows atomically.
        op.execute("""
            CREATE FUNCTION check_biomechanical_assessment_regions() RETURNS trigger
            LANGUAGE plpgsql AS $$
            DECLARE target_id uuid;
            BEGIN
                IF TG_TABLE_NAME = 'exercise_biomechanical_assessments' THEN
                    target_id := NEW.id;
                ELSIF TG_OP = 'DELETE' THEN
                    target_id := OLD.assessment_id;
                ELSE
                    target_id := NEW.assessment_id;
                END IF;
                IF EXISTS (SELECT 1 FROM exercise_biomechanical_assessments WHERE id = target_id)
                   AND (SELECT count(*) FROM exercise_region_demands
                        WHERE assessment_id = target_id) != 5 THEN
                    RAISE EXCEPTION 'A biomechanical assessment must contain exactly five regions';
                END IF;
                IF TG_OP = 'UPDATE' AND TG_TABLE_NAME = 'exercise_region_demands' THEN
                    IF OLD.assessment_id != NEW.assessment_id
                       AND EXISTS (SELECT 1 FROM exercise_biomechanical_assessments
                                   WHERE id = OLD.assessment_id)
                       AND (SELECT count(*) FROM exercise_region_demands
                            WHERE assessment_id = OLD.assessment_id) != 5 THEN
                        RAISE EXCEPTION 'The original assessment must retain five regions';
                    END IF;
                END IF;
                RETURN NULL;
            END $$;
        """)
        for table, events in (
            ("exercise_biomechanical_assessments", "INSERT OR UPDATE"),
            ("exercise_region_demands", "INSERT OR UPDATE OR DELETE"),
        ):
            op.execute(f"""
                CREATE CONSTRAINT TRIGGER {table}_complete
                AFTER {events} ON {table}
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
                EXECUTE FUNCTION check_biomechanical_assessment_regions()
            """)
        op.execute("""
            CREATE FUNCTION guard_biomechanical_assessment() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF EXISTS (SELECT 1 FROM biomechanical_assessment_reviews
                           WHERE assessment_id = OLD.id) THEN
                    IF TG_OP = 'UPDATE' THEN
                        IF NEW.created_by IS NULL AND OLD.created_by IS NOT NULL
                           AND (to_jsonb(NEW) - 'created_by') = (to_jsonb(OLD) - 'created_by') THEN
                            RETURN NEW;
                        END IF;
                    END IF;
                    RAISE EXCEPTION 'Reviewed assessments are immutable; create a new assessment';
                END IF;
                IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END $$;
        """)
        op.execute("""
            CREATE TRIGGER biomechanical_assessment_immutable
            BEFORE UPDATE OR DELETE ON exercise_biomechanical_assessments
            FOR EACH ROW EXECUTE FUNCTION guard_biomechanical_assessment()
        """)
        op.execute("""
            CREATE FUNCTION guard_biomechanical_region() RETURNS trigger
            LANGUAGE plpgsql AS $$
            DECLARE target_id uuid;
            BEGIN
                IF TG_OP = 'DELETE' THEN target_id := OLD.assessment_id;
                ELSE target_id := NEW.assessment_id; END IF;
                IF TG_OP = 'UPDATE' AND NEW.assessment_id != OLD.assessment_id THEN
                    RAISE EXCEPTION 'A region cannot be moved to another assessment';
                END IF;
                PERFORM id FROM exercise_biomechanical_assessments
                WHERE id = target_id FOR UPDATE;
                IF EXISTS (SELECT 1 FROM biomechanical_assessment_reviews
                           WHERE assessment_id = target_id) THEN
                    RAISE EXCEPTION 'Reviewed region results are immutable';
                END IF;
                IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END $$;
        """)
        op.execute("""
            CREATE TRIGGER biomechanical_region_immutable
            BEFORE INSERT OR UPDATE OR DELETE ON exercise_region_demands
            FOR EACH ROW EXECUTE FUNCTION guard_biomechanical_region()
        """)
        op.execute("""
            CREATE FUNCTION guard_biomechanical_review() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    PERFORM id FROM exercise_biomechanical_assessments
                    WHERE id = NEW.assessment_id FOR UPDATE;
                    IF (SELECT count(*) FROM exercise_region_demands
                        WHERE assessment_id = NEW.assessment_id) != 5 THEN
                        RAISE EXCEPTION 'An assessment must contain five regions before review';
                    END IF;
                    RETURN NEW;
                END IF;
                IF TG_OP = 'UPDATE' THEN
                    IF NEW.reviewed_by IS NULL AND OLD.reviewed_by IS NOT NULL
                       AND (to_jsonb(NEW) - 'reviewed_by') = (to_jsonb(OLD) - 'reviewed_by') THEN
                        RETURN NEW;
                    END IF;
                END IF;
                RAISE EXCEPTION 'Review decisions are immutable';
            END $$;
        """)
        op.execute("""
            CREATE TRIGGER biomechanical_review_immutable
            BEFORE INSERT OR UPDATE OR DELETE ON biomechanical_assessment_reviews
            FOR EACH ROW EXECUTE FUNCTION guard_biomechanical_review()
        """)


def downgrade() -> None:
    op.drop_table("biomechanical_assessment_reviews")
    op.drop_table("exercise_region_demands")
    op.drop_table("exercise_biomechanical_assessments")
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP FUNCTION check_biomechanical_assessment_regions()")
        op.execute("DROP FUNCTION guard_biomechanical_assessment()")
        op.execute("DROP FUNCTION guard_biomechanical_region()")
        op.execute("DROP FUNCTION guard_biomechanical_review()")
