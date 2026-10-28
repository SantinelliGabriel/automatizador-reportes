"""Contrato de presentación de la web local, sin cambiar el núcleo contable."""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

from tests.django_utils import limpiar_bd, preparar_bd

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.http import HttpRequest
from django.test import Client, override_settings
from django.urls import resolve
from django.views.static import serve

from tests.helpers import ROOT, TEMP_ROOT


class ElementosHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.labels = set()
        self.fields = set()
        self.inline = []
        self.headers_without_scope = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "style" in values or any(name.startswith("on") for name in values):
            self.inline.append(tag)
        if tag == "script" and not values.get("src"):
            self.inline.append("script")
        if tag == "style":
            self.inline.append("style")
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag == "label" and values.get("for"):
            self.labels.add(values["for"])
        if tag in {"input", "select", "textarea"} and values.get("type") != "hidden":
            self.fields.add(values.get("id"))
        if tag == "th" and values.get("scope") != "col":
            self.headers_without_scope.append(values)


class TestWebPresentacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preparar_bd()

    def setUp(self):
        if "auth_user" not in connection.introspection.table_names():
            call_command("migrate", verbosity=0)
        limpiar_bd()
        self.usuario = User.objects.create_user("operador", password="clave-sintetica", is_staff=True)
        self.cliente = Client()
        self.cliente.force_login(self.usuario)

    def test_menu_enlaces_locales_y_pagina_activa(self):
        for ruta, nombre in (("/", "clientes"), ("/cargar/", "cargar"), ("/historial/", "historial"),
                             ("/observaciones/", "observaciones"), ("/informes/", "informes")):
            with self.subTest(ruta=ruta):
                respuesta = self.cliente.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                contenido = respuesta.content.decode()
                self.assertRegex(contenido, rf'href="{re.escape(ruta)}" aria-current="page"')
                parser = ElementosHTML()
                parser.feed(contenido)
                for enlace in parser.links:
                    destino = urlsplit(enlace)
                    if destino.path.startswith("/") and not destino.path.startswith("/static/"):
                        self.assertIsNotNone(resolve(destino.path).url_name, enlace)

    def test_html_sin_estilos_ni_scripts_en_linea_y_campos_etiquetados(self):
        paginas = [Client().get("/login/"), self.cliente.get("/"), self.cliente.get("/cargar/"),
                   self.cliente.get("/clientes/nuevo/"), self.cliente.get("/historial/"),
                   self.cliente.get("/observaciones/"), self.cliente.get("/informes/")]
        for respuesta in paginas:
            with self.subTest(pagina=respuesta.request.get("PATH_INFO")):
                parser = ElementosHTML()
                parser.feed(respuesta.content.decode())
                self.assertEqual(parser.inline, [])
                self.assertEqual(parser.headers_without_scope, [])
                self.assertFalse(parser.fields - parser.labels)
                self.assertIn('/static/comprobantes/web.css', respuesta.content.decode())

    def test_errores_403_404_500_con_aviso_y_sin_detalles_tecnicos(self):
        lector = User.objects.create_user("lector", password="clave-sintetica", is_staff=False)
        navegador = Client(raise_request_exception=False)
        navegador.force_login(lector)
        with override_settings(DEBUG=False, DEMO_MODE=True):
            prohibida = navegador.get("/cargar/")
            ausente = navegador.get("/pagina-sintetica-inexistente/")
            with patch("web.comprobantes.views.RepositorioDjango.consultar_importaciones",
                       side_effect=RuntimeError("detalle técnico sintético")):
                inesperado = navegador.get("/historial/")
        for respuesta, codigo in ((prohibida, 403), (ausente, 404), (inesperado, 500)):
            with self.subTest(codigo=codigo):
                self.assertEqual(respuesta.status_code, codigo)
                html = respuesta.content.decode()
                self.assertIn("Modo demo: datos ficticios, solo lectura", html)
                self.assertNotIn("detalle técnico sintético", html)
                self.assertNotIn("Traceback", html)
                parser = ElementosHTML()
                parser.feed(html)
                self.assertEqual(parser.inline, [])

    def test_collectstatic_y_servicio_local_con_debug_desactivado(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as carpeta:
            raiz = Path(carpeta)
            entorno = os.environ.copy()
            entorno.update({"DJANGO_DEBUG": "0", "DJANGO_ALLOWED_HOSTS": "example.test",
                            "DJANGO_SECRET_KEY": "clave-sintetica-para-collectstatic-2026",
                            "DJANGO_STATIC_ROOT": str(raiz)})
            proceso = subprocess.run([sys.executable, "web/manage.py", "collectstatic", "--noinput", "--verbosity", "0"],
                                     cwd=ROOT, env=entorno, capture_output=True, text=True, check=False)
            self.assertEqual(proceso.returncode, 0, proceso.stderr)
            for nombre in ("web.css", "formulario.js"):
                ruta = raiz / "comprobantes" / nombre
                self.assertTrue(ruta.is_file())
                solicitud = HttpRequest()
                solicitud.method = "GET"
                respuesta = serve(solicitud, f"comprobantes/{nombre}", document_root=raiz)
                self.assertEqual(respuesta.status_code, 200)
                self.assertGreater(len(b"".join(respuesta.streaming_content)), 20)
                respuesta.close()


if __name__ == "__main__":
    unittest.main()
