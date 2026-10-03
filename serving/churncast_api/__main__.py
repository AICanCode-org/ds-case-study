"""python -m churncast_api [--host 127.0.0.1] [--port 8000]: run the API with uvicorn."""

from __future__ import annotations

import argparse

import uvicorn

from .observability import configure_logging


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="churncast_api")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    configure_logging()
    # uvicorn's own access log is off: the app writes one JSON line per request (no client address, no body)
    uvicorn.run(
        "churncast_api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
