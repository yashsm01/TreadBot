"""create portfolio tables

Revision ID: create_portfolio_tables
Revises:
Create Date: 2024-05-03 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_portfolio_tables'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create portfolios table
    op.create_table(
        'portfolios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('quantity', sa.Float(), default=0),
        sa.Column('avg_buy_price', sa.Float(), nullable=False),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('total', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='SET NULL')
    )

    # Create indexes
    op.create_index('ix_portfolios_user_id', 'portfolios', ['user_id'])
    op.create_index('ix_portfolios_symbol', 'portfolios', ['symbol'])
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('ix_transactions_symbol', 'transactions', ['symbol'])
    op.create_index('ix_transactions_portfolio_id', 'transactions', ['portfolio_id'])

def downgrade():
    # Drop indexes
    op.drop_index('ix_transactions_portfolio_id')
    op.drop_index('ix_transactions_symbol')
    op.drop_index('ix_transactions_user_id')
    op.drop_index('ix_portfolios_symbol')
    op.drop_index('ix_portfolios_user_id')

    # Drop tables
    op.drop_table('transactions')
    op.drop_table('portfolios')
