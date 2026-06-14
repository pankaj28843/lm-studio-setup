from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import ValidationError

from lmstudio_setup.lmstudio import ensure_model, options_from_env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ensure-lmstudio-codex-model")
    parser.add_argument("--estimate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        options = options_from_env(estimate_only=args.estimate_only)
    except (ValidationError, ValueError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit(asyncio.run(ensure_model(options)))


if __name__ == "__main__":
    main()
