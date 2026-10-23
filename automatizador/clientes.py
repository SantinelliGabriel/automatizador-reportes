"""Identidad compartida de clientes sin modificar el nombre visible."""

import unicodedata


def clave_cliente(nombre: str) -> str:
    """Normaliza NFC, extremos, espacios internos y mayúsculas; conserva acentos."""
    if not isinstance(nombre, str):
        raise ValueError("El nombre del cliente debe ser texto.")
    normalizado = unicodedata.normalize("NFC", nombre)
    clave = " ".join(normalizado.strip().split()).casefold()
    if not clave:
        raise ValueError("El nombre del cliente no puede estar vacío.")
    return clave
