import unittest
from decimal import Decimal
from pathlib import Path

import pandas as pd

from automatizador.procesamiento import ResultadoProcesamiento, previsualizar, procesar
from tests.helpers import ROOT, comprobante, directorio_temporal


class TestProcesamiento(unittest.TestCase):
    def test_informa_operaciones_reemplazadas_y_conservadas(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            entrada = carpeta / "Cliente Sintético.csv"
            base = carpeta / "comprobantes.db"
            pd.DataFrame([comprobante(numero=1, operacion="compras")]).to_csv(entrada, index=False)
            procesar(entrada, carpeta / "reporte.xlsx", base, "2026-09")
            pd.DataFrame([comprobante(numero=2, operacion="ventas")]).to_csv(entrada, index=False)
            resultado = procesar(entrada, carpeta / "reporte.xlsx", base, "2026-09")
            self.assertEqual(resultado.operaciones_reemplazadas, ("Cliente Sintético: ventas",))
            self.assertEqual(resultado.operaciones_conservadas, ("Cliente Sintético: compras",))

    def test_conflicto_en_carpeta_aparece_en_vista_previa_y_continua_otro_cliente(self):
        with directorio_temporal() as carpeta:
            carpeta = Path(carpeta)
            entradas = carpeta / "entradas"
            entradas.mkdir()
            pd.DataFrame([comprobante(numero=1)]).to_csv(entradas / "Cliente Sintético.csv", index=False)
            pd.DataFrame([comprobante(numero=2)]).to_excel(entradas / "Cliente Sintético.xlsx", index=False)
            pd.DataFrame([comprobante(numero=3)]).to_csv(entradas / "Otro Cliente.csv", index=False)
            vista = previsualizar(entradas, "2026-09")
            self.assertEqual(vista.filas_validas, 1)
            self.assertEqual(vista.filas_observadas, 2)
            self.assertEqual([a.aplicar for a in vista.archivos], [False, False, True])
            resultado = procesar(entradas, carpeta / "reporte.xlsx", carpeta / "comprobantes.db", "2026-09")
            self.assertEqual(resultado.comprobantes["numero"].tolist(), [3])
            self.assertEqual(resultado.filas_observadas, 2)
            self.assertTrue(all("Conflicto en el lote" in motivo for motivo in resultado.errores["motivo"]))
            self.assertEqual(len(resultado.conflictos), 2)

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
