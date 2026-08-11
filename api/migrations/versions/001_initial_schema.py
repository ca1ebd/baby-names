"""Initial schema with six tables

Revision ID: 001
Revises:
Create Date: 2026-08-10 07:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create names table
    op.create_table('names',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('gender', sa.String(), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('is_core', sa.Boolean(), nullable=False),
    sa.CheckConstraint("gender IN ('girl', 'boy')", name='ck_names_gender'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    sa.UniqueConstraint('gender', 'rank', name='uq_names_gender_rank')
    )
    op.create_index('ix_names_gender_rank', 'names', ['gender', 'rank'], unique=False)

    # Create accounts table
    op.create_table('accounts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('deck_seed', sa.Integer(), nullable=False),
    sa.Column('last_name', sa.String(), nullable=False),
    sa.Column('gender_filter', sa.String(), nullable=False),
    sa.Column('onboarded', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    # Create swipers table
    op.create_table('swipers',
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('slot', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint('slot IN (0, 1)', name='ck_swipers_slot'),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('account_id', 'slot')
    )

    # Create served_order table
    op.create_table('served_order',
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('name_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['name_id'], ['names.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('account_id', 'position'),
    sa.UniqueConstraint('account_id', 'name_id', name='uq_served_order_account_name')
    )

    # Create picks table
    op.create_table('picks',
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('slot', sa.Integer(), nullable=False),
    sa.Column('name_id', sa.Integer(), nullable=False),
    sa.Column('verdict', sa.String(), nullable=False),
    sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('slot IN (0, 1)', name='ck_picks_slot'),
    sa.CheckConstraint("verdict IN ('keep', 'no')", name='ck_picks_verdict'),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['name_id'], ['names.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('account_id', 'slot', 'name_id')
    )

    # Create rate_limit_windows table
    op.create_table('rate_limit_windows',
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('request_count', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('account_id', 'window_start')
    )


def downgrade() -> None:
    op.drop_table('rate_limit_windows')
    op.drop_table('picks')
    op.drop_table('served_order')
    op.drop_table('swipers')
    op.drop_table('accounts')
    op.drop_index('ix_names_gender_rank', table_name='names')
    op.drop_table('names')
