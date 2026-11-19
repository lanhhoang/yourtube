"""Run the server: ``python -m app [--reload]``, honouring ``YT_HOST`` and ``YT_PORT``."""

from __future__ import annotations

import argparse
from typing import Any

import uvicorn

from app.config import Settings, settings


def uvicorn_options(s: Settings, *, reload: bool) -> dict[str, Any]:
    return {"app": "app.main:app", "host": s.host, "port": s.port, "reload": reload}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app")
    parser.add_argument("--reload", action="store_true", help="restart on code changes")
    args = parser.parse_args(argv)
    uvicorn.run(**uvicorn_options(settings, reload=args.reload))


if __name__ == "__main__":
    main()
