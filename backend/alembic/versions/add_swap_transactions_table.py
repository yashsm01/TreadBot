"""add_swap_transactions_table

Revision ID: add_swap_transactions
Revises: update_trade_table
Create Date: 2023-11-16 10:40:33.380224

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_swap_transactions'
down_revision = 'update_trade_table'
branch_labels = None
depends_on = None


def upgrade():
    # Create the swap_transactions table
    op.create_table('swap_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.String(), nullable=False),
        sa.Column('from_symbol', sa.String(), nullable=False),
        sa.Column('to_symbol', sa.String(), nullable=False),
        sa.Column('from_amount', sa.Float(), nullable=False),
        sa.Column('to_amount', sa.Float(), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.Column('fee_percentage', sa.Float(), nullable=False),
        sa.Column('fee_amount', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id')
    )


def downgrade():
    # Drop the swap_transactions table
    op.drop_table('swap_transactions')
