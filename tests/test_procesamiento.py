import unittest
from pathlib import Path

from automatizador.procesamiento import ResultadoProcesamiento, procesar
from tests.helpers import ROOT, directorio_temporal


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
            self.assertIn("iva", resultado.totales)


if __name__ == "__main__":
    unittest.main()
