"""Ejecuta el escenario concurrente con una base SQLite compartida entre hilos."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from tests.django_utils import preparar_bd

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings

from tests.helpers import comprobante
from web.comprobantes.models import Cliente
from web.comprobantes.repositorio import RepositorioDjango


def main():
    preparar_bd()
    with override_settings(PREVIEW_DIR=Path(os.environ["DJANGO_PREVIEW_TEST_DIR"])):
        usuario = User.objects.create_user("operador", password="clave-sintetica", is_staff=True)
        cliente = Cliente.objects.create(nombre="Cliente Sintético")
        solicitudes = []
        for numero in (1, 2):
            navegador = Client()
            navegador.force_login(usuario)
            archivo = SimpleUploadedFile(
                f"archivo-{numero}.csv",
                pd.DataFrame([comprobante(numero=numero)]).to_csv(index=False).encode("utf-8"),
            )
            respuesta = navegador.post("/cargar/", {"cliente": cliente.pk, "periodo": "2026-09",
                                                      "origen": "estandar", "operacion": "ventas", "archivo": archivo})
            if respuesta.status_code != 302:
                raise AssertionError(f"La carga no abrió la vista previa: {respuesta.status_code}")
            solicitudes.append((navegador, navegador.session["preview"]["token"]))

        def confirmar_una(item):
            navegador, token = item
            return navegador.post("/confirmar/", {"token": token}).status_code

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            estados = sorted(ejecutor.map(confirmar_una, solicitudes))
        cantidad = len(RepositorioDjango().consultar_comprobantes("2026-09"))
        print(f"RESULTADO {estados} {cantidad}")


if __name__ == "__main__":
    main()
