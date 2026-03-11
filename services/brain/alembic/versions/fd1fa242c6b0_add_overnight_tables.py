"""add_overnight_tables

Revision ID: fd1fa242c6b0
Revises: a03fad7040ca
Create Date: 2026-03-11 10:22:55.293684

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'fd1fa242c6b0'
down_revision: Union[str, Sequence[str], None] = 'a03fad7040ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'overnight_instructions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('replace_previous', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'overnight_docs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('doc_type', sa.Text(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        'overnight_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_date', sa.Date(), nullable=False),
        sa.Column('task_name', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table('overnight_runs')
    op.drop_table('overnight_docs')
    op.drop_table('overnight_instructions')
