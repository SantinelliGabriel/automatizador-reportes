"""Comprueba la vigencia de observaciones tras intentos aplicados y fallidos."""

import sqlite3
import unittest
from pathlib import Path

import pandas as pd

from automatizador.repositorio import RepositorioSQLite
from automatizador.validaciones import validar_comprobantes
from tests.helpers import comprobante, directorio_temporal


CLIENTE = "Cliente Sintético"
PERIODO = "2026-09"


def lote(nombre, *filas):
    aceptados, rechazados = validar_comprobantes(pd.DataFrame(filas), PERIODO)
    return {
        "cliente": CLIENTE,
        "periodo": PERIODO,
        "comprobantes": aceptados,
        "rechazados": rechazados,
        "archivo_origen": nombre,
        "aplicar": not aceptados.empty,
    }


class TestVigenciaObservaciones(unittest.TestCase):
    def test_conflicto_conserva_observacion_vigente_y_ambos_intentos(self):
        with directorio_temporal() as carpeta:
            repo = RepositorioSQLite(Path(carpeta) / "comprobantes.db")
            repo.reemplazar_periodos([lote(
                "ventas-inicial.csv",
                comprobante(numero=1),
                comprobante(numero=2, cuit="CUIT sintético inválido"),
            )])
            repo.reemplazar_periodos([
                lote("ventas-conflicto-a.csv", comprobante(numero=3)),
                lote("ventas-conflicto-b.csv", comprobante(numero=4)),
            ])

            self.assertEqual(repo.consultar_comprobantes(PERIODO)["numero"].tolist(), [1])
            self.assertEqual(repo.consultar_importaciones()["operaciones"].tolist(),
                             ["ventas", "ventas", "ventas"])
            self.assertEqual(repo.consultar_importaciones()["aceptados"].tolist(), [0, 0, 1])
            self.assertEqual(repo.consultar_importaciones()["estado"].tolist(), [
                "no aplicada: conflicto", "no aplicada: conflicto", "aplicada",
            ])
            self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["2", "3", "4"])

    def test_archivo_totalmente_rechazado_conserva_observacion_vigente(self):
        with directorio_temporal() as carpeta:
            repo = RepositorioSQLite(Path(carpeta) / "comprobantes.db")
            repo.reemplazar_periodos([lote(
                "ventas-inicial.csv",
                comprobante(numero=1),
                comprobante(numero=2, cuit="CUIT sintético inválido"),
            )])
            repo.reemplazar_periodos([lote(
                "ventas-rechazadas.csv", comprobante(numero=3, cuit="CUIT sintético inválido"),
            )])

            self.assertEqual(repo.consultar_comprobantes(PERIODO)["numero"].tolist(), [1])
            self.assertEqual(repo.consultar_importaciones()["operaciones"].tolist(), ["", "ventas"])
            self.assertEqual(repo.consultar_importaciones()["aceptados"].tolist(), [0, 1])
            self.assertEqual(repo.consultar_importaciones()["estado"].tolist(), [
                "no aplicada: sin filas aceptadas", "aplicada",
            ])
            self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["2", "3"])

    def test_reimportar_ventas_conserva_compras_y_sus_observaciones(self):
        with directorio_temporal() as carpeta:
            repo = RepositorioSQLite(Path(carpeta) / "comprobantes.db")
            repo.reemplazar_periodos([lote(
                "ventas-inicial.csv", comprobante(numero=1),
                comprobante(numero=2, cuit="CUIT sintético inválido"),
            )])
            repo.reemplazar_periodos([lote(
                "compras.csv", comprobante(numero=3, operacion="compras"),
                comprobante(numero=4, operacion="compras", cuit="CUIT sintético inválido"),
            )])
            repo.reemplazar_periodos([lote(
                "ventas-nuevas.csv", comprobante(numero=5),
                comprobante(numero=6, cuit="CUIT sintético inválido"),
            )])

            self.assertEqual(set(repo.consultar_comprobantes(PERIODO)["numero"]), {3, 5})
            self.assertEqual(repo.consultar_importaciones()["operaciones"].tolist(),
                             ["ventas", "compras", "ventas"])
            self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["4", "6"])

    def test_historial_heredado_sin_operaciones_usa_comprobantes_vigentes(self):
        with directorio_temporal() as carpeta:
            base = Path(carpeta) / "comprobantes.db"
            repo = RepositorioSQLite(base)
            repo.reemplazar_periodos([lote("primero.csv", comprobante(numero=1),
                                         comprobante(numero=2, cuit="CUIT sintético inválido"))])
            repo.reemplazar_periodos([lote("despues.csv", comprobante(numero=3,
                                         cuit="CUIT sintético inválido"))])
            conexion = sqlite3.connect(base)
            try:
                conexion.execute("UPDATE importaciones SET operaciones = '' WHERE aceptados > 0")
                conexion.commit()
            finally:
                conexion.close()
            self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["2", "3"])

    def test_dos_operaciones_en_paralelo_y_primer_intento_fallido(self):
        with directorio_temporal() as carpeta:
            repo = RepositorioSQLite(Path(carpeta) / "comprobantes.db")
            repo.reemplazar_periodos([lote("compra-fallida.csv", comprobante(
                numero=1, operacion="compras", cuit="CUIT sintético inválido"))])
            repo.reemplazar_periodos([lote("ventas.csv", comprobante(numero=2), comprobante(
                numero=3, cuit="CUIT sintético inválido"))])
            self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["1", "3"])

    def test_observacion_sin_operacion_vigente_hasta_aplicacion_siguiente(self):
        with directorio_temporal() as carpeta:
            repo = RepositorioSQLite(Path(carpeta) / "comprobantes.db")
            sin_operacion = comprobante(numero=1, cuit="CUIT sintético inválido")
            sin_operacion.pop("operacion")
            repo.reemplazar_periodos([lote("fallido.csv", sin_operacion)])
            self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["1"])
            repo.reemplazar_periodos([lote("aplicado.csv", comprobante(numero=2))])
            self.assertTrue(repo.consultar_observaciones(PERIODO).empty)
