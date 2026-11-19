import uvicorn

from app import __main__ as entry
from app.__main__ import uvicorn_options
from app.config import Settings


def test_uvicorn_options_use_settings(monkeypatch):
    monkeypatch.setenv("YT_HOST", "0.0.0.0")
    monkeypatch.setenv("YT_PORT", "8123")
    opts = uvicorn_options(Settings(), reload=True)
    assert opts == {"app": "app.main:app", "host": "0.0.0.0", "port": 8123, "reload": True}


def test_default_host_is_loopback(monkeypatch):
    monkeypatch.delenv("YT_HOST", raising=False)
    assert uvicorn_options(Settings(_env_file=None), reload=False)["host"] == "127.0.0.1"


def test_main_passes_reload_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda **kw: calls.append(kw))
    entry.main(["--reload"])
    entry.main([])
    assert [c["reload"] for c in calls] == [True, False]
