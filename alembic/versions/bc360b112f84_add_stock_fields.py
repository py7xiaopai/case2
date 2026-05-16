"""add_stock_fields

Note: columns already included in c50e9b52a39b init migration, this is a no-op.

Revision ID: bc360b112f84
Revises: c50e9b52a39b
Create Date: 2026-05-16 15:44:44.341728

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'bc360b112f84'
down_revision: Union[str, None] = 'c50e9b52a39b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
