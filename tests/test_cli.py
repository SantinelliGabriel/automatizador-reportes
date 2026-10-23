import unittest
import io
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd

from automatizador.cli import main
from tests.helpers import comprobante, directorio_temporal
from tests.test_migracion_decimal import base_v1


class TestConsola(unittest.TestCase):
    def test_history_muestra_estado_derivado(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            entrada = carpeta / "Cliente Sintético.csv"
            base = carpeta / "comprobantes.db"
            pd.DataFrame([comprobante()]).to_csv(entrada, index=False)
            self.assertEqual(main(["--input", str(entrada), "--output", str(carpeta / "salida.xlsx"),
                                   "--database", str(base), "--period", "2026-09"]), 0)
            salida = io.StringIO()
            with redirect_stdout(salida):
                self.assertEqual(main(["--database", str(base), "--history"]), 0)
            self.assertIn("estado", salida.getvalue())
            self.assertIn("aplicada", salida.getvalue())

    def test_informa_conflicto_de_operacion_en_lote(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            entradas = carpeta / "entradas"
            entradas.mkdir()
            pd.DataFrame([comprobante(numero=1)]).to_csv(entradas / "Cliente Sintético.csv", index=False)
            pd.DataFrame([comprobante(numero=2)]).to_excel(entradas / "Cliente Sintético.xlsx", index=False)
            with self.assertLogs(level="INFO") as registros:
                codigo = main([
                    "--input", str(entradas), "--output", str(carpeta / "reporte.xlsx"),
                    "--database", str(carpeta / "comprobantes.db"), "--period", "2026-09",
                ])
            self.assertEqual(codigo, 2)
            self.assertTrue(any("Conflicto en el lote:" in linea for linea in registros.output))
            self.assertTrue(any("Operaciones reemplazadas: ninguna" in linea for linea in registros.output))

    def test_base_nueva_no_anuncia_migracion_ni_crea_respaldo(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            entrada = carpeta / "Cliente Sintético.csv"
            pd.DataFrame([comprobante()]).to_csv(entrada, index=False)
            base = carpeta / "nueva.db"
            with self.assertLogs(level="INFO") as registros:
                codigo = main([
                    "--input", str(entrada), "--output", str(carpeta / "reporte.xlsx"),
                    "--database", str(base), "--period", "2026-09",
                ])
            self.assertEqual(codigo, 0)
            self.assertFalse(any("Base SQLite migrada" in linea for linea in registros.output))
            self.assertEqual(list(carpeta.glob("*.bak*.db")), [])

    def test_avisa_migracion_y_ruta_del_respaldo(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            base = base_v1(carpeta)
            entrada = carpeta / "Cliente Sintético.csv"
            pd.DataFrame([comprobante()]).to_csv(entrada, index=False)
            with self.assertLogs(level="INFO") as registros:
                codigo = main([
                    "--input", str(entrada), "--output", str(carpeta / "reporte.xlsx"),
                    "--database", str(base), "--period", "2026-09",
                ])
            self.assertEqual(codigo, 0)
            self.assertTrue(any(
                "Base SQLite migrada de versión 1 a 3" in linea
                and str(carpeta / "legacy.v1.bak.db") in linea
                for linea in registros.output
            ))

    def test_crea_directorios_inexistentes_para_reporte_y_base(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            entrada = carpeta / "Cliente Sintético.csv"
            pd.DataFrame([comprobante()]).to_csv(entrada, index=False)
            salida = carpeta / "resultados" / "reporte.xlsx"
            base = carpeta / "datos" / "comprobantes.db"
            self.assertFalse(salida.parent.exists())
            self.assertFalse(base.parent.exists())

            codigo = main([
                "--input", str(entrada), "--output", str(salida),
                "--database", str(base), "--period", "2026-09",
            ])

            self.assertEqual(codigo, 0)
            self.assertTrue(salida.is_file())
            self.assertTrue(base.is_file())
            self.assertEqual(len(pd.read_excel(salida, sheet_name="Comprobantes")), 1)

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
