"""Contrato HTTP de la primera etapa de la interfaz Django."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import pandas as pd

from tests.django_utils import limpiar_bd, preparar_bd

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, override_settings
from django.conf import settings

from tests.helpers import TEMP_ROOT, comprobante
from web.comprobantes.models import Cliente, Importacion
from web.comprobantes.previews import DURACION_SEGUNDOS
from web.comprobantes.repositorio import RepositorioDjango


class TestWebVistas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preparar_bd()

    def setUp(self):
        limpiar_bd()
        self.temporal = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.temporal.cleanup)
        self.config = override_settings(PREVIEW_DIR=Path(self.temporal.name))
        self.config.enable()
        self.addCleanup(self.config.disable)
        self.usuario = User.objects.create_user("operador", password="clave-sintetica", is_staff=True)
        self.cliente = Cliente.objects.create(nombre="Cliente Sintético")
        self.navegador = Client()
        self.navegador.force_login(self.usuario)

    def carga(self, **cambios):
        fila = comprobante(**cambios)
        archivo = SimpleUploadedFile("archivo.csv", pd.DataFrame([fila]).to_csv(index=False).encode("utf-8"))
        return self.navegador.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                              "origen": "estandar", "operacion": "ventas", "archivo": archivo})

    def test_urls_privadas_redirigen_al_login(self):
        anonimo = Client()
        for ruta in ("/", "/clientes/nuevo/", "/cargar/", "/vista-previa/", "/confirmar/"):
            with self.subTest(ruta=ruta):
                respuesta = anonimo.get(ruta)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn("/login/", respuesta["Location"])
        self.assertIn("/admin/login/", anonimo.get("/admin/")["Location"])

    def test_login_y_alta_de_cliente_con_clave_compartida(self):
        anonimo = Client()
        self.assertEqual(anonimo.post("/login/", {"username": "operador",
                                                  "password": "clave-sintetica"}).status_code, 302)
        self.assertEqual(anonimo.get("/").status_code, 200)
        self.assertEqual(anonimo.post("/clientes/nuevo/", {"nombre": " Cliente   Á ", "cuit": ""}).status_code,
                         302)
        self.assertEqual(Cliente.objects.get(nombre_clave="cliente á").nombre, "Cliente   Á")
        respuesta = anonimo.post("/clientes/nuevo/", {"nombre": "cliente á", "cuit": ""})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b"Ya existe un cliente", respuesta.content)

    def test_configuracion_de_seguridad_y_admin(self):
        self.assertEqual(settings.DATABASES["default"]["OPTIONS"]["transaction_mode"], "IMMEDIATE")
        self.assertGreater(settings.DATABASES["default"]["OPTIONS"]["timeout"], 0)
        self.assertGreater(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 10 * 1024 * 1024)
        self.assertLess(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 10 * 1024 * 1024)
        lector = User.objects.create_user("lector", password="clave-sintetica", is_staff=False)
        navegador = Client()
        navegador.force_login(lector)
        self.assertEqual(navegador.get("/admin/").status_code, 302)
        self.assertEqual(navegador.get("/cargar/").status_code, 403)

    def test_token_y_archivo_modificados_no_confirman(self):
        self.carga()
        meta = self.navegador.session["preview"]
        ruta = Path(self.temporal.name) / f"{meta['id']}{meta['sufijo']}"
        self.assertNotIn("archivo.csv", ruta.name)
        self.assertEqual(self.navegador.post("/confirmar/", {"token": meta["token"] + "x"}).status_code, 400)
        with ruta.open("ab") as contenido:
            contenido.write(b"\n")
        self.assertEqual(self.navegador.post("/confirmar/", {"token": meta["token"]}).status_code, 400)
        self.assertEqual(Importacion.objects.count(), 0)

    def test_csrf_obligatorio_en_confirmacion(self):
        navegador = Client(enforce_csrf_checks=True)
        navegador.force_login(self.usuario)
        self.assertEqual(navegador.post("/confirmar/", {"token": "sintetico"}).status_code, 403)

    def test_cliente_explicitamente_elegido_y_token_de_un_solo_uso(self):
        self.assertEqual(self.carga().status_code, 302)
        vista = self.navegador.get("/vista-previa/")
        self.assertEqual(vista.status_code, 200)
        self.assertIn(b"Cliente Sint", vista.content)
        token = self.navegador.session["preview"]["token"]
        respuesta = self.navegador.post("/confirmar/", {"token": token})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(RepositorioDjango().consultar_comprobantes("2026-09")["cliente"].tolist(),
                         ["Cliente Sintético"])
        self.assertEqual(Importacion.objects.get().archivo_origen, "archivo.csv")
        self.assertEqual(self.navegador.post("/confirmar/", {"token": token}).status_code, 400)
        self.assertFalse(list(Path(self.temporal.name).glob("*.csv")))
        self.assertIn("no-store", vista["Cache-Control"])

    def test_operacion_incompatible_bloquea_confirmacion(self):
        respuesta = self.carga(operacion="compras")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b"no coincide", respuesta.content)
        self.assertNotIn("preview", self.navegador.session)
        self.assertEqual(Importacion.objects.count(), 0)

    def test_error_de_lectura_no_revela_ruta_temporal(self):
        archivo = SimpleUploadedFile("invalido.csv", b"columna_invalida\nvalor\n")
        respuesta = self.navegador.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                                      "origen": "estandar", "operacion": "ventas",
                                                      "archivo": archivo})
        self.assertEqual(respuesta.status_code, 302)
        vista = self.navegador.get("/vista-previa/")
        self.assertEqual(vista.status_code, 200)
        self.assertIn(b"No se pudo interpretar el archivo", vista.content)
        self.assertNotIn(str(self.temporal.name).encode(), vista.content)

    def test_vencimiento_y_limpieza_por_comando(self):
        self.carga()
        meta = self.navegador.session["preview"]
        ruta = Path(self.temporal.name) / f"{meta['id']}{meta['sufijo']}"
        momento = time.time() - DURACION_SEGUNDOS - 5
        os.utime(ruta, (momento, momento))
        self.assertEqual(self.navegador.get("/vista-previa/").status_code, 400)
        call_command("limpiar_previsualizaciones", verbosity=0)
        self.assertFalse(ruta.exists())

    def test_limpieza_oportunista_al_cargar_y_confirmar(self):
        vencido = Path(self.temporal.name) / "antiguo.csv"
        vencido.write_text("sintetico", encoding="utf-8")
        momento = time.time() - DURACION_SEGUNDOS - 5
        os.utime(vencido, (momento, momento))
        self.carga()
        self.assertFalse(vencido.exists())
        vencido.write_text("sintetico", encoding="utf-8")
        os.utime(vencido, (momento, momento))
        token = self.navegador.session["preview"]["token"]
        self.assertEqual(self.navegador.post("/confirmar/", {"token": token}).status_code, 302)
        self.assertFalse(vencido.exists())

    def test_cambio_concurrente_de_version_se_rechaza(self):
        self.carga()
        token = self.navegador.session["preview"]["token"]
        otro = Client()
        otro.force_login(self.usuario)
        archivo = SimpleUploadedFile("otro.csv", pd.DataFrame([comprobante(numero=2)]).to_csv(index=False).encode())
        self.assertEqual(otro.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                              "origen": "estandar", "operacion": "ventas", "archivo": archivo}).status_code, 302)
        segundo = otro.session["preview"]["token"]
        self.assertEqual(otro.post("/confirmar/", {"token": segundo}).status_code, 302)
        self.assertEqual(self.navegador.post("/confirmar/", {"token": token}).status_code, 409)
        self.assertEqual(RepositorioDjango().consultar_comprobantes("2026-09")["numero"].tolist(), [2])


class TestConfirmacionesConcurrentes(unittest.TestCase):
    def test_dos_confirmaciones_compiten_por_cliente_periodo_y_operacion(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporal:
            entorno = os.environ.copy()
            entorno["DJANGO_DB_PATH"] = str(Path(temporal) / "concurrente.sqlite3")
            entorno["DJANGO_DEBUG"] = "1"
            entorno["DJANGO_PREVIEW_TEST_DIR"] = str(Path(temporal) / "previews")
            proceso = subprocess.run([sys.executable, "-m", "tests.web_concurrencia_worker"],
                                     env=entorno, capture_output=True, text=True, check=False)
            self.assertEqual(proceso.returncode, 0, proceso.stdout + proceso.stderr)
            self.assertIn("RESULTADO [302, 409] 1", proceso.stdout)


if __name__ == "__main__":
    unittest.main()
