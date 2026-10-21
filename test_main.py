"""Pruebas de validación y del flujo contable por período."""

import tempfile
import unittest
import sqlite3
from pathlib import Path

import pandas as pd

from database import crear_tabla, consultar_comprobantes, reemplazar_periodo
from generar_datos_demo import cuit_sintetico
from reportes import construir_hojas
from validaciones import validar_comprobantes


def comprobante(**cambios):
    fila = {
        "fecha": "2026-09-03", "tipo_comprobante": "A", "punto_venta": 1,
        "numero": 101, "cuit": cuit_sintetico("3071234567"),
        "razon_social": "Empresa Sintética", "operacion": "ventas",
        "neto_gravado": 100000, "alicuota": 21, "iva": 21000,
        "no_gravado_exento": 0, "percepciones": 0, "total": 121000,
    }
    fila.update(cambios)
    return fila


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
        df = pd.DataFrame([comprobante(), comprobante()])
        aceptados, rechazados = validar_comprobantes(df, "2026-09")
        self.assertEqual(len(aceptados), 1)
        self.assertIn("duplicado", rechazados.iloc[0]["motivo"])

    def test_rechaza_alicuota_no_admitida(self):
        aceptados, rechazados = validar_comprobantes(pd.DataFrame([comprobante(alicuota=19)]), "2026-09")
        self.assertTrue(aceptados.empty)
        self.assertIn("Alícuota inválida", rechazados.iloc[0]["motivo"])


class TestPersistenciaYReportes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
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
        # La validación descarta el segundo duplicado; forzamos la restricción
        # de SQLite para comprobar que el borrado previo también se revierte.
        forzado = pd.concat([aceptados, aceptados], ignore_index=True)
        with self.assertRaises(sqlite3.IntegrityError):
            reemplazar_periodo("Cliente Demo", "2026-09", forzado, rechazados, "demo.xlsx", self.db)
        guardados = consultar_comprobantes(self.db, "2026-09")
        self.assertEqual(len(guardados), 1)
        self.assertEqual(guardados.iloc[0]["numero"], 101)

    def test_notas_de_credito_reducen_el_resumen(self):
        venta = comprobante()
        nota = comprobante(tipo_comprobante="NC A", numero=102, neto_gravado=10000, iva=2100, total=12100)
        buenos, malos = validar_comprobantes(pd.DataFrame([venta, nota]), "2026-09")
        reemplazar_periodo("Cliente Demo", "2026-09", buenos, malos, "demo.xlsx", self.db)
        detalle, por_cliente, por_alicuota = construir_hojas(consultar_comprobantes(self.db))
        self.assertEqual(len(detalle), 2)
        self.assertEqual(por_cliente.iloc[0]["iva"], 18900)
        self.assertEqual(por_alicuota.iloc[0]["neto_gravado"], 90000)


if __name__ == "__main__":
    unittest.main()
