
from pathlib import Path


CARPETA_PROYECTO = Path(__file__).resolve().parents[1]

ARCHIVO_ENTRADA = CARPETA_PROYECTO / "ejemplos" / "Cliente Demo Norte.xlsx"
ARCHIVO_SALIDA = Path.cwd() / "reporte_iva.xlsx"
ARCHIVO_BD = Path.cwd() / "comprobantes.db"
