"""Contrato observable de la persistencia SQLite anterior al repositorio."""

import sqlite3
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import pandas as pd

from automatizador.database import (
    consultar_comprobantes,
    consultar_importaciones,
    consultar_totales,
    crear_tabla,
    reemplazar_periodos,
)
from automatizador.validaciones import validar_comprobantes
from tests.helpers import comprobante, directorio_temporal


def lote(cliente, periodo, *filas):
    aceptados, rechazados = validar_comprobantes(pd.DataFrame(filas), periodo)
    return {
        "cliente": cliente,
        "periodo": periodo,
        "comprobantes": aceptados,
        "rechazados": rechazados,
        "archivo_origen": f"{cliente}.csv",
    }


class TestCaracterizacionSQLite(unittest.TestCase):
    def test_reemplaza_cliente_periodo_y_conserva_historial_y_otros_clientes(self):
        with directorio_temporal() as carpeta:
            base = Path(carpeta) / "comprobantes.db"
            crear_tabla(base)
            reemplazar_periodos([
                lote("Cliente Sintético Uno", "2026-09", comprobante(numero=1)),
                lote("Cliente Sintético Dos", "2026-09", comprobante(numero=2)),
                lote("Cliente Sintético Uno", "2026-10", comprobante(fecha="2026-10-03", numero=3)),
            ], base)
            reemplazar_periodos([
                lote("Cliente Sintético Uno", "2026-09", comprobante(numero=4)),
            ], base)

            actual = consultar_comprobantes(base)
            self.assertEqual(set(actual["numero"]), {2, 3, 4})
            historial = consultar_importaciones(base)
            self.assertEqual(len(historial), 4)
            self.assertEqual(historial.iloc[0]["cliente"], "Cliente Sintético Uno")
            self.assertEqual(historial.iloc[0]["periodo"], "2026-09")
            self.assertEqual(historial.iloc[0]["aceptados"], 1)
            with closing(sqlite3.connect(base)) as conexion:
                centavos = conexion.execute(
                    "SELECT total_centavos FROM comprobantes WHERE cliente = ? AND periodo = ?",
                    ("Cliente Sintético Uno", "2026-09"),
                ).fetchone()[0]
            self.assertEqual(centavos, 12100000)

    def test_un_lote_fallido_revierte_todos_los_reemplazos(self):
        with directorio_temporal() as carpeta:
            base = Path(carpeta) / "comprobantes.db"
            crear_tabla(base)
            reemplazar_periodos([lote("Cliente Sintético Uno", "2026-09", comprobante(numero=1))], base)
            valido = lote("Cliente Sintético Uno", "2026-09", comprobante(numero=2))
            duplicado = lote("Cliente Sintético Dos", "2026-09", comprobante(numero=3))
            duplicado["comprobantes"] = pd.concat([duplicado["comprobantes"]] * 2, ignore_index=True)

            with self.assertRaises(sqlite3.IntegrityError):
                reemplazar_periodos([valido, duplicado], base)

            self.assertEqual(consultar_comprobantes(base)["numero"].tolist(), [1])
            self.assertEqual(len(consultar_importaciones(base)), 1)

    def test_importes_persistidos_en_centavos_y_totales_con_signo_de_nc(self):
        with directorio_temporal() as carpeta:
            base = Path(carpeta) / "comprobantes.db"
            crear_tabla(base)
            reemplazar_periodos([lote(
                "Cliente Sintético", "2026-09",
                comprobante(numero=1, neto_gravado="0.20", iva="0.04", total="0.24"),
                comprobante(numero=2, tipo_comprobante="NC A", neto_gravado="0.10", iva="0.02", total="0.12"),
            )], base)

            with closing(sqlite3.connect(base)) as conexion:
                centavos = conexion.execute(
                    "SELECT neto_gravado_centavos, iva_centavos, total_centavos FROM comprobantes ORDER BY numero"
                ).fetchall()
            self.assertEqual(centavos, [(20, 4, 24), (10, 2, 12)])
            self.assertEqual(consultar_totales(base, "2026-09"), {
                "neto_gravado": Decimal("0.10"), "iva": Decimal("0.02"), "total": Decimal("0.12"),
            })
