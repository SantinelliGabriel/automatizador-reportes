"""Migración de una base v2 generada con el código de main y datos sintéticos."""

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from automatizador.database import crear_tabla
from tests.helpers import ROOT, directorio_temporal


FUTURA_BASE = ROOT / "tests" / "fixtures" / "sqlite" / "main_v2_sintetica.sql"


def base_v2(ruta):
    with closing(sqlite3.connect(ruta)) as conexion:
        conexion.executescript(FUTURA_BASE.read_text(encoding="utf-8"))


class TestMigracionV3(unittest.TestCase):
    def test_rellena_operaciones_y_conserva_centavos_con_respaldo(self):
        with directorio_temporal() as carpeta:
            base = Path(carpeta) / "comprobantes.db"
            base_v2(base)
            original = base.read_bytes()
            migracion = crear_tabla(base)
            self.assertEqual(migracion.version_anterior, 2)
            self.assertEqual(migracion.version_actual, 3)
            self.assertEqual(migracion.respaldo.name, "comprobantes.v2.bak.db")
            self.assertEqual(migracion.respaldo.read_bytes(), original)
            with closing(sqlite3.connect(base)) as conexion:
                self.assertEqual(conexion.execute("PRAGMA user_version").fetchone()[0], 3)
                self.assertEqual(conexion.execute(
                    "SELECT archivo_origen, operaciones FROM importaciones ORDER BY id"
                ).fetchall(), [
                    ("ventas.csv", ""), ("compras.csv", ""),
                    ("mixto.csv", "compras,ventas"), ("observado.csv", ""),
                ])
                self.assertEqual(conexion.execute(
                    "SELECT total_centavos FROM comprobantes ORDER BY id"
                ).fetchall(), [(12100000,), (12100000,)])
            self.assertIsNone(crear_tabla(base))
            self.assertEqual(len(list(Path(carpeta).glob("*.bak*.db"))), 1)

    def test_fallo_revierte_solo_migracion_v3_y_deja_respaldo(self):
        with directorio_temporal() as carpeta:
            base = Path(carpeta) / "comprobantes.db"
            base_v2(base)
            original = base.read_bytes()

            def fallar(conexion):
                conexion.execute("ALTER TABLE importaciones ADD COLUMN operaciones TEXT NOT NULL DEFAULT ''")
                raise RuntimeError("fallo sintético")

            with patch("automatizador.database._migrar_a_v3", side_effect=fallar):
                with self.assertRaisesRegex(RuntimeError, "fallo sintético"):
                    crear_tabla(base)
            with closing(sqlite3.connect(base)) as conexion:
                self.assertEqual(conexion.execute("PRAGMA user_version").fetchone()[0], 2)
                self.assertNotIn("operaciones", [r[1] for r in conexion.execute("PRAGMA table_info(importaciones)")])
            self.assertEqual((Path(carpeta) / "comprobantes.v2.bak.db").read_bytes(), original)

    def test_version_futura_no_se_modifica(self):
        with directorio_temporal() as carpeta:
            base = Path(carpeta) / "comprobantes.db"
            base_v2(base)
            with closing(sqlite3.connect(base)) as conexion:
                conexion.execute("PRAGMA user_version = 4")
            original = base.read_bytes()
            with self.assertRaisesRegex(ValueError, "versión de esquema no admitida"):
                crear_tabla(base)
            self.assertEqual(base.read_bytes(), original)
            self.assertFalse(list(Path(carpeta).glob("*.bak*.db")))
