"""Allow empty assessment justifications and review notes.

Revision ID: 0014
Revises: 0013
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("exercise_region_demands") as batch:
        batch.drop_constraint("ck_exercise_region_demand_reason", type_="check")
    with op.batch_alter_table("biomechanical_assessment_reviews") as batch:
        batch.drop_constraint("ck_biomechanical_review_notes", type_="check")


def downgrade() -> None:
    # Empty texts must be resolved explicitly before restoring the old constraints.
    with op.batch_alter_table("exercise_region_demands") as batch:
        batch.create_check_constraint(
            "ck_exercise_region_demand_reason", "length(trim(justification)) > 0"
        )
    with op.batch_alter_table("biomechanical_assessment_reviews") as batch:
        batch.create_check_constraint("ck_biomechanical_review_notes", "length(trim(notes)) > 0")
