"""Selecciona observaciones vigentes a partir de un historial ya leído."""


def seleccionar_observaciones_vigentes(importaciones, observaciones, operaciones_guardadas=None):
    """Conserva observaciones desde la última aplicación de su operación.

    Las entradas son diccionarios simples. ``operaciones_guardadas`` permite
    identificar importaciones heredadas cuyo campo operaciones quedó vacío.
    """
    operaciones_guardadas = operaciones_guardadas or {}
    ultimas_por_operacion = {}
    ultimas_por_periodo = {}
    for importacion in importaciones:
        if int(importacion["aceptados"]) <= 0:
            continue
        identificador = importacion["id"]
        clave = (importacion["cliente"], importacion["periodo"])
        ultimas_por_periodo[clave] = max(identificador, ultimas_por_periodo.get(clave, 0))
        operaciones = set(filter(None, (importacion.get("operaciones") or "").split(",")))
        if not operaciones:
            operaciones = set(operaciones_guardadas.get(identificador, ()))
        for operacion in operaciones:
            clave_operacion = (*clave, operacion)
            ultimas_por_operacion[clave_operacion] = max(
                identificador, ultimas_por_operacion.get(clave_operacion, 0)
            )

    vigentes = []
    for observacion in observaciones:
        clave = (observacion["cliente"], observacion["periodo"])
        operacion = observacion.get("operacion")
        if operacion in {"ventas", "compras"}:
            referencia = ultimas_por_operacion.get((*clave, operacion), 0)
        else:
            referencia = ultimas_por_periodo.get(clave, 0)
        if observacion["importacion_id"] >= referencia:
            vigentes.append(observacion)
    return vigentes
