"""python -m churncast_api [--host 127.0.0.1] [--port 8000]: run the API with uvicorn."""

from __future__ import annotations

import argparse
import logging

import uvicorn


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="churncast_api")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run("churncast_api.app:create_app", factory=True, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
