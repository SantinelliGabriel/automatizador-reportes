from database import (crear_tabla,guardar_ventas,consultar_ventas,)
from validaciones import validar_ventas
from reportes import aplicar_formato_excel
from config import ARCHIVO_ENTRADA, ARCHIVO_SALIDA
import logging
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def generar_reporte():
    """Lee, valida, calcula y genera el reporte de ventas."""
    logging.info("Iniciando la generación del reporte.")

    if not ARCHIVO_ENTRADA.exists():
        raise FileNotFoundError(
            f"No se encontró '{ARCHIVO_ENTRADA.name}'. "
            "Colocá el archivo en la carpeta del proyecto."
        )

    try:
        ventas = pd.read_excel(ARCHIVO_ENTRADA)
    except PermissionError as error:
        raise RuntimeError(
            "No se puede leer el archivo. Comprobá sus permisos."
        ) from error
    except (OSError, ValueError) as error:
        raise RuntimeError(
            "No se pudo leer el Excel. Comprobá que sea válido."
        ) from error

    ventas = validar_ventas(ventas)

    crear_tabla()
    guardar_ventas(ventas)

    ventas = consultar_ventas()
    total_ventas = ventas["total"].sum()

    if not pd.notna(total_ventas) or abs(total_ventas) == float("inf"):
        raise ValueError("El total calculado no es válido.")

    fila_total = {
        "producto": "TOTAL GENERAL",
        "unidades": ventas["unidades"].sum(),
        "precio_unitario": None,
        "total": total_ventas,
    }

    reporte = pd.concat(
        [ventas, pd.DataFrame([fila_total])],
        ignore_index=True,
    )

    try:
        reporte.to_excel(ARCHIVO_SALIDA, index=False)
        aplicar_formato_excel(ARCHIVO_SALIDA)
    except PermissionError as error:
        raise RuntimeError(
            "No se pudo guardar el reporte. Cerrá el Excel de salida "
            "si está abierto e intentá nuevamente."
        ) from error
    except OSError as error:
        raise RuntimeError(
            "Ocurrió un problema al guardar el reporte."
        ) from error

    logging.info("Reporte generado correctamente.")
    logging.info("Productos procesados: %s", len(ventas))
    logging.info("Total de ventas: $%s", f"{total_ventas:,.2f}")
    logging.info("Archivo generado: %s", ARCHIVO_SALIDA)


if __name__ == "__main__":
    try:
        generar_reporte()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        logging.error("%s", error)
