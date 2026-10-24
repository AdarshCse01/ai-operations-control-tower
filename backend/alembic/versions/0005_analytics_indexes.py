"""Add performance indexes for analytics queries on orders table

Revision ID: 0005_analytics_indexes
Revises: 0004_add_recommendations
Create Date: 2026-10-14 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0005_analytics_indexes'
down_revision: Union[str, None] = '0004_add_recommendations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_index(op.f('ix_orders_created_at'), 'orders', ['created_at'], unique=False)
    op.create_index(op.f('ix_orders_status_created_at'), 'orders', ['status', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_orders_status_created_at'), table_name='orders')
    op.drop_index(op.f('ix_orders_created_at'), table_name='orders')
    op.drop_index(op.f('ix_orders_status'), table_name='orders')
