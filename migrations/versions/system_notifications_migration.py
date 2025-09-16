"""Add system notification tables

Revision ID: system_notifications_001
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'system_notifications_001'
down_revision = '0bdb241e8aa5'
branch_labels = None
depends_on = None


def upgrade():
    # Create system_notifications table
    op.create_table('system_notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('target_type', sa.String(length=20), nullable=False),
    sa.Column('target_departments', sa.Text(), nullable=True),
    sa.Column('target_roles', sa.Text(), nullable=True),
    sa.Column('target_users', sa.Text(), nullable=True),
    sa.Column('email_enabled', sa.Boolean(), nullable=True),
    sa.Column('popup_enabled', sa.Boolean(), nullable=True),
    sa.Column('include_parents', sa.Boolean(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('send_immediately', sa.Boolean(), nullable=True),
    sa.Column('scheduled_for', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=True),
    sa.Column('email_sent_count', sa.Integer(), nullable=True),
    sa.Column('popup_delivered_count', sa.Integer(), nullable=True),
    sa.Column('delivery_status', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create user_system_notifications table
    op.create_table('user_system_notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('system_notification_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('delivered_at', sa.DateTime(), nullable=True),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('email_sent', sa.Boolean(), nullable=True),
    sa.Column('popup_shown', sa.Boolean(), nullable=True),
    sa.Column('popup_shown_at', sa.DateTime(), nullable=True),
    sa.Column('is_read', sa.Boolean(), nullable=True),
    sa.Column('is_dismissed', sa.Boolean(), nullable=True),
    sa.Column('dismissed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['system_notification_id'], ['system_notifications.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('system_notification_id', 'user_id', name='unique_system_notification_user')
    )
    
    # Set default values (PostgreSQL boolean syntax)
    op.execute("UPDATE system_notifications SET type = 'general' WHERE type IS NULL")
    op.execute("UPDATE system_notifications SET priority = 'normal' WHERE priority IS NULL")
    op.execute("UPDATE system_notifications SET target_type = 'all' WHERE target_type IS NULL")
    op.execute("UPDATE system_notifications SET email_enabled = TRUE WHERE email_enabled IS NULL")
    op.execute("UPDATE system_notifications SET popup_enabled = FALSE WHERE popup_enabled IS NULL")
    op.execute("UPDATE system_notifications SET include_parents = FALSE WHERE include_parents IS NULL")
    op.execute("UPDATE system_notifications SET is_active = TRUE WHERE is_active IS NULL")
    op.execute("UPDATE system_notifications SET send_immediately = TRUE WHERE send_immediately IS NULL")
    op.execute("UPDATE system_notifications SET email_sent_count = 0 WHERE email_sent_count IS NULL")
    op.execute("UPDATE system_notifications SET popup_delivered_count = 0 WHERE popup_delivered_count IS NULL")
    
    op.execute("UPDATE user_system_notifications SET email_sent = FALSE WHERE email_sent IS NULL")
    op.execute("UPDATE user_system_notifications SET popup_shown = FALSE WHERE popup_shown IS NULL")
    op.execute("UPDATE user_system_notifications SET is_read = FALSE WHERE is_read IS NULL")
    op.execute("UPDATE user_system_notifications SET is_dismissed = FALSE WHERE is_dismissed IS NULL")


def downgrade():
    # Drop tables in reverse order
    op.drop_table('user_system_notifications')
    op.drop_table('system_notifications')