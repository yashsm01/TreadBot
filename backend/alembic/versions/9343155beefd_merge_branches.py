"""merge_branches

Revision ID: 9343155beefd
Revises: add_swap_transactions, fix_trades_table_002
Create Date: 2025-05-17 13:22:57.952421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9343155beefd'
down_revision: Union[str, None] = ('add_swap_transactions', 'fix_trades_table_002')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
