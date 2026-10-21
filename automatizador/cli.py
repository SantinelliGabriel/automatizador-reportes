"""Punto de entrada de consola."""

import argparse
import logging
import sqlite3
from pathlib import Path

from automatizador.config import ARCHIVO_BD, ARCHIVO_ENTRADA, ARCHIVO_SALIDA
from automatizador.database import crear_tabla, consultar_importaciones
from automatizador.procesamiento import procesar

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Valida comprobantes y genera reportes mensuales.")
    parser.add_argument("--input", type=Path, default=ARCHIVO_ENTRADA, help="Excel de un cliente o carpeta con archivos por cliente.")
    parser.add_argument("--output", type=Path, default=ARCHIVO_SALIDA, help="Libro consolidado a generar.")
    parser.add_argument("--database", type=Path, default=ARCHIVO_BD, help="Base SQLite de comprobantes.")
    parser.add_argument("--period", help="Período mensual a procesar, formato AAAA-MM.")
    parser.add_argument("--source", choices=("estandar", "arca", "holistor"), default="estandar", help="Formato del archivo de entrada.")
    parser.add_argument("--operation", choices=("ventas", "compras"), default="ventas", help="Libro asociado a la descarga ARCA/Holistor.")
    parser.add_argument("--mapping", type=Path, help="JSON de mapeo de columnas/ancho fijo para Holistor.")
    parser.add_argument("--history", action="store_true", help="Muestra el historial de importaciones.")
    args = parser.parse_args(argv)
    try:
        args.database.parent.mkdir(parents=True, exist_ok=True)
        crear_tabla(args.database)
        if args.history:
            historial = consultar_importaciones(args.database)
            print("No hay importaciones registradas." if historial.empty else historial.to_string(index=False))
            return 0
        if not args.period or len(args.period) != 7 or args.period[4] != "-" or not args.period.replace("-", "").isdigit() or not 1 <= int(args.period[5:]) <= 12:
            parser.error("--period es obligatorio y debe usar AAAA-MM con mes entre 01 y 12.")
        resultado = procesar(args.input, args.output, args.database, args.period, args.source, args.operation, args.mapping)
        totales = ", ".join(f"{columna}={importe:.2f}" for columna, importe in resultado.totales.items())
        logging.info("Filas válidas: %s; observadas: %s; totales: %s", resultado.filas_validas, resultado.filas_observadas, totales)
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.Error, OSError) as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
