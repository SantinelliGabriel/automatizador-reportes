import sqlite3
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import pandas as pd

from automatizador.database import _centavos, crear_tabla, consultar_comprobantes, consultar_totales, reemplazar_periodo
from automatizador.validaciones import validar_comprobantes
from tests.helpers import comprobante, directorio_temporal


class TestPersistencia(unittest.TestCase):
    def test_centavos_acepta_decimales_exactos_y_rechaza_fracciones_de_centavo(self):
        self.assertEqual(_centavos(Decimal("0.56")), 56)
        self.assertEqual(_centavos(Decimal("0.560")), 56)
        self.assertEqual(_centavos(Decimal("-0.56")), -56)
        with self.assertRaisesRegex(ValueError, "no como float"):
            _centavos(0.5699999999999999)
        for valor in ("0.5699999999999999", Decimal("0.565"), Decimal("0.561")):
            with self.subTest(valor=str(valor)), self.assertRaisesRegex(ValueError, "más de dos decimales"):
                _centavos(valor)

    def setUp(self):
        self.temp = directorio_temporal()
        self.db = Path(self.temp.name) / "comprobantes.db"
        crear_tabla(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def importar(self, periodo, registro):
        buenos, malos = validar_comprobantes(pd.DataFrame([registro]), periodo)
        reemplazar_periodo("Cliente Demo", periodo, buenos, malos, "demo.xlsx", self.db)

    def test_reimportar_reemplaza_solo_cliente_y_periodo(self):
        self.importar("2026-09", comprobante())
        self.importar("2026-10", comprobante(fecha="2026-10-03", numero=102))
        self.importar("2026-09", comprobante(numero=103))
        todos = consultar_comprobantes(self.db)
        self.assertEqual(len(todos), 2)
        self.assertEqual(set(todos["periodo"]), {"2026-09", "2026-10"})
        septiembre = consultar_comprobantes(self.db, "2026-09")
        self.assertEqual(septiembre.iloc[0]["numero"], 103)

    def test_rollback_conserva_periodo_anterior_si_falla_por_duplicado(self):
        self.importar("2026-09", comprobante())
        duplicados = pd.DataFrame([comprobante(numero=202), comprobante(numero=202)])
        aceptados, rechazados = validar_comprobantes(duplicados, "2026-09")
        forzado = pd.concat([aceptados, aceptados], ignore_index=True)
        with self.assertRaises(sqlite3.IntegrityError):
            reemplazar_periodo("Cliente Demo", "2026-09", forzado, rechazados, "demo.xlsx", self.db)
        guardados = consultar_comprobantes(self.db, "2026-09")
        self.assertEqual(len(guardados), 1)
        self.assertEqual(guardados.iloc[0]["numero"], 101)

    def test_persiste_moneda_cotizacion_e_importes_de_origen_y_ars(self):
        fila = comprobante(neto_gravado=100, iva=21, total=121, moneda="USD", tipo_cambio=1000)
        self.importar("2026-09", fila)

        guardado = consultar_comprobantes(self.db, "2026-09").iloc[0]
        self.assertEqual(guardado["moneda"], "USD")
        self.assertEqual(guardado["tipo_cambio"], 1000)
        self.assertEqual(guardado["neto_gravado"], 100000)
        self.assertEqual(guardado["neto_gravado_origen"], 100)
        self.assertEqual(guardado["total"], 121000)
        self.assertEqual(guardado["total_origen"], 121)

    def test_cotizaciones_textuales_conservan_valor_y_formato_canonico(self):
        casos = (
            ("1000", "1000", "100000"),
            ("1500.50", "1500.5", "100000"),
            ("100", "100", "100000"),
            ("0.00000001", "0.00000001", "100000000"),
            ("1e3", "1000", "100000"),
        )
        for indice, (cotizacion, esperado, origen) in enumerate(casos, start=1):
            with self.subTest(cotizacion=cotizacion):
                fila = comprobante(
                    numero=indice, neto_gravado=origen, iva=0,
                    alicuota=0, total=origen, moneda="USD", tipo_cambio=cotizacion,
                )
                aceptados, rechazados = validar_comprobantes(pd.DataFrame([fila]), "2026-09")
                self.assertTrue(rechazados.empty, rechazados.to_dict("records"))
                reemplazar_periodo("Cliente Demo", "2026-09", aceptados, rechazados, "sintetico.csv", self.db)
                with closing(sqlite3.connect(self.db)) as conexion:
                    guardado = conexion.execute(
                        "SELECT tipo_cambio FROM comprobantes WHERE numero = ?", (indice,)
                    ).fetchone()[0]
                leido = consultar_comprobantes(self.db, "2026-09").iloc[0]["tipo_cambio"]
                self.assertEqual(guardado, esperado)
                self.assertEqual(leido, Decimal(esperado))
                self.assertNotIn("e", guardado.lower())

    def test_totales_sin_comprobantes_devuelven_cero_decimal(self):
        totales = consultar_totales(self.db, "2026-09")

        self.assertEqual(totales, dict.fromkeys(("neto_gravado", "iva", "total"), Decimal("0.00")))
        for importe in totales.values():
            self.assertIsInstance(importe, Decimal)
            self.assertEqual(importe.as_tuple().exponent, -2)

    def test_totales_conservan_centavos_que_float_no_puede_representar(self):
        importe = "90071992547409.93"
        self.importar("2026-09", comprobante(neto_gravado=importe, alicuota=0, iva=0, total=importe))

        self.assertEqual(consultar_totales(self.db, "2026-09"), {
            "neto_gravado": Decimal(importe), "iva": Decimal("0.00"), "total": Decimal(importe),
        })

    def test_totales_filtran_periodo_y_aplican_signos_de_notas_en_ventas_y_compras(self):
        registros = [
            comprobante(numero=1, neto_gravado="0.10", iva="0.02", total="0.12"),
            comprobante(numero=2, operacion="compras", neto_gravado="0.20", iva="0.04", total="0.24"),
            comprobante(numero=3, tipo_comprobante="NC A", neto_gravado="0.40", iva="0.08", total="0.48"),
            comprobante(numero=4, tipo_comprobante="ND A", operacion="compras",
                        neto_gravado="0.05", iva="0.01", total="0.06"),
        ]
        buenos, malos = validar_comprobantes(pd.DataFrame(registros), "2026-09")
        self.assertTrue(malos.empty)
        reemplazar_periodo("Cliente Demo", "2026-09", buenos, malos, "demo.csv", self.db)
        self.importar("2026-10", comprobante(fecha="2026-10-03"))

        self.assertEqual(consultar_totales(self.db, "2026-09"), {
            "neto_gravado": Decimal("-0.05"), "iva": Decimal("-0.01"), "total": Decimal("-0.06"),
        })
        self.assertEqual(consultar_totales(self.db), {
            "neto_gravado": Decimal("99999.95"), "iva": Decimal("20999.99"), "total": Decimal("120999.94"),
        })
