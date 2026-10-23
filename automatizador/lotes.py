"""Detecta operaciones repetidas entre archivos de una confirmación."""

from collections import Counter

import pandas as pd


def operaciones_aceptadas(item):
    comprobantes = item["comprobantes"]
    if comprobantes.empty or "operacion" not in comprobantes:
        return ()
    return tuple(sorted(set(comprobantes["operacion"])))


def resolver_conflictos(importaciones):
    """Rechaza ambos archivos si compiten por una operación del mismo período."""
    claves = Counter(
        (item["cliente"], item["periodo"], operacion)
        for item in importaciones if item.get("aplicar", True)
        for operacion in operaciones_aceptadas(item)
    )
    resultado = []
    for item in importaciones:
        operaciones = operaciones_aceptadas(item)
        repetidas = [op for op in operaciones if claves[item["cliente"], item["periodo"], op] > 1]
        if not repetidas or not item.get("aplicar", True):
            resultado.append(item)
            continue
        motivo = (
            f"Conflicto en el lote: {item['cliente']}, {item['periodo']}, "
            f"operación {', '.join(repetidas)} aparece en más de un archivo; no se aplicó este archivo."
        )
        observadas = item["comprobantes"].copy()
        observadas["motivo"] = motivo
        observadas["fila_excel"] = range(2, len(observadas) + 2)
        rechazos = pd.concat([item["rechazados"], observadas], ignore_index=True)
        resultado.append({**item, "rechazados": rechazos, "aplicar": False, "conflicto": motivo})
    return resultado


def preparar_lotes(importaciones):
    """Prepara conflictos y operaciones para cualquier implementación del repositorio."""
    return [{**item, "operaciones": operaciones_aceptadas(item)}
            for item in resolver_conflictos(importaciones)]
