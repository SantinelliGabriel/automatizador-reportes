"""Configura una base SQLite temporal para pruebas unittest de Django."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.config.settings")
os.environ.setdefault("DJANGO_DEBUG", "1")
os.environ.setdefault("DJANGO_DB_PATH", ":memory:")

import django  # noqa: E402
from django.core.management import call_command  # noqa: E402

django.setup()

_migrada = False


def preparar_bd():
    global _migrada
    if not _migrada:
        call_command("migrate", verbosity=0)
        _migrada = True


def limpiar_bd():
    call_command("flush", verbosity=0, interactive=False)
