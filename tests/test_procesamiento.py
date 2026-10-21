import unittest
from decimal import Decimal
from pathlib import Path

import pandas as pd

from automatizador.procesamiento import ResultadoProcesamiento, procesar
from tests.helpers import ROOT, comprobante, directorio_temporal


class TestProcesamiento(unittest.TestCase):
    def test_devuelve_metricas_y_reporte_excel(self):
        entrada = ROOT / "ejemplos" / "Cliente Demo Norte.xlsx"
        with directorio_temporal() as carpeta:
            salida = Path(carpeta) / "reporte.xlsx"
            base = Path(carpeta) / "comprobantes.db"
            resultado = procesar(entrada, salida, base, "2026-09")

            self.assertIsInstance(resultado, ResultadoProcesamiento)
            self.assertTrue(resultado.salida.exists())
            self.assertEqual(resultado.filas_validas, len(resultado.comprobantes))
            self.assertEqual(resultado.filas_observadas, len(resultado.errores))
            self.assertEqual(resultado.totales, {
                "neto_gravado": Decimal("150000.00"),
                "iva": Decimal("26250.00"),
                "total": Decimal("176250.00"),
            })
            for importe in resultado.totales.values():
                self.assertIsInstance(importe, Decimal)
                self.assertEqual(importe.as_tuple().exponent, -2)

    def test_totales_suman_centavos_exactos_de_todos_los_clientes_guardados(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            base = carpeta / "comprobantes.db"
            for nombre, neto, iva, total in (
                ("Cliente Sintético Uno", "0.10", "0.02", "0.12"),
                ("Cliente Sintético Dos", "0.20", "0.04", "0.24"),
            ):
                entrada = carpeta / f"{nombre}.csv"
                pd.DataFrame([comprobante(neto_gravado=neto, iva=iva, total=total)]).to_csv(entrada, index=False)
                resultado = procesar(entrada, carpeta / "reporte.xlsx", base, "2026-09")

            self.assertEqual(len(resultado.comprobantes), 2)
            self.assertEqual(resultado.totales, {
                "neto_gravado": Decimal("0.30"), "iva": Decimal("0.06"), "total": Decimal("0.36"),
            })
            for importe in resultado.totales.values():
                self.assertIsInstance(importe, Decimal)

    def test_periodo_sin_comprobantes_devuelve_totales_decimales(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            entrada = carpeta / "Cliente Sintético.csv"
            pd.DataFrame([comprobante(fecha="2026-10-03")]).to_csv(entrada, index=False)
            resultado = procesar(entrada, carpeta / "reporte.xlsx", carpeta / "comprobantes.db", "2026-09")

            self.assertEqual(resultado.filas_validas, 0)
            self.assertEqual(resultado.filas_observadas, 1)
            for importe in resultado.totales.values():
                self.assertIsInstance(importe, Decimal)
                self.assertEqual(importe, Decimal("0.00"))
                self.assertEqual(importe.as_tuple().exponent, -2)


if __name__ == "__main__":
    unittest.main()
