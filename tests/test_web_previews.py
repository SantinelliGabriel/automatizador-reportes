"""Identidad, expiración y limpieza de vistas previas privadas."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from tests.helpers import TEMP_ROOT
from web.comprobantes.previews import (
    DURACION_SEGUNDOS, firmar, guardar_temporal, hash_opciones, limpiar_vencidas,
    ruta_temporal, verificar,
)


class TestPreviews(unittest.TestCase):
    def test_archivo_privado_usa_nombre_aleatorio_y_limpieza(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporal:
            with override_settings(PREVIEW_DIR=Path(temporal)):
                archivo = SimpleUploadedFile("nombre-sintetico.csv", b"dato\n")
                identificador, ruta, digest = guardar_temporal(archivo, ".csv")
                self.assertEqual(ruta, ruta_temporal(identificador, ".csv"))
                self.assertNotIn("nombre-sintetico", ruta.name)
                self.assertEqual(len(digest), 64)
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
