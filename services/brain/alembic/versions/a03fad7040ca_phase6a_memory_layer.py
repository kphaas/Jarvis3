"""phase6a_memory_layer

Revision ID: a03fad7040ca
Revises:
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'a03fad7040ca'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS vector'))

    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id VARCHAR(32) PRIMARY KEY,
            profile_data JSONB NOT NULL DEFAULT '{}',
            memory_token_budget INTEGER NOT NULL DEFAULT 800,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    '''))

    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS user_profile_history (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id VARCHAR(32) NOT NULL REFERENCES user_profile(user_id),
            previous_data JSONB NOT NULL,
            changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            changed_by VARCHAR(32) NOT NULL DEFAULT 'system'
        )
    '''))

    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS conversation_memory (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id VARCHAR(32) NOT NULL REFERENCES user_profile(user_id),
            summary TEXT,
            structured_data JSONB,
            embedding vector(384),
            embedding_model VARCHAR(64) NOT NULL DEFAULT 'all-MiniLM-L6-v2',
            memory_type VARCHAR(16) NOT NULL DEFAULT 'episodic',
            access_count INTEGER NOT NULL DEFAULT 0,
            promoted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_accessed TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ
        )
    '''))

    op.execute(sa.text('''
        CREATE INDEX IF NOT EXISTS idx_memory_user_id
        ON conversation_memory(user_id)
    '''))

    op.execute(sa.text('''
        CREATE INDEX IF NOT EXISTS idx_memory_expires_at
        ON conversation_memory(expires_at)
        WHERE expires_at IS NOT NULL
    '''))

    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS memory_review_queue (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            memory_id UUID NOT NULL REFERENCES conversation_memory(id) ON DELETE CASCADE,
            user_id VARCHAR(32) NOT NULL,
            llm_summary TEXT,
            recommendation VARCHAR(16) NOT NULL DEFAULT 'purge',
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reviewed_at TIMESTAMPTZ
        )
    '''))

    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS memory_jobs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            job_type VARCHAR(32) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ
        )
    '''))

    op.execute(sa.text('''
        CREATE INDEX IF NOT EXISTS idx_memory_jobs_status
        ON memory_jobs(status)
        WHERE status IN ('pending', 'failed')
    '''))

    op.execute(sa.text('''
        CREATE TABLE IF NOT EXISTS memory_audit_log (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id VARCHAR(32) NOT NULL,
            memory_id UUID,
            action VARCHAR(32) NOT NULL,
            triggered_by VARCHAR(32) NOT NULL DEFAULT 'system',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    '''))

    pass  # seed data inserted directly via psql

def downgrade():
    op.execute(sa.text('DROP TABLE IF EXISTS memory_audit_log CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS memory_jobs CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS memory_review_queue CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS conversation_memory CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS user_profile_history CASCADE'))
    op.execute(sa.text('DROP TABLE IF EXISTS user_profile CASCADE'))
