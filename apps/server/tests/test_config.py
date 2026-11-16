from pathlib import Path

from app.config import REPO_ROOT, Settings, resolve_repo_path, settings


def test_settings_defaults():
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000


def test_database_url_defaults_to_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("YT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("YT_DATABASE_URL", raising=False)

    configured = Settings()

    assert configured.data_dir == tmp_path
    assert configured.database_url == f"sqlite:///{tmp_path / 'yourtube.db'}"


def test_env_file_is_repo_root():
    assert Settings.model_config["env_file"] == REPO_ROOT / ".env"
    assert (REPO_ROOT / "apps" / "server" / "app" / "config.py").exists()


def test_relative_dirs_resolve_against_repo_root(monkeypatch):
    monkeypatch.setenv("YT_DATA_DIR", "./tmp/data")
    monkeypatch.setenv("YT_DOWNLOADS_DIR", "tmp/downloads")
    monkeypatch.setenv("YT_COOKIES_PATH", "cookies.txt")
    monkeypatch.delenv("YT_DATABASE_URL", raising=False)
    s = Settings()
    assert s.data_dir == REPO_ROOT / "tmp" / "data"
    assert s.downloads_dir == REPO_ROOT / "tmp" / "downloads"
    assert s.cookies_path == REPO_ROOT / "cookies.txt"
    assert s.database_url == f"sqlite:///{REPO_ROOT / 'tmp' / 'data' / 'yourtube.db'}"


def test_absolute_dirs_are_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("YT_DATA_DIR", str(tmp_path))
    assert Settings().data_dir == tmp_path


def test_resolve_repo_path():
    assert resolve_repo_path("tmp/downloads/a.mp4") == REPO_ROOT / "tmp/downloads/a.mp4"
    assert resolve_repo_path("/abs/a.mp4") == Path("/abs/a.mp4")


def test_empty_path_vars_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("YT_DATA_DIR", "")
    monkeypatch.setenv("YT_DOWNLOADS_DIR", "")
    monkeypatch.setenv("YT_COOKIES_PATH", "")
    monkeypatch.delenv("YT_DATABASE_URL", raising=False)
    s = Settings()
    assert s.data_dir == REPO_ROOT / "tmp" / "data"
    assert s.downloads_dir == REPO_ROOT / "tmp" / "downloads"
    assert s.cookies_path is None
    assert s.database_url == f"sqlite:///{REPO_ROOT / 'tmp' / 'data' / 'yourtube.db'}"


def test_relative_sqlite_database_url_resolves_against_repo_root(monkeypatch):
    monkeypatch.setenv("YT_DATABASE_URL", "sqlite:///./tmp/data/custom.db")
    assert Settings().database_url == f"sqlite:///{REPO_ROOT / 'tmp' / 'data' / 'custom.db'}"


def test_absolute_and_non_sqlite_database_urls_are_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("YT_DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    assert Settings().database_url == f"sqlite:///{tmp_path / 'x.db'}"
    monkeypatch.setenv("YT_DATABASE_URL", "sqlite:///:memory:")
    assert Settings().database_url == "sqlite:///:memory:"
    monkeypatch.setenv("YT_DATABASE_URL", "postgresql://u@h/db")
    assert Settings().database_url == "postgresql://u@h/db"
