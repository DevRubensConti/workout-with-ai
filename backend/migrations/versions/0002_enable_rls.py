"""habilita RLS nas tabelas (Supabase)

No Supabase, tabelas do schema public ficam acessíveis pela Data API (PostgREST)
com a anon key. Com RLS ligado e sem policies, ninguém além de roles que
ignoram RLS (a conexão `postgres` usada por este backend) consegue ler/escrever.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27 22:30:00
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("users", "password_reset_tokens")


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    if not _is_postgres():
        return
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
