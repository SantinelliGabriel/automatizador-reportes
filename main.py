"""Importa comprobantes contables y genera un libro consolidado."""

import argparse
import logging
import sqlite3
from pathlib import Path

import pandas as pd

from config import ARCHIVO_BD, ARCHIVO_ENTRADA, ARCHIVO_SALIDA
from adaptadores import leer_comprobantes
from database import crear_tabla, reemplazar_periodo, consultar_comprobantes, consultar_importaciones
from reportes import aplicar_formato_excel, construir_hojas
from validaciones import validar_comprobantes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def procesar(origen, salida, base, periodo, formato="estandar", operacion="ventas", mapping_path=None):
    origen = Path(origen)
    if not origen.exists():
        raise FileNotFoundError(f"No se encontró la ruta de entrada: {origen}")
    extensiones = ("*.xlsx", "*.xlsm", "*.xls", "*.csv", "*.txt", "*.prn")
    archivos = sorted(p for patron in extensiones for p in origen.glob(patron)) if origen.is_dir() else [origen]
    archivos = [p for p in archivos if not p.name.startswith("~$")]
    if not archivos:
        raise ValueError("La carpeta no contiene archivos .xlsx para importar.")

    base = Path(base)
    base.parent.mkdir(parents=True, exist_ok=True)
    crear_tabla(base)
    rechazos = []
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
    return salida


def main(argv=None):
    parser = argparse.ArgumentParser(description="Valida comprobantes de ventas y compras y genera reportes por período.")
    parser.add_argument("--input", type=Path, default=ARCHIVO_ENTRADA, help="Excel de un cliente o carpeta con un Excel por cliente.")
    parser.add_argument("--output", type=Path, default=ARCHIVO_SALIDA, help="Libro consolidado a generar.")
    parser.add_argument("--database", type=Path, default=ARCHIVO_BD, help="Base SQLite de comprobantes.")
    parser.add_argument("--period", help="Período mensual a procesar, formato AAAA-MM.")
    parser.add_argument("--source", choices=("estandar", "arca", "holistor"), default="estandar", help="Formato del archivo de entrada.")
    parser.add_argument("--operation", choices=("ventas", "compras"), default="ventas", help="Libro asociado a la descarga ARCA/Holistor.")
    parser.add_argument("--mapping", type=Path, help="JSON de mapeo de columnas/ancho fijo para la plantilla Holistor.")
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
            parser.error("--period es obligatorio y debe usar el formato AAAA-MM con mes entre 01 y 12.")
        procesar(args.input, args.output, args.database, args.period, args.source, args.operation, args.mapping)
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.Error, OSError) as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
