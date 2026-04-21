"""add revoke_logs table

Revision ID: 23ad21251631
Revises: e3b2f39e55bb
Create Date: 2026-04-21 12:13:51.434561

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '23ad21251631'
down_revision: Union[str, Sequence[str], None] = 'e3b2f39e55bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create revoke_logs table for detailed revoke audit trail."""
    op.create_table('revoke_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('case_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('revoke_type', sa.String(length=50), nullable=False),
        sa.Column('from_status', sa.String(length=50), nullable=False),
        sa.Column('to_status', sa.String(length=50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_revoke_logs_case_id', 'revoke_logs', ['case_id'], unique=False)
    op.create_index('ix_revoke_logs_revoked_at', 'revoke_logs', ['revoked_at'], unique=False)
    op.create_index('ix_revoke_logs_user_id', 'revoke_logs', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop revoke_logs table."""
    op.drop_index('ix_revoke_logs_user_id', table_name='revoke_logs')
    op.drop_index('ix_revoke_logs_revoked_at', table_name='revoke_logs')
    op.drop_index('ix_revoke_logs_case_id', table_name='revoke_logs')
    op.drop_table('revoke_logs')
