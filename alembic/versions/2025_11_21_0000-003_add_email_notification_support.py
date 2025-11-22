"""Add email notification support with user preferences and delivery tracking

Revision ID: 003_email_notifications
Revises: 2025_11_20_2259-a085810eaf1d
Create Date: 2025-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_email_notifications'
down_revision: Union[str, None] = '2025_11_20_2259-a085810eaf1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new fields to user_preferences table
    op.add_column('user_preferences', sa.Column('email', sa.String(length=255), nullable=True, comment="User's email address for notifications"))
    op.add_column('user_preferences', sa.Column('enable_notifications', sa.Boolean(), nullable=False, server_default='true', comment='Master switch for all email notifications'))
    op.add_column('user_preferences', sa.Column('enable_daily_digest', sa.Boolean(), nullable=False, server_default='true', comment='Receive daily digest emails with top deals'))
    op.add_column('user_preferences', sa.Column('enable_instant_alerts', sa.Boolean(), nullable=False, server_default='true', comment='Receive instant alerts for exceptional deals'))
    op.add_column('user_preferences', sa.Column('enable_parent_escape_digest', sa.Boolean(), nullable=False, server_default='true', comment='Receive weekly parent escape recommendations'))
    op.add_column('user_preferences', sa.Column('unsubscribe_token', sa.String(length=64), nullable=True, comment='Unique token for unsubscribe links'))

    # Create indexes for user_preferences
    op.create_index(op.f('ix_user_preferences_email'), 'user_preferences', ['email'], unique=False)
    op.create_index(op.f('ix_user_preferences_unsubscribe_token'), 'user_preferences', ['unsubscribe_token'], unique=True)

    # Create email_delivery_logs table
    op.create_table(
        'email_delivery_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=False, comment="Recipient's email address"),
        sa.Column('subject', sa.String(length=255), nullable=False, comment='Email subject line'),
        sa.Column('email_type', sa.String(length=50), nullable=False, comment="Type: 'daily_digest', 'instant_alert', 'parent_escape_digest'"),
        sa.Column('user_preference_id', sa.Integer(), nullable=True, comment='User preference that triggered the email'),
        sa.Column('trip_package_id', sa.Integer(), nullable=True, comment='Trip package for instant alerts (if applicable)'),
        sa.Column('sent_successfully', sa.Boolean(), nullable=False, server_default='false', comment='Whether email was sent successfully'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message if delivery failed'),
        sa.Column('num_deals_included', sa.Integer(), nullable=True, comment='Number of deals included in the email (for digests)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['trip_package_id'], ['trip_packages.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_preference_id'], ['user_preferences.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for email_delivery_logs
    op.create_index(op.f('ix_email_delivery_logs_email_type'), 'email_delivery_logs', ['email_type'], unique=False)
    op.create_index(op.f('ix_email_delivery_logs_recipient_email'), 'email_delivery_logs', ['recipient_email'], unique=False)
    op.create_index(op.f('ix_email_delivery_logs_sent_successfully'), 'email_delivery_logs', ['sent_successfully'], unique=False)
    op.create_index(op.f('ix_email_delivery_logs_trip_package_id'), 'email_delivery_logs', ['trip_package_id'], unique=False)
    op.create_index(op.f('ix_email_delivery_logs_user_preference_id'), 'email_delivery_logs', ['user_preference_id'], unique=False)


def downgrade() -> None:
    # Drop email_delivery_logs table and indexes
    op.drop_index(op.f('ix_email_delivery_logs_user_preference_id'), table_name='email_delivery_logs')
    op.drop_index(op.f('ix_email_delivery_logs_trip_package_id'), table_name='email_delivery_logs')
    op.drop_index(op.f('ix_email_delivery_logs_sent_successfully'), table_name='email_delivery_logs')
    op.drop_index(op.f('ix_email_delivery_logs_recipient_email'), table_name='email_delivery_logs')
    op.drop_index(op.f('ix_email_delivery_logs_email_type'), table_name='email_delivery_logs')
    op.drop_table('email_delivery_logs')

    # Drop indexes and columns from user_preferences
    op.drop_index(op.f('ix_user_preferences_unsubscribe_token'), table_name='user_preferences')
    op.drop_index(op.f('ix_user_preferences_email'), table_name='user_preferences')
    op.drop_column('user_preferences', 'unsubscribe_token')
    op.drop_column('user_preferences', 'enable_parent_escape_digest')
    op.drop_column('user_preferences', 'enable_instant_alerts')
    op.drop_column('user_preferences', 'enable_daily_digest')
    op.drop_column('user_preferences', 'enable_notifications')
    op.drop_column('user_preferences', 'email')
