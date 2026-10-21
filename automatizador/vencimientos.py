"""Agenda de vencimientos basada en fechas oficiales cargadas por el usuario."""

from pathlib import Path
import unicodedata

import pandas as pd


COLUMNAS_REQUERIDAS = {"impuesto", "periodo", "terminacion_cuit", "fecha_vencimiento"}


def cargar_calendario(path):
    path = Path(path)
    if path.suffix.casefold() in {".xlsx", ".xls"}:
        calendario = pd.read_excel(path)
    else:
        calendario = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
    def clave(valor):
        texto = unicodedata.normalize("NFKD", str(valor).strip().casefold())
        return "".join(c for c in texto if not unicodedata.combining(c))
    renombres = {
        "obligacion": "impuesto", "tributo": "impuesto",
        "terminacion": "terminacion_cuit", "terminacioncuit": "terminacion_cuit",
        "fechavencimiento": "fecha_vencimiento", "vencimiento": "fecha_vencimiento",
        "fecha": "fecha_vencimiento", "fuente": "fuente_oficial", "url": "fuente_oficial",
        "periodofiscal": "periodo",
    }
    calendario = calendario.rename(columns={c: renombres.get(clave(c), clave(c).replace(" ", "_")) for c in calendario.columns})
    faltantes = COLUMNAS_REQUERIDAS - set(calendario.columns)
    if faltantes:
        raise ValueError("El calendario requiere estas columnas: " + ", ".join(sorted(faltantes)))
    calendario["fecha_vencimiento"] = pd.to_datetime(calendario["fecha_vencimiento"], errors="coerce", dayfirst=True).dt.date
    calendario["terminacion_cuit"] = calendario["terminacion_cuit"].astype(str).str.replace(" ", "", regex=False)
    if calendario["fecha_vencimiento"].isna().any():
        raise ValueError("El calendario contiene fechas de vencimiento inválidas.")
    return calendario


def terminacion(cuit):
    if isinstance(cuit, float) and cuit.is_integer():
        cuit = str(int(cuit))
    digitos = "".join(c for c in str(cuit) if c.isdigit())
    if len(digitos) != 11:
        raise ValueError(f"CUIT inválida para agenda: {cuit}")
    return digitos[-1]


def _grupo_contiene(grupo, digito):
    grupo = str(grupo).strip().upper()
    if grupo in {"TODAS", "TODOS", "*"}:
        return True
    return digito in grupo.replace(";", "-").replace(",", "-").split("-")


def proximos_vencimientos(clientes, calendario, desde=None, dias=30):
    """Cruza calendario oficial y CUITs de clientes dentro de una ventana futura."""
    desde = pd.Timestamp(desde or pd.Timestamp.today().date()).date()
    hasta = desde + pd.Timedelta(days=dias)
    filas = []
    for cliente in clientes:
        digito = terminacion(cliente["cuit"])
        for _, item in calendario.iterrows():
            fecha = item["fecha_vencimiento"]
            if fecha < desde or fecha > hasta or not _grupo_contiene(item["terminacion_cuit"], digito):
                continue
            filas.append({
                "cliente": cliente["cliente"], "terminacion_cuit": digito,
                "impuesto": item["impuesto"], "periodo": item["periodo"],
                "fecha_vencimiento": fecha,
                "dias_restantes": (fecha - desde).days,
                "fuente_oficial": item.get("fuente_oficial", ""),
            })
    return pd.DataFrame(filas).sort_values(["fecha_vencimiento", "cliente"], ignore_index=True) if filas else pd.DataFrame(columns=["cliente", "terminacion_cuit", "impuesto", "periodo", "fecha_vencimiento", "dias_restantes", "fuente_oficial"])
