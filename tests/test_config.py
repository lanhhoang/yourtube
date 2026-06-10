from app.config import Settings, settings


def test_settings_defaults():
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000


def test_database_url_defaults_to_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("YT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("YT_DATABASE_URL", raising=False)

    configured = Settings()

    assert configured.data_dir == tmp_path
    assert configured.database_url == f"sqlite:///{tmp_path / 'yourtube.db'}"
