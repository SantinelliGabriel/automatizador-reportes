import sqlite3
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import pandas as pd

from automatizador.database import consultar_comprobantes, crear_tabla, reemplazar_periodo
from automatizador.decimales import normalizar_decimal
from automatizador.reportes import construir_hojas
from automatizador.validaciones import validar_comprobantes
from tests.helpers import comprobante, directorio_temporal


class TestDecimales(unittest.TestCase):
    def test_una_forma_canonica_y_escalas_maximas(self):
        self.assertEqual({normalizar_decimal(valor, "alicuota") for valor in (21, "21.0", "21.00")}, {"21"})
        self.assertEqual(normalizar_decimal("10,50%", "alicuota"), "10.5")
        self.assertEqual(normalizar_decimal("1000.250000", "tipo_cambio"), "1000.25")
        with self.assertRaisesRegex(ValueError, "escala máxima de 1"):
            normalizar_decimal("10.51", "alicuota")
        with self.assertRaisesRegex(ValueError, "escala máxima de 8"):
            normalizar_decimal("1.123456789", "tipo_cambio")

    def test_exceso_de_escala_queda_observado_sin_redondeo(self):
        filas = [
            comprobante(numero=1, alicuota="21.01"),
            comprobante(numero=2, moneda="USD", tipo_cambio="1.123456789"),
            comprobante(numero=3, detalle_alicuotas=[{
                "alicuota": "10.55", "neto_gravado": 100, "iva": 10.55,
            }]),
        ]
        aceptados, observados = validar_comprobantes(pd.DataFrame(filas), "2026-09")
        self.assertTrue(aceptados.empty)
        self.assertEqual(len(observados), 3)
        self.assertTrue(observados["motivo"].str.contains("escala máxima").all())

    def test_sqlite_guarda_texto_decimal_y_resumen_suma_decimal(self):
        with directorio_temporal() as carpeta:
            base = Path(carpeta) / "comprobantes.db"
            crear_tabla(base)
            filas = [
                comprobante(numero=1, neto_gravado="0.10", alicuota="0", iva="0", total="0.10"),
                comprobante(numero=2, neto_gravado="0.20", alicuota="0.0", iva="0", total="0.20"),
                comprobante(numero=3, tipo_comprobante="NC A", neto_gravado="0.05",
                            alicuota="0.00", iva="0", total="0.05"),
            ]
            aceptados, observados = validar_comprobantes(pd.DataFrame(filas), "2026-09")
            self.assertTrue(observados.empty)
            reemplazar_periodo("Cliente Sintético", "2026-09", aceptados, observados, "demo.csv", base)
            with closing(sqlite3.connect(base)) as conexion:
                self.assertEqual(conexion.execute(
                    "SELECT typeof(alicuota), alicuota, typeof(tipo_cambio), tipo_cambio "
                    "FROM comprobantes LIMIT 1"
                ).fetchone(), ("text", "0", "text", "1"))
            comprobantes = consultar_comprobantes(base)
            _, cliente, tasa = construir_hojas(comprobantes)
            self.assertEqual(cliente.iloc[0]["neto_gravado"], Decimal("0.25"))
            self.assertEqual(cliente.iloc[0]["total"], Decimal("0.25"))
            self.assertEqual(tasa.iloc[0]["neto_gravado"], Decimal("0.25"))
            for valor in (cliente.iloc[0]["neto_gravado"], cliente.iloc[0]["total"],
                          tasa.iloc[0]["neto_gravado"], tasa.iloc[0]["alicuota"]):
                self.assertIsInstance(valor, Decimal)
