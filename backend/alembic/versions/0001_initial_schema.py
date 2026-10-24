"""Initial schema migration: User, Supplier, Product, Warehouse, Inventory, Order, OrderItem, AuditLog

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-12 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='operator', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'operator', 'analyst', 'manager')", name='ck_user_role'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. suppliers
    op.create_table(
        'suppliers',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('lead_time_days', sa.Integer(), server_default='7', nullable=False),
        sa.Column('reliability_score', sa.Numeric(precision=3, scale=2), server_default='0.95', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('lead_time_days >= 0', name='ck_supplier_lead_time_days'),
        sa.CheckConstraint('reliability_score >= 0.00 AND reliability_score <= 1.00', name='ck_supplier_reliability_score'),
    )
    op.create_index(op.f('ix_suppliers_code'), 'suppliers', ['code'], unique=True)
    op.create_index(op.f('ix_suppliers_name'), 'suppliers', ['name'], unique=False)

    # 3. products
    op.create_table(
        'products',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('sku', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('reorder_point', sa.Integer(), server_default='10', nullable=False),
        sa.Column('safety_stock', sa.Integer(), server_default='5', nullable=False),
        sa.Column('supplier_id', GUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='SET NULL'),
        sa.CheckConstraint('unit_price >= 0', name='ck_product_unit_price'),
        sa.CheckConstraint('unit_cost >= 0', name='ck_product_unit_cost'),
        sa.CheckConstraint('reorder_point >= 0', name='ck_product_reorder_point'),
        sa.CheckConstraint('safety_stock >= 0', name='ck_product_safety_stock'),
    )
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=True)
    op.create_index(op.f('ix_products_name'), 'products', ['name'], unique=False)
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)
    op.create_index(op.f('ix_products_supplier_id'), 'products', ['supplier_id'], unique=False)

    # 4. warehouses
    op.create_table(
        'warehouses',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('location', sa.String(length=255), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('capacity > 0', name='ck_warehouse_capacity'),
    )
    op.create_index(op.f('ix_warehouses_code'), 'warehouses', ['code'], unique=True)

    # 5. inventories
    op.create_table(
        'inventories',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('product_id', GUID(), nullable=False),
        sa.Column('warehouse_id', GUID(), nullable=False),
        sa.Column('quantity_on_hand', sa.Integer(), server_default='0', nullable=False),
        sa.Column('quantity_reserved', sa.Integer(), server_default='0', nullable=False),
        sa.Column('reorder_quantity', sa.Integer(), server_default='50', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('product_id', 'warehouse_id', name='uq_inventory_product_warehouse'),
        sa.CheckConstraint('quantity_on_hand >= 0', name='ck_inventory_qty_on_hand'),
        sa.CheckConstraint('quantity_reserved >= 0', name='ck_inventory_qty_reserved'),
        sa.CheckConstraint('quantity_reserved <= quantity_on_hand', name='ck_inventory_reserved_lte_on_hand'),
        sa.CheckConstraint('reorder_quantity >= 0', name='ck_inventory_reorder_qty'),
    )
    op.create_index(op.f('ix_inventories_product_id'), 'inventories', ['product_id'], unique=False)
    op.create_index(op.f('ix_inventories_warehouse_id'), 'inventories', ['warehouse_id'], unique=False)

    # 6. orders
    op.create_table(
        'orders',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('order_number', sa.String(length=100), nullable=False),
        sa.Column('customer_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='PENDING', nullable=False),
        sa.Column('priority', sa.String(length=50), server_default='NORMAL', nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False),
        sa.Column('warehouse_id', GUID(), nullable=True),
        sa.Column('created_by_user_id', GUID(), nullable=True),
        sa.Column('expected_delivery_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint("status IN ('PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED')", name='ck_order_status'),
        sa.CheckConstraint("priority IN ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')", name='ck_order_priority'),
        sa.CheckConstraint('total_amount >= 0', name='ck_order_total_amount'),
    )
    op.create_index(op.f('ix_orders_order_number'), 'orders', ['order_number'], unique=True)
    op.create_index(op.f('ix_orders_warehouse_id'), 'orders', ['warehouse_id'], unique=False)
    op.create_index(op.f('ix_orders_created_by_user_id'), 'orders', ['created_by_user_id'], unique=False)

    # 7. order_items
    op.create_table(
        'order_items',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('order_id', GUID(), nullable=False),
        sa.Column('product_id', GUID(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('order_id', 'product_id', name='uq_order_item_order_product'),
        sa.CheckConstraint('quantity > 0', name='ck_order_item_quantity'),
        sa.CheckConstraint('unit_price >= 0', name='ck_order_item_unit_price'),
        sa.CheckConstraint('subtotal >= 0', name='ck_order_item_subtotal'),
    )
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)
    op.create_index(op.f('ix_order_items_product_id'), 'order_items', ['product_id'], unique=False)

    # 8. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('actor_id', GUID(), nullable=True),
        sa.Column('actor_name', sa.String(length=255), server_default='system', nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index(op.f('ix_audit_logs_entity_type'), 'audit_logs', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_id'), 'audit_logs', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('inventories')
    op.drop_table('warehouses')
    op.drop_table('products')
    op.drop_table('suppliers')
    op.drop_table('users')
