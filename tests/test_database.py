import sqlite3
import unittest
from pathlib import Path

import pandas as pd

from automatizador.database import crear_tabla, consultar_comprobantes, reemplazar_periodo
from automatizador.validaciones import validar_comprobantes
from tests.helpers import comprobante, directorio_temporal


class TestPersistencia(unittest.TestCase):
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
