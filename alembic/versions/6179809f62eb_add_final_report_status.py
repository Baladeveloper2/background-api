"""Add final_report_status

Revision ID: 6179809f62eb
Revises: 8ff9b0ac27cc
Create Date: 2026-05-11 20:54:54.313212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '6179809f62eb'
down_revision: Union[str, Sequence[str], None] = '8ff9b0ac27cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('cases', sa.Column('final_report_status', sa.String(length=50), nullable=True))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('cases', 'final_report_status')
