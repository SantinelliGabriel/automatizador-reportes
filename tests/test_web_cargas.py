"""Límites y detección de archivos malformados de la interfaz web."""

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.test import override_settings

from tests.django_utils import preparar_bd
from tests.helpers import TEMP_ROOT
from web.comprobantes.cargas import validar_archivo


class ArchivoFalso(io.BytesIO):
    def __init__(self, nombre, contenido):
        super().__init__(contenido)
        self.name = nombre
        self.size = len(contenido)


class TestCargaSegura(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preparar_bd()

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
        with self.assertRaisesRegex(ValidationError, "extensión"):
            validar_archivo(ArchivoFalso("falso.exe", b"fecha,numero\n"), "estandar")

    @staticmethod
    def excel_sintetico(xml=b"<workbook/>", incluir_libro=True):
        contenido = io.BytesIO()
        with ZipFile(contenido, "w") as comprimido:
            comprimido.writestr("[Content_Types].xml", "<Types/>")
            if incluir_libro:
                comprimido.writestr("xl/workbook.xml", xml)
        return contenido.getvalue()

    def test_zip_corrupto_truncado_y_sin_libro(self):
        for contenido in (b"PK\x03\x04truncado", self.excel_sintetico()[:-10]):
            with self.subTest(contenido=contenido[:8]):
                with self.assertRaisesRegex(ValidationError, "estructura válida"):
                    validar_archivo(ArchivoFalso("corrupto.xlsx", contenido), "estandar")
        with self.assertRaisesRegex(ValidationError, "estructura válida"):
            validar_archivo(ArchivoFalso("sin-libro.xlsx", self.excel_sintetico(incluir_libro=False)),
                            "estandar")

    def test_xml_malicioso_se_rechaza_sin_expandir_entidades(self):
        ejemplos = (
            b'<!DOCTYPE workbook [<!ENTITY externo SYSTEM "file:///sin-archivo-sintetico">]>'
            b'<workbook>&externo;</workbook>',
            b'<!DOCTYPE workbook [<!ENTITY a "x"><!ENTITY b "&a;&a;&a;&a;">]>'
            b'<workbook>&b;</workbook>',
        )
        for xml in ejemplos:
            with self.subTest(xml=xml[:40]):
                with self.assertRaisesRegex(ValidationError, "estructura válida"):
                    validar_archivo(ArchivoFalso("malicioso.xlsx", self.excel_sintetico(xml)), "estandar")

    def test_xml_valido_y_relaciones_se_inspeccionan(self):
        archivo = ArchivoFalso("sintetico.xlsx", self.excel_sintetico())
        self.assertEqual(validar_archivo(archivo, "estandar"), ("sintetico.xlsx", ".xlsx"))
        self.assertEqual(archivo.tell(), 0)

    def test_rechaza_zip_bomb_simulado(self):
        archivo = ArchivoFalso("falso.xlsx", b"PK\x03\x04contenido")
        info = SimpleNamespace(file_size=101 * 1024 * 1024, compress_size=100, filename="xl/workbook.xml")
        with patch("web.comprobantes.cargas.ZipFile") as zip_falso:
            zip_falso.return_value.__enter__.return_value.infolist.return_value = [info]
            with self.assertRaisesRegex(ValidationError, "descomprimido"):
                validar_archivo(archivo, "estandar")
        info.file_size = 2 * 1024 * 1024
        with patch("web.comprobantes.cargas.ZipFile") as zip_falso:
            zip_falso.return_value.__enter__.return_value.infolist.return_value = [info]
            with self.assertRaisesRegex(ValidationError, "compresión"):
                validar_archivo(archivo, "estandar")

    def test_xls_falso_texto_binario_y_codificacion_invalida(self):
        with self.assertRaisesRegex(ValidationError, "estructura válida"):
            validar_archivo(ArchivoFalso("falso.xls", b"no es OLE"), "estandar")
        with self.assertRaisesRegex(ValidationError, "estructura válida"):
            validar_archivo(ArchivoFalso("falso.csv", b"fecha,numero\n1,2\x00"), "estandar")
        with self.assertRaisesRegex(ValidationError, "codificación"):
            validar_archivo(ArchivoFalso("falso.csv", b"fecha,numero\n\x81,2"), "estandar")

    def test_prn_requiere_mapeo_configurado(self):
        with override_settings(HOLISTOR_MAPPING_PATH=None):
            with self.assertRaisesRegex(ValidationError, "mapeo Holistor"):
                validar_archivo(ArchivoFalso("sintetico.prn", b"2026 09"), "holistor")
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporal:
            mapeo = Path(temporal) / "mapeo-sintetico.json"
            mapeo.write_text("{}", encoding="utf-8")
            with override_settings(HOLISTOR_MAPPING_PATH=mapeo):
                self.assertEqual(validar_archivo(ArchivoFalso("sintetico.prn", b"2026 09"), "holistor"),
                                 ("sintetico.prn", ".prn"))
