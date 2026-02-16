"""Module entrypoint for `python -m tool`."""

from tool.cli.user import main


if __name__ == "__main__":
    raise SystemExit(main())
