import unittest

import pandas as pd

from automatizador.validaciones import validar_comprobantes
from tests.helpers import comprobante


class TestValidacionComprobantes(unittest.TestCase):
    def test_acepta_comprobante_y_alias_de_encabezados(self):
        df = pd.DataFrame([comprobante()]).rename(columns={
            "fecha": "Fecha comprobante", "tipo_comprobante": "Tipo",
            "punto_venta": "Pto. Venta", "razon_social": "Razón Social",
        })
        aceptados, rechazados = validar_comprobantes(df, "2026-09")
        self.assertEqual(len(aceptados), 1)
        self.assertTrue(rechazados.empty)

    def test_rechaza_cuit_total_y_periodo_en_observaciones(self):
        df = pd.DataFrame([comprobante(cuit="20123456789", total=120000, fecha="2026-08-03")])
        aceptados, rechazados = validar_comprobantes(df, "2026-09")
        self.assertTrue(aceptados.empty)
        self.assertIn("CUIT inválido", rechazados.iloc[0]["motivo"])
        self.assertIn("período", rechazados.iloc[0]["motivo"])
        self.assertIn("total", rechazados.iloc[0]["motivo"])

    def test_marca_segunda_ocurrencia_duplicada(self):
        aceptados, rechazados = validar_comprobantes(pd.DataFrame([comprobante(), comprobante()]), "2026-09")
        self.assertEqual(len(aceptados), 1)
        self.assertIn("duplicado", rechazados.iloc[0]["motivo"])

    def test_rechaza_alicuota_no_admitida(self):
        aceptados, rechazados = validar_comprobantes(pd.DataFrame([comprobante(alicuota=19)]), "2026-09")
        self.assertTrue(aceptados.empty)
        self.assertIn("Alícuota inválida", rechazados.iloc[0]["motivo"])
