
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter


CARPETA_PROYECTO = Path(__file__).parent
ARCHIVO_ENTRADA = CARPETA_PROYECTO / "ventas_entrada.xlsx"
ARCHIVO_SALIDA = CARPETA_PROYECTO / "reporte_ventas.xlsx"

COLUMNAS_REQUERIDAS = [
    "producto",
    "unidades",
    "precio_unitario",
]


def validar_ventas(ventas):
    """Comprueba que los datos de ventas sean válidos."""

    if ventas.empty:
        raise ValueError("El Excel no contiene ventas para procesar.")

    columnas_faltantes = [
        columna
        for columna in COLUMNAS_REQUERIDAS
        if columna not in ventas.columns
    ]

    if columnas_faltantes:
        raise ValueError(
            "Faltan estas columnas en el Excel: "
            + ", ".join(columnas_faltantes)
        )

    if ventas[COLUMNAS_REQUERIDAS].isna().any().any():
        raise ValueError("Hay celdas vacías en los datos de ventas.")

    nombres = ventas["producto"].astype(str).str.strip()

    if nombres.eq("").any():
        raise ValueError("Hay productos sin nombre.")

    for columna in ["unidades", "precio_unitario"]:
        try:
            ventas[columna] = pd.to_numeric(
                ventas[columna],
                errors="raise",
            )
        except (ValueError, TypeError) as error:
            raise ValueError(
                f"La columna '{columna}' contiene valores no numéricos."
            ) from error

        if not ventas[columna].map(
            lambda valor: pd.notna(valor) and abs(valor) != float("inf")
        ).all():
            raise ValueError(
                f"La columna '{columna}' contiene números no válidos."
            )

    if (ventas["unidades"] <= 0).any():
        raise ValueError("Las unidades deben ser mayores que cero.")

    if (ventas["unidades"] % 1 != 0).any():
        raise ValueError("Las unidades deben ser números enteros.")

    if (ventas["precio_unitario"] < 0).any():
        raise ValueError("Los precios no pueden ser negativos.")

    return ventas


def aplicar_formato_excel(ruta_archivo):
    """Aplica formato profesional al reporte generado."""

    libro = load_workbook(ruta_archivo)
    hoja = libro.active

    azul_oscuro = "1F4E78"
    azul_claro = "D9EAF7"
    blanco = "FFFFFF"

    for celda in hoja[1]:
        celda.fill = PatternFill(
            fill_type="solid",
            fgColor=azul_oscuro,
        )
        celda.font = Font(bold=True, color=blanco, size=11)
        celda.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

    for columna in hoja.columns:
        letra = get_column_letter(columna[0].column)
        ancho = max(
            len(str(celda.value or ""))
            for celda in columna
        )
        hoja.column_dimensions[letra].width = ancho + 4

    for fila in range(2, hoja.max_row + 1):
        hoja.cell(fila, 3).number_format = '"$"#,##0.00'
        hoja.cell(fila, 4).number_format = '"$"#,##0.00'

        for columna in [2, 3, 4]:
            hoja.cell(fila, columna).alignment = Alignment(
                horizontal="right"
            )

    for celda in hoja[hoja.max_row]:
        celda.fill = PatternFill(
            fill_type="solid",
            fgColor=azul_claro,
        )
        celda.font = Font(bold=True, color=azul_oscuro)
        celda.border = Border(
            top=Side(style="thin", color=azul_oscuro)
        )

    hoja.freeze_panes = "A2"

    # Los filtros abarcan los encabezados y los productos,
    # sin incluir la fila TOTAL GENERAL.
    hoja.auto_filter.ref = f"A1:D{hoja.max_row - 1}"
    hoja.row_dimensions[1].height = 24

    libro.save(ruta_archivo)
    libro.close()


def generar_reporte():
    """Lee, valida, calcula y genera el reporte de ventas."""

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

    ventas["total"] = ventas["unidades"] * ventas["precio_unitario"]
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

    print("Reporte generado correctamente.")
    print(f"Productos procesados: {len(ventas)}")
    print(f"Total de ventas: ${total_ventas:,.2f}")
    print(f"Archivo generado: {ARCHIVO_SALIDA}")


if __name__ == "__main__":
    try:
        generar_reporte()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}")
