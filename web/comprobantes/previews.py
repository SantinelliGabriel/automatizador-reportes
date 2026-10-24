"""Archivos de vista previa privados y comprobación de identidad."""

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.core import signing

from web.comprobantes.models import Importacion


DURACION_SEGUNDOS = 30 * 60
SAL = "automatizador-vista-previa-v1"


def directorio() -> Path:
    ruta = settings.PREVIEW_DIR
    ruta.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(ruta, 0o700)
    return ruta


def limpiar_vencidas() -> int:
    """Retira archivos y candados antiguos sin acceder a la base."""
    limite = time.time() - DURACION_SEGUNDOS
    retirados = 0
    for ruta in directorio().iterdir():
        if ruta.is_file() and ruta.stat().st_mtime < limite:
            try:
                ruta.unlink()
                retirados += 1
            except FileNotFoundError:
                pass
    return retirados


def guardar_temporal(archivo, sufijo: str) -> tuple[str, Path, str]:
    identificador = uuid.uuid4().hex
    ruta = directorio() / f"{identificador}{sufijo}"
    digest = hashlib.sha256()
    descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as destino:
            for bloque in archivo.chunks():
                digest.update(bloque)
                destino.write(bloque)
    except Exception:
        ruta.unlink(missing_ok=True)
        raise
    return identificador, ruta, digest.hexdigest()


def ruta_temporal(identificador: str, sufijo: str) -> Path:
    if len(identificador) != 32 or any(c not in "0123456789abcdef" for c in identificador):
        raise ValueError("Vista previa no válida.")
    if sufijo not in {".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".prn"}:
        raise ValueError("Vista previa no válida.")
    return directorio() / f"{identificador}{sufijo}"


def hash_opciones(opciones: dict) -> str:
    contenido = json.dumps(opciones, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def hash_plan(plan) -> str:
    def tabla(df):
        return {"columnas": list(df.columns), "filas": [[str(valor) for valor in fila]
                for fila in df.itertuples(index=False, name=None)]}

    archivos = [{"cliente": a.cliente, "nombre": a.nombre, "aplicar": a.aplicar,
                 "conflicto": a.conflicto, "comprobantes": tabla(a.comprobantes),
                 "observaciones": tabla(a.observaciones)} for a in plan.archivos]
    return hash_opciones({"periodo": plan.periodo, "archivos": archivos})


def version_operacion(cliente, periodo: str, operacion: str) -> list[int]:
    """Identificadores que podrían alterar la operación revisada."""
    filas = Importacion.objects.filter(cliente=cliente, periodo=periodo).values_list("id", "operaciones")
    return sorted(pk for pk, operaciones in filas if not operaciones or operacion in operaciones.split(","))


def firmar(datos: dict) -> str:
    return signing.dumps(datos, salt=SAL)


def verificar(token: str) -> dict:
    return signing.loads(token, salt=SAL, max_age=DURACION_SEGUNDOS)
