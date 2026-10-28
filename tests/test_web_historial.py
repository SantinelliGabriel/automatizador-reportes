"""Pantallas de lectura, descarga consolidada y modo demo."""

import io
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from automatizador.cli import main as cli_main
from tests.django_utils import limpiar_bd, preparar_bd

from django.contrib.auth.models import User
from django.test import Client

from automatizador.procesamiento import confirmar_importacion, generar_informe, previsualizar
from automatizador.repositorio import RepositorioSQLite
from tests.test_contrato_repositorios import lote
from tests.helpers import comprobante
from tests.helpers import directorio_temporal
from web.comprobantes.models import Cliente, Comprobante, Importacion, Observacion
from web.comprobantes.repositorio import RepositorioDjango


class TestLecturasWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preparar_bd()

    def setUp(self):
        limpiar_bd()
        self.usuario = User.objects.create_user("operador", password="clave-sintetica", is_staff=True)
        self.navegador = Client()
        self.navegador.force_login(self.usuario)
        self.fuente = Path(__file__).resolve().parents[1] / "ejemplos" / "Cliente Demo Norte.xlsx"

    def importar(self):
        plan = previsualizar(self.fuente, "2026-09", "estandar", "mixto", cliente="Cliente Demo Norte")
        confirmar_importacion(plan, RepositorioDjango())

    def test_login_obligatorio_y_pantallas_vacias(self):
        anonimo = Client()
        for ruta in ("/historial/", "/observaciones/", "/informes/2026-09/"):
            with self.subTest(ruta=ruta):
                respuesta = anonimo.get(ruta)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn("/login/", respuesta["Location"])
        for ruta, texto in (("/historial/", "Todavía no hay importaciones"),
                            ("/observaciones/", "No hay observaciones vigentes"),
                            ("/informes/2026-09/", "todavía no hay comprobantes")):
            respuesta = self.navegador.get(ruta)
            self.assertEqual(respuesta.status_code, 200)
            self.assertIn(texto, respuesta.content.decode())
            self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertIn("Todavía no hay clientes", self.navegador.get("/").content.decode())

    def test_historial_muestra_columnas_estado_y_orden(self):
        self.importar()
        cliente = Cliente.objects.get()
        Importacion.objects.create(cliente=cliente, periodo="2026-09", archivo_origen="fallido.csv",
                                  rechazados=1, operaciones="ventas")
        conflicto = Importacion.objects.create(cliente=cliente, periodo="2026-09", archivo_origen="conflicto.csv",
                                               rechazados=1, operaciones="ventas")
        Observacion.objects.create(importacion=conflicto, motivo="Conflicto en el lote: archivo duplicado",
                                   datos={"operacion": "ventas"})
        respuesta = self.navegador.get("/historial/")
        for texto in ("Cliente Demo Norte", "2026-09", "fallido.csv", "operaciones", "no aplicada: sin filas aceptadas",
                      "no aplicada: conflicto", "aplicada", "Informe consolidado del período: todos los clientes"):
            self.assertIn(texto.casefold(), respuesta.content.decode().casefold())
        self.assertLess(respuesta.content.index(b"conflicto.csv"), respuesta.content.index(b"fallido.csv"))

    def test_observaciones_vigentes_filtra_cliente_y_operacion(self):
        self.importar()
        cliente = Cliente.objects.get()
        fallida = Importacion.objects.create(cliente=cliente, periodo="2026-09", archivo_origen="errores.csv",
                                             rechazados=1, operaciones="ventas")
        Observacion.objects.create(importacion=fallida, fila_excel="3", motivo="Dato sintético inválido",
                                   datos={"operacion": "ventas"})
        respuesta = self.navegador.get("/observaciones/?periodo=2026-09&cliente=Cliente%20Demo%20Norte&operacion=ventas")
        self.assertIn("Dato sintético inválido", respuesta.content.decode())
        self.assertIn("errores.csv", respuesta.content.decode())
        self.assertIn("3", respuesta.content.decode())
        self.assertNotIn("Dato sintético inválido", self.navegador.get("/observaciones/?operacion=compras").content.decode())
        self.assertEqual(self.navegador.get("/observaciones/?periodo=2026-13").status_code, 400)
        self.assertEqual(self.navegador.get("/observaciones/?operacion=otra").status_code, 400)

    def test_excel_consolidado_igual_al_nucleo_y_temporal_limpio(self):
        self.importar()
        with directorio_temporal() as temporal:
            plan = previsualizar(self.fuente, "2026-09", "estandar", "mixto", cliente="Cliente Demo Norte")
            sqlite = RepositorioSQLite(Path(temporal) / "base.db")
            confirmar_importacion(plan, sqlite)
            esperado = Path(temporal) / "cli.xlsx"
            generar_informe("2026-09", esperado, sqlite)
            respuesta = self.navegador.get("/informes/2026-09/")
            self.assertEqual(respuesta.status_code, 200)
            self.assertIn("no-store", respuesta["Cache-Control"])
            self.assertEqual(respuesta["Content-Disposition"],
                             'attachment; filename="informe_consolidado_2026-09.xlsx"')
            with pd.ExcelFile(io.BytesIO(respuesta.content)) as libro_web, pd.ExcelFile(esperado) as libro_cli:
                self.assertEqual(libro_web.sheet_names, libro_cli.sheet_names)
                for hoja in libro_cli.sheet_names:
                    pd.testing.assert_frame_equal(pd.read_excel(libro_web, hoja), pd.read_excel(libro_cli, hoja))
        self.assertEqual(self.navegador.get("/informes/2026-13/").status_code, 400)

    def test_excel_con_nc_nd_coincide_con_cli_y_ajusta_iva(self):
        filas = [comprobante(numero=1, neto_gravado="0.20", iva="0.04", total="0.24"),
                 comprobante(numero=2, tipo_comprobante="NC A", neto_gravado="0.10", iva="0.02", total="0.12"),
                 comprobante(numero=3, tipo_comprobante="ND A", neto_gravado="0.10", iva="0.02", total="0.12")]
        datos = lote("notas.csv", *filas, cliente="notas")
        RepositorioDjango().reemplazar_periodos([datos])
        with directorio_temporal() as temporal:
            entrada = Path(temporal) / "notas.csv"
            pd.DataFrame(filas).to_csv(entrada, index=False)
            esperado = Path(temporal) / "cli.xlsx"
            self.assertEqual(cli_main(["--input", str(entrada), "--output", str(esperado),
                                       "--database", str(Path(temporal) / "base.db"), "--period", "2026-09"]), 0)
            respuesta = self.navegador.get("/informes/2026-09/")
            with pd.ExcelFile(io.BytesIO(respuesta.content)) as web, pd.ExcelFile(esperado) as cli:
                for hoja in cli.sheet_names:
                    pd.testing.assert_frame_equal(pd.read_excel(web, hoja), pd.read_excel(cli, hoja))
                resumen = pd.read_excel(web, "Resumen por cliente")
                alicuotas = pd.read_excel(web, "IVA por alícuota")
                self.assertEqual(str(resumen.iloc[0]["total"]), "0.24")
                self.assertEqual(str(alicuotas.iloc[0]["iva"]), "0.04")

    def test_vigencia_en_pantalla_escenarios_a_b_c(self):
        repo = RepositorioDjango()
        repo.reemplazar_periodos([lote("ventas-inicial.csv", comprobante(numero=1),
                                        comprobante(numero=2, cuit="CUIT sintético inválido"))])
        repo.reemplazar_periodos([lote("conflicto-a.csv", comprobante(numero=3)),
                                  lote("conflicto-b.csv", comprobante(numero=4))])
        pagina = self.navegador.get("/observaciones/?periodo=2026-09").content.decode()
        for archivo in ("ventas-inicial.csv", "conflicto-a.csv", "conflicto-b.csv"):
            self.assertIn(archivo, pagina)
        self.assertEqual(Comprobante.objects.count(), 1)
        repo.reemplazar_periodos([lote("rechazado.csv", comprobante(numero=5, cuit="CUIT sintético inválido"))])
        self.assertIn("rechazado.csv", self.navegador.get("/observaciones/").content.decode())
        self.assertEqual(Comprobante.objects.count(), 1)
        repo.reemplazar_periodos([lote("compras.csv", comprobante(numero=6, operacion="compras"),
                                        comprobante(numero=7, operacion="compras", cuit="CUIT sintético inválido"))])
        repo.reemplazar_periodos([lote("ventas-nuevas.csv", comprobante(numero=8),
                                        comprobante(numero=9, cuit="CUIT sintético inválido"))])
        pagina = self.navegador.get("/observaciones/?periodo=2026-09").content.decode()
        self.assertIn("compras.csv", pagina)
        self.assertIn("ventas-nuevas.csv", pagina)
        self.assertNotIn("ventas-inicial.csv", pagina)
        self.assertNotIn("rechazado.csv", pagina)
        self.assertEqual(set(Comprobante.objects.values_list("numero", flat=True)), {6, 8})

    def test_temporal_se_elimina_si_falla_generacion(self):
        self.importar()
        rutas = []

        def fallar(periodo, salida, repositorio):
            rutas.append(salida)
            salida.write_bytes(b"sintetico")
            raise ValueError("Error de prueba")

        with patch("web.comprobantes.views.generar_informe", side_effect=fallar):
            with self.assertRaises(ValueError):
                self.navegador.get("/informes/2026-09/")
        self.assertFalse(rutas[0].exists())

