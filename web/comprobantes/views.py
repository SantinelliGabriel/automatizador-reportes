"""Pantallas locales de clientes y confirmación de importaciones."""

import hashlib
import re
import tempfile
import time
from functools import wraps
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from automatizador.adaptadores import leer_comprobantes
from automatizador.clientes import clave_cliente
from automatizador.lotes import operaciones_aceptadas
from automatizador.procesamiento import confirmar_importacion, previsualizar
from automatizador.procesamiento import generar_informe
from web.comprobantes.forms import CargaForm, ClienteForm
from web.comprobantes.models import Cliente
from web.comprobantes.previews import (
    DURACION_SEGUNDOS, firmar, guardar_temporal, hash_opciones, hash_plan, limpiar_vencidas,
    ruta_temporal, verificar, version_operacion,
)
from web.comprobantes.repositorio import RepositorioDjango


class CargaRechazada(ValueError):
    """Error de validación con mensaje apto para mostrar al usuario."""


def solo_operador(vista):
    @login_required
    @wraps(vista)
    def protegida(request, *args, **kwargs):
        if settings.DEMO_MODE or not request.user.is_staff:
            return HttpResponseForbidden("Acceso de solo lectura.")
        return vista(request, *args, **kwargs)

    return protegida


@never_cache
@login_required
def historial(request):
    filas = RepositorioDjango().consultar_importaciones().to_dict("records")
    return render(request, "comprobantes/historial.html", {"importaciones": filas})


@never_cache
@login_required
def observaciones(request):
    periodo = request.GET.get("periodo", "")
    cliente = request.GET.get("cliente", "")
    operacion = request.GET.get("operacion", "")
    if periodo and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periodo):
        return HttpResponseBadRequest("Período inválido. Usá AAAA-MM.")
    if operacion not in {"", "ventas", "compras"}:
        return HttpResponseBadRequest("Operación inválida.")
    tabla = RepositorioDjango().consultar_observaciones(periodo or None)
    if cliente:
        tabla = tabla[tabla["cliente"] == cliente]
    if operacion:
        tabla = tabla[tabla["operacion"] == operacion] if "operacion" in tabla else tabla.iloc[0:0]
    return render(request, "comprobantes/observaciones.html", {
        "observaciones": tabla.to_dict("records"), "periodo": periodo, "cliente": cliente,
        "operacion": operacion, "clientes": Cliente.objects.order_by("nombre"),
    })


