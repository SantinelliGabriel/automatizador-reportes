"""Lectores para Excel común, Mis Comprobantes de ARCA y plantillas Holistor."""

import csv
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

from automatizador.validaciones import clave_encabezado, normalizar_columnas


ARCA_CAMPOS = {
    "fecha": {"fecha", "fechaemision", "fechadeemision"},
    "tipo": {"tipo", "tipodecomprobante"},
    "punto_venta": {"puntodeventa"},
    "numero_desde": {"numerodesde", "nrodesde"},
    "numero_hasta": {"numerohasta", "nrohasta"},
    "cuit": {"nrodocemisor", "nrodocreceptor", "cuit"},
    "razon_social": {"denominacionemisor", "denominacionreceptor", "razonsocial"},
    "neto_gravado": {"impnetogravado", "impnetogravadototal"},
    "no_gravado": {"impnetonogravado", "impnetonogravadototal"},
    "exento": {"impoperacionesexentas", "impopexentas", "exento"},
    "otros": {"otrostributos"},
    "iva": {"iva", "impuestoiva"},
    "total": {"imptotal", "importetotal", "total"},
    "moneda": {"moneda"},
    "cambio": {"tipocambio"},
}

TIPOS_ARCA = {
    "1": "A", "2": "ND A", "3": "NC A",
    "6": "B", "7": "ND B", "8": "NC B",
    "11": "C", "12": "ND C", "13": "NC C",
    "19": "E", "20": "ND E", "21": "NC E",
    "51": "M", "52": "ND M", "53": "NC M",
}
TASAS = (0, 2.5, 5, 10.5, 21, 27)


def _agregar_error(actual, nuevo):
    return f"{actual} {nuevo}".strip()


def _tasa_de_clave(clave):
    coincidencia = re.search(r"(?:iva)(\d+(?:\d+)?)$", clave)
    if not coincidencia:
        return None
    sufijo = coincidencia.group(1)
    equivalencias = {"025": 2.5, "25": 2.5, "05": 5.0, "105": 10.5}
    try:
        tasa = equivalencias.get(sufijo, float(sufijo))
    except ValueError:
        return None
    return tasa if tasa in TASAS else None


