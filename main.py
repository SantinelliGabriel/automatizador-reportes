import argparse
import logging
import os
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd

from config import ARCHIVO_BD, ARCHIVO_ENTRADA, ARCHIVO_SALIDA
from database import crear_tabla, guardar_ventas
from reportes import aplicar_formato_excel, construir_reporte
from validaciones import validar_ventas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def generar_reporte(archivo_entrada=None, archivo_salida=None, archivo_bd=None):
    """Lee, valida, calcula y genera el reporte de ventas."""
    archivo_entrada = archivo_entrada or ARCHIVO_ENTRADA
    archivo_salida = archivo_salida or ARCHIVO_SALIDA
    logging.info("Iniciando la generación del reporte.")

    if not archivo_entrada.exists():
        raise FileNotFoundError(
            f"No se encontró '{archivo_entrada.name}'. "
            "Colocá el archivo en la carpeta del proyecto."
        )

    try:
        ventas = pd.read_excel(archivo_entrada)
    except PermissionError as error:
        raise RuntimeError(
            "No se puede leer el archivo. Comprobá sus permisos."
        ) from error
    except (OSError, ValueError) as error:
        raise RuntimeError(
            "No se pudo leer el Excel. Comprobá que sea válido."
        ) from error

    ventas = validar_ventas(ventas)

    try:
        archivo_salida.parent.mkdir(parents=True, exist_ok=True)
        if archivo_bd is not None:
            archivo_bd.parent.mkdir(parents=True, exist_ok=True)
        crear_tabla(archivo_bd)
        descriptor, temporal_nombre = tempfile.mkstemp(
            suffix=archivo_salida.suffix,
            prefix=f"{archivo_salida.stem}_",
            dir=archivo_salida.parent,
        )
        os.close(descriptor)
        temporal = Path(temporal_nombre)
        respaldo = archivo_salida.read_bytes() if archivo_salida.exists() else None
        publicado = False
        total_ventas = 0

        def publicar_reporte(ventas_guardadas):
            nonlocal publicado, total_ventas
            reporte, total_ventas = construir_reporte(ventas_guardadas)
            if not pd.notna(total_ventas) or abs(total_ventas) == float("inf"):
                raise ValueError("El total calculado no es válido.")
            reporte.to_excel(temporal, index=False)
            aplicar_formato_excel(temporal)
            os.replace(temporal, archivo_salida)
            publicado = True

        try:
            guardar_ventas(
                ventas,
                antes_de_commit=publicar_reporte,
                ruta=archivo_bd,
            )
        except Exception:
            if publicado:
                if respaldo is None:
                    archivo_salida.unlink(missing_ok=True)
                else:
                    archivo_salida.write_bytes(respaldo)
            raise
        finally:
            temporal.unlink(missing_ok=True)
    except sqlite3.Error as error:
        raise RuntimeError("No se pudo actualizar la base de datos de ventas.") from error
    except PermissionError as error:
        raise RuntimeError(
            "No se pudo guardar el reporte. Cerrá el Excel de salida "
            "si está abierto e intentá nuevamente."
        ) from error
    except OSError as error:
        raise RuntimeError("Ocurrió un problema al guardar el reporte.") from error

    logging.info("Reporte generado correctamente.")
    logging.info("Productos procesados: %s", len(ventas))
    logging.info("Total de ventas: $%s", f"{total_ventas:,.2f}")
    logging.info("Archivo generado: %s", archivo_salida)


def main(argv=None):
    """Punto de entrada de consola."""
    parser = argparse.ArgumentParser(
        description="Valida ventas de Excel y genera un reporte formateado."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ARCHIVO_ENTRADA,
        help=f"Excel de entrada (predeterminado: {ARCHIVO_ENTRADA.name})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ARCHIVO_SALIDA,
        help=f"Reporte a generar (predeterminado: {ARCHIVO_SALIDA.name})",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=ARCHIVO_BD,
        help=f"Base SQLite (predeterminada: {ARCHIVO_BD.name})",
    )
    argumentos = parser.parse_args(argv)
    try:
        generar_reporte(argumentos.input, argumentos.output, argumentos.database)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
