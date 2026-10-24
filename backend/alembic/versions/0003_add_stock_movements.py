"""Add stock_movements table for controlled inventory movements and auditability

Revision ID: 0003_add_stock_movements
Revises: 0002_update_user_roles
Create Date: 2026-10-12 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

revision: str = '0003_add_stock_movements'
down_revision: Union[str, None] = '0002_update_user_roles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stock_movements',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('product_id', GUID(), nullable=False),
        sa.Column('warehouse_id', GUID(), nullable=False),
        sa.Column('inventory_id', GUID(), nullable=True),
        sa.Column('movement_type', sa.String(length=50), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(length=255), server_default='', nullable=False),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('actor_id', GUID(), nullable=True),
        sa.Column('actor_name', sa.String(length=255), server_default='system', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['inventory_id'], ['inventories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint(
            "movement_type IN ('RECEIPT', 'ISSUE', 'RESERVATION', 'RELEASE', 'ADJUSTMENT')",
            name='ck_stock_movement_type',
        ),
        sa.CheckConstraint('quantity > 0', name='ck_stock_movement_quantity'),
    )
    op.create_index(op.f('ix_stock_movements_product_id'), 'stock_movements', ['product_id'], unique=False)
    op.create_index(op.f('ix_stock_movements_warehouse_id'), 'stock_movements', ['warehouse_id'], unique=False)
    op.create_index(op.f('ix_stock_movements_inventory_id'), 'stock_movements', ['inventory_id'], unique=False)
    op.create_index(op.f('ix_stock_movements_movement_type'), 'stock_movements', ['movement_type'], unique=False)
    op.create_index(op.f('ix_stock_movements_idempotency_key'), 'stock_movements', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_stock_movements_created_at'), 'stock_movements', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('stock_movements')
