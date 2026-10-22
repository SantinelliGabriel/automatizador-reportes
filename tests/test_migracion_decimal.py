"""Migración transaccional desde el esquema REAL heredado."""

import shutil
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from automatizador.database import VERSION_ESQUEMA, _migrar_a_v2, crear_tabla
from tests.helpers import comprobante, directorio_temporal


def base_v1(carpeta):
    carpeta = Path(carpeta)
    nueva = carpeta / "nueva.db"
    crear_tabla(nueva)
    vieja = carpeta / "legacy.db"
    shutil.copy2(carpeta / "nueva.v1.bak.db", vieja)
    with closing(sqlite3.connect(vieja)) as conexion:
        conexion.execute(
            "INSERT INTO importaciones(archivo_origen, cliente, periodo, aceptados) VALUES (?, ?, ?, ?)",
            ("sintetico.csv", "Cliente Sintético", "2026-09", 3),
        )
        cuit = comprobante()["cuit"]
        for numero, cambio, origen, ars in (
            (1, 1.25, 100, 125),
            (2, 1.2345678901234567, 0, 0),
            (3, 2.0, 100, 201),
        ):
            conexion.execute("""INSERT INTO comprobantes (
                importacion_id, cliente, periodo, operacion, fecha, tipo_comprobante,
                punto_venta, numero, cuit, razon_social, neto_gravado_centavos,
                alicuota, iva_centavos, no_gravado_exento_centavos, percepciones_centavos,
                total_centavos, moneda, tipo_cambio, neto_gravado_origen_centavos,
                total_origen_centavos
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                1, "Cliente Sintético", "2026-09", "ventas", "2026-09-03", "A",
                1, numero, cuit, "Entidad Sintética", ars, 0.0, 0, 0, 0, ars,
                "USD", cambio, origen, origen,
            ))
        conexion.commit()
    return vieja


def instantanea(ruta):
    with closing(sqlite3.connect(ruta)) as conexion:
        return (
            conexion.execute("PRAGMA user_version").fetchone()[0],
            conexion.execute(
                "SELECT numero, neto_gravado_centavos, total_centavos, "
                "neto_gravado_origen_centavos, total_origen_centavos "
                "FROM comprobantes ORDER BY numero"
            ).fetchall(),
        )


class TestMigracionDecimal(unittest.TestCase):
    def test_respaldo_revision_selectiva_centavos_intactos_e_idempotencia(self):
        with directorio_temporal() as carpeta:
            base = base_v1(carpeta)
            version_previa, centavos_previos = instantanea(base)
            self.assertEqual(version_previa, 1)

            crear_tabla(base)
            version_nueva, centavos_nuevos = instantanea(base)
            self.assertEqual(version_nueva, VERSION_ESQUEMA)
            self.assertEqual(centavos_nuevos, centavos_previos)
            respaldo = Path(carpeta) / "legacy.v1.bak.db"
            self.assertEqual(instantanea(respaldo), (1, centavos_previos))
            with closing(sqlite3.connect(base)) as conexion:
                filas = conexion.execute(
                    "SELECT numero, typeof(alicuota), alicuota, typeof(tipo_cambio), "
                    "tipo_cambio, revision_decimal FROM comprobantes ORDER BY numero"
                ).fetchall()
            self.assertEqual(filas[0], (1, "text", "0", "text", "1.25", ""))
            self.assertIn("15 cifras significativas", filas[1][-1])
            self.assertNotIn("conversión", filas[1][-1])
            self.assertEqual(filas[2][-1], "conversión a ARS diferente")

            crear_tabla(base)
            self.assertEqual(instantanea(base), (VERSION_ESQUEMA, centavos_previos))
            self.assertEqual(list(Path(carpeta).glob("legacy.v1.bak*.db")), [respaldo])

    def test_error_despues_de_recrear_tabla_revierte_todo_y_deja_version_1(self):
        with directorio_temporal() as carpeta:
            base = base_v1(carpeta)
            previo = instantanea(base)

            def fallar_despues_de_copiar(conexion):
                _migrar_a_v2(conexion)
                raise RuntimeError("error sintético tras copiar")

            with patch("automatizador.database._migrar_a_v2", side_effect=fallar_despues_de_copiar):
                with self.assertRaisesRegex(RuntimeError, "error sintético"):
                    crear_tabla(base)

            self.assertEqual(instantanea(base), previo)
            with closing(sqlite3.connect(base)) as conexion:
                self.assertEqual(conexion.execute(
                    "SELECT type FROM pragma_table_info('comprobantes') WHERE name = 'tipo_cambio'"
                ).fetchone()[0], "REAL")
                self.assertIsNone(conexion.execute(
                    "SELECT name FROM sqlite_master WHERE name = 'comprobantes_v2'"
                ).fetchone())
            self.assertEqual(instantanea(Path(carpeta) / "legacy.v1.bak.db"), previo)
