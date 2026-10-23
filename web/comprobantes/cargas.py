"""Validación de archivos recibidos por la interfaz web."""

from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import iterparse
from django.core.exceptions import ValidationError


LIMITE_ARCHIVO = 10 * 1024 * 1024
LIMITE_DESCOMPRIMIDO = 100 * 1024 * 1024
EXTENSIONES = {
    "estandar": {".xlsx", ".xlsm", ".xls", ".csv", ".txt"},
    "arca": {".xlsx", ".xlsm", ".xls", ".csv", ".txt"},
    "holistor": {".xlsx", ".xlsm", ".xls", ".csv", ".txt"},
}


def validar_archivo(archivo, formato: str) -> tuple[str, str]:
    """Devuelve nombre seguro y extensión tras revisar tamaño y estructura."""
    nombre = str(archivo.name)
    if not nombre or any(c in nombre for c in ("/", "\\", "\x00")) or nombre in {".", ".."}:
        raise ValidationError("Nombre de archivo no válido.")
    sufijo = Path(nombre).suffix.casefold()
    if sufijo not in EXTENSIONES.get(formato, set()):
        raise ValidationError("La extensión no corresponde al origen elegido.")
    if archivo.size == 0 or archivo.size > LIMITE_ARCHIVO:
        raise ValidationError("El archivo debe tener entre 1 byte y 10 MiB.")
    encabezado = archivo.read(8)
    archivo.seek(0)
    if sufijo in {".xlsx", ".xlsm"}:
        if not encabezado.startswith(b"PK"):
            raise ValidationError("El archivo Excel no tiene una estructura válida.")
        try:
            with ZipFile(archivo) as comprimido:
                miembros = comprimido.infolist()
                if len(miembros) > 2000 or sum(info.file_size for info in miembros) > LIMITE_DESCOMPRIMIDO:
                    raise ValidationError("El Excel descomprimido excede el límite permitido.")
                if any(info.file_size > max(info.compress_size, 1) * 1000 for info in miembros):
                    raise ValidationError("La compresión del Excel excede el límite permitido.")
                if "[Content_Types].xml" not in comprimido.namelist() or "xl/workbook.xml" not in comprimido.namelist():
                    raise ValidationError("El archivo Excel no tiene una estructura válida.")
                for info in miembros:
                    if info.filename.endswith(".xml"):
                        with comprimido.open(info) as contenido:
                            for _, elemento in iterparse(contenido, events=("end",)):
                                elemento.clear()
        except (BadZipFile, OSError, ValueError, RuntimeError, ParseError, DefusedXmlException) as error:
            raise ValidationError("El archivo Excel no tiene una estructura válida.") from error
        finally:
            archivo.seek(0)
    elif sufijo == ".xls":
        if encabezado != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ValidationError("El archivo Excel no tiene una estructura válida.")
    elif b"\x00" in encabezado:
        raise ValidationError("El archivo de texto no tiene una estructura válida.")
    return nombre, sufijo
