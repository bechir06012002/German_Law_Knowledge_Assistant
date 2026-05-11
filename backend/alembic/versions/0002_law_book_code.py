"""Add `book_code` for statutes.

Statutes and decisions share `source_documents`, but a statute's identity is
(book, §) — `KSchG` + `§ 1`. Overloading `court_name` with the book code would work and would
also be a trap: `court_name` is rendered directly in citation chips, so a statute would show
up in the UI as if a court called "KSchG" had decided something.

Revision ID: 0002
Create Date: 2026-08-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_documents", sa.Column("book_code", sa.String(64)))
    # Statute lookup is always (book, section) — the join from a decision's norm_refs.
    op.create_index(
        "ix_source_documents_book_section", "source_documents", ["book_code", "file_number"]
    )


def downgrade() -> None:
    op.drop_index("ix_source_documents_book_section", table_name="source_documents")
    op.drop_column("source_documents", "book_code")
