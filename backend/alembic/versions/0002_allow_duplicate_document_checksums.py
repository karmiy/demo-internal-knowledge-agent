"""Allow managed seed documents to share uploaded document checksums.

Revision ID: 0002_nonunique_checksums
Revises: 0001_initial
Create Date: 2026-07-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_nonunique_checksums"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.create_index(
        "ix_documents_checksum", "documents", ["checksum"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.create_index(
        "ix_documents_checksum", "documents", ["checksum"], unique=True
    )
