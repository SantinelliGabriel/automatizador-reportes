import unittest
from pathlib import Path

import pandas as pd

from automatizador.vencimientos import cargar_calendario, proximos_vencimientos, terminacion
from tests.helpers import directorio_temporal


class TestVencimientos(unittest.TestCase):
    def test_carga_aliases_y_normaliza_calendario_csv(self):
        with directorio_temporal() as carpeta:
            ruta = Path(carpeta) / "calendario.csv"
            pd.DataFrame([{
                "Obligación": "IVA",
                "Periodo": "2026-09",
                "Terminación CUIT": "0-3",
                "Vencimiento": "15/10/2026",
                "Fuente": "https://ejemplo.invalid/calendario",
            }]).to_csv(ruta, index=False)

            calendario = cargar_calendario(ruta)

        self.assertEqual(calendario.loc[0, "impuesto"], "IVA")
        self.assertEqual(calendario.loc[0, "terminacion_cuit"], "0-3")
        self.assertEqual(str(calendario.loc[0, "fecha_vencimiento"]), "2026-10-15")
        self.assertEqual(calendario.loc[0, "fuente_oficial"], "https://ejemplo.invalid/calendario")

    def test_rechaza_columnas_faltantes_y_fechas_invalidas(self):
        with directorio_temporal() as carpeta:
            ruta = Path(carpeta) / "calendario.csv"
            pd.DataFrame([{"Impuesto": "IVA"}]).to_csv(ruta, index=False)
            with self.assertRaisesRegex(ValueError, "El calendario requiere estas columnas"):
                cargar_calendario(ruta)

            pd.DataFrame([{
                "impuesto": "IVA", "periodo": "2026-09", "terminacion_cuit": "0",
                "fecha_vencimiento": "no es fecha",
            }]).to_csv(ruta, index=False)
            with self.assertRaisesRegex(ValueError, "fechas de vencimiento inválidas"):
                cargar_calendario(ruta)

    def test_terminacion_valida_cuit_y_rechaza_longitud_incorrecta(self):
        self.assertEqual(terminacion("20-12345678-9"), "9")
        with self.assertRaisesRegex(ValueError, "CUIT inválida"):
            terminacion("12345")

    def test_filtra_por_digito_y_ventana_y_ordena_por_fecha(self):
        calendario = pd.DataFrame([
            {"impuesto": "Ganancias", "periodo": "2026-09", "terminacion_cuit": "TODAS", "fecha_vencimiento": pd.Timestamp("2026-10-25").date(), "fuente_oficial": ""},
            {"impuesto": "IVA", "periodo": "2026-09", "terminacion_cuit": "8-9", "fecha_vencimiento": pd.Timestamp("2026-10-15").date(), "fuente_oficial": "ARCA"},
            {"impuesto": "IVA", "periodo": "2026-09", "terminacion_cuit": "0-3", "fecha_vencimiento": pd.Timestamp("2026-10-20").date(), "fuente_oficial": "ARCA"},
            {"impuesto": "IVA", "periodo": "2026-09", "terminacion_cuit": "9", "fecha_vencimiento": pd.Timestamp("2026-11-20").date(), "fuente_oficial": "ARCA"},
        ])
        clientes = [
            {"cliente": "Cliente Nueve", "cuit": "20-12345678-9"},
            {"cliente": "Cliente Cuatro", "cuit": "20-12345678-4"},
        ]

        resultado = proximos_vencimientos(clientes, calendario, desde="2026-10-10", dias=20)

        self.assertEqual(
            list(zip(resultado["cliente"], resultado["impuesto"])),
            [("Cliente Nueve", "IVA"), ("Cliente Cuatro", "Ganancias"), ("Cliente Nueve", "Ganancias")],
        )
        self.assertEqual(resultado["dias_restantes"].tolist(), [5, 15, 15])

    def test_sin_vencimientos_devuelve_tabla_con_columnas_estables(self):
        calendario = pd.DataFrame([{
            "impuesto": "IVA", "periodo": "2026-09", "terminacion_cuit": "0",
            "fecha_vencimiento": pd.Timestamp("2026-12-01").date(),
        }])

        resultado = proximos_vencimientos(
            [{"cliente": "Cliente", "cuit": "20-12345678-9"}],
            calendario,
            desde="2026-10-10",
            dias=10,
        )

        self.assertTrue(resultado.empty)
        self.assertIn("dias_restantes", resultado.columns)


if __name__ == "__main__":
    unittest.main()
