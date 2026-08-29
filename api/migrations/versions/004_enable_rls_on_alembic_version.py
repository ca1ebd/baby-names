"""Enable row-level security on alembic_version too

002 enabled RLS on the six application tables but deliberately left
alembic_version alone, and the guard test in
tests/integration/test_row_level_security.py excluded it by name.
alembic_version holds no user data, but it still lives in the `public`
schema Supabase's PostgREST auto-exposes via the anon key, so there's
no reason to leave it as the one unprotected table.

Revision ID: 004
Revises: 003
Create Date: 2026-08-29 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.execute('ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY')