def _num(valor):
    if valor is None or pd.isna(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace("$", "").replace(" ", "")
    if not texto:
        return 0.0
    negativo = texto.startswith("(") and texto.endswith(")")
    texto = texto.strip("()")
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    resultado = float(texto)
    return -resultado if negativo else resultado


def _leer(path, sheet_name=0):
    path = Path(path)
    if path.suffix.casefold() in {".csv", ".txt"}:
        try:
            return pd.read_csv(path, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                return pd.read_csv(path, sep=None, engine="python", dtype=str, encoding="cp1252")
            except csv.Error as error:
                raise ValueError("No se pudo interpretar el archivo de texto.") from error
        except csv.Error as error:
            raise ValueError("No se pudo interpretar el archivo de texto.") from error
    if path.suffix.casefold() in {".xlsx", ".xlsm", ".xls"}:
        if path.suffix.casefold() in {".xlsx", ".xlsm"}:
            return pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl",
                                 engine_kwargs={"read_only": True, "data_only": True, "keep_links": False})
        return pd.read_excel(path, sheet_name=sheet_name, engine="xlrd")
    raise ValueError(f"Formato no admitido: {path.suffix}. Use Excel, CSV o TXT.")


def _mapear_arca(df, operacion):
    por_clave = {clave_encabezado(c): c for c in df.columns}
    origen = {}
    for destino, alias in ARCA_CAMPOS.items():
        encontrados = [por_clave[a] for a in alias if a in por_clave]
        # Si coexisten Emisor/Receptor, preferir emisor para emitidos y receptor para recibidos.
        if encontrados:
            if destino == "cuit":
                preferido = "nrodocemisor" if operacion == "compras" else "nrodocreceptor"
                origen[destino] = por_clave.get(preferido, encontrados[0])
            elif destino == "razon_social":
                preferido = "denominacionemisor" if operacion == "compras" else "denominacionreceptor"
                origen[destino] = por_clave.get(preferido, encontrados[0])
            else:
                origen[destino] = encontrados[0]
    requeridos = {"fecha", "tipo", "punto_venta", "numero_desde", "cuit", "razon_social", "total"}
    faltantes = sorted(requeridos - origen.keys())
    if faltantes:
        raise ValueError("No reconozco estas columnas de Mis Comprobantes ARCA: " + ", ".join(faltantes))

    filas = []
    netos_por_tasa = {
        _tasa_de_clave(k): c for k, c in por_clave.items()
        if _tasa_de_clave(k) is not None and ("netogravadoiva" in k or "netograviva" in k)
    }
    iva_por_tasa = {
        _tasa_de_clave(k): c for k, c in por_clave.items()
        if _tasa_de_clave(k) is not None and "iva" in k and "neto" not in k
    }
    for _, row in df.iterrows():
        tipo_raw = str(row[origen["tipo"]]).strip().replace(".0", "")
        if tipo_raw.isdigit():
            tipo_raw = str(int(tipo_raw))
        tipo = TIPOS_ARCA.get(tipo_raw)
        if tipo is None:
            tipo_texto = unicodedata.normalize("NFKD", tipo_raw.upper().replace("_", " "))
            tipo_texto = "".join(c for c in tipo_texto if not unicodedata.combining(c))
            tipo_texto = " ".join(tipo_texto.split())
            for etiqueta, codigo in (("FACTURA A", "1"), ("NOTA DE DEBITO A", "2"), ("NOTA DE CREDITO A", "3"),
                                     ("FACTURA B", "6"), ("NOTA DE DEBITO B", "7"), ("NOTA DE CREDITO B", "8"),
                                     ("FACTURA C", "11"), ("NOTA DE DEBITO C", "12"), ("NOTA DE CREDITO C", "13"),
                                     ("FACTURA E", "19"), ("NOTA DE DEBITO E", "20"), ("NOTA DE CREDITO E", "21"),
                                     ("FACTURA M", "51"), ("NOTA DE DEBITO M", "52"), ("NOTA DE CREDITO M", "53")):
                if etiqueta in tipo_texto:
                    tipo = TIPOS_ARCA[codigo]
                    break
        error = ""
        if not tipo:
            tipo = tipo_raw
            error = _agregar_error(error, f"Código de comprobante ARCA no soportado: {tipo_raw}.")
        activos = {}
        try:
            importes_por_tasa = {
                tasa: (abs(_num(row[col_neto])) if col_neto else 0.0,
                       abs(_num(row[iva_por_tasa[tasa]])) if tasa in iva_por_tasa else
                       (abs(_num(row[origen["iva"]])) if len(netos_por_tasa) == 1 and "iva" in origen else 0.0))
                for tasa, col_neto in netos_por_tasa.items()
            }
            activos = {t: valores for t, valores in importes_por_tasa.items() if any(valores)}
            if not activos and iva_por_tasa:
                iva_individual = {t: abs(_num(row[c])) for t, c in iva_por_tasa.items()}
                iva_activo = {t: val for t, val in iva_individual.items() if val}
                if iva_activo:
                    neto_generico = abs(_num(row[origen["neto_gravado"]])) if "neto_gravado" in origen else 0.0
                    if len(iva_activo) == 1:
                        tasa, iva_desglosado = next(iter(iva_activo.items()))
                        activos = {tasa: (neto_generico, iva_desglosado)}
                    else:
                        error = _agregar_error(error, "ARCA informa IVA en varias alícuotas sin el neto desglosado por tasa.")
            if activos:
                neto = sum(v[0] for v in activos.values())
                iva = sum(v[1] for v in activos.values())
            else:
                neto = abs(_num(row[origen["neto_gravado"]])) if "neto_gravado" in origen else 0.0
                iva = abs(_num(row[origen["iva"]])) if "iva" in origen else 0.0
            no_gravado = abs(_num(row[origen["no_gravado"]])) if "no_gravado" in origen else 0.0
            exento = abs(_num(row[origen["exento"]])) if "exento" in origen else 0.0
            otros = abs(_num(row[origen["otros"]])) if "otros" in origen else 0.0
            total = abs(_num(row[origen["total"]]))
        except (ValueError, TypeError, OverflowError) as exc:
            neto = iva = no_gravado = exento = otros = total = 0.0
            error = _agregar_error(error, f"Importes ARCA inválidos: {exc}.")

        moneda = str(row[origen["moneda"]]).strip().upper() if "moneda" in origen else "ARS"
        moneda = {"PES": "ARS", "DOL": "USD"}.get(moneda, moneda)
        if moneda in {"", "NAN", "NONE"}:
            moneda = "ARS"
        cambio_raw = row[origen["cambio"]] if "cambio" in origen else None
        if cambio_raw is None or pd.isna(cambio_raw) or not str(cambio_raw).strip():
            tipo_cambio = 1 if moneda == "ARS" else None
        else:
            tipo_cambio = _num(cambio_raw)
        if otros > 0:
            error = _agregar_error(error, "ARCA agrupa otros tributos y percepciones; este formato no permite separarlos con fiabilidad.")
        if "numero_hasta" in origen and str(row[origen["numero_hasta"]]).strip() not in {"", "nan", "None"}:
            try:
                desde = int(_num(row[origen["numero_desde"]]))
                hasta = int(_num(row[origen["numero_hasta"]]))
                if desde != hasta:
                    error = _agregar_error(error, "El registro agrupa un rango de comprobantes; requiere desagregación previa.")
            except (ValueError, TypeError):
                error = _agregar_error(error, "Número de comprobante inválido.")

        alicuota = 0.0
        detalle_alicuotas = [
            {"alicuota": tasa, "neto_gravado": importes[0], "iva": importes[1]}
            for tasa, importes in sorted(activos.items())
        ]
        if len(activos) == 1:
            alicuota = next(iter(activos))
            if alicuota != 0 and activos[alicuota][0] and not activos[alicuota][1]:
                error = _agregar_error(error, "Falta el importe de IVA para la alícuota identificada.")
        elif len(activos) > 1:
            # El detalle por tasa está completo; no hace falta inferir una
            # única tasa desde los importes agregados.
            alicuota = 0.0
        elif neto and iva:
            candidatas = [t for t in TASAS if abs(round(neto * t / 100, 2) - round(iva, 2)) <= 0.01]
            if len(candidatas) == 1:
                alicuota = candidatas[0]
            else:
                error = _agregar_error(error, "ARCA no permite inferir una única alícuota a partir de los importes agregados.")
        elif neto or iva:
            error = _agregar_error(error, "El desglose de neto e IVA de ARCA es incompleto; verificar el comprobante original.")
        elif total and tipo in {"A", "B", "C", "E", "M"}:
            error = _agregar_error(error, "El archivo ARCA no informa neto e IVA por alícuota para este comprobante.")

        fecha = row[origen["fecha"]]
        if isinstance(fecha, str):
            fecha = fecha.strip()
        record = {
            "fecha": fecha, "tipo_comprobante": tipo,
            "punto_venta": row[origen["punto_venta"]],
            "numero": row[origen["numero_desde"]],
            "cuit": row[origen["cuit"]], "razon_social": row[origen["razon_social"]],
            "operacion": operacion, "neto_gravado": neto,
            "alicuota": alicuota, "iva": iva,
            "no_gravado_exento": no_gravado + exento,
            "percepciones": otros, "total": total,
            "moneda": moneda, "tipo_cambio": tipo_cambio,
            "detalle_alicuotas": detalle_alicuotas,
            "_error_adaptador": error,
        }
        filas.append(record)
    return pd.DataFrame(filas)


def _adaptar_holistor(path, operacion, mapping_path=None):
    path = Path(path)
    mapping = {}
    widths = None
    columns = None
    if mapping_path:
        config = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
        mapping = config.get("columnas", {})
        widths = config.get("anchos_prn")
        columns = config.get("columnas_prn")
    if path.suffix.casefold() == ".prn":
        if not widths or not columns or len(widths) != len(columns):
            raise ValueError("El .prn de Holistor es de ancho fijo. Configure `anchos_prn` y `columnas_prn` con la plantilla provista por su instalación.")
        df = pd.read_fwf(path, widths=widths, names=columns, dtype=str)
    else:
        sheet = "HWComprobantes Emitidos" if operacion == "ventas" and path.suffix.casefold() in {".xlsx", ".xlsm", ".xls"} else 0
        try:
            df = _leer(path, sheet_name=sheet)
        except ValueError:
            df = _leer(path, sheet_name=0)
    if mapping:
        df = df.rename(columns=mapping)
    df = normalizar_columnas(df)
    df["operacion"] = operacion
    return df


def leer_comprobantes(path, formato="estandar", operacion="ventas", mapping_path=None):
    """Lee archivo y lo convierte a las columnas canónicas del importador."""
    formato = formato.casefold()
    if formato == "arca":
        return _mapear_arca(_leer(path), operacion)
    if formato == "holistor":
        return _adaptar_holistor(path, operacion, mapping_path)
    df = _leer(path)
    df = normalizar_columnas(df)
    if "operacion" not in df.columns:
        df["operacion"] = operacion
    else:
        df["operacion"] = df["operacion"].fillna(operacion)
    return df


def ejemplo_mapeo_holistor():
    """Contrato de ejemplo editable; usar nombres reales de la plantilla local."""
    return {
        "columnas": {
            "Fecha": "fecha", "Tipo": "tipo_comprobante",
            "Punto de Venta": "punto_venta", "Número": "numero",
            "CUIT": "cuit", "Razón Social": "razon_social",
            "Neto Gravado": "neto_gravado", "Alícuota": "alicuota",
            "IVA": "iva", "No Gravado/Exento": "no_gravado_exento",
            "Percepciones": "percepciones", "Total": "total",
            "Moneda": "moneda", "Tipo de Cambio": "tipo_cambio",
        },
        "anchos_prn": None,
        "columnas_prn": None,
    }
