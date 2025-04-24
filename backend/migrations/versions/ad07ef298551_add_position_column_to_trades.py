"""add position column to trades

Revision ID: ad07ef298551
Revises: 52ba6661cd87
Create Date: 2025-04-24 15:15:23.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ad07ef298551'
down_revision = '52ba6661cd87'
branch_labels = None
depends_on = None

def upgrade():
    # Create PositionType enum if it doesn't exist
    position_type = postgresql.ENUM('LONG', 'SHORT', name='positiontype')
    position_type.create(op.get_bind(), checkfirst=True)

    # Add position column with default value
    op.add_column('trades', sa.Column('position',
        sa.Enum('LONG', 'SHORT', name='positiontype'),
        nullable=False,
        server_default='LONG'
    ))

def downgrade():
    # Remove position column
    op.drop_column('trades', 'position')

    # Drop the enum type
    position_type = postgresql.ENUM('LONG', 'SHORT', name='positiontype')
    position_type.drop(op.get_bind())
