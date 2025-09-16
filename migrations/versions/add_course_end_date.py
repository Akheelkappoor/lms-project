"""Add course end date and batch fields to students

Revision ID: add_course_end_date
Revises: 3f7a3eafc2ba
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_course_end_date'
down_revision = '3f7a3eafc2ba'
branch_labels = None
depends_on = None

def upgrade():
    # Add course end date and batch identifier to students table
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('course_end_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('batch_identifier', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('course_duration_months', sa.Integer(), nullable=True))

def downgrade():
    # Remove the added columns
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('course_duration_months')
        batch_op.drop_column('batch_identifier')
        batch_op.drop_column('course_end_date')