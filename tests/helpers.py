import tempfile
from pathlib import Path

from automatizador.generar_datos_demo import cuit_sintetico


ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT / ".test_tmp"
TEMP_ROOT.mkdir(exist_ok=True)


def directorio_temporal():
    return tempfile.TemporaryDirectory(dir=TEMP_ROOT)


def comprobante(**cambios):
    fila = {
        "fecha": "2026-09-03", "tipo_comprobante": "A", "punto_venta": 1,
        "numero": 101, "cuit": cuit_sintetico("3071234567"),
        "razon_social": "Empresa Sintética", "operacion": "ventas",
        "neto_gravado": 100000, "alicuota": 21, "iva": 21000,
        "no_gravado_exento": 0, "percepciones": 0, "total": 121000,
    }
    fila.update(cambios)
    return fila
