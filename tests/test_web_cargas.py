"""Límites y detección de archivos malformados de la interfaz web."""

import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError

from web.comprobantes.cargas import validar_archivo


class ArchivoFalso(io.BytesIO):
    def __init__(self, nombre, contenido):
        super().__init__(contenido)
        self.name = nombre
        self.size = len(contenido)


class TestCargaSegura(unittest.TestCase):
    def test_rechaza_archivo_mayor_a_10_mib(self):
        archivo = ArchivoFalso("grande.csv", b"a")
        archivo.size = 10 * 1024 * 1024 + 1
        with self.assertRaisesRegex(ValidationError, "10 MiB"):
            validar_archivo(archivo, "estandar")

    def test_rechaza_nombre_con_ruta_y_extension_falsa(self):
        with self.assertRaises(ValidationError):
            validar_archivo(ArchivoFalso("../x.csv", b"fecha,numero\n"), "estandar")
        with self.assertRaises(ValidationError):
            validar_archivo(ArchivoFalso("falso.xlsx", b"fecha,numero\n"), "estandar")

    def test_rechaza_zip_bomb_simulado(self):
        archivo = ArchivoFalso("falso.xlsx", b"PK\x03\x04contenido")
        info = SimpleNamespace(file_size=101 * 1024 * 1024, compress_size=100, filename="xl/workbook.xml")
        with patch("web.comprobantes.cargas.ZipFile") as zip_falso:
            zip_falso.return_value.__enter__.return_value.infolist.return_value = [info]
            with self.assertRaisesRegex(ValidationError, "descomprimido"):
                validar_archivo(archivo, "estandar")
