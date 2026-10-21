"""Casos de uso de importación y generación de reportes, independientes de la CLI."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from automatizador.adaptadores import leer_comprobantes
from automatizador.database import crear_tabla, reemplazar_periodo, consultar_comprobantes
from automatizador.reportes import aplicar_formato_excel, construir_hojas
from automatizador.validaciones import validar_comprobantes


@dataclass(frozen=True)
class ResultadoProcesamiento:
    """Resumen de una importación listo para usar desde CLI, interfaz o tests."""

    salida: Path
    comprobantes: pd.DataFrame
    errores: pd.DataFrame
    filas_validas: int
    filas_observadas: int
    totales: dict[str, float]


def procesar(origen, salida, base, periodo, formato="estandar", operacion="ventas", mapping_path=None):
    """Importa comprobantes, actualiza SQLite y genera un informe Excel.

    Devuelve los comprobantes del período, las filas observadas y los totales
    resumidos para que otras interfaces puedan presentar el resultado.
    """
    origen = Path(origen)
    if not origen.exists():
        raise FileNotFoundError(f"No se encontró la ruta de entrada: {origen}")
    extensiones = ("*.xlsx", "*.xlsm", "*.xls", "*.csv", "*.txt", "*.prn")
    archivos = sorted(p for patron in extensiones for p in origen.glob(patron)) if origen.is_dir() else [origen]
    archivos = [p for p in archivos if not p.name.startswith("~$")]
    if not archivos:
        raise ValueError("La carpeta no contiene archivos para importar.")

    base = Path(base)
    base.parent.mkdir(parents=True, exist_ok=True)
    crear_tabla(base)
    rechazos = []
    filas_validas = 0
    for archivo in archivos:
        cliente = archivo.stem.strip()
        archivo_valido = True
        try:
            origen_df = leer_comprobantes(archivo, formato, operacion, mapping_path)
            origen_df["_fila_original"] = range(2, len(origen_df) + 2)
            aceptados, rechazados = validar_comprobantes(origen_df, periodo)
            if "_error_adaptador" in origen_df and not rechazados.empty:
                errores_por_fila = origen_df.set_index("_fila_original")["_error_adaptador"].fillna("").to_dict()
                for idx, fila in rechazados.iterrows():
                    extra = str(errores_por_fila.get(fila.get("fila_excel"), "")).strip()
                    if extra:
                        rechazados.at[idx, "motivo"] = f"{fila['motivo']} {extra}".strip()
            if "_error_adaptador" in aceptados:
                errores = aceptados[aceptados["_error_adaptador"].fillna("").astype(str).str.strip().ne("")].copy()
                if not errores.empty:
                    extra = errores.copy()
                    extra["fila_excel"] = extra["_fila_original"]
                    extra["motivo"] = extra["_error_adaptador"]
                    rechazados = pd.concat([rechazados, extra], ignore_index=True)
                    aceptados = aceptados.drop(index=errores.index)
                aceptados = aceptados.drop(columns=["_error_adaptador", "_fila_original"], errors="ignore")
            rechazados = rechazados.drop(columns=["_error_adaptador", "_fila_original"], errors="ignore")
            if "cliente" not in rechazados.columns:
                rechazados.insert(0, "cliente", cliente)
        except (ValueError, OSError, ImportError) as error:
            archivo_valido = False
            aceptados = pd.DataFrame()
            rechazados = pd.DataFrame([{
                "cliente": cliente, "archivo": archivo.name, "fila_excel": "",
                "motivo": f"No se pudo procesar el archivo: {error}",
            }])
        filas_validas += len(aceptados)
        if archivo_valido and (not aceptados.empty or rechazados.empty):
            reemplazar_periodo(cliente, periodo, aceptados, rechazados, archivo.name, base)
        else:
            logging.error("Se conserva la base previa de %s para %s porque no hay una importación utilizable.", cliente, periodo)
            if archivo_valido and aceptados.empty and not rechazados.empty:
                rechazados = pd.concat([rechazados, pd.DataFrame([{
                    "cliente": cliente,
                    "motivo": "No se reemplazó el período porque no hubo filas aceptadas; se conserva la importación anterior.",
                }])], ignore_index=True)
        rechazos.append(rechazados)
        logging.info("%s: %s aceptados, %s observados.", cliente, len(aceptados), len(rechazados))

    comprobantes = consultar_comprobantes(base, periodo)
    detalle, resumen_cliente, resumen_alicuota = construir_hojas(comprobantes)
    observaciones = pd.concat(rechazos, ignore_index=True) if rechazos else pd.DataFrame()
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        detalle.to_excel(writer, sheet_name="Comprobantes", index=False)
        resumen_cliente.to_excel(writer, sheet_name="Resumen por cliente", index=False)
        resumen_alicuota.to_excel(writer, sheet_name="IVA por alícuota", index=False)
        observaciones.to_excel(writer, sheet_name="Observaciones", index=False)
    aplicar_formato_excel(salida)
    logging.info("Período %s: reporte guardado en %s", periodo, salida)
    logging.info("Observaciones: %s", len(observaciones))
    totales = {
        columna: float(resumen_cliente[columna].sum()) if columna in resumen_cliente else 0.0
        for columna in ("neto_gravado", "iva", "total")
    }
    return ResultadoProcesamiento(
        salida=salida,
        comprobantes=comprobantes,
        errores=observaciones,
        filas_validas=filas_validas,
        filas_observadas=len(observaciones),
        totales=totales,
    )
