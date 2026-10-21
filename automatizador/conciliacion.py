"""Cruce bancario por importe/fecha, referencias explícitas y revisión de ambigüedades."""

from pathlib import Path
from itertools import combinations
import re

import pandas as pd

from automatizador.adaptadores import _num, _leer


def _codigo_comprobante(doc):
    return f"{doc['tipo_comprobante']} {int(doc['punto_venta']):05d}-{int(doc['numero']):08d}"


def _referencia_en_texto(texto, doc):
    """Busca punto de venta y número juntos, con o sin ceros a la izquierda."""
    posventa = re.escape(str(int(doc["punto_venta"])))
    numero = re.escape(str(int(doc["numero"])))
    patron = rf"(?<!\d)0*{posventa}[\s./-]+0*{numero}(?!\d)"
    return re.search(patron, str(texto), flags=re.IGNORECASE) is not None


def conciliar_banco(path, comprobantes, columna_fecha, columna_importe,
                    columna_descripcion=None, dias_tolerancia=3,
                    tolerancia_importe=0.01):
    """Cruza movimientos sin resolver empates automáticamente.

    Si varios movimientos o comprobantes tienen la misma mejor puntuación,
    quedan marcados como ambiguos y se listan sus candidatos para revisión.
    """
    banco = _leer(Path(path))
    faltantes = [c for c in (columna_fecha, columna_importe) if c not in banco.columns]
    if columna_descripcion and columna_descripcion not in banco.columns:
        faltantes.append(columna_descripcion)
    if faltantes:
        raise ValueError("El extracto no tiene las columnas: " + ", ".join(faltantes))
    banco = banco.copy().reset_index(drop=True)
    banco["_fecha"] = pd.to_datetime(banco[columna_fecha], errors="coerce", dayfirst=True)
    banco["_importe"] = banco[columna_importe].map(_num)
    banco["Estado"] = "Sin coincidencia"
    banco["Comprobante"] = ""
    banco["Candidatos"] = ""

    docs = comprobantes.copy().reset_index(drop=True)
    docs["_fecha"] = pd.to_datetime(docs["fecha"], errors="coerce")
    signo_nc = docs["tipo_comprobante"].astype(str).str.startswith("NC").map({True: -1, False: 1})
    signo_operacion = docs["operacion"].astype(str).str.casefold().map({"ventas": 1, "compras": -1}).fillna(1)
    docs["_importe_esperado"] = docs["total"].astype(float) * signo_nc * signo_operacion
    docs["Estado"] = "Sin coincidencia"
    docs["Movimientos candidatos"] = ""

    candidatos_por_movimiento = {}
    referencias_fuera_de_tolerancia = {}
    for indice_banco, movimiento in banco.iterrows():
        descripcion = movimiento[columna_descripcion] if columna_descripcion else ""
        candidatos = []
        referencias = []
        if not pd.isna(movimiento["_fecha"]):
            for indice_doc, doc in docs.iterrows():
                if pd.isna(doc["_fecha"]):
                    continue
                referencia = bool(columna_descripcion and _referencia_en_texto(descripcion, doc))
                diferencia_importe = abs(float(movimiento["_importe"]) - doc["_importe_esperado"])
                diferencia_dias = abs((movimiento["_fecha"].date() - doc["_fecha"].date()).days)
                if referencia:
                    referencias.append((indice_doc, diferencia_importe, diferencia_dias))
                if diferencia_importe <= tolerancia_importe and diferencia_dias <= dias_tolerancia:
                    candidatos.append((indice_doc, referencia, diferencia_dias, diferencia_importe))

        # Una referencia explícita acota el cruce cuando el importe/fecha también es válido.
        referenciados_validos = [c for c in candidatos if c[1]]
        if referenciados_validos:
            candidatos = referenciados_validos
        candidatos_por_movimiento[indice_banco] = candidatos
        if referencias and not referenciados_validos and not candidatos:
            referencias_fuera_de_tolerancia[indice_banco] = referencias

    pendientes_banco = set(candidatos_por_movimiento)
    pendientes_docs = set(range(len(docs)))
    conciliados = []
    while True:
        mejores = {}
        inversos = {}
        for indice_banco in pendientes_banco:
            opciones = [c for c in candidatos_por_movimiento[indice_banco] if c[0] in pendientes_docs]
            if not opciones:
                continue
            puntaje = min((not ref, dias, importe) for _, ref, dias, importe in opciones)
            mejores[indice_banco] = [
                indice_doc for indice_doc, ref, dias, importe in opciones
                if (not ref, dias, importe) == puntaje
            ]
            for indice_doc in mejores[indice_banco]:
                inversos.setdefault(indice_doc, []).append(indice_banco)
        pares = [
            (indice_banco, opciones[0])
            for indice_banco, opciones in mejores.items()
            if len(opciones) == 1 and len(inversos[opciones[0]]) == 1
        ]
        if not pares:
            break
        for indice_banco, indice_doc in pares:
            conciliados.append((indice_banco, indice_doc))
            pendientes_banco.remove(indice_banco)
            pendientes_docs.remove(indice_doc)

    for indice_banco, indice_doc in conciliados:
        doc = docs.loc[indice_doc]
        banco.at[indice_banco, "Estado"] = "Conciliado"
        banco.at[indice_banco, "Comprobante"] = _codigo_comprobante(doc)
        docs.at[indice_doc, "Estado"] = "Conciliado"

    for indice_banco in pendientes_banco:
        opciones = [c for c in candidatos_por_movimiento[indice_banco] if c[0] in pendientes_docs]
        opciones.sort(key=lambda c: (not c[1], c[2], c[3]))
        if opciones:
            banco.at[indice_banco, "Estado"] = "Coincidencia ambigua"
            banco.at[indice_banco, "Candidatos"] = "; ".join(
                _codigo_comprobante(docs.loc[opcion[0]]) for opcion in opciones
            )
        elif indice_banco in referencias_fuera_de_tolerancia:
            referencias = [
                item for item in referencias_fuera_de_tolerancia[indice_banco]
                if item[0] in pendientes_docs
            ]
            if not referencias:
                banco.at[indice_banco, "Estado"] = "Referencia a comprobante ya conciliado; revisar"
                continue
            indice_doc, diferencia_importe, diferencia_dias = min(referencias, key=lambda x: (x[1], x[2]))
            doc = docs.loc[indice_doc]
            banco.at[indice_banco, "Estado"] = "Referencia detectada; revisar diferencia"
            banco.at[indice_banco, "Candidatos"] = _codigo_comprobante(doc)
            if abs(float(banco.at[indice_banco, "_importe"])) < abs(float(doc["_importe_esperado"])):
                banco.at[indice_banco, "Estado"] = "Posible pago parcial; revisar"

    for indice_doc in pendientes_docs:
        movimientos = [
            i for i in pendientes_banco
            if any(opcion[0] == indice_doc for opcion in candidatos_por_movimiento[i])
        ]
        referencias = [
            i for i, filas in referencias_fuera_de_tolerancia.items()
            if i in pendientes_banco and any(fila[0] == indice_doc for fila in filas)
        ]
        if movimientos:
            docs.at[indice_doc, "Estado"] = "Coincidencia ambigua"
            docs.at[indice_doc, "Movimientos candidatos"] = ", ".join(str(i + 2) for i in movimientos)
        elif referencias:
            docs.at[indice_doc, "Estado"] = "Referencia detectada; revisar diferencia"
            docs.at[indice_doc, "Movimientos candidatos"] = ", ".join(str(i + 2) for i in referencias)

    # Señala pagos que parecen cubrir varias facturas, sin conciliarlos automáticamente.
    for indice_banco in pendientes_banco:
        if banco.at[indice_banco, "Estado"] != "Sin coincidencia":
            continue
        movimiento = banco.loc[indice_banco]
        opciones = []
        for indice_doc in pendientes_docs:
            doc = docs.loc[indice_doc]
            if pd.isna(doc["_fecha"]):
                continue
            diferencia_dias = abs((movimiento["_fecha"].date() - doc["_fecha"].date()).days) if not pd.isna(movimiento["_fecha"]) else dias_tolerancia + 1
            mismo_signo = float(movimiento["_importe"]) * float(doc["_importe_esperado"]) > 0
            if diferencia_dias <= dias_tolerancia and mismo_signo:
                opciones.append(indice_doc)
        if 1 < len(opciones) <= 8:
            grupos = []
            for cantidad in range(2, min(4, len(opciones)) + 1):
                for grupo in combinations(opciones, cantidad):
                    suma = sum(float(docs.loc[i, "_importe_esperado"]) for i in grupo)
                    if abs(suma - float(movimiento["_importe"])) <= tolerancia_importe:
                        grupos.append(grupo)
            if len(grupos) == 1:
                banco.at[indice_banco, "Estado"] = "Posible pago agrupado; revisar"
                banco.at[indice_banco, "Candidatos"] = "; ".join(
                    _codigo_comprobante(docs.loc[i]) for i in grupos[0]
                )
                for indice_doc in grupos[0]:
                    docs.at[indice_doc, "Estado"] = "Posible pago agrupado; revisar"
                    docs.at[indice_doc, "Movimientos candidatos"] = str(indice_banco + 2)

    # Una factura cubierta por varios movimientos solo se sugiere cuando cada
    # movimiento identifica esa factura en la descripción bancaria.
    for indice_doc in pendientes_docs:
        doc = docs.loc[indice_doc]
        if pd.isna(doc["_fecha"]):
            continue
        parciales = []
        for indice_banco, referencias in referencias_fuera_de_tolerancia.items():
            if banco.at[indice_banco, "Estado"] not in {
                "Posible pago parcial; revisar", "Referencia detectada; revisar diferencia"
            }:
                continue
            if not any(referencia[0] == indice_doc for referencia in referencias):
                continue
            movimiento = banco.loc[indice_banco]
            diferencia_dias = abs((movimiento["_fecha"].date() - doc["_fecha"].date()).days)
            mismo_signo = float(movimiento["_importe"]) * float(doc["_importe_esperado"]) > 0
            es_parcial = abs(float(movimiento["_importe"])) < abs(float(doc["_importe_esperado"]))
            if diferencia_dias <= dias_tolerancia and mismo_signo and es_parcial:
                parciales.append(indice_banco)
        if len(parciales) < 2 or len(parciales) > 8:
            continue
        grupos = []
        for cantidad in range(2, min(4, len(parciales)) + 1):
            for grupo in combinations(parciales, cantidad):
                suma = sum(float(banco.loc[i, "_importe"]) for i in grupo)
                if abs(suma - float(doc["_importe_esperado"])) <= tolerancia_importe:
                    grupos.append(grupo)
        if len(grupos) == 1:
            codigo = _codigo_comprobante(doc)
            for indice_banco in grupos[0]:
                banco.at[indice_banco, "Estado"] = "Posible pago fraccionado; revisar"
                banco.at[indice_banco, "Candidatos"] = codigo
            docs.at[indice_doc, "Estado"] = "Posible pago fraccionado; revisar"
            docs.at[indice_doc, "Movimientos candidatos"] = ", ".join(str(i + 2) for i in grupos[0])

    banco = banco.drop(columns=["_fecha", "_importe"])
    docs = docs.drop(columns=["_fecha", "_importe_esperado"])
    return banco, docs


def exportar_conciliacion(path, movimientos, comprobantes):
    """Guarda el cruce, candidatos y pendientes en hojas separadas."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        movimientos.to_excel(writer, sheet_name="Extracto bancario", index=False)
        comprobantes.to_excel(writer, sheet_name="Comprobantes", index=False)
        movimientos[movimientos["Estado"] != "Conciliado"].to_excel(writer, sheet_name="Pendientes banco", index=False)
        comprobantes[comprobantes["Estado"] != "Conciliado"].to_excel(writer, sheet_name="Pendientes comprobantes", index=False)
