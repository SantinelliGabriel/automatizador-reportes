"""Implementación Django del contrato compartido de persistencia."""

import json
from decimal import Decimal

import pandas as pd
from django.db import transaction

from automatizador.database import COLUMNAS_IMPORTES, _centavos, _valor_observado
from automatizador.decimales import normalizar_decimal
from automatizador.repositorio import RepositorioLotes
from automatizador.vigencia import seleccionar_observaciones_vigentes
from web.comprobantes.models import Cliente, Comprobante, DetalleAlicuota, Importacion, Observacion


class RepositorioDjango(RepositorioLotes):
    """Usa modelos Django sin exponerlos al núcleo, la CLI ni Streamlit."""

    def _guardar_lotes(self, importaciones: list[dict]) -> list[int]:
        ids = []
        with transaction.atomic():
            for item in importaciones:
                nombre = item["cliente"]
                cliente = Cliente.objects.filter(nombre_clave=nombre.casefold()).first()
                if cliente is None:
                    cliente = Cliente.objects.create(nombre=nombre)
                operaciones = item["operaciones"]
                aplicar = item.get("aplicar", True)
                comprobantes = item["comprobantes"]
                rechazados = item["rechazados"]
                if aplicar and operaciones:
                    Comprobante.objects.filter(
                        cliente=cliente, periodo=item["periodo"], operacion__in=operaciones,
                    ).delete()
                importacion = Importacion.objects.create(
                    cliente=cliente, periodo=item["periodo"], archivo_origen=item["archivo_origen"],
                    sha256=item.get("sha256", ""), aceptados=len(comprobantes) if aplicar else 0,
                    rechazados=len(rechazados), operaciones=",".join(operaciones),
                    cantidad_ventas=len(comprobantes) if aplicar else 0,
                    total_centavos=sum(_centavos(valor) for valor in comprobantes.get("total", [])) if aplicar else 0,
                )
                ids.append(importacion.id)
                for fila in (comprobantes.to_dict("records") if aplicar else []):
                    importes = {f"{campo}_centavos": _centavos(fila[campo]) for campo in COLUMNAS_IMPORTES}
                    origen = {f"{campo}_origen_centavos": _centavos(fila.get(f"{campo}_origen", fila[campo]))
                              for campo in COLUMNAS_IMPORTES}
                    detalle = json.loads(json.dumps(fila.get("detalle_alicuotas", []), default=str))
                    comprobante = Comprobante.objects.create(
                        importacion=importacion, cliente=cliente, periodo=item["periodo"],
                        operacion=fila["operacion"], fecha=fila["fecha"],
                        tipo_comprobante=fila["tipo_comprobante"], punto_venta=int(fila["punto_venta"]),
                        numero=int(fila["numero"]), cuit=fila["cuit"], razon_social=fila["razon_social"],
                        alicuota=normalizar_decimal(fila["alicuota"], "alicuota"),
                        moneda=fila.get("moneda", "ARS"),
                        tipo_cambio=normalizar_decimal(fila.get("tipo_cambio", 1), "tipo_cambio"),
                        detalle_alicuotas=detalle, revision_decimal=fila.get("revision_decimal", ""),
                        **importes, **origen,
                    )
                    for partida in detalle:
                        DetalleAlicuota.objects.create(
                            comprobante=comprobante, alicuota=partida["alicuota"],
                            neto_gravado_centavos=_centavos(partida["neto_gravado"]),
                            iva_centavos=_centavos(partida["iva"]),
                        )
                for fila in rechazados.to_dict("records"):
                    datos = {str(clave): _valor_observado(valor) for clave, valor in fila.items()
                             if clave not in {"fila_excel", "motivo", "cliente"}}
                    Observacion.objects.create(
                        importacion=importacion, fila_excel=_valor_observado(fila.get("fila_excel")) or "",
                        motivo=str(fila.get("motivo", "")), datos=datos,
                    )
        return ids

    def consultar_comprobantes(self, periodo: str | None = None) -> pd.DataFrame:
        consulta = Comprobante.objects.select_related("cliente")
        if periodo:
            consulta = consulta.filter(periodo=periodo)
        consulta = consulta.order_by("cliente__nombre", "fecha", "punto_venta", "numero")
        columnas = ["cliente", "periodo", "operacion", "fecha", "tipo_comprobante", "punto_venta",
                    "numero", "cuit", "razon_social", "alicuota", "moneda", "tipo_cambio",
                    "revision_decimal", "neto_gravado", "neto_gravado_origen", "iva", "iva_origen",
                    "no_gravado_exento", "no_gravado_exento_origen", "percepciones",
                    "percepciones_origen", "total", "total_origen", "detalle_alicuotas"]
        filas = []
        for comprobante in consulta:
            fila = {campo: getattr(comprobante, campo) for campo in columnas
                    if campo not in {*COLUMNAS_IMPORTES, *(f"{c}_origen" for c in COLUMNAS_IMPORTES),
                                     "cliente", "fecha"}}
            fila["cliente"] = comprobante.cliente.nombre
            fila["fecha"] = comprobante.fecha.isoformat()
            for campo in COLUMNAS_IMPORTES:
                fila[campo] = Decimal(getattr(comprobante, f"{campo}_centavos")).scaleb(-2)
                fila[f"{campo}_origen"] = Decimal(getattr(comprobante, f"{campo}_origen_centavos")).scaleb(-2)
            filas.append(fila)
        return pd.DataFrame(filas, columns=columnas)

    def consultar_importaciones(self) -> pd.DataFrame:
        columnas = ["id", "fecha_importacion", "archivo_origen", "sha256", "cliente", "periodo",
                    "aceptados", "rechazados", "cantidad_ventas", "total_centavos", "operaciones", "estado"]
        conflictos = set(Observacion.objects.filter(motivo__startswith="Conflicto en el lote:")
                        .values_list("importacion_id", flat=True))
        filas = []
        for importacion in Importacion.objects.select_related("cliente").order_by("-id"):
            fila = {campo: getattr(importacion, campo) for campo in columnas
                    if campo not in {"cliente", "estado"}}
            fila["cliente"] = importacion.cliente.nombre
            fila["estado"] = ("aplicada" if importacion.aceptados > 0 else
                              "no aplicada: conflicto" if importacion.id in conflictos else
                              "no aplicada: sin filas aceptadas")
            filas.append(fila)
        return pd.DataFrame(filas, columns=columnas)

    def consultar_observaciones(self, periodo: str | None = None,
                                importacion_id: int | None = None) -> pd.DataFrame:
        columnas = ("importacion_id", "cliente", "periodo", "archivo_origen", "fila_excel", "motivo")
        consulta = Observacion.objects.select_related("importacion__cliente")
        if periodo is not None:
            consulta = consulta.filter(importacion__periodo=periodo)
        if importacion_id is not None:
            consulta = consulta.filter(importacion_id=importacion_id)
        resultado = []
        for observacion in consulta.order_by("importacion__cliente__nombre", "id"):
            importacion = observacion.importacion
            registro = {**observacion.datos, "importacion_id": importacion.id,
                        "cliente": importacion.cliente.nombre, "periodo": importacion.periodo,
                        "archivo_origen": importacion.archivo_origen, "fila_excel": observacion.fila_excel,
                        "motivo": observacion.motivo}
            resultado.append(registro)
        if importacion_id is None:
            importaciones = Importacion.objects.select_related("cliente")
            if periodo is not None:
                importaciones = importaciones.filter(periodo=periodo)
            simples = [{"id": item.id, "cliente": item.cliente.nombre, "periodo": item.periodo,
                        "aceptados": item.aceptados, "operaciones": item.operaciones} for item in importaciones]
            operaciones_guardadas = {}
            for identificador, operacion in Comprobante.objects.values_list("importacion_id", "operacion").distinct():
                operaciones_guardadas.setdefault(identificador, set()).add(operacion)
            resultado = seleccionar_observaciones_vigentes(simples, resultado, operaciones_guardadas)
        extras = sorted({clave for fila in resultado for clave in fila if clave not in columnas})
        return pd.DataFrame(resultado, columns=[*columnas, *extras])
