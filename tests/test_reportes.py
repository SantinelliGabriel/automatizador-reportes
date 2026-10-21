import unittest
from pathlib import Path

import pandas as pd

from automatizador.database import crear_tabla, consultar_comprobantes, reemplazar_periodo
from automatizador.reportes import construir_hojas
from automatizador.validaciones import validar_comprobantes
from tests.helpers import comprobante, directorio_temporal


class TestReportes(unittest.TestCase):
    def test_notas_de_credito_y_debito_ajustan_resumen_y_alicuota(self):
        venta = comprobante()
        nota_credito = comprobante(tipo_comprobante="NC A", numero=102, neto_gravado=10000, iva=2100, total=12100)
        nota_debito = comprobante(tipo_comprobante="ND A", numero=103, neto_gravado=5000, iva=1050, total=6050)
        buenos, malos = validar_comprobantes(
            pd.DataFrame([venta, nota_credito, nota_debito]), "2026-09"
        )
        with directorio_temporal() as carpeta:
            base = Path(carpeta) / "comprobantes.db"
            crear_tabla(base)
            reemplazar_periodo("Cliente Demo", "2026-09", buenos, malos, "demo.xlsx", base)
            detalle, por_cliente, por_alicuota = construir_hojas(consultar_comprobantes(base))
        self.assertEqual(len(detalle), 3)
        self.assertTrue(malos.empty)
        self.assertEqual(por_cliente.iloc[0]["neto_gravado"], 95000)
        self.assertEqual(por_cliente.iloc[0]["iva"], 19950)
        self.assertEqual(por_cliente.iloc[0]["total"], 114950)
        self.assertEqual(por_alicuota.iloc[0]["neto_gravado"], 95000)
        self.assertEqual(por_alicuota.iloc[0]["iva"], 19950)
