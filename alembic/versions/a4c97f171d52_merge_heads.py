"""merge heads

Revision ID: a4c97f171d52
Revises: 6179809f62eb, a1b2c3d4e5f6
Create Date: 2026-06-24 19:24:36.313601

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4c97f171d52'
down_revision: Union[str, Sequence[str], None] = ('6179809f62eb', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
