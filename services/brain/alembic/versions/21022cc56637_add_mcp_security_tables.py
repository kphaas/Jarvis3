"""add_mcp_security_tables

Revision ID: 21022cc56637
Revises: fd1fa242c6b0
Create Date: 2026-03-13 15:49:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '21022cc56637'
down_revision = 'fd1fa242c6b0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'mcp_registry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('server_name', sa.Text(), nullable=False),
        sa.Column('github_url', sa.Text(), nullable=True),
        sa.Column('trust_level', sa.Text(), nullable=False),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('installed_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('approved_by', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='active'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('server_name')
    )

    op.create_table(
        'mcp_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('server_id', sa.Integer(), nullable=False),
        sa.Column('permission_type', sa.Text(), nullable=False),
        sa.Column('resource', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.Text(), nullable=False),
        sa.Column('approved_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['server_id'], ['mcp_registry.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'mcp_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('server_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('resource', sa.Text(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['server_id'], ['mcp_registry.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('mcp_audit_log')
    op.drop_table('mcp_permissions')
    op.drop_table('mcp_registry')
