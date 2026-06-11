"""Lightweight runtime diagnostics for the YourTube web app.

The diagnostics service is a small, read-only status snapshot. It
checks the runtime environment (Node.js on PATH) and the worker
configuration (enabled vs disabled) and returns a dataclass the page
layer can render without needing to know how the check was performed.

Phase 5 introduces this service so the settings page can warn the user
when the environment is degraded (e.g. Node.js missing, workers
disabled). It deliberately stays small: no separate admin area, no
new write APIs, no telemetry. Phase 6 may surface diagnostics in
additional pages without changing the contract here.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeDiagnostics:
    """A renderable snapshot of the runtime/worker health.

    ``level`` is one of ``"ok"`` (no problems) or ``"warning"`` (at
    least one issue). ``messages`` is a human-readable list of issues,
    ordered for display. ``js_runtime_ready`` reports whether a Node.js
    binary is discoverable on ``PATH``. ``workers_enabled`` mirrors the
    worker pool's configured state.
    """

    level: str
    messages: list[str]
    js_runtime_ready: bool
    workers_enabled: bool


def collect_runtime_diagnostics(*, workers_enabled: bool) -> RuntimeDiagnostics:
    """Collect the runtime status of the deployed environment.

    Probes the PATH for a Node.js binary (yt-dlp needs a JS runtime to
    solve YouTube's JS challenges) and folds in the configured worker
    state. Returns a frozen dataclass the template layer can render
    directly; no side effects.
    """
    node_present = shutil.which("node") is not None
    messages: list[str] = []
    if not node_present:
        messages.append("Node.js runtime missing. YouTube extraction may be incomplete.")
    if not workers_enabled:
        messages.append(
            "Background workers are disabled. New downloads will not start automatically."
        )
    level = "ok" if not messages else "warning"
    return RuntimeDiagnostics(
        level=level,
        messages=messages,
        js_runtime_ready=node_present,
        workers_enabled=workers_enabled,
    )
