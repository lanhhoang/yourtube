from pathlib import Path

from app.models import Download, Setting


def test_model_tables_named():
    assert Download.__tablename__ == "downloads"
    assert Setting.__tablename__ == "settings"


def test_migrations_create_expected_tables(db_inspector):
    table_names = set(db_inspector.get_table_names())
    assert "downloads" in table_names
    assert "settings" in table_names
    assert "push_subscriptions" in table_names


def test_downloads_has_quality_cap_column(db_inspector):
    assert "quality_cap" in {c["name"] for c in db_inspector.get_columns("downloads")}


def test_downloads_has_hdr_column(db_inspector):
    assert "hdr" in {c["name"] for c in db_inspector.get_columns("downloads")}


def test_migration_downgrade_and_upgrade(tmp_path, monkeypatch):
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    from alembic import command
    from app.config import settings

    url = f"sqlite:///{tmp_path / 'm.db'}"
    # alembic/env.py replaces sqlalchemy.url with settings.database_url
    monkeypatch.setattr(settings, "database_url", url)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

    def cols() -> set[str]:
        return {c["name"] for c in inspect(create_engine(url)).get_columns("downloads")}

    command.upgrade(cfg, "head")
    assert "hdr" in cols()
    command.downgrade(cfg, "20261115120000")
    assert "hdr" not in cols()
    assert "quality_cap" in cols()
    command.upgrade(cfg, "head")
    assert "hdr" in cols()
