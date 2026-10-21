"""Interfaz local en Streamlit para importaciones, conciliación y vencimientos."""

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from adaptadores import ejemplo_mapeo_holistor, _leer
from config import ARCHIVO_BD
from conciliacion import conciliar_banco, exportar_conciliacion
from database import crear_tabla, consultar_comprobantes
from main import procesar
from vencimientos import cargar_calendario, proximos_vencimientos


st.set_page_config(page_title="Comprobantes e IVA", page_icon="📑", layout="wide")
st.title("Comprobantes e informes de IVA")
st.caption("Herramienta local de revisión. Los archivos se procesan en esta computadora.")

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

    if st.button("Importar y generar reporte", type="primary", disabled=not archivos or (fuente == "Plantilla Holistor" and not mapeo_texto)):
        try:
            if len(periodo) != 7 or periodo[4] != "-" or not periodo.replace("-", "").isdigit() or not 1 <= int(periodo[5:]) <= 12:
                raise ValueError("El período debe tener el formato AAAA-MM.")
            with tempfile.TemporaryDirectory(prefix="comprobantes_") as carpeta:
                _guardar_subidos(archivos, carpeta)
                mapping_path = None
                if mapeo_texto:
                    mapping_path = Path(carpeta) / "mapeo_holistor.json"
                    mapping_path.write_text(mapeo_texto, encoding="utf-8")
                salida = Path(carpeta) / "reporte.xlsx"
                procesar(carpeta, salida, base, periodo, formatos[fuente], operacion, mapping_path)
                st.success("Importación terminada. Revisá la hoja Observaciones para las filas rechazadas.")
                st.download_button("Descargar reporte Excel", salida.read_bytes(), file_name=f"reporte_iva_{periodo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as error:
            st.error(str(error))


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
                st.caption("Se esperan créditos bancarios positivos para ventas y débitos negativos para compras.")
                if st.button("Conciliar", type="primary"):
                    try:
                        crear_tabla(base)
                        comprobantes = consultar_comprobantes(base, periodo_conciliacion)
                        if comprobantes.empty:
                            raise ValueError("No hay comprobantes guardados para ese período.")
                        banco, docs = conciliar_banco(ruta_banco, comprobantes, fecha_col, importe_col, None if descripcion_col == "(ninguna)" else descripcion_col, int(margen_dias), float(margen_importe))
                        salida = Path(carpeta) / f"conciliacion_{periodo}.xlsx"
                        exportar_conciliacion(salida, banco, docs)
                        conciliados = int((banco["Estado"] == "Conciliado").sum())
                        st.metric("Movimientos conciliados", conciliados)
                        st.dataframe(banco, use_container_width=True)
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
                    calendario_path = Path(__file__).parent / "vencimientos_iva_2026_10.csv"
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
