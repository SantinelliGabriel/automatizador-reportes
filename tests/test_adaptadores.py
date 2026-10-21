import unittest

from automatizador.adaptadores import leer_comprobantes
from tests.helpers import ROOT


class TestAdaptadorArca(unittest.TestCase):
    def test_lee_estructura_sintetica_y_observa_varias_alicuotas(self):
        archivo = ROOT / "tests" / "fixtures" / "arca" / "mis_comprobantes_sintetico.csv"
        comprobantes = leer_comprobantes(archivo, "arca", "ventas")

        self.assertEqual(len(comprobantes), 2)
        simple, multialicuota = comprobantes.to_dict("records")
        self.assertEqual(simple["tipo_comprobante"], "A")
        self.assertEqual(simple["numero"], "123")
        self.assertEqual(simple["neto_gravado"], 1000)
        self.assertEqual(simple["iva"], 210)
        self.assertEqual(simple["moneda"], "ARS")
        self.assertEqual(simple["tipo_cambio"], 1)
        self.assertEqual(simple["_error_adaptador"], "")
        self.assertEqual(multialicuota["neto_gravado"], 1500)
        self.assertEqual(multialicuota["iva"], 262.5)
        self.assertEqual(multialicuota["moneda"], "USD")
        self.assertEqual(multialicuota["tipo_cambio"], 1000)
        self.assertIn("varias alícuotas", multialicuota["_error_adaptador"])


if __name__ == "__main__":
    unittest.main()
