"""fix trades table

Revision ID: fix_trades_table_002
Revises: create_portfolio_tables
Create Date: 2024-05-08 02:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_trades_table_002'
down_revision = 'create_portfolio_tables'
branch_labels = None
depends_on = None

def upgrade():
    # Drop existing trades table and its dependencies
    op.execute('DROP TYPE IF EXISTS tradestatus CASCADE')
    op.execute('DROP TYPE IF EXISTS tradetype CASCADE')
    op.execute('DROP TYPE IF EXISTS positiontype CASCADE')
    op.drop_table('trades')

    # Create positions table first
    op.create_table(
        'positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('strategy', sa.String(), nullable=False),
        sa.Column('total_quantity', sa.Float(), server_default='0', nullable=False),
        sa.Column('average_entry_price', sa.Float(), nullable=True),
        sa.Column('realized_pnl', sa.Float(), server_default='0', nullable=False),
        sa.Column('unrealized_pnl', sa.Float(), server_default='0', nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('open_time', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('close_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED','IN_PROGRESS')", name='positions_status_check')
    )

    # Create indexes for positions
    op.create_index(op.f('ix_positions_symbol'), 'positions', ['symbol'], unique=False)
    op.create_index(op.f('ix_positions_strategy'), 'positions', ['strategy'], unique=False)
    op.create_index(op.f('ix_positions_status'), 'positions', ['status'], unique=False)

    # Create trades table
    op.create_table(
        'trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('order_type', sa.String(), server_default='STOP', nullable=False),
        sa.Column('strategy', sa.String(), server_default='STRADDLE', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('entered_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('pnl', sa.Float(), nullable=True),
        sa.Column('realized_pnl', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('position_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['position_id'], ['positions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name='trades_side_check'),
        sa.CheckConstraint("status IN ('PENDING', 'OPEN', 'CLOSED', 'CANCELLED')", name='trades_status_check'),
        sa.CheckConstraint("order_type IN ('MARKET', 'LIMIT', 'STOP')", name='trades_order_type_check')
    )

    # Create indexes for trades
    op.create_index(op.f('ix_trades_symbol'), 'trades', ['symbol'], unique=False)
    op.create_index(op.f('ix_trades_status'), 'trades', ['status'], unique=False)
    op.create_index(op.f('ix_trades_strategy'), 'trades', ['strategy'], unique=False)

def downgrade():
    # Drop trades table first (due to foreign key constraint)
    op.drop_table('trades')

    # Drop positions table
    op.drop_table('positions')

    # Recreate original trades table
    op.create_table(
        'trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('coin', sa.String(), nullable=True),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('profit_pct', sa.Float(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'CLOSED', name='tradestatus'), nullable=True),
        sa.Column('type', sa.Enum('MARKET', 'LIMIT', name='tradetype'), nullable=True),
        sa.Column('position', sa.Enum('LONG', 'SHORT', name='positiontype'), server_default='LONG', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Recreate original indexes
    op.create_index('ix_trades_id', 'trades', ['id'], unique=False)
    op.create_index('ix_trades_coin', 'trades', ['coin'], unique=False)
