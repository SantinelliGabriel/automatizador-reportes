import unittest
from decimal import Decimal

import pandas as pd

from automatizador.validaciones import validar_comprobantes, validar_cuit
from tests.helpers import comprobante
from automatizador.generar_datos_demo import cuit_sintetico


class TestValidacionComprobantes(unittest.TestCase):
    def test_rechaza_alicuota_negativa_y_tipo_de_cambio_no_positivo(self):
        filas = [
            comprobante(numero=1, alicuota="-1"),
            comprobante(numero=2, detalle_alicuotas=[{
                "alicuota": "-1", "neto_gravado": "100.00", "iva": "-1.00",
            }]),
            comprobante(numero=3, moneda="USD", tipo_cambio="0"),
            comprobante(numero=4, moneda="USD", tipo_cambio="-1"),
        ]

        aceptados, rechazados = validar_comprobantes(pd.DataFrame(filas), "2026-09")

        self.assertTrue(aceptados.empty)
        self.assertEqual(len(rechazados), 4)
        self.assertIn("Alícuota inválida", rechazados.iloc[0]["motivo"])
        self.assertIn("Detalle de alícuotas inválido", rechazados.iloc[1]["motivo"])
        self.assertIn("mayor que cero", rechazados.iloc[2]["motivo"])
        self.assertIn("mayor que cero", rechazados.iloc[3]["motivo"])

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

    def test_convierte_moneda_extranjera_a_ars_y_conserva_importes_de_origen(self):
        fila = comprobante(
            neto_gravado=100, iva=21, total=121, moneda="USD", tipo_cambio=1000,
        )
        aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila]), "2026-09")

        self.assertTrue(rechazados.empty)
        self.assertEqual(aceptados.iloc[0]["neto_gravado"], 100000)
        self.assertEqual(aceptados.iloc[0]["iva"], 21000)
        self.assertEqual(aceptados.iloc[0]["total"], 121000)
        self.assertEqual(aceptados.iloc[0]["neto_gravado_origen"], 100)
        self.assertEqual(aceptados.iloc[0]["moneda"], "USD")
        self.assertEqual(aceptados.iloc[0]["tipo_cambio"], 1000)

    def test_rechaza_moneda_extranjera_sin_tipo_de_cambio(self):
        fila = comprobante(moneda="USD", tipo_cambio=None)
        aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila]), "2026-09")

        self.assertTrue(aceptados.empty)
        self.assertIn("Falta el tipo de cambio", rechazados.iloc[0]["motivo"])

    def test_acepta_tolerancia_de_un_centavo_con_redondeo_comercial(self):
        fila = comprobante(neto_gravado="100.03", alicuota="21%", iva="21.02", total="121.05")

        aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila]), "2026-09")

        self.assertEqual(len(aceptados), 1)
        self.assertTrue(rechazados.empty)
        self.assertEqual(aceptados.iloc[0]["neto_gravado"], Decimal("100.03"))

    def test_rechaza_diferencia_de_iva_superior_a_un_centavo(self):
        fila = comprobante(neto_gravado=100.03, iva=21.03, total=121.06)

        aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila]), "2026-09")

        self.assertTrue(aceptados.empty)
        self.assertIn("IVA no coincide", rechazados.iloc[0]["motivo"])

    def test_valida_desglose_de_varias_alicuotas_y_totales(self):
        fila = comprobante(
            neto_gravado=200, alicuota=0, iva=31.5, total=231.5,
            detalle_alicuotas=[
                {"alicuota": 21, "neto_gravado": 100, "iva": 21},
                {"alicuota": 10.5, "neto_gravado": 100, "iva": 10.5},
            ],
        )

        aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila]), "2026-09")

        self.assertEqual(len(aceptados), 1)
        self.assertTrue(rechazados.empty)
        self.assertEqual(aceptados.iloc[0]["alicuota"], 0)
        self.assertEqual(len(aceptados.iloc[0]["detalle_alicuotas"]), 2)
        self.assertEqual(aceptados.iloc[0]["detalle_alicuotas"][1]["alicuota"], 10.5)

    def test_rechaza_detalle_de_alicuotas_malformado_o_inconsistente(self):
        casos = [
            comprobante(detalle_alicuotas="{esto no es json"),
            comprobante(detalle_alicuotas=[{"alicuota": 19, "neto_gravado": 100, "iva": 19}]),
            comprobante(detalle_alicuotas=[{"alicuota": 21, "neto_gravado": 100, "iva": 20}]),
            comprobante(detalle_alicuotas=["no es un objeto"]),
        ]

        aceptados, rechazados = validar_comprobantes(pd.DataFrame(casos), "2026-09")

        self.assertTrue(aceptados.empty)
        self.assertEqual(len(rechazados), len(casos))
        self.assertTrue(rechazados["motivo"].str.contains("Detalle de alícuotas inválido").all())

    def test_reporta_campos_obligatorios_y_encabezados_ambiguos(self):
        with self.assertRaisesRegex(ValueError, "Faltan columnas obligatorias"):
            validar_comprobantes(pd.DataFrame([{"fecha": "2026-09-03"}]), "2026-09")
        with self.assertRaisesRegex(ValueError, "no contiene comprobantes"):
            validar_comprobantes(pd.DataFrame(columns=["fecha"]), "2026-09")

        fila = comprobante()
        fila["Fecha"] = fila["fecha"]
        fila["date"] = fila["fecha"]
        with self.assertRaisesRegex(ValueError, "ambiguos para 'fecha'"):
            validar_comprobantes(pd.DataFrame([fila]), "2026-09")

    def test_rechaza_datos_de_cabecera_invalidos_y_acumula_motivos(self):
        fila = comprobante(
            fecha="fecha inválida", tipo_comprobante="desconocido", punto_venta=0,
            numero="no entero", cuit="123", razon_social=" ", alicuota="abc",
            operacion="ajuste", moneda="PESOS", neto_gravado="NaN",
        )

        aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila]), "2026-09")

        self.assertTrue(aceptados.empty)
        motivo = rechazados.iloc[0]["motivo"]
        for esperado in ("Fecha inválida", "Tipo de comprobante no reconocido", "enteros válidos", "CUIT inválido", "Razón social vacía", "Alícuota inválida", "Importe inválido", "Moneda inválida", "Operación debe ser"):
            self.assertIn(esperado, motivo)

    def test_valida_tipo_de_cambio_y_rechaza_cotizaciones_invalidas(self):
        filas = [
            comprobante(moneda="ARS", tipo_cambio=2),
            comprobante(moneda="USD", tipo_cambio=0),
            comprobante(moneda="USD", tipo_cambio="no numérico"),
        ]

        aceptados, rechazados = validar_comprobantes(pd.DataFrame(filas), "2026-09")

        self.assertTrue(aceptados.empty)
        self.assertIn("Para ARS, el tipo de cambio debe ser 1", rechazados.iloc[0]["motivo"])
        self.assertIn("mayor que cero", rechazados.iloc[1]["motivo"])
        self.assertIn("Tipo de cambio inválido", rechazados.iloc[2]["motivo"])

    def test_normaliza_pes_y_asigna_ars_por_defecto(self):
        fila = comprobante(moneda="PES", tipo_cambio=None)
        aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila]), "2026-09")

        self.assertTrue(rechazados.empty)
        self.assertEqual(aceptados.iloc[0]["moneda"], "ARS")
        self.assertEqual(aceptados.iloc[0]["tipo_cambio"], 1)

        fila_sin_moneda = comprobante()
        aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila_sin_moneda]), "2026-09")
        self.assertTrue(rechazados.empty)
        self.assertEqual(aceptados.iloc[0]["moneda"], "ARS")

    def test_valida_cuit_con_prefijo_alternativo_y_formato_con_separadores(self):
        cuit = cuit_sintetico("2012345678")
        self.assertTrue(validar_cuit(cuit))
        # Este prefijo llega al caso especial de verificador 10 -> dígito 9.
        self.assertTrue(validar_cuit("20000000019"))
        fila = comprobante(cuit=f"{cuit[:2]}-{cuit[2:10]}-{cuit[-1]}")

        aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila]), "2026-09")

        self.assertEqual(len(aceptados), 1)
        self.assertTrue(rechazados.empty)
        self.assertEqual(aceptados.iloc[0]["cuit"], cuit)
