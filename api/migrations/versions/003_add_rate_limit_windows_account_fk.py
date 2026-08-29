"""Add the missing accounts FK on rate_limit_windows.account_id

data-model.md always specified this as `uuid FK -> accounts` (same as
swipers, served_order, and picks), and the app already relies on that
guarantee in practice: `get_current_user` provisions the account row
before any handler runs, so `check_rate_limit` never writes a row for
an account that doesn't exist. The migration that created the table
just never added the constraint. `ON DELETE CASCADE` matches the other
three account_id FKs, so a reset/account deletion clears its rate
limit counters along with everything else.

Revision ID: 003
Revises: 002
Create Date: 2026-08-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        'rate_limit_windows_account_id_fkey',
        'rate_limit_windows',
        'accounts',
        ['account_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint(
        'rate_limit_windows_account_id_fkey',
        'rate_limit_windows',
        type_='foreignkey',
    )
