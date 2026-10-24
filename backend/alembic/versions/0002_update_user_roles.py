"""Update user role constraint to include ADMIN, OPERATIONS_MANAGER, ANALYST, VIEWER

Revision ID: 0002_update_user_roles
Revises: 0001_initial_schema
Create Date: 2026-10-12 10:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_update_user_roles'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # For PostgreSQL / SQLite: replace check constraint on users.role
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('ck_user_role', type_='check')
        batch_op.create_check_constraint(
            'ck_user_role',
            "role IN ('ADMIN', 'OPERATIONS_MANAGER', 'ANALYST', 'VIEWER', 'admin', 'operator', 'analyst', 'manager')",
        )


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('ck_user_role', type_='check')
        batch_op.create_check_constraint(
            'ck_user_role',
            "role IN ('admin', 'operator', 'analyst', 'manager')",
        )
