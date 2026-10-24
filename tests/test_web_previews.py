"""Identidad, expiración y limpieza de vistas previas privadas."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from tests.django_utils import preparar_bd
from tests.helpers import TEMP_ROOT
from web.comprobantes.previews import (
    DURACION_SEGUNDOS, directorio, firmar, guardar_temporal, hash_opciones, limpiar_vencidas,
    ruta_temporal, verificar,
)


class TestPreviews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preparar_bd()

    def test_archivo_privado_usa_nombre_aleatorio_y_limpieza(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporal:
            with override_settings(PREVIEW_DIR=Path(temporal)):
                if os.name != "nt":
                    os.chmod(temporal, 0o777)
                archivo = SimpleUploadedFile("nombre-sintetico.csv", b"dato\n")
                identificador, ruta, digest = guardar_temporal(archivo, ".csv")
                self.assertEqual(ruta, ruta_temporal(identificador, ".csv"))
                self.assertNotIn("nombre-sintetico", ruta.name)
                self.assertEqual(len(digest), 64)
                if os.name != "nt":
                    self.assertEqual(directorio().stat().st_mode & 0o777, 0o700)
                    self.assertEqual(ruta.stat().st_mode & 0o777, 0o600)
                momento = time.time() - DURACION_SEGUNDOS - 1
                os.utime(ruta, (momento, momento))
                self.assertEqual(limpiar_vencidas(), 1)
                self.assertFalse(ruta.exists())

    def test_token_firmado_y_opciones_sensibles_a_cambios(self):
        datos = {"cliente": 1, "periodo": "2026-09", "operacion": "ventas"}
        token = firmar(datos)
        self.assertEqual(verificar(token), datos)
        self.assertNotEqual(hash_opciones(datos), hash_opciones({**datos, "operacion": "compras"}))
        with self.assertRaises(ValueError):
            ruta_temporal("../otro", ".csv")
        with self.assertRaises(ValueError):
            ruta_temporal("a" * 32, ".exe")

    def test_limpieza_tolera_archivo_eliminado_por_otro_proceso(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporal:
            with override_settings(PREVIEW_DIR=Path(temporal)):
                ruta = Path(temporal) / "vencido.csv"
                ruta.write_bytes(b"sintetico")
                momento = time.time() - DURACION_SEGUNDOS - 1
                os.utime(ruta, (momento, momento))
                with patch.object(Path, "unlink", side_effect=FileNotFoundError):
                    self.assertEqual(limpiar_vencidas(), 0)

    def test_error_de_escritura_elimina_archivo_incompleto(self):
        class ArchivoInterrumpido:
            def chunks(self):
                yield b"dato-sintetico"
                raise OSError("lectura interrumpida")

        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporal:
            with override_settings(PREVIEW_DIR=Path(temporal)):
                with self.assertRaises(OSError):
                    guardar_temporal(ArchivoInterrumpido(), ".csv")
                self.assertEqual(list(Path(temporal).iterdir()), [])
