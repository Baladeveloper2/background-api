"""add missing candidate fields

Revision ID: 727e4bc482ec
Revises: 2e3584f65ec2
Create Date: 2026-06-29 01:55:42.527311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '727e4bc482ec'
down_revision: Union[str, Sequence[str], None] = '2e3584f65ec2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def column_exists(table_name, column_name):
    bind = op.get_context().bind
    insp = Inspector.from_engine(bind)
    has_column = False
    for col in insp.get_columns(table_name):
        if col['name'] == column_name:
            has_column = True
    return has_column

def upgrade() -> None:
    if not column_exists('candidates', 'created_by'):
        op.add_column('candidates', sa.Column('created_by', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'candidates', 'users', ['created_by'], ['id'])
    
    if not column_exists('candidates', 'assigned_executive_id'):
        op.add_column('candidates', sa.Column('assigned_executive_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'candidates', 'users', ['assigned_executive_id'], ['id'])

def downgrade() -> None:
    pass
