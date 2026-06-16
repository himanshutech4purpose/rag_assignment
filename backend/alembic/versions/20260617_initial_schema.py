"""initial schema

Revision ID: 20260617_initial_schema
Revises:
Create Date: 2026-06-17 01:14:58.658073

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260617_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            size_bytes INTEGER NOT NULL,
            minio_object VARCHAR(255) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL PRIMARY KEY,
            document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
            document_name VARCHAR(255) NOT NULL,
            page_number INTEGER,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(384),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            sources JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunks_embedding
            ON document_chunks USING hnsw (embedding vector_cosine_ops)
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)"
    )

    op.execute(
        """
        ALTER TABLE document_chunks
            ADD COLUMN IF NOT EXISTS search_vector tsvector
            GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_search_vector ON document_chunks USING GIN (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_search_vector")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_vector")
    op.execute("DROP INDEX IF EXISTS idx_messages_conversation_id")
    op.execute("DROP INDEX IF EXISTS idx_chunks_document_id")
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("DROP TABLE IF EXISTS document_chunks")
    op.execute("DROP TABLE IF EXISTS documents")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
    op.execute("DROP EXTENSION IF EXISTS vector")
