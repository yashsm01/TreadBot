"""Add realized_profit fields for P/L tracking

Revision ID: a1b2c3d4e5f6
Revises: 8754907c019f
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8754907c019f'
branch_labels = None
depends_on = None

def upgrade():
    # Add realized_profit column to portfolios table
    op.add_column('portfolios', sa.Column('realized_profit', sa.Float(), nullable=False, server_default='0.0'))

    # Add realized_profit column to swap_transactions table
    op.add_column('swap_transactions', sa.Column('realized_profit', sa.Float(), nullable=False, server_default='0.0'))

    # Add missing columns to swap_transactions if they don't exist
    try:
        op.add_column('swap_transactions', sa.Column('position_id', sa.Integer(), nullable=True))
    except Exception:
        pass  # Column might already exist

    try:
        op.add_column('swap_transactions', sa.Column('to_stable', sa.Boolean(), nullable=False, server_default='false'))
    except Exception:
        pass  # Column might already exist

def downgrade():
    # Remove realized_profit column from swap_transactions table
    op.drop_column('swap_transactions', 'realized_profit')

    # Remove realized_profit column from portfolios table
    op.drop_column('portfolios', 'realized_profit')

    # Note: Not removing position_id and to_stable columns in downgrade
    # as they might be needed by other parts of the system
