
import unittest

import pandas as pd

from main import validar_ventas


class TestValidacionesVentas(unittest.TestCase):

    
    
    def test_rechaza_precio_no_numerico(self):
        ventas = self.ventas.copy()
        ventas["precio_unitario"] = ventas["precio_unitario"].astype(object)
        ventas.loc[0, "precio_unitario"] = "abc"

        with self.assertRaisesRegex(
            ValueError,
            "no numéricos",
        ):
            validar_ventas(ventas)

    def test_rechaza_unidades_decimales(self):
        ventas = self.ventas.copy()
        ventas["unidades"] = ventas["unidades"].astype(float)
        ventas.loc[0, "unidades"] = 2.5

        with self.assertRaisesRegex(
            ValueError,
            "números enteros",
        ):
            validar_ventas(ventas)

    def test_acepta_precio_cero(self):
        self.ventas.loc[0, "precio_unitario"] = 0

        resultado = validar_ventas(self.ventas)

        self.assertEqual(resultado.loc[0, "precio_unitario"], 0)

    def setUp(self):
        # Datos correctos para reutilizar en las pruebas
        self.ventas = pd.DataFrame({
            "producto": ["Teclado", "Mouse"],
            "unidades": [5, 8],
            "precio_unitario": [12000, 7500],
        })

    def test_acepta_datos_correctos(self):
        resultado = validar_ventas(self.ventas.copy())
        self.assertEqual(len(resultado), 2)

    def test_rechaza_precio_negativo(self):
        self.ventas.loc[0, "precio_unitario"] = -12000

        with self.assertRaisesRegex(ValueError, "precios no pueden ser negativos"):
            validar_ventas(self.ventas)

    def test_rechaza_unidades_cero(self):
        self.ventas.loc[0, "unidades"] = 0

        with self.assertRaisesRegex(ValueError, "unidades deben ser mayores que cero"):
            validar_ventas(self.ventas)

    def test_rechaza_columna_faltante(self):
        ventas = self.ventas.drop(columns=["producto"])

        with self.assertRaisesRegex(ValueError, "Faltan estas columnas"):
            validar_ventas(ventas)

    def test_rechaza_celdas_vacias(self):
        self.ventas.loc[0, "producto"] = None

        with self.assertRaisesRegex(ValueError, "celdas vacías"):
            validar_ventas(self.ventas)


if __name__ == "__main__":
    unittest.main(verbosity=2)
