"""Actualización transaccional de claves en bases Django ya inicializadas."""

import importlib
import unittest
from types import SimpleNamespace

from django.apps import apps
from django.db import connection

from tests.django_utils import limpiar_bd, preparar_bd
from web.comprobantes.models import Cliente


normalizar_claves = importlib.import_module(
    "web.comprobantes.migrations.0002_normaliza_claves_cliente"
).normalizar_claves


class TestMigracionClaveCliente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preparar_bd()

    def setUp(self):
        limpiar_bd()

    def test_actualiza_clave_antigua_con_espacios_y_unicode(self):
        cliente = Cliente.objects.create(nombre=" Cliente  Á ")
        Cliente.objects.filter(pk=cliente.pk).update(nombre_clave=" cliente  á ")
        normalizar_claves(apps, SimpleNamespace(connection=connection))
        cliente.refresh_from_db()
        self.assertEqual(cliente.nombre_clave, "cliente á")

    def test_rechaza_ambiguedad_sin_modificar_claves(self):
        primero = Cliente.objects.create(nombre="Cliente A")
        segundo = Cliente.objects.create(nombre="Cliente B")
        Cliente.objects.filter(pk=segundo.pk).update(nombre=" Cliente  A ", nombre_clave=" cliente  a ")
        with self.assertRaisesRegex(ValueError, "requieren consolidación"):
            normalizar_claves(apps, SimpleNamespace(connection=connection))
        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual((primero.nombre_clave, segundo.nombre_clave), ("cliente a", " cliente  a "))
