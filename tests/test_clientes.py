"""Identidad de clientes antes de cualquier backend."""

import unicodedata
import unittest

from automatizador.clientes import clave_cliente


class TestClaveCliente(unittest.TestCase):
    def test_normaliza_espacios_mayusculas_y_unicode_sin_quitar_acentos(self):
        variantes = ["Cliente Á", "cliente á", " Cliente  Á ",
                     unicodedata.normalize("NFD", "Cliente Á")]
        self.assertEqual([clave_cliente(nombre) for nombre in variantes], ["cliente á"] * 4)
        self.assertNotEqual(clave_cliente("Cliente Á"), clave_cliente("Cliente A"))

    def test_rechaza_nombre_vacio(self):
        with self.assertRaises(ValueError):
            clave_cliente("  \t ")
