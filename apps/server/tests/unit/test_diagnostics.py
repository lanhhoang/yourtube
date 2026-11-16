"""Unit tests for ``app.services.diagnostics`` runtime status reporting.

The diagnostics service is a small, read-only status snapshot. It
checks the runtime environment (Node.js on PATH) and the worker
configuration (enabled vs disabled) and returns a dataclass the page
layer can render without needing to know how the check was performed.
"""

from __future__ import annotations

from app.services.diagnostics import collect_runtime_diagnostics


def test_collect_runtime_diagnostics_reports_missing_node(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None if name == "node" else "/usr/bin/ffmpeg")

    status = collect_runtime_diagnostics(workers_enabled=True)

    assert status.js_runtime_ready is False
    assert status.level == "warning"
    assert "Node.js" in status.messages[0]


def test_collect_runtime_diagnostics_reports_disabled_workers(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/node" if name == "node" else None)

    status = collect_runtime_diagnostics(workers_enabled=False)

    assert status.workers_enabled is False
    assert status.js_runtime_ready is True
    assert status.level == "warning"
    assert any("workers" in message.lower() for message in status.messages)


def test_collect_runtime_diagnostics_is_ok_when_runtime_is_healthy(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/node" if name == "node" else None)

    status = collect_runtime_diagnostics(workers_enabled=True)

    assert status.js_runtime_ready is True
    assert status.workers_enabled is True
    assert status.level == "ok"
    assert status.messages == []
