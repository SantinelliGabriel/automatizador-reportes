"""Migración transaccional desde el esquema REAL heredado."""

import shutil
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from automatizador.database import VERSION_ESQUEMA, _migrar_a_v1, _migrar_a_v2, crear_tabla
from automatizador.procesamiento import generar_informe
from automatizador.repositorio import RepositorioSQLite
from tests.helpers import comprobante, directorio_temporal


def base_v1(carpeta):
    carpeta = Path(carpeta)
    vieja = carpeta / "legacy.db"
    with closing(sqlite3.connect(vieja)) as conexion:
        _migrar_a_v1(conexion)
        conexion.execute("PRAGMA user_version = 1")
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


def base_v0_main(carpeta):
    ruta = Path(carpeta) / "main_v0.db"
    sql = (Path(__file__).parent / "fixtures" / "sqlite" / "main_v0_sintetica.sql").read_text(encoding="utf-8")
    with closing(sqlite3.connect(ruta)) as conexion:
        conexion.executescript(sql)
    return ruta


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
    def test_base_nueva_y_archivo_vacio_no_generan_respaldo_ni_aviso(self):
        with directorio_temporal() as carpeta:
            nueva = Path(carpeta) / "nueva.db"
            self.assertIsNone(crear_tabla(nueva))
            self.assertEqual(list(Path(carpeta).glob("*.bak*.db")), [])
            vacia = Path(carpeta) / "vacia.db"
            vacia.touch()
            self.assertIsNone(crear_tabla(vacia))
            self.assertEqual(list(Path(carpeta).glob("*.bak*.db")), [])

    def test_base_v0_de_main_respalda_bytes_originales_antes_de_migrar(self):
        with directorio_temporal() as carpeta:
            base = base_v0_main(carpeta)
            original = base.read_bytes()
            with closing(sqlite3.connect(base)) as conexion:
                self.assertEqual(conexion.execute("PRAGMA user_version").fetchone()[0], 0)
                self.assertEqual(conexion.execute("SELECT COUNT(*) FROM comprobantes").fetchone()[0], 3)

            migracion = crear_tabla(base)

            respaldo = Path(carpeta) / "main_v0.v0.bak.db"
            self.assertEqual(migracion.version_anterior, 0)
            self.assertEqual(migracion.respaldo, respaldo)
            self.assertEqual(respaldo.read_bytes(), original)
            with closing(sqlite3.connect(base)) as conexion:
                self.assertEqual(conexion.execute("PRAGMA user_version").fetchone()[0], VERSION_ESQUEMA)
                self.assertEqual(conexion.execute("SELECT COUNT(*) FROM comprobantes").fetchone()[0], 3)

    def test_version_futura_falla_sin_modificar_base_ni_crear_respaldo(self):
        with directorio_temporal() as carpeta:
            base = base_v1(carpeta)
            with closing(sqlite3.connect(base)) as conexion:
                conexion.execute(f"PRAGMA user_version = {VERSION_ESQUEMA + 1}")
            antes = base.read_bytes()
            with self.assertRaisesRegex(ValueError, f"versión de esquema no admitida: {VERSION_ESQUEMA + 1}"):
                crear_tabla(base)
            self.assertEqual(base.read_bytes(), antes)
            self.assertEqual(list(Path(carpeta).glob("legacy.v1.bak*.db")), [])

    def test_respaldo_existente_se_conserva_y_se_crea_otro(self):
        with directorio_temporal() as carpeta:
            base = base_v1(carpeta)
            primero = Path(carpeta) / "legacy.v1.bak.db"
            shutil.copy2(base, primero)
            contenido_original = primero.read_bytes()

            migracion = crear_tabla(base)

            segundo = Path(carpeta) / "legacy.v1.bak.1.db"
            self.assertEqual(primero.read_bytes(), contenido_original)
            self.assertEqual(migracion.respaldo, segundo)
            self.assertEqual(instantanea(segundo), (1, instantanea(primero)[1]))
            self.assertIn(str(segundo), migracion.mensaje())

    def test_revision_migrada_figura_en_hoja_comprobantes(self):
        with directorio_temporal() as carpeta:
            base = base_v1(carpeta)
            crear_tabla(base)
            salida = Path(carpeta) / "reporte.xlsx"
            generar_informe("2026-09", salida, RepositorioSQLite(base))
            detalle = pd.read_excel(salida, sheet_name="Comprobantes")
            observaciones = pd.read_excel(salida, sheet_name="Observaciones")
            motivos = dict(zip(detalle["numero"], detalle["revision_decimal"].fillna("")))
            self.assertEqual(motivos[1], "")
            self.assertIn("15 cifras significativas", motivos[2])
            self.assertEqual(motivos[3], "conversión a ARS diferente")
            self.assertTrue(observaciones.empty)

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
