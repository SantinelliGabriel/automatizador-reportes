"""Cruce uno a uno entre movimientos bancarios y comprobantes."""

from pathlib import Path

import pandas as pd

from automatizador.adaptadores import _num, _leer


def conciliar_banco(path, comprobantes, columna_fecha, columna_importe,
                    columna_descripcion=None, dias_tolerancia=3,
                    tolerancia_importe=0.01):
    """Devuelve movimientos bancarios y comprobantes marcados como conciliados."""
    banco = _leer(Path(path))
    faltantes = [c for c in (columna_fecha, columna_importe) if c not in banco.columns]
    if faltantes:
        raise ValueError("El extracto no tiene las columnas: " + ", ".join(faltantes))
    banco = banco.copy().reset_index(drop=True)
    banco["_fecha"] = pd.to_datetime(banco[columna_fecha], errors="coerce", dayfirst=True)
    banco["_importe"] = banco[columna_importe].map(_num)
    banco["Estado"] = "Sin coincidencia"
    banco["Comprobante"] = ""
    docs = comprobantes.copy().reset_index(drop=True)
    docs["_fecha"] = pd.to_datetime(docs["fecha"], errors="coerce")
    signo_nc = docs["tipo_comprobante"].astype(str).str.startswith("NC").map({True: -1, False: 1})
    signo_operacion = docs["operacion"].astype(str).str.casefold().map({"ventas": 1, "compras": -1}).fillna(1)
    docs["_importe_esperado"] = docs["total"].astype(float) * signo_nc * signo_operacion
    docs["Estado"] = "Sin coincidencia"

    usados = set()
    for indice_banco, movimiento in banco.iterrows():
        if pd.isna(movimiento["_fecha"]):
            continue
        candidatos = []
        for indice_doc, doc in docs.iterrows():
            if indice_doc in usados or pd.isna(doc["_fecha"]):
                continue
            diferencia_importe = abs(float(movimiento["_importe"]) - doc["_importe_esperado"])
            diferencia_dias = abs((movimiento["_fecha"].date() - doc["_fecha"].date()).days)
            if diferencia_importe <= tolerancia_importe and diferencia_dias <= dias_tolerancia:
                candidatos.append((diferencia_dias, diferencia_importe, indice_doc))
        if candidatos:
            _, _, indice_doc = min(candidatos)
            doc = docs.loc[indice_doc]
            usados.add(indice_doc)
            banco.at[indice_banco, "Estado"] = "Conciliado"
            codigo = f"{doc['tipo_comprobante']} {int(doc['punto_venta']):05d}-{int(doc['numero']):08d}"
            banco.at[indice_banco, "Comprobante"] = codigo
            docs.at[indice_doc, "Estado"] = "Conciliado"

    banco = banco.drop(columns=["_fecha", "_importe"])
    docs = docs.drop(columns=["_fecha", "_importe_esperado"])
    return banco, docs


def exportar_conciliacion(path, movimientos, comprobantes):
    """Guarda el cruce y pendientes en hojas separadas."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        movimientos.to_excel(writer, sheet_name="Extracto bancario", index=False)
        comprobantes.to_excel(writer, sheet_name="Comprobantes", index=False)
        movimientos[movimientos["Estado"] != "Conciliado"].to_excel(writer, sheet_name="Pendientes banco", index=False)
        comprobantes[comprobantes["Estado"] != "Conciliado"].to_excel(writer, sheet_name="Pendientes comprobantes", index=False)
