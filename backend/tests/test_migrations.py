import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import (
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.exc import IntegrityError


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "0002_allow_duplicate_document_checksums.py"
)


def load_checksum_migration() -> ModuleType:
    assert MIGRATION_PATH.exists(), "checksum index migration is missing"
    spec = importlib.util.spec_from_file_location("checksum_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checksum_migration_allows_seed_upload_match_but_rejects_two_uploads(
    monkeypatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    documents = Table(
        "documents",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("checksum", String(64), nullable=False),
    )
    Index("ix_documents_checksum", documents.c.checksum, unique=True)
    metadata.create_all(engine)

    migration = load_checksum_migration()
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)
        migration.upgrade()
        assert "is_seed" in {
            column["name"] for column in inspect(connection).get_columns("documents")
        }
        connection.execute(
            text(
                "INSERT INTO documents (id, checksum, is_seed) "
                "VALUES (1, :checksum, true), (2, :checksum, false)"
            ),
            {"checksum": "a" * 64},
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO documents (id, checksum, is_seed) "
                    "VALUES (3, :checksum, false)"
                ),
                {"checksum": "a" * 64},
            )

        upload_checksum_index = next(
            item
            for item in inspect(connection).get_indexes("documents")
            if item["name"] == "uq_documents_upload_checksum"
        )
        assert upload_checksum_index["unique"] == 1

        connection.execute(text("DELETE FROM documents WHERE id = 1"))
        migration.downgrade()
        assert "is_seed" not in {
            column["name"] for column in inspect(connection).get_columns("documents")
        }
        checksum_index = next(
            item
            for item in inspect(connection).get_indexes("documents")
            if item["name"] == "ix_documents_checksum"
        )
        assert checksum_index["unique"] == 1

    engine.dispose()


def test_checksum_migration_downgrade_preflights_duplicates(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    documents = Table(
        "documents",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("checksum", String(64), nullable=False),
    )
    Index("ix_documents_checksum", documents.c.checksum, unique=True)
    metadata.create_all(engine)

    migration = load_checksum_migration()
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)
        migration.upgrade()
        connection.execute(
            text(
                "INSERT INTO documents (id, checksum, is_seed) "
                "VALUES (1, :checksum, true), (2, :checksum, false)"
            ),
            {"checksum": "b" * 64},
        )
        with pytest.raises(RuntimeError, match="duplicate document checksums"):
            migration.downgrade()

    engine.dispose()
