"""Point d'entrée `python -m vte` : délègue à la CLI (vte.cli.main)."""

from vte.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
