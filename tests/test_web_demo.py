"""Reconstrucción y permisos del modo demo de Django."""

import importlib
import io
import os
import unittest
from unittest.mock import patch

from tests.django_utils import limpiar_bd, preparar_bd

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, override_settings
from django.urls import clear_url_caches

from web.comprobantes.models import Cliente, Comprobante, Importacion
from django.conf import settings


class TestWebDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preparar_bd()

    def setUp(self):
        limpiar_bd()

    def test_modo_demo_bloquea_escritura_y_comando_es_idempotente(self):
        with override_settings(DEMO_MODE=True), patch.dict(os.environ, {"DJANGO_DEMO_PASSWORD": "clave-sintetica"}):
            call_command("reconstruir_demo", stdout=io.StringIO())
            primer_total = Comprobante.objects.count()
            primeras_importaciones = Importacion.objects.count()
            call_command("reconstruir_demo", stdout=io.StringIO())
            self.assertEqual(Comprobante.objects.count(), primer_total)
            self.assertEqual(Importacion.objects.count(), primeras_importaciones)
            self.assertGreater(primer_total, 0)
            demo = User.objects.get(username="demo")
            self.assertFalse(demo.is_staff)
            self.assertFalse(demo.is_superuser)
            navegador = Client()
            navegador.force_login(demo)
            for ruta in ("/clientes/nuevo/", "/cargar/", "/confirmar/"):
                for metodo in ("get", "post"):
                    with self.subTest(ruta=ruta, metodo=metodo):
                        self.assertEqual(getattr(navegador, metodo)(ruta).status_code, 403)
            self.assertEqual(navegador.get("/historial/").status_code, 200)
            self.assertEqual(navegador.get("/observaciones/").status_code, 200)
            self.assertEqual(navegador.get("/informes/2026-09/").status_code, 200)
            self.assertNotIn(b"Subir archivo", navegador.get("/").content)
            for ruta in ("/", "/historial/", "/observaciones/", "/informes/2026-10/", "/login/"):
                with self.subTest(aviso=ruta):
                    self.assertIn(b"Modo demo: datos ficticios, solo lectura", navegador.get(ruta).content)

    def test_admin_no_esta_publicado_en_modo_demo(self):
        from web.config import urls

        try:
            with override_settings(DEMO_MODE=True):
                importlib.reload(urls)
                clear_url_caches()
                self.assertEqual(Client().get("/admin/").status_code, 404)
        finally:
            importlib.reload(urls)
            clear_url_caches()

    def test_comando_demo_rechaza_configuracion_y_datos_ajenos(self):
        with self.assertRaisesRegex(CommandError, "DJANGO_DEMO_MODE"):
            call_command("reconstruir_demo", stdout=io.StringIO())
        with override_settings(DEMO_MODE=True):
            with patch.dict(os.environ, {"DJANGO_DEMO_PASSWORD": ""}):
                with self.assertRaisesRegex(CommandError, "DJANGO_DEMO_PASSWORD"):
                    call_command("reconstruir_demo", stdout=io.StringIO())
            with patch.dict(os.environ, {"DJANGO_DEMO_PASSWORD": "clave-sintetica"}):
                with patch("web.comprobantes.management.commands.reconstruir_demo.Path.glob", return_value=[]):
                    with self.assertRaisesRegex(CommandError, "ejemplos sintéticos"):
                        call_command("reconstruir_demo", stdout=io.StringIO())
                Cliente.objects.create(nombre="Cliente Ajeno Sintético")
                with self.assertRaisesRegex(CommandError, "clientes ajenos"):
                    call_command("reconstruir_demo", stdout=io.StringIO())
                Cliente.objects.all().delete()
                User.objects.create_user("otro", password="clave-sintetica")
                with self.assertRaisesRegex(CommandError, "otros usuarios"):
                    call_command("reconstruir_demo", stdout=io.StringIO())

    def test_base_no_dedicada_y_cliente_sintetico_no_demo_quedan_intactos(self):
        with override_settings(DEMO_MODE=True), patch.dict(os.environ, {"DJANGO_DEMO_PASSWORD": "clave-sintetica"}):
            with patch.dict(settings.DATABASES["default"], {"NAME": "comprobantes.db"}):
                with self.assertRaisesRegex(CommandError, "base dedicada"):
                    call_command("reconstruir_demo", stdout=io.StringIO())
            cliente = Cliente.objects.create(nombre="Cliente Demo Norte")
            importacion = Importacion.objects.create(cliente=cliente, periodo="2026-09",
                                                     archivo_origen="Cliente Demo Norte.xlsx", sha256="no-demo")
            with self.assertRaisesRegex(CommandError, "importaciones ajenas"):
                call_command("reconstruir_demo", stdout=io.StringIO())
            self.assertTrue(Cliente.objects.filter(pk=cliente.pk).exists())
            self.assertTrue(Importacion.objects.filter(pk=importacion.pk, sha256="no-demo").exists())
            self.assertFalse(User.objects.filter(username="demo").exists())

    def test_cliente_con_nombre_demo_sin_importacion_no_se_borra(self):
        with override_settings(DEMO_MODE=True), patch.dict(os.environ, {"DJANGO_DEMO_PASSWORD": "clave-sintetica"}):
            cliente = Cliente.objects.create(nombre="Cliente Demo Norte")
            with self.assertRaisesRegex(CommandError, "sin importaciones de demo"):
                call_command("reconstruir_demo", stdout=io.StringIO())
            self.assertTrue(Cliente.objects.filter(pk=cliente.pk).exists())
            self.assertFalse(User.objects.filter(username="demo").exists())

    def test_password_no_tiene_valor_por_defecto_ni_se_imprime(self):
        salida = io.StringIO()
        secreto = "clave-sintetica-privada"
        with override_settings(DEMO_MODE=True):
            with patch.dict(os.environ, {"DJANGO_DEMO_PASSWORD": ""}):
                with self.assertRaisesRegex(CommandError, "DJANGO_DEMO_PASSWORD"):
                    call_command("reconstruir_demo", stdout=salida)
            with patch.dict(os.environ, {"DJANGO_DEMO_PASSWORD": secreto}):
                with self.assertLogs(level="INFO") as registros:
                    call_command("reconstruir_demo", stdout=salida)
        self.assertNotIn(secreto, salida.getvalue())
        self.assertNotIn(secreto, "\n".join(registros.output))
        self.assertTrue(User.objects.get(username="demo").check_password(secreto))
