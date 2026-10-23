"""Configuración sensible de Django según variables de entorno."""

import os
import subprocess
import sys
import unittest


class TestDjangoSettings(unittest.TestCase):
    def test_configuracion_segura_y_sqlite_immediate(self):
        entorno = os.environ.copy()
        entorno["DJANGO_SECRET_KEY"] = "ci-configuracion-sintetica-segura-5b62e2e44c7848b0abfa0097815629a9"
        entorno["DJANGO_DEBUG"] = "0"
        entorno["DJANGO_ALLOWED_HOSTS"] = "example.test"
        proceso = subprocess.run([
            sys.executable, "-c", "from web.config import settings; "
            "print(settings.DATABASES['default']['OPTIONS'], settings.SESSION_COOKIE_SECURE, "
            "settings.CSRF_COOKIE_SECURE, settings.X_FRAME_OPTIONS)"
        ], env=entorno, capture_output=True, text=True, check=True)
        self.assertIn("'transaction_mode': 'IMMEDIATE'", proceso.stdout)
        self.assertIn("True True DENY", proceso.stdout)

    def test_secret_key_obligatoria_fuera_de_desarrollo(self):
        entorno = os.environ.copy()
        entorno.pop("DJANGO_SECRET_KEY", None)
        entorno["DJANGO_DEBUG"] = "0"
        proceso = subprocess.run(
            [sys.executable, "-c", "from web.config import settings"],
            env=entorno, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(proceso.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY es obligatoria", proceso.stderr)

    def test_hosts_idioma_y_zona_horaria(self):
        entorno = os.environ.copy()
        entorno["DJANGO_SECRET_KEY"] = "clave-sintetica-de-pruebas"
        entorno["DJANGO_DEBUG"] = "0"
        entorno["DJANGO_ALLOWED_HOSTS"] = "localhost, 127.0.0.1"
        proceso = subprocess.run(
            [sys.executable, "-c", "from web.config import settings; "
             "print(settings.ALLOWED_HOSTS, settings.LANGUAGE_CODE, settings.TIME_ZONE, settings.DEBUG)"],
            env=entorno, capture_output=True, text=True, check=True,
        )
        self.assertIn("['localhost', '127.0.0.1'] es-ar America/Argentina/Buenos_Aires False", proceso.stdout)
