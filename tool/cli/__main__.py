"""Module entrypoint for `python -m tool.cli`."""

from tool.cli.user import main


if __name__ == "__main__":
    raise SystemExit(main())
