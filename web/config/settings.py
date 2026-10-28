"""Configuración local de la capa Django opcional."""

import os
import tempfile
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parents[1]
DEBUG = os.getenv("DJANGO_DEBUG", "0").lower() in {"1", "true", "yes"}
DEMO_MODE = os.getenv("DJANGO_DEMO_MODE", "0").lower() in {"1", "true", "yes"}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-inseguro-solo-desarrollo-local"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY es obligatoria fuera de desarrollo.")
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "web.comprobantes",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "web.config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "web.comprobantes.contexto.modo_demo",
    ]},
}]
WSGI_APPLICATION = "web.config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(os.getenv("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3"))),
        "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 20},
    }
}

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.getenv("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "clientes"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
PREVIEW_DIR = Path(os.getenv("DJANGO_PREVIEW_DIR", str(Path(tempfile.gettempdir()) / "automatizador-previews")))
if os.name == "nt" and not PREVIEW_DIR.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
    raise ImproperlyConfigured("DJANGO_PREVIEW_DIR debe estar dentro del directorio temporal del usuario en Windows.")
for ruta_servida in (BASE_DIR, STATIC_ROOT, MEDIA_ROOT):
    if PREVIEW_DIR.resolve().is_relative_to(ruta_servida.resolve()):
        raise ImproperlyConfigured("DJANGO_PREVIEW_DIR debe estar fuera del proyecto y de rutas servidas.")
HOLISTOR_MAPPING_PATH = Path(os.environ["DJANGO_HOLISTOR_MAPPING_PATH"]) if os.getenv("DJANGO_HOLISTOR_MAPPING_PATH") else None
