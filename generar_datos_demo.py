"""Genera Excel ficticios para probar la importación sin datos de clientes."""

from pathlib import Path
import argparse

import pandas as pd


def cuit_sintetico(base):
    """Calcula el dígito de control de una base sintética de diez dígitos."""
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
    verificador = 11 - resto
    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        verificador = 9 if base[:2] in {"20", "23", "24", "27"} else 0
    return base + str(verificador)


def generar(carpeta):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    datos = {
        "Cliente Demo Norte": [
            ["2026-09-03", "A", 1, 101, cuit_sintetico("3071234567"), "Proveedor Sintético Uno", "ventas", 100000, 21, 21000, 0, 0, 121000],
            ["2026-09-08", "A", 2, 44, cuit_sintetico("3077654321"), "Cliente Sintético Dos", "compras", 50000, 10.5, 5250, 0, 0, 55250],
        ],
        "Cliente Demo Sur": [
            ["2026-09-11", "B", 1, 205, cuit_sintetico("3073333333"), "Cliente Sintético Tres", "ventas", 25000, 21, 5250, 0, 0, 30250],
            ["2026-09-17", "NC A", 2, 19, cuit_sintetico("3074444444"), "Proveedor Sintético Cuatro", "compras", 10000, 21, 2100, 0, 0, 12100],
        ],
    }
    columnas = ["fecha", "tipo_comprobante", "punto_venta", "numero", "cuit", "razon_social", "operacion", "neto_gravado", "alicuota", "iva", "no_gravado_exento", "percepciones", "total"]
    for cliente, filas in datos.items():
        pd.DataFrame(filas, columns=columnas).to_excel(carpeta / f"{cliente}.xlsx", index=False)
    return carpeta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "datos_demo")
    print(f"Archivos ficticios generados en: {generar(parser.parse_args().output)}")
