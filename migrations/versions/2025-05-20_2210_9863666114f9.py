"""Add new table measurement info

Revision ID: 9863666114f9
Revises: 980ddeeebd9c
Create Date: 2025-05-20 22:10:44.612723

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9863666114f9'
down_revision = '980ddeeebd9c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'measurement_files',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('google_drive_file_id', sa.String, nullable=False),
        sa.Column('measurement_id', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['measurement_id'], ['measurement_info.id'], ),
    )


def downgrade() -> None:
    op.drop_table('measurement_files')
