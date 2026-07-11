import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
)


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


def test_checksum_migration_allows_duplicate_values_and_is_reversible(
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
        connection.execute(
            documents.insert(),
            [
                {"id": 1, "checksum": "a" * 64},
                {"id": 2, "checksum": "a" * 64},
            ],
        )
        checksum_index = next(
            item
            for item in inspect(connection).get_indexes("documents")
            if item["name"] == "ix_documents_checksum"
        )
        assert checksum_index["unique"] == 0

        connection.execute(documents.delete().where(documents.c.id == 2))
        migration.downgrade()
        checksum_index = next(
            item
            for item in inspect(connection).get_indexes("documents")
            if item["name"] == "ix_documents_checksum"
        )
        assert checksum_index["unique"] == 1
    engine.dispose()
