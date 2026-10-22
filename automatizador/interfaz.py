"""Interfaz local en Streamlit para importaciones, conciliación y vencimientos."""

import json
import hashlib
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from automatizador.adaptadores import ejemplo_mapeo_holistor, _leer
from automatizador.config import ARCHIVO_BD
from automatizador.conciliacion import conciliar_banco, exportar_conciliacion
from automatizador.database import crear_tabla, consultar_comprobantes
from automatizador.procesamiento import confirmar_previsualizacion, previsualizar, procesar
from automatizador.vencimientos import cargar_calendario, proximos_vencimientos


st.set_page_config(page_title="Comprobantes e IVA", page_icon="📑", layout="wide")
st.title("Comprobantes e informes de IVA")
modo_demo = os.getenv("AUTOMATIZADOR_DEMO") == "1"
st.caption(
    "Modo demo: se muestran datos ficticios; la carga de archivos está deshabilitada."
    if modo_demo else "Herramienta local de revisión. Los archivos se procesan en esta computadora."
)

if modo_demo:
    st.subheader("Demostración con comprobantes sintéticos")
    st.info("Esta vista usa únicamente el archivo de ejemplo incluido en el repositorio. No acepta archivos ni datos ingresados por visitantes.")
    ejemplo = Path(__file__).resolve().parents[1] / "ejemplos" / "Cliente Demo Norte.xlsx"
    demo_db = Path(tempfile.gettempdir()) / "automatizador_demo.db"
    if "demo_resultado" not in st.session_state:
        with tempfile.TemporaryDirectory(prefix="demo_iva_") as carpeta:
            resultado = procesar(ejemplo, Path(carpeta) / "reporte.xlsx", demo_db, "2026-09")
            st.session_state["demo_resultado"] = resultado.comprobantes
            st.session_state["demo_totales"] = resultado.totales
            st.session_state["demo_reporte"] = (Path(carpeta) / "reporte.xlsx").read_bytes()
    st.caption("Período de muestra: septiembre de 2026. Importes consolidados en pesos argentinos.")
    metricas = st.columns(4)
    metricas[0].metric("Comprobantes", len(st.session_state["demo_resultado"]))
    for indice, (columna, etiqueta) in enumerate(
        (("neto_gravado", "Neto gravado"), ("iva", "IVA"), ("total", "Total")), start=1
    ):
        metricas[indice].metric(
            f"{etiqueta} (ARS)", f"${st.session_state['demo_totales'][columna]:,.2f}"
        )
    columnas_demo = ["cliente", "operacion", "fecha", "tipo_comprobante", "numero", "total"]
    st.dataframe(
        st.session_state["demo_resultado"][columnas_demo],
        hide_index=True,
        width="stretch",
        column_config={"total": st.column_config.NumberColumn("Total (ARS)", format="$%.2f")},
    )
    st.download_button(
        "Descargar reporte ficticio",
        st.session_state["demo_reporte"],
        file_name="reporte_iva_demo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.stop()

pagina = st.sidebar.radio("Módulo", ["Importar comprobantes", "Conciliación bancaria", "Vencimientos"])
base = Path(st.sidebar.text_input("Base SQLite", str(ARCHIVO_BD)))


def _guardar_subidos(archivos, carpeta):
    rutas = []
    for archivo in archivos:
        nombre = Path(archivo.name).name
        ruta = Path(carpeta) / nombre
        ruta.write_bytes(archivo.getvalue())
        rutas.append(ruta)
    return rutas


def _firma_importacion(archivos, periodo, operacion, fuente, base, mapeo):
    """Detecta cambios en los archivos/opciones después de generar la vista previa."""
    hashes = [(a.name, hashlib.sha256(a.getvalue()).hexdigest()) for a in (archivos or [])]
    datos = json.dumps(
        [hashes, periodo, operacion, fuente, str(base), mapeo],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(datos.encode("utf-8")).hexdigest()


def _mapeo_holistor():
    ejemplo = json.dumps(ejemplo_mapeo_holistor(), ensure_ascii=False, indent=2)
    texto = st.text_area("Mapeo JSON de Holistor (ajustá los encabezados a tu plantilla)", value=ejemplo, height=260)
    try:
        json.loads(texto)
        return texto
    except json.JSONDecodeError as error:
        st.error(f"El JSON no es válido: {error}")
        return None


if pagina == "Importar comprobantes":
    st.subheader("Importación mensual")
    fuente = st.selectbox("Formato de origen", ["Excel estándar", "Mis Comprobantes ARCA", "Plantilla Holistor"])
    formatos = {"Excel estándar": "estandar", "Mis Comprobantes ARCA": "arca", "Plantilla Holistor": "holistor"}
    periodo = st.text_input("Período (AAAA-MM)", value=pd.Timestamp.today().strftime("%Y-%m"))
    operacion = st.selectbox("Operación", ["ventas", "compras"])
    extensiones = ["xlsx", "xls", "xlsm", "csv", "txt"] if fuente != "Plantilla Holistor" else ["xlsx", "xls", "xlsm", "csv", "txt", "prn"]
    archivos = st.file_uploader("Un archivo por cliente", type=extensiones, accept_multiple_files=True)
    mapeo_texto = _mapeo_holistor() if fuente == "Plantilla Holistor" else None
    if fuente == "Plantilla Holistor":
        st.info("Holistor distribuye modelos según producto y versión. El adaptador acepta encabezados normalizados o este mapeo editable; para .prn se configuran además anchos y columnas.")

    firma = _firma_importacion(archivos, periodo, operacion, fuente, base, mapeo_texto)
    plan_guardado = st.session_state.get("plan_importacion")
    firma_confirmada = st.session_state.get("firma_confirmada")
    if (
        archivos
        and (fuente != "Plantilla Holistor" or mapeo_texto)
        and (plan_guardado is None or plan_guardado["firma"] != firma)
        and firma_confirmada != firma
    ):
        try:
            if len(periodo) != 7 or periodo[4] != "-" or not periodo.replace("-", "").isdigit() or not 1 <= int(periodo[5:]) <= 12:
                raise ValueError("El período debe tener el formato AAAA-MM.")
            with tempfile.TemporaryDirectory(prefix="comprobantes_") as carpeta:
                _guardar_subidos(archivos, carpeta)
                mapping_path = None
                if mapeo_texto:
                    mapping_path = Path(carpeta) / "mapeo_holistor.json"
                    mapping_path.write_text(mapeo_texto, encoding="utf-8")
                plan = previsualizar(carpeta, periodo, formatos[fuente], operacion, mapping_path)
                st.session_state["plan_importacion"] = {"firma": firma, "plan": plan, "base": str(base)}
                st.session_state.pop("resultado_importacion", None)
                plan_guardado = st.session_state["plan_importacion"]
        except Exception as error:
            st.error(str(error))

    if plan_guardado and plan_guardado["firma"] == firma:
        plan = plan_guardado["plan"]
        st.subheader("Vista previa: todavía no se modificó la base")
        st.caption("La vista previa se recalcula al cambiar los archivos o las opciones. La base se actualiza solo después de confirmar.")
        metrica = st.columns(3)
        metrica[0].metric("Archivos", len(plan.archivos))
        metrica[1].metric("Filas válidas", plan.filas_validas)
        metrica[2].metric("Filas observadas", plan.filas_observadas)
        st.dataframe(pd.DataFrame([{
            "Cliente": archivo.cliente,
            "Archivo": archivo.nombre,
            "Válidos": len(archivo.comprobantes),
            "Observados": len(archivo.observaciones),
            "Se aplicará": "Sí" if archivo.aplicar else "No; conserva los datos actuales",
        } for archivo in plan.archivos]), hide_index=True, width="stretch")
        if plan.filas_validas:
            filas_vista = pd.concat(
                [a.comprobantes.assign(cliente=a.cliente) for a in plan.archivos if not a.comprobantes.empty],
                ignore_index=True,
            )
            st.caption("Muestra de comprobantes que se importarían (hasta 100 filas).")
            st.dataframe(filas_vista.head(100), hide_index=True, width="stretch")
        if plan.filas_observadas:
            with st.expander("Ver observaciones"):
                st.dataframe(plan.observaciones, hide_index=True, width="stretch")
        confirmar_click = st.button("Confirmar importación y generar reporte", type="primary")
        if confirmar_click:
            try:
                with tempfile.TemporaryDirectory(prefix="reporte_iva_") as carpeta:
                    salida = Path(carpeta) / f"reporte_iva_{periodo}.xlsx"
                    resultado = confirmar_previsualizacion(plan, salida, Path(plan_guardado["base"]))
                    st.session_state["resultado_importacion"] = {
                        "periodo": periodo,
                        "filas_validas": resultado.filas_validas,
                        "filas_observadas": resultado.filas_observadas,
                        "totales": resultado.totales,
                        "reporte": salida.read_bytes(),
                        "migracion": resultado.migracion,
                    }
                    st.session_state["firma_confirmada"] = firma
                st.session_state.pop("plan_importacion", None)
                st.rerun()
            except Exception as error:
                st.error(f"No se confirmó la importación: {error}")

    resultado_guardado = st.session_state.get("resultado_importacion")
    if resultado_guardado and resultado_guardado["periodo"] == periodo:
        if resultado_guardado["migracion"]:
            st.info(resultado_guardado["migracion"].mensaje())
        st.success(
            f"Importación terminada y confirmada: {resultado_guardado['filas_validas']} filas válidas y "
            f"{resultado_guardado['filas_observadas']} observadas."
        )
        st.write("Totales (ARS)", {
            columna: f"${importe:,.2f}" for columna, importe in resultado_guardado["totales"].items()
        })
        st.download_button(
            "Descargar reporte Excel",
            resultado_guardado["reporte"],
            file_name=f"reporte_iva_{periodo}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


elif pagina == "Conciliación bancaria":
    st.subheader("Conciliar extracto bancario con comprobantes")
    periodo = st.text_input("Período a conciliar (AAAA-MM)", value=pd.Timestamp.today().strftime("%Y-%m"), key="periodo_conciliacion")
    archivo_banco = st.file_uploader("Extracto bancario CSV o Excel", type=["csv", "xlsx", "xls"])
    if archivo_banco:
        with tempfile.TemporaryDirectory(prefix="extracto_") as carpeta:
            ruta_banco = _guardar_subidos([archivo_banco], carpeta)[0]
            try:
                muestra = _leer(ruta_banco)
                columnas = list(muestra.columns)
                c1, c2, c3 = st.columns(3)
                with c1:
                    fecha_col = st.selectbox("Columna fecha", columnas)
                with c2:
                    importe_col = st.selectbox("Columna importe firmado", columnas, index=min(1, len(columnas)-1))
                with c3:
                    descripcion_col = st.selectbox("Columna descripción (opcional)", ["(ninguna)"] + columnas)
                margen_dias = st.number_input("Diferencia máxima de días", min_value=0, max_value=30, value=3)
                margen_importe = st.number_input("Tolerancia de importe ($)", min_value=0.0, value=0.01, step=0.01)
                st.caption(
                    "Se esperan créditos positivos para ventas y débitos negativos para compras. "
                    "Las referencias del detalle se priorizan; los empates y posibles pagos agrupados "
                    "se marcan para revisión y no se concilian automáticamente."
                )
                if st.button("Conciliar", type="primary"):
                    try:
                        crear_tabla(base)
                        comprobantes = consultar_comprobantes(base, periodo)
                        if comprobantes.empty:
                            raise ValueError("No hay comprobantes guardados para ese período.")
                        banco, docs = conciliar_banco(ruta_banco, comprobantes, fecha_col, importe_col, None if descripcion_col == "(ninguna)" else descripcion_col, int(margen_dias), float(margen_importe))
                        salida = Path(carpeta) / f"conciliacion_{periodo}.xlsx"
                        exportar_conciliacion(salida, banco, docs)
                        conciliados = int((banco["Estado"] == "Conciliado").sum())
                        ambiguos = int(banco["Estado"].str.contains("ambigua|revisar", case=False, regex=True).sum())
                        metricas = st.columns(3)
                        metricas[0].metric("Movimientos conciliados", conciliados)
                        metricas[1].metric("Para revisar", ambiguos)
                        metricas[2].metric("Sin coincidencia", int((banco["Estado"] == "Sin coincidencia").sum()))
                        st.dataframe(banco, use_container_width=True)
                        with st.expander("Estado de los comprobantes"):
                            st.dataframe(docs, use_container_width=True)
                        st.download_button("Descargar conciliación", salida.read_bytes(), file_name=salida.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    except Exception as error:
                        st.error(str(error))
            except Exception as error:
                st.error(f"No se pudo leer el extracto: {error}")


else:
    st.subheader("Vencimientos por cliente")
    st.caption("Las fechas cambian por obligación y período. Cargá el calendario oficial actualizado de ARCA; el archivo de ejemplo solo cubre octubre de 2026.")
    calendario_subido = st.file_uploader("Calendario oficial CSV o Excel (opcional)", type=["csv", "xlsx", "xls"])
    clientes_subidos = st.file_uploader("Clientes CSV/Excel con columnas cliente y cuit", type=["csv", "xlsx", "xls"])
    dias = st.slider("Avisar dentro de los próximos días", min_value=1, max_value=90, value=14)
    if st.button("Consultar agenda", type="primary", disabled=not clientes_subidos):
        try:
            calendario_path = None
            clientes_path = None
            with tempfile.TemporaryDirectory(prefix="agenda_") as carpeta:
                if calendario_subido:
                    calendario_path = _guardar_subidos([calendario_subido], carpeta)[0]
                else:
                    calendario_path = Path(__file__).resolve().parents[1] / "ejemplos" / "vencimientos_iva_2026_10.csv"
                clientes_path = _guardar_subidos([clientes_subidos], carpeta)[0]
                calendario = cargar_calendario(calendario_path)
                clientes_df = _leer(clientes_path)
                renombres = {str(c).strip().casefold(): c for c in clientes_df.columns}
                if "cliente" not in renombres or "cuit" not in renombres:
                    raise ValueError("El archivo de clientes requiere las columnas cliente y cuit.")
                clientes = clientes_df.rename(columns={renombres["cliente"]: "cliente", renombres["cuit"]: "cuit"})[["cliente", "cuit"]].to_dict("records")
                agenda = proximos_vencimientos(clientes, calendario, dias=int(dias))
                if agenda.empty:
                    st.info("No hay vencimientos en el rango elegido según el calendario cargado.")
                else:
                    proximo = agenda.iloc[0]
                    if proximo["dias_restantes"] <= 3:
                        st.warning(f"Próximo vencimiento: {proximo['impuesto']} para {proximo['cliente']} el {proximo['fecha_vencimiento']}.")
                    st.dataframe(agenda, use_container_width=True)
        except Exception as error:
            st.error(str(error))
