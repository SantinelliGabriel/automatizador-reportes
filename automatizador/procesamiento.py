"""Casos de uso de importación y generación de reportes, independientes de la CLI."""

import logging
import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd

from automatizador.adaptadores import leer_comprobantes
from automatizador.clientes import clave_cliente
from automatizador.database import (
    MigracionBase,
    consultar_totales,
)
from automatizador.lotes import operaciones_aceptadas, resolver_conflictos
from automatizador.repositorio import RepositorioComprobantes, RepositorioSQLite
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
    sha256: str = ""
    conflicto: str | None = None


@dataclass(frozen=True)
class PrevisualizacionImportacion:
    periodo: str
    archivos: tuple[ArchivoPrevisualizado, ...]

    @property
    def filas_validas(self):
        return sum(len(archivo.comprobantes) for archivo in self.archivos if archivo.aplicar)

    @property
    def filas_observadas(self):
        return sum(len(archivo.observaciones) for archivo in self.archivos)

    @property
    def observaciones(self):
        tablas = [a.observaciones for a in self.archivos if not a.observaciones.empty]
        return pd.concat(tablas, ignore_index=True) if tablas else pd.DataFrame()

    @property
    def conflictos(self) -> tuple[str, ...]:
        return tuple(archivo.conflicto for archivo in self.archivos if archivo.conflicto is not None)


@dataclass(frozen=True)
class ResultadoProcesamiento:
    """Resumen de una importación listo para usar desde CLI, interfaz o tests."""

    salida: Path
    comprobantes: pd.DataFrame
    errores: pd.DataFrame
    filas_validas: int
    filas_observadas: int
    totales: dict[str, Decimal]
    migracion: MigracionBase | None = None
    operaciones_reemplazadas: tuple[str, ...] = ()
    operaciones_conservadas: tuple[str, ...] = ()
    conflictos: tuple[str, ...] = ()


def previsualizar(origen, periodo, formato="estandar", operacion="ventas", mapping_path=None,
                  cliente=None, nombre_archivo=None):
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
        cliente_actual = cliente if cliente is not None else archivo.stem.strip()
        clave_cliente(cliente_actual)
        digest = hashlib.sha256()
        sha256 = ""
        aplicar = True
        try:
            with archivo.open("rb") as origen_bytes:
                for bloque in iter(lambda: origen_bytes.read(1024 * 1024), b""):
                    digest.update(bloque)
            sha256 = digest.hexdigest()
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
                rechazados.insert(0, "cliente", cliente_actual)
            elif cliente is not None:
                rechazados["cliente"] = cliente_actual
            if aceptados.empty and not rechazados.empty:
                aplicar = False
        except (ValueError, OSError, ImportError) as error:
            aplicar = False
            aceptados = pd.DataFrame()
            rechazados = pd.DataFrame([{
                "cliente": cliente_actual,
                "archivo": nombre_archivo or archivo.name,
                "fila_excel": "",
                "motivo": f"No se pudo procesar el archivo: {error}",
            }])
        previsualizados.append(ArchivoPrevisualizado(
            cliente=cliente_actual,
            nombre=nombre_archivo or archivo.name,
            comprobantes=aceptados,
            observaciones=rechazados,
            aplicar=aplicar,
            sha256=sha256,
        ))
        logging.info("Archivo previsualizado: %s aceptados, %s observados.", len(aceptados), len(rechazados))
    lotes = resolver_conflictos([{
        "cliente": archivo.cliente, "periodo": periodo, "comprobantes": archivo.comprobantes,
        "rechazados": archivo.observaciones, "aplicar": archivo.aplicar,
    } for archivo in previsualizados])
    return PrevisualizacionImportacion(periodo=periodo, archivos=tuple(
        ArchivoPrevisualizado(
            cliente=archivo.cliente, nombre=archivo.nombre, comprobantes=archivo.comprobantes,
            observaciones=lote["rechazados"], aplicar=lote["aplicar"], sha256=archivo.sha256,
            conflicto=lote.get("conflicto"),
        ) for archivo, lote in zip(previsualizados, lotes)
    ))


def confirmar_importacion(previsualizacion: PrevisualizacionImportacion,
                          repositorio: RepositorioComprobantes) -> list[int]:
    """Confirma comprobantes y observaciones; no genera archivos."""
    lotes = [
        {
            "cliente": archivo.cliente,
            "periodo": previsualizacion.periodo,
            "comprobantes": archivo.comprobantes,
            "rechazados": archivo.observaciones,
            "archivo_origen": archivo.nombre,
            "sha256": archivo.sha256,
            "aplicar": archivo.aplicar,
        }
        for archivo in previsualizacion.archivos
    ]
    return repositorio.reemplazar_periodos(lotes) if lotes else []


def generar_informe(periodo: str, salida: Path, repositorio: RepositorioComprobantes) -> Path:
    """Regenera el Excel desde los datos confirmados en el repositorio."""
    comprobantes = repositorio.consultar_comprobantes(periodo)
    detalle, resumen_cliente, resumen_alicuota = construir_hojas(comprobantes)
    detalle_iva = construir_detalle_alicuotas(comprobantes)
    observaciones = repositorio.consultar_observaciones(periodo)
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        detalle.to_excel(writer, sheet_name="Comprobantes", index=False)
        detalle_iva.to_excel(writer, sheet_name="Detalle IVA", index=False)
        resumen_cliente.to_excel(writer, sheet_name="Resumen por cliente", index=False)
        resumen_alicuota.to_excel(writer, sheet_name="IVA por alícuota", index=False)
        observaciones.to_excel(writer, sheet_name="Observaciones", index=False)
    aplicar_formato_excel(salida)
    logging.info("Período %s: reporte guardado en %s", periodo, salida)
    logging.info("Observaciones: %s", len(observaciones))
    return salida


def confirmar_previsualizacion(previsualizacion, salida, base):
    """Compatibilidad: confirma y genera el informe para CLI y Streamlit."""
    repositorio = RepositorioSQLite(base)
    anteriores = repositorio.consultar_comprobantes(previsualizacion.periodo)
    reemplazadas = {
        (archivo.cliente, operacion)
        for archivo in previsualizacion.archivos if archivo.aplicar
        for operacion in operaciones_aceptadas({"comprobantes": archivo.comprobantes})
    }
    conservadas = ({(fila.cliente, fila.operacion) for fila in anteriores.itertuples()}
                  - reemplazadas)
    confirmar_importacion(previsualizacion, repositorio)
    salida = generar_informe(previsualizacion.periodo, salida, repositorio)
    comprobantes = repositorio.consultar_comprobantes(previsualizacion.periodo)
    observaciones = previsualizacion.observaciones
    totales = consultar_totales(base, previsualizacion.periodo)
    return ResultadoProcesamiento(
        salida=salida,
        comprobantes=comprobantes,
        errores=observaciones,
        filas_validas=previsualizacion.filas_validas,
        filas_observadas=previsualizacion.filas_observadas,
        totales=totales,
        migracion=repositorio.migracion,
        operaciones_reemplazadas=tuple(f"{cliente}: {operacion}" for cliente, operacion in sorted(reemplazadas)),
        operaciones_conservadas=tuple(f"{cliente}: {operacion}" for cliente, operacion in sorted(conservadas)),
        conflictos=previsualizacion.conflictos,
    )


def procesar(origen, salida, base, periodo, formato="estandar", operacion="ventas", mapping_path=None):
    """Compatibilidad de una sola llamada: previsualiza, confirma y genera informe."""
    plan = previsualizar(origen, periodo, formato, operacion, mapping_path)
    return confirmar_previsualizacion(plan, salida, base)
