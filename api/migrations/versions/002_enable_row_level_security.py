"""Enable row-level security on all tables

Every table lives in the `public` schema, which Supabase's PostgREST API
auto-exposes to anyone holding the project's anon key — and that key ships
in the frontend's public JS bundle (VITE_SUPABASE_ANON_KEY), so it's not a
secret. With RLS off, that API can read and write every account, swiper,
and pick directly, completely bypassing the FastAPI backend's auth.

No policies are added because none are needed: the backend never talks to
Postgres through PostgREST — it connects directly via DATABASE_URL as the
table-owning role, which bypasses RLS by default. Enabling RLS with zero
policies only closes the PostgREST path; the app keeps working unchanged.

Revision ID: 002
Revises: 001
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    'names',
    'accounts',
    'swipers',
    'served_order',
    'picks',
    'rate_limit_windows',
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
