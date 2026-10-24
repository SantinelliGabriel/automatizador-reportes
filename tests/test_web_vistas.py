"""Contrato HTTP de la primera etapa de la interfaz Django."""

import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tests.django_utils import limpiar_bd, preparar_bd

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, override_settings
from django.conf import settings

from tests.helpers import TEMP_ROOT, comprobante
from web.comprobantes.models import Cliente, Importacion
from web.comprobantes.previews import DURACION_SEGUNDOS, firmar
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

    def subir(self, filas, *, periodo="2026-09", origen="estandar", nombre="archivo.csv"):
        archivo = SimpleUploadedFile(nombre, pd.DataFrame(filas).to_csv(index=False).encode("utf-8"))
        return self.navegador.post("/cargar/", {"cliente": self.cliente.pk, "periodo": periodo,
                                              "origen": origen, "operacion": "ventas", "archivo": archivo})

    def test_urls_privadas_redirigen_al_login(self):
        anonimo = Client()
        for ruta in ("/", "/clientes/nuevo/", "/cargar/", "/vista-previa/", "/confirmar/"):
            with self.subTest(ruta=ruta):
                respuesta = anonimo.get(ruta)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn("/login/", respuesta["Location"])
        for ruta in ("/clientes/nuevo/", "/cargar/", "/confirmar/"):
            with self.subTest(post=ruta):
                respuesta = anonimo.post(ruta)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn("/login/", respuesta["Location"])
        self.assertIn("/admin/login/", anonimo.get("/admin/")["Location"])
        self.assertEqual(self.navegador.get("/vista-previa/").status_code, 400)

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

    def test_alta_cliente_informa_una_colision_de_base(self):
        with patch("web.comprobantes.views.ClienteForm.save", side_effect=IntegrityError):
            respuesta = self.navegador.post("/clientes/nuevo/", {"nombre": "Otro Cliente Sintético", "cuit": ""})
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

    def test_token_firmado_vencido_impide_ver_y_confirmar(self):
        with patch("django.core.signing.time.time", return_value=time.time() - DURACION_SEGUNDOS - 1):
            self.assertEqual(self.carga().status_code, 302)
        token = self.navegador.session["preview"]["token"]
        self.assertEqual(self.navegador.get("/vista-previa/").status_code, 400)
        self.assertEqual(self.navegador.post("/confirmar/", {"token": token}).status_code, 400)
        self.assertEqual(Importacion.objects.count(), 0)

    def test_doble_envio_del_mismo_token_toma_candado(self):
        self.carga()
        meta = self.navegador.session["preview"]
        ruta = Path(self.temporal.name) / f"{meta['id']}{meta['sufijo']}"
        candado = Path(str(ruta) + ".lock")
        candado.touch()
        try:
            self.assertEqual(self.navegador.post("/confirmar/", {"token": meta["token"]}).status_code, 409)
            self.assertEqual(Importacion.objects.count(), 0)
        finally:
            candado.unlink()
        self.assertEqual(self.navegador.post("/confirmar/", {"token": meta["token"]}).status_code, 302)

    def test_token_y_opciones_firmadas_deben_coincidir(self):
        self.carga()
        sesion = self.navegador.session
        meta = sesion["preview"]
        meta["token"] = firmar({"id": "otro-token-sintetico"})
        sesion["preview"] = meta
        sesion.save()
        self.assertEqual(self.navegador.post("/confirmar/", {"token": meta["token"]}).status_code, 400)
        self.carga()
        sesion = self.navegador.session
        meta = sesion["preview"]
        meta["opciones"]["periodo"] = "2026-10"
        sesion["preview"] = meta
        sesion.save()
        self.assertEqual(self.navegador.post("/confirmar/", {"token": meta["token"]}).status_code, 400)
        self.assertEqual(Importacion.objects.count(), 0)

    def test_cambio_de_cliente_o_del_resultado_obliga_a_revisar(self):
        self.carga()
        self.cliente.nombre = "Cliente Renombrado Sintético"
        self.cliente.save()
        self.assertEqual(self.navegador.get("/vista-previa/").status_code, 400)
        self.carga()
        with patch("web.comprobantes.views.hash_plan", return_value="hash-distinto"):
            self.assertEqual(self.navegador.get("/vista-previa/").status_code, 400)

    def test_cambio_de_mapeo_holistor_invalida_la_vista(self):
        mapeo = Path(self.temporal.name) / "mapeo-sintetico.json"
        mapeo.write_text('{"columnas": {}}', encoding="utf-8")
        with override_settings(HOLISTOR_MAPPING_PATH=mapeo):
            self.assertEqual(self.subir([comprobante()], origen="holistor").status_code, 302)
            mapeo.write_text('{"columnas": {"Fecha": "fecha"}}', encoding="utf-8")
            self.assertEqual(self.navegador.get("/vista-previa/").status_code, 400)

    def test_operacion_incompatible_bloquea_confirmacion(self):
        respuesta = self.carga(operacion="compras")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b"no coincide", respuesta.content)
        self.assertNotIn("preview", self.navegador.session)
        self.assertEqual(Importacion.objects.count(), 0)

    def test_nombre_con_directorio_se_sanea_y_solo_escribe_temporal_privado(self):
        contenido = (Path(__file__).resolve().parents[1] / "ejemplos" / "Cliente Demo Norte.xlsx").read_bytes()
        limite = "limite-sintetico"
        partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{campo}"\r\n\r\n{valor}\r\n'.encode()
                  for campo, valor in {"cliente": self.cliente.pk, "periodo": "2026-09", "origen": "estandar",
                                       "operacion": "mixto"}.items()]
        partes.extend([f'--{limite}\r\nContent-Disposition: form-data; name="archivo"; '
                       'filename="../x.xlsx"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + contenido + b"\r\n",
                       f'--{limite}--\r\n'.encode()])
        respuesta = self.navegador.generic("POST", "/cargar/", b"".join(partes),
                                          content_type=f"multipart/form-data; boundary={limite}")
        self.assertEqual(respuesta.status_code, 302)
        meta = self.navegador.session["preview"]
        self.assertEqual(meta["opciones"]["nombre_archivo"], "x.xlsx")
        ruta = Path(self.temporal.name) / f"{meta['id']}{meta['sufijo']}"
        self.assertTrue(ruta.is_file())
        self.assertTrue(ruta.resolve().is_relative_to(Path(self.temporal.name).resolve()))
        self.assertRegex(ruta.name, r"^[0-9a-f]{32}\.xlsx$")
        self.assertEqual(list(Path(self.temporal.name).iterdir()), [ruta])
        self.assertFalse((Path(self.temporal.name).parent / "x.xlsx").exists())
        self.assertEqual(self.navegador.post("/confirmar/", {"token": meta["token"]}).status_code, 302)
        self.assertEqual(Importacion.objects.get().archivo_origen, "x.xlsx")

    def test_ejemplo_mixto_muestra_operaciones_y_reemplaza_solo_presentes(self):
        ejemplo = (Path(__file__).resolve().parents[1] / "ejemplos" / "Cliente Demo Norte.xlsx").read_bytes()

        def cargar_ejemplo(operacion):
            return self.navegador.post("/cargar/", {
                "cliente": self.cliente.pk, "periodo": "2026-09", "origen": "estandar",
                "operacion": operacion, "archivo": SimpleUploadedFile("ejemplo.xlsx", ejemplo),
            })

        self.assertEqual(cargar_ejemplo("mixto").status_code, 302)
        vista = self.navegador.get("/vista-previa/")
        self.assertEqual(vista.status_code, 200)
        self.assertIn("compras: 1", vista.content.decode())
        self.assertIn("ventas: 1", vista.content.decode())
        self.assertIn("Operaciones que se reemplazarán: compras, ventas", vista.content.decode())
        token = self.navegador.session["preview"]["token"]
        self.assertEqual(self.navegador.post("/confirmar/", {"token": token}).status_code, 302)
        repo = RepositorioDjango()
        self.assertEqual(sorted(repo.consultar_comprobantes("2026-09")["operacion"]), ["compras", "ventas"])
        self.assertEqual(Importacion.objects.get().operaciones, "compras,ventas")

        self.assertEqual(self.subir([comprobante(numero=202)]).status_code, 302)
        vista = self.navegador.get("/vista-previa/")
        self.assertIn("Operaciones que se reemplazarán: ventas", vista.content.decode())
        token = self.navegador.session["preview"]["token"]
        self.assertEqual(self.navegador.post("/confirmar/", {"token": token}).status_code, 302)
        actuales = repo.consultar_comprobantes("2026-09")
        self.assertEqual(sorted(actuales["operacion"]), ["compras", "ventas"])
        self.assertEqual(actuales.loc[actuales["operacion"] == "ventas", "numero"].tolist(), [202])

        incompatible = cargar_ejemplo("ventas")
        self.assertEqual(incompatible.status_code, 200)
        self.assertIn(b"no coincide", incompatible.content)
        self.assertNotIn("preview", self.navegador.session)

    def test_mixto_detecta_cambio_concurrente_en_cualquiera_de_sus_operaciones(self):
        ejemplo = (Path(__file__).resolve().parents[1] / "ejemplos" / "Cliente Demo Norte.xlsx").read_bytes()
        respuesta = self.navegador.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                                 "origen": "estandar", "operacion": "mixto",
                                                 "archivo": SimpleUploadedFile("ejemplo.xlsx", ejemplo)})
        self.assertEqual(respuesta.status_code, 302)
        token = self.navegador.session["preview"]["token"]
        otro = Client()
        otro.force_login(self.usuario)
        compras = SimpleUploadedFile("compras.csv", pd.DataFrame([
            comprobante(operacion="compras", numero=202)]).to_csv(index=False).encode())
        self.assertEqual(otro.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                               "origen": "estandar", "operacion": "compras",
                                               "archivo": compras}).status_code, 302)
        self.assertEqual(otro.post("/confirmar/", {"token": otro.session["preview"]["token"]}).status_code, 302)
        self.assertEqual(self.navegador.post("/confirmar/", {"token": token}).status_code, 409)
        actuales = RepositorioDjango().consultar_comprobantes("2026-09")
        self.assertEqual(actuales["operacion"].tolist(), ["compras"])
        self.assertEqual(actuales["numero"].tolist(), [202])

    def test_mixto_exige_operacion_por_fila_y_no_se_ofrece_a_arca_holistor(self):
        for origen in ("arca", "holistor"):
            with self.subTest(origen=origen):
                respuesta = self.subir([comprobante()], origen=origen)
                self.assertEqual(respuesta.status_code, 302)
                archivo = SimpleUploadedFile("archivo.csv", pd.DataFrame([comprobante()]).to_csv(index=False).encode())
                rechazo = self.navegador.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                                           "origen": origen, "operacion": "mixto", "archivo": archivo})
                self.assertEqual(rechazo.status_code, 200)
                self.assertIn(b"solo est", rechazo.content)
        sin_operacion = pd.DataFrame([comprobante()]).drop(columns="operacion").to_csv(index=False).encode()
        rechazo = self.navegador.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                                   "origen": "estandar", "operacion": "mixto",
                                                   "archivo": SimpleUploadedFile("sin-operacion.csv", sin_operacion)})
        self.assertEqual(rechazo.status_code, 200)
        self.assertIn(b"requiere una columna", rechazo.content)

    def test_csrf_httponly_y_formularios_sin_javascript(self):
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        navegador = Client(enforce_csrf_checks=True)

        def csrf(ruta):
            respuesta = navegador.get(ruta)
            self.assertEqual(respuesta.status_code, 200)
            return re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', respuesta.content).group(1).decode()

        token = csrf("/login/")
        self.assertTrue(navegador.cookies["csrftoken"]["httponly"])
        self.assertEqual(navegador.post("/login/", {"username": "operador", "password": "clave-sintetica",
                                                    "csrfmiddlewaretoken": token}).status_code, 302)
        token = csrf("/clientes/nuevo/")
        self.assertEqual(navegador.post("/clientes/nuevo/", {"nombre": "Otro Cliente Sintético", "cuit": "",
                                                             "csrfmiddlewaretoken": token}).status_code, 302)
        token = csrf("/cargar/")
        archivo = SimpleUploadedFile("archivo.csv", pd.DataFrame([comprobante()]).to_csv(index=False).encode())
        self.assertEqual(navegador.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                                     "origen": "estandar", "operacion": "ventas", "archivo": archivo,
                                                     "csrfmiddlewaretoken": token}).status_code, 302)
        token = csrf("/vista-previa/")
        firmado = navegador.session["preview"]["token"]
        self.assertEqual(navegador.post("/confirmar/", {"token": firmado,
                                                        "csrfmiddlewaretoken": token}).status_code, 302)

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

    def test_error_inesperado_de_carga_no_expone_ruta_y_limpia(self):
        ruta_privada = str(Path(self.temporal.name) / "contenido-sintetico.csv")
        with patch("web.comprobantes.views.guardar_temporal", side_effect=OSError(ruta_privada)):
            respuesta = self.carga()
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b"No se pudo procesar el archivo", respuesta.content)
        self.assertNotIn(ruta_privada.encode(), respuesta.content)
        with patch("web.comprobantes.views._hash_mapeo", side_effect=ValueError(ruta_privada)):
            respuesta = self.carga()
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(ruta_privada.encode(), respuesta.content)
        self.assertEqual(list(Path(self.temporal.name).glob("*.csv")), [])

    def test_log_de_carga_no_incluye_cuit_razon_social_ni_importe(self):
        fila = comprobante(razon_social="Entidad Ficticia Reservada", total=121000)
        with self.assertLogs(level="INFO") as capturado:
            self.assertEqual(self.subir([fila]).status_code, 302)
        mensajes = "\n".join(capturado.output)
        self.assertNotIn(fila["cuit"], mensajes)
        self.assertNotIn(fila["razon_social"], mensajes)
        self.assertNotIn("121000", mensajes)

    def test_csv_sin_datos_observado_y_codificacion_invalida_rechazada(self):
        archivo = SimpleUploadedFile("vacio.csv", b"\n")
        respuesta = self.navegador.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                                      "origen": "estandar", "operacion": "ventas", "archivo": archivo})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(b"No se pudo interpretar", self.navegador.get("/vista-previa/").content)
        invalido = SimpleUploadedFile("invalido.csv", b"fecha,numero\n\x81,2")
        respuesta = self.navegador.post("/cargar/", {"cliente": self.cliente.pk, "periodo": "2026-09",
                                                      "origen": "estandar", "operacion": "ventas", "archivo": invalido})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b"codificaci", respuesta.content)

    def test_archivo_con_mas_de_diez_mil_filas_no_genera_vista(self):
        respuesta = self.subir([comprobante()] * 10001)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b"10.000 filas", respuesta.content)
        self.assertEqual(Importacion.objects.count(), 0)

    def test_nueva_carga_elimina_la_vista_anterior(self):
        self.carga()
        primera = self.navegador.session["preview"]
        ruta = Path(self.temporal.name) / f"{primera['id']}{primera['sufijo']}"
        self.assertTrue(ruta.exists())
        self.carga(numero=2)
        self.assertFalse(ruta.exists())

    def test_mismo_cliente_en_dos_periodos_no_reemplaza_el_anterior(self):
        self.carga()
        primero = self.navegador.session["preview"]["token"]
        self.assertEqual(self.navegador.post("/confirmar/", {"token": primero}).status_code, 302)
        self.assertEqual(self.subir([comprobante(numero=2, fecha="2026-10-03")],
                                   periodo="2026-10").status_code, 302)
        segundo = self.navegador.session["preview"]["token"]
        self.assertEqual(self.navegador.post("/confirmar/", {"token": segundo}).status_code, 302)
        self.assertEqual(RepositorioDjango().consultar_comprobantes("2026-09")["numero"].tolist(), [101])
        self.assertEqual(RepositorioDjango().consultar_comprobantes("2026-10")["numero"].tolist(), [2])

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