@never_cache
@login_required
def descargar_informe(request, periodo):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periodo):
        return HttpResponseBadRequest("Período inválido. Usá AAAA-MM.")
    repositorio = RepositorioDjango()
    if repositorio.consultar_comprobantes(periodo).empty:
        return render(request, "comprobantes/sin_informe.html", {"periodo": periodo})
    with tempfile.TemporaryDirectory(prefix="automatizador-informe-") as temporal:
        salida = Path(temporal) / "informe.xlsx"
        try:
            generar_informe(periodo, salida, repositorio)
            contenido = salida.read_bytes()
        finally:
            salida.unlink(missing_ok=True)
    respuesta = HttpResponse(contenido, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    respuesta["Content-Disposition"] = f'attachment; filename="informe_consolidado_{periodo}.xlsx"'
    return respuesta


def _error_generico(plan):
    for archivo in plan.archivos:
        if "motivo" in archivo.observaciones:
            motivos = archivo.observaciones["motivo"].astype(str)
            mascara = motivos.str.startswith("No se pudo procesar el archivo:")
            archivo.observaciones.loc[mascara, "motivo"] = "No se pudo interpretar el archivo. Revisá el formato."


def _mapeo(origen):
    ruta = settings.HOLISTOR_MAPPING_PATH if origen == "holistor" else None
    return ruta if ruta and ruta.is_file() else None


def _hash_mapeo(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest() if ruta else ""


def _operaciones_del_plan(plan):
    return tuple(sorted({operacion for archivo in plan.archivos if archivo.aplicar
                         for operacion in operaciones_aceptadas({"comprobantes": archivo.comprobantes})}))


def _leer_plan(meta):
    opciones = meta["opciones"]
    cliente = get_object_or_404(Cliente, pk=opciones["cliente_id"])
    if clave_cliente(cliente.nombre) != opciones["cliente_clave"]:
        raise ValueError("El cliente cambió desde la vista previa.")
    ruta = ruta_temporal(meta["id"], meta["sufijo"])
    if not ruta.is_file() or time.time() - ruta.stat().st_mtime > DURACION_SEGUNDOS:
        raise ValueError("La vista previa venció.")
    if hashlib.sha256(ruta.read_bytes()).hexdigest() != meta["sha256"]:
        raise ValueError("El archivo cambió desde la vista previa.")
    mapeo = _mapeo(opciones["origen"])
    if _hash_mapeo(mapeo) != opciones["mapeo_sha256"]:
        raise ValueError("El mapeo cambió desde la vista previa.")
    plan = previsualizar(ruta, opciones["periodo"], opciones["origen"], opciones["operacion"],
                         mapping_path=mapeo, cliente=cliente.nombre,
                         nombre_archivo=opciones["nombre_archivo"])
    _error_generico(plan)
    if hash_plan(plan) != meta["plan_sha256"]:
        raise ValueError("La validación cambió desde la vista previa.")
    return cliente, plan, ruta


@never_cache
@login_required
def clientes(request):
    return render(request, "comprobantes/clientes.html", {"clientes": Cliente.objects.order_by("nombre")})


@never_cache
@solo_operador
def cliente_nuevo(request):
    formulario = ClienteForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            formulario.save()
        except IntegrityError:
            formulario.add_error("nombre", "Ya existe un cliente con ese nombre.")
        else:
            messages.success(request, "Cliente creado.")
            return redirect("clientes")
    return render(request, "comprobantes/formulario.html", {"formulario": formulario, "titulo": "Nuevo cliente"})


@never_cache
@solo_operador
def cargar(request):
    if request.method == "POST":
        limpiar_vencidas()
    formulario = CargaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and formulario.is_valid():
        datos = formulario.cleaned_data
        cliente = datos["cliente"]
        archivo = datos["archivo"]
        ruta = None
        try:
            identificador, ruta, sha256 = guardar_temporal(archivo, datos["sufijo"])
            mapeo = _mapeo(datos["origen"])
            try:
                filas = leer_comprobantes(ruta, datos["origen"], datos["operacion"], mapeo)
            except (ValueError, OSError, ImportError) as error:
                if datos["operacion"] == "mixto":
                    raise CargaRechazada("Mixto requiere una columna operación válida en cada fila.") from error
                filas = None
            if filas is not None:
                if len(filas) > 10000:
                    raise CargaRechazada("El archivo excede el límite de 10.000 filas.")
                if datos["operacion"] != "mixto" and "operacion" in filas and any(
                    str(valor).strip().casefold() != datos["operacion"]
                    for valor in filas["operacion"].dropna()
                ):
                    raise CargaRechazada("La operación del archivo no coincide con la elegida.")
            plan = previsualizar(ruta, datos["periodo"], datos["origen"], datos["operacion"],
                                 mapping_path=mapeo, cliente=cliente.nombre,
                                 nombre_archivo=datos["nombre_archivo"])
            _error_generico(plan)
            operaciones = _operaciones_del_plan(plan)
            opciones = {"cliente_id": cliente.pk, "cliente_clave": clave_cliente(cliente.nombre),
                        "periodo": datos["periodo"], "origen": datos["origen"],
                        "operacion": datos["operacion"], "nombre_archivo": datos["nombre_archivo"],
                        "mapeo_sha256": _hash_mapeo(mapeo)}
            anterior = request.session.get("preview")
            if anterior:
                ruta_temporal(anterior["id"], anterior["sufijo"]).unlink(missing_ok=True)
            request.session.save()
            meta = {"id": identificador, "sufijo": datos["sufijo"], "sha256": sha256,
                    "plan_sha256": hash_plan(plan), "opciones": opciones,
                    "opciones_sha256": hash_opciones(opciones),
                    "versiones": {operacion: version_operacion(cliente, datos["periodo"], operacion)
                                 for operacion in operaciones}}
            meta["token"] = firmar({"id": identificador, "sha256": sha256,
                                    "plan_sha256": meta["plan_sha256"],
                                    "opciones_sha256": meta["opciones_sha256"],
                                    "usuario": request.user.pk, "sesion": request.session.session_key})
            request.session["preview"] = meta
            return redirect("vista_previa")
        except CargaRechazada as error:
            if ruta:
                ruta.unlink(missing_ok=True)
            formulario.add_error("archivo", str(error))
        except (ValueError, OSError):
            if ruta:
                ruta.unlink(missing_ok=True)
            formulario.add_error("archivo", "No se pudo procesar el archivo. Revisá el formato.")
    return render(request, "comprobantes/formulario.html", {"formulario": formulario,
                                                             "titulo": "Subir comprobantes"})


@never_cache
@solo_operador
def vista_previa(request):
    meta = request.session.get("preview")
    if not meta:
        return HttpResponseBadRequest("No hay una vista previa activa.")
    try:
        verificar(meta["token"])
        cliente, plan, _ = _leer_plan(meta)
    except (ValueError, signing.BadSignature, signing.SignatureExpired):
        return HttpResponseBadRequest("La vista previa venció o cambió. Volvé a subir el archivo.")
    archivo = plan.archivos[0]
    cantidades_operacion = (archivo.comprobantes["operacion"].value_counts().to_dict()
                           if "operacion" in archivo.comprobantes else {})
    return render(request, "comprobantes/vista_previa.html", {
        "cliente": cliente, "periodo": plan.periodo, "archivo": archivo,
        "validas": archivo.comprobantes.head(50).to_dict("records"),
        "observadas": archivo.observaciones.head(50).to_dict("records"),
        "columnas_validas": archivo.comprobantes.columns,
        "columnas_observadas": archivo.observaciones.columns,
        "cantidad_validas": len(archivo.comprobantes), "cantidad_observadas": len(archivo.observaciones),
        "cantidades_operacion": sorted(cantidades_operacion.items()),
        "operaciones_reemplazo": _operaciones_del_plan(plan),
        "token": meta["token"],
    })


@never_cache
@solo_operador
@require_POST
def confirmar(request):
    limpiar_vencidas()
    meta = request.session.get("preview")
    token = request.POST.get("token", "")
    if not meta or token != meta["token"]:
        return HttpResponseBadRequest("La vista previa no es válida.")
    try:
        firmado = verificar(token)
        if firmado != {"id": meta["id"], "sha256": meta["sha256"],
                       "plan_sha256": meta["plan_sha256"], "opciones_sha256": meta["opciones_sha256"],
                       "usuario": request.user.pk, "sesion": request.session.session_key}:
            raise ValueError("La vista previa cambió.")
        if hash_opciones(meta["opciones"]) != meta["opciones_sha256"]:
            raise ValueError("Las opciones cambiaron.")
        cliente, plan, ruta = _leer_plan(meta)
    except (ValueError, signing.BadSignature, signing.SignatureExpired):
        request.session.pop("preview", None)
        return HttpResponseBadRequest("La vista previa venció o cambió. Volvé a subir el archivo.")
    candado = Path(str(ruta) + ".lock")
    try:
        with candado.open("x"):
            pass
    except FileExistsError:
        return HttpResponse("La confirmación ya está en curso.", status=409)
    try:
        with transaction.atomic():
            for operacion in _operaciones_del_plan(plan):
                if version_operacion(cliente, plan.periodo, operacion) != meta["versiones"][operacion]:
                    raise ValueError("Hay una importación más reciente. Volvé a revisar el archivo.")
            confirmar_importacion(plan, RepositorioDjango())
        messages.success(request, "Importación confirmada.")
        return redirect("clientes")
    except (ValueError, IntegrityError):
        return HttpResponse("No se confirmó: los datos cambiaron o son incompatibles. Volvé a subir el archivo.",
                            status=409)
    finally:
        request.session.pop("preview", None)
        ruta.unlink(missing_ok=True)
        candado.unlink(missing_ok=True)
