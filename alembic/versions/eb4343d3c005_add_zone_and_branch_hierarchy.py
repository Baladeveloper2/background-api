"""Add Zone and Branch Hierarchy

Revision ID: eb4343d3c005
Revises: a4c97f171d52
Create Date: 2026-06-28 20:04:40

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb4343d3c005'
down_revision = 'a4c97f171d52'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create Zones table
    op.create_table('zones',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('zone_name', sa.String(length=255), nullable=False),
        sa.Column('zone_code', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_zones_zone_code'), 'zones', ['zone_code'], unique=True)
    op.create_index(op.f('ix_zones_zone_name'), 'zones', ['zone_name'], unique=True)

    # 2. Add columns to Customers table
    op.add_column('customers', sa.Column('zone_id', sa.String(length=36), nullable=True))
    op.add_column('customers', sa.Column('company_name', sa.String(length=255), nullable=True))
    op.add_column('customers', sa.Column('company_code', sa.String(length=50), nullable=True))
    op.add_column('customers', sa.Column('head_office', sa.String(length=255), nullable=True))
    op.add_column('customers', sa.Column('industry', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_customers_zone_id'), 'customers', ['zone_id'], unique=False)
    op.create_foreign_key(None, 'customers', 'zones', ['zone_id'], ['id'])

    # 3. Create Branches table
    op.create_table('branches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('branch_code', sa.String(length=50), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('contact_person', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_branches_branch_code'), 'branches', ['branch_code'], unique=True)

    # 4. Add columns to Users table
    op.add_column('users', sa.Column('zone_id', sa.String(length=36), nullable=True))
    op.add_column('users', sa.Column('branch_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_users_zone_id'), 'users', ['zone_id'], unique=False)
    op.create_index(op.f('ix_users_branch_id'), 'users', ['branch_id'], unique=False)
    op.create_foreign_key(None, 'users', 'zones', ['zone_id'], ['id'])
    op.create_foreign_key(None, 'users', 'branches', ['branch_id'], ['id'])

    # 5. Add columns to Candidates table
    op.add_column('candidates', sa.Column('zone_id', sa.String(length=36), nullable=True))
    op.add_column('candidates', sa.Column('customer_id', sa.String(length=36), nullable=True))
    op.add_column('candidates', sa.Column('branch_id', sa.String(length=36), nullable=True))
    op.add_column('candidates', sa.Column('created_by', sa.String(length=36), nullable=True))
    op.add_column('candidates', sa.Column('assigned_executive_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(None, 'candidates', 'zones', ['zone_id'], ['id'])
    op.create_foreign_key(None, 'candidates', 'customers', ['customer_id'], ['id'])
    op.create_foreign_key(None, 'candidates', 'branches', ['branch_id'], ['id'])
    op.create_foreign_key(None, 'candidates', 'users', ['created_by'], ['id'])
    op.create_foreign_key(None, 'candidates', 'users', ['assigned_executive_id'], ['id'])

    # 6. Add columns to Cases table
    op.add_column('cases', sa.Column('zone_id', sa.String(length=36), nullable=True))
    op.add_column('cases', sa.Column('branch_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(None, 'cases', 'zones', ['zone_id'], ['id'])
    op.create_foreign_key(None, 'cases', 'branches', ['branch_id'], ['id'])

    # 7. Add columns to Batches table
    op.add_column('batches', sa.Column('zone_id', sa.String(length=36), nullable=True))
    op.add_column('batches', sa.Column('branch_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(None, 'batches', 'zones', ['zone_id'], ['id'])
    op.create_foreign_key(None, 'batches', 'branches', ['branch_id'], ['id'])


def downgrade() -> None:
    pass
