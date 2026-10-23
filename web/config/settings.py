"""Configuración local de la capa Django opcional."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parents[1]
DEBUG = os.getenv("DJANGO_DEBUG", "0").lower() in {"1", "true", "yes"}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-inseguro-solo-desarrollo-local"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY es obligatoria fuera de desarrollo.")
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]

INSTALLED_APPS = ["django.contrib.contenttypes", "web.comprobantes"]
MIDDLEWARE = []
ROOT_URLCONF = "web.config.urls"
TEMPLATES = []
WSGI_APPLICATION = "web.config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(os.getenv("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3"))),
    }
}

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
