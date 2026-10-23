"""Registra la vigencia observable antes de cambiar su criterio de cálculo."""

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


class TestVigenciaObservacionesActual(unittest.TestCase):
    def test_conflicto_de_dos_archivos_oculta_observacion_de_venta_vigente_y_del_primer_conflicto(self):
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
            self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["4"])

    def test_archivo_totalmente_rechazado_oculta_observacion_de_venta_vigente(self):
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
            self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["3"])

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
