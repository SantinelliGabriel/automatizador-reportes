"""Casos de uso de importación y generación de reportes, independientes de la CLI."""

import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd

from automatizador.adaptadores import leer_comprobantes
from automatizador.database import (
    crear_tabla,
    consultar_comprobantes,
    consultar_totales,
    reemplazar_periodos,
)
from automatizador.reportes import (
    aplicar_formato_excel,
    construir_detalle_alicuotas,
    construir_hojas,
)
from automatizador.validaciones import validar_comprobantes


@dataclass(frozen=True)
class ArchivoPrevisualizado:
    cliente: str
    nombre: str
    comprobantes: pd.DataFrame
    observaciones: pd.DataFrame
    aplicar: bool


@dataclass(frozen=True)
class PrevisualizacionImportacion:
    periodo: str
    archivos: tuple[ArchivoPrevisualizado, ...]

    @property
    def filas_validas(self):
        return sum(len(archivo.comprobantes) for archivo in self.archivos)

    @property
    def filas_observadas(self):
        return sum(len(archivo.observaciones) for archivo in self.archivos)

    @property
    def observaciones(self):
        tablas = [a.observaciones for a in self.archivos if not a.observaciones.empty]
        return pd.concat(tablas, ignore_index=True) if tablas else pd.DataFrame()


@dataclass(frozen=True)
class ResultadoProcesamiento:
    """Resumen de una importación listo para usar desde CLI, interfaz o tests."""

    salida: Path
    comprobantes: pd.DataFrame
    errores: pd.DataFrame
    filas_validas: int
    filas_observadas: int
    totales: dict[str, Decimal]


def previsualizar(origen, periodo, formato="estandar", operacion="ventas", mapping_path=None):
    """Lee y valida archivos sin crear ni modificar la base de datos."""
    origen = Path(origen)
    if not origen.exists():
        raise FileNotFoundError(f"No se encontró la ruta de entrada: {origen}")
    extensiones = ("*.xlsx", "*.xlsm", "*.xls", "*.csv", "*.txt", "*.prn")
    archivos = sorted(p for patron in extensiones for p in origen.glob(patron)) if origen.is_dir() else [origen]
    archivos = [p for p in archivos if not p.name.startswith("~$")]
    if not archivos:
        raise ValueError("La carpeta no contiene archivos para importar.")

    previsualizados = []
    for archivo in archivos:
        cliente = archivo.stem.strip()
        aplicar = True
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
            if aceptados.empty and not rechazados.empty:
                aplicar = False
        except (ValueError, OSError, ImportError) as error:
            aplicar = False
            aceptados = pd.DataFrame()
            rechazados = pd.DataFrame([{
                "cliente": cliente,
                "archivo": archivo.name,
                "fila_excel": "",
                "motivo": f"No se pudo procesar el archivo: {error}",
            }])
        previsualizados.append(ArchivoPrevisualizado(
            cliente=cliente,
            nombre=archivo.name,
            comprobantes=aceptados,
            observaciones=rechazados,
            aplicar=aplicar,
        ))
        logging.info("%s: %s aceptados, %s observados.", cliente, len(aceptados), len(rechazados))
    return PrevisualizacionImportacion(periodo=periodo, archivos=tuple(previsualizados))


def confirmar_previsualizacion(previsualizacion, salida, base):
    """Aplica de forma atómica los archivos utilizables y genera el informe."""
    crear_tabla(base)
    lotes = [
        {
            "cliente": archivo.cliente,
            "periodo": previsualizacion.periodo,
            "comprobantes": archivo.comprobantes,
            "rechazados": archivo.observaciones,
            "archivo_origen": archivo.nombre,
        }
        for archivo in previsualizacion.archivos
        if archivo.aplicar
    ]
    if lotes:
        reemplazar_periodos(lotes, base)

    comprobantes = consultar_comprobantes(base, previsualizacion.periodo)
    detalle, resumen_cliente, resumen_alicuota = construir_hojas(comprobantes)
    detalle_iva = construir_detalle_alicuotas(comprobantes)
    observaciones = previsualizacion.observaciones
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        detalle.to_excel(writer, sheet_name="Comprobantes", index=False)
        detalle_iva.to_excel(writer, sheet_name="Detalle IVA", index=False)
        resumen_cliente.to_excel(writer, sheet_name="Resumen por cliente", index=False)
        resumen_alicuota.to_excel(writer, sheet_name="IVA por alícuota", index=False)
        observaciones.to_excel(writer, sheet_name="Observaciones", index=False)
    aplicar_formato_excel(salida)
    logging.info("Período %s: reporte guardado en %s", previsualizacion.periodo, salida)
    logging.info("Observaciones: %s", len(observaciones))
    totales = consultar_totales(base, previsualizacion.periodo)
    return ResultadoProcesamiento(
        salida=salida,
        comprobantes=comprobantes,
        errores=observaciones,
        filas_validas=previsualizacion.filas_validas,
        filas_observadas=previsualizacion.filas_observadas,
        totales=totales,
    )


def procesar(origen, salida, base, periodo, formato="estandar", operacion="ventas", mapping_path=None):
    """Compatibilidad de una sola llamada: previsualiza, confirma y genera informe."""
    plan = previsualizar(origen, periodo, formato, operacion, mapping_path)
    return confirmar_previsualizacion(plan, salida, base)
