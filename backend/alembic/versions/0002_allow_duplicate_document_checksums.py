"""Allow managed seed documents to share uploaded document checksums.

Revision ID: 0002_nonunique_checksums
Revises: 0001_initial
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_nonunique_checksums"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "is_seed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.create_index(
        "ix_documents_checksum", "documents", ["checksum"], unique=False
    )
    op.create_index(
        "uq_documents_upload_checksum",
        "documents",
        ["checksum"],
        unique=True,
        postgresql_where=sa.text("is_seed = false"),
        sqlite_where=sa.text("is_seed = 0"),
    )


def downgrade() -> None:
    duplicate = op.get_bind().execute(
        sa.text(
            "SELECT checksum FROM documents "
            "GROUP BY checksum HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot downgrade while duplicate document checksums exist; "
            "remove or reconcile duplicates before retrying."
        )

    op.drop_index("uq_documents_upload_checksum", table_name="documents")
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.create_index(
        "ix_documents_checksum", "documents", ["checksum"], unique=True
    )
    op.drop_column("documents", "is_seed")
