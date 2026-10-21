"""Compatibilidad para ejecutar el comando desde el checkout."""

from automatizador.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
