"""add zone branch fields

Revision ID: 2e3584f65ec2
Revises: eb4343d3c005
Create Date: 2026-06-29 01:50:15.627216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = '2e3584f65ec2'
down_revision: Union[str, Sequence[str], None] = 'eb4343d3c005'
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
    # Users
    if not column_exists('users', 'zone_id'):
        op.add_column('users', sa.Column('zone_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'users', 'zones', ['zone_id'], ['id'])
    if not column_exists('users', 'branch_id'):
        op.add_column('users', sa.Column('branch_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'users', 'branches', ['branch_id'], ['id'])
    
    # Candidates
    if not column_exists('candidates', 'zone_id'):
        op.add_column('candidates', sa.Column('zone_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'candidates', 'zones', ['zone_id'], ['id'])
    if not column_exists('candidates', 'branch_id'):
        op.add_column('candidates', sa.Column('branch_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'candidates', 'branches', ['branch_id'], ['id'])
    if not column_exists('candidates', 'customer_id'):
        op.add_column('candidates', sa.Column('customer_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'candidates', 'customers', ['customer_id'], ['id'])

    # Cases
    if not column_exists('cases', 'zone_id'):
        op.add_column('cases', sa.Column('zone_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'cases', 'zones', ['zone_id'], ['id'], ondelete='CASCADE')
    if not column_exists('cases', 'branch_id'):
        op.add_column('cases', sa.Column('branch_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'cases', 'branches', ['branch_id'], ['id'], ondelete='CASCADE')

    # Customers
    if not column_exists('customers', 'zone_id'):
        op.add_column('customers', sa.Column('zone_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'customers', 'zones', ['zone_id'], ['id'])
    if not column_exists('customers', 'company_name'):
        op.add_column('customers', sa.Column('company_name', sa.String(length=255), nullable=True))
    if not column_exists('customers', 'company_code'):
        op.add_column('customers', sa.Column('company_code', sa.String(length=50), nullable=True))
    if not column_exists('customers', 'head_office'):
        op.add_column('customers', sa.Column('head_office', sa.String(length=255), nullable=True))
    if not column_exists('customers', 'industry'):
        op.add_column('customers', sa.Column('industry', sa.String(length=100), nullable=True))

    # Batches
    if not column_exists('batches', 'zone_id'):
        op.add_column('batches', sa.Column('zone_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'batches', 'zones', ['zone_id'], ['id'])
    if not column_exists('batches', 'branch_id'):
        op.add_column('batches', sa.Column('branch_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(None, 'batches', 'branches', ['branch_id'], ['id'])

def downgrade() -> None:
    pass
