from app.models import Download, Setting


def test_model_tables_named():
    assert Download.__tablename__ == "downloads"
    assert Setting.__tablename__ == "settings"


def test_migrations_create_expected_tables(db_inspector):
    table_names = set(db_inspector.get_table_names())
    assert "downloads" in table_names
    assert "settings" in table_names
