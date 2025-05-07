"""update trade table

Revision ID: update_trade_table
Revises: create_portfolio_tables
Create Date: 2024-05-08 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'update_trade_table'
down_revision = 'create_portfolio_tables'
branch_labels = None
depends_on = None

def upgrade():
    # Add new columns
    op.add_column('trades', sa.Column('take_profit', sa.Float(), nullable=True))
    op.add_column('trades', sa.Column('stop_loss', sa.Float(), nullable=True))
    op.add_column('trades', sa.Column('order_type', sa.String(), server_default='STOP', nullable=False))
    op.add_column('trades', sa.Column('strategy', sa.String(), server_default='STRADDLE', nullable=False))

    # Add timestamp columns
    op.add_column('trades', sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
    op.add_column('trades', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('trades', sa.Column('entered_at', sa.DateTime(), nullable=True))
    op.add_column('trades', sa.Column('closed_at', sa.DateTime(), nullable=True))

    # Add PnL columns
    op.add_column('trades', sa.Column('realized_pnl', sa.Float(), nullable=True))
    op.add_column('trades', sa.Column('unrealized_pnl', sa.Float(), nullable=True))

    # Drop old columns
    op.drop_column('trades', 'entry_time')
    op.drop_column('trades', 'exit_time')

    # Update status column to allow new states
    op.execute("ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_status_check")
    op.create_check_constraint(
        "trades_status_check",
        "trades",
        "status IN ('PENDING', 'OPEN', 'CLOSED', 'CANCELLED')"
    )

    # Make position_id nullable
    op.alter_column('trades', 'position_id',
                    existing_type=sa.Integer(),
                    nullable=True)

def downgrade():
    # Remove new columns
    op.drop_column('trades', 'take_profit')
    op.drop_column('trades', 'stop_loss')
    op.drop_column('trades', 'order_type')
    op.drop_column('trades', 'strategy')
    op.drop_column('trades', 'created_at')
    op.drop_column('trades', 'updated_at')
    op.drop_column('trades', 'entered_at')
    op.drop_column('trades', 'closed_at')
    op.drop_column('trades', 'realized_pnl')
    op.drop_column('trades', 'unrealized_pnl')

    # Add back old columns
    op.add_column('trades', sa.Column('entry_time', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
    op.add_column('trades', sa.Column('exit_time', sa.DateTime(), nullable=True))

    # Revert status constraint
    op.execute("ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_status_check")
    op.create_check_constraint(
        "trades_status_check",
        "trades",
        "status IN ('OPEN', 'CLOSED')"
    )

    # Make position_id non-nullable again
    op.alter_column('trades', 'position_id',
                    existing_type=sa.Integer(),
                    nullable=False)
