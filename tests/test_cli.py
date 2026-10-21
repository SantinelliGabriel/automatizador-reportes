import unittest
from pathlib import Path

import pandas as pd

from automatizador.cli import main
from tests.helpers import comprobante, directorio_temporal


class TestConsola(unittest.TestCase):
    def test_muestra_totales_decimales_con_dos_decimales(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            entrada = carpeta / "Cliente Sintético.csv"
            pd.DataFrame([
                comprobante(numero=1, neto_gravado="0.10", iva="0.02", total="0.12"),
                comprobante(numero=2, neto_gravado="0.20", iva="0.04", total="0.24"),
            ]).to_csv(entrada, index=False)
            salida = carpeta / "reporte.xlsx"
            with self.assertLogs(level="INFO") as registros:
                codigo = main([
                    "--input", str(entrada), "--output", str(salida),
                    "--database", str(carpeta / "comprobantes.db"), "--period", "2026-09",
                ])

            self.assertEqual(codigo, 0)
            self.assertTrue(salida.exists())
            resumen = next(linea for linea in registros.output if "Filas válidas:" in linea)
            self.assertIn("neto_gravado=0.30", resumen)
            self.assertIn("iva=0.06", resumen)
            self.assertIn("total=0.36", resumen)
            self.assertNotIn("Decimal(", resumen)


if __name__ == "__main__":
    unittest.main()
