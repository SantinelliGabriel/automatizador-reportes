"""Texto decimal exacto y restricciones básicas en SQLite de Django."""

import unittest
from decimal import Decimal

from django import forms
from django.db import IntegrityError, connection

from tests.django_utils import limpiar_bd, preparar_bd
from web.comprobantes.campos import TextoDecimalField
from web.comprobantes.models import Cliente, Comprobante, Importacion


class TestTextoDecimalField(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preparar_bd()

    def setUp(self):
        limpiar_bd()

    def test_cotizaciones_se_normalizan_sin_exponente_ni_perdida(self):
        campo = TextoDecimalField(campo="tipo_cambio")
        for valor, esperado in (("1500.12345678", "1500.12345678"),
                                ("0.00000001", "0.00000001"),
                                ("123456789.12345678", "123456789.12345678"),
                                ("1000", "1000")):
            with self.subTest(valor=valor):
                self.assertEqual(campo.get_prep_value(valor), esperado)
                self.assertEqual(campo.from_db_value(esperado, None, None), Decimal(valor))

    def test_alicuotas_equivalentes_y_escala_excedida(self):
        campo = TextoDecimalField(campo="alicuota")
        self.assertEqual([campo.get_prep_value(valor) for valor in ("21", "21.0", "21.00")],
                         ["21", "21", "21"])
        with self.assertRaisesRegex(ValueError, "escala máxima"):
            campo.get_prep_value("21.01")
        with self.assertRaisesRegex(ValueError, "escala máxima"):
            TextoDecimalField(campo="tipo_cambio").get_prep_value("0.000000001")

    def test_formfield_usa_decimalfield(self):
        campo = TextoDecimalField(campo="tipo_cambio")
        self.assertIsInstance(campo.formfield(), forms.DecimalField)
        self.assertEqual(campo.formfield().decimal_places, 8)

    def test_ida_y_vuelta_en_sqlite_mantiene_texto_exacto(self):
        cliente = Cliente.objects.create(nombre="Cliente Sintético")
        importacion = Importacion.objects.create(cliente=cliente, periodo="2026-09", archivo_origen="sintetico.csv")
        for numero, cotizacion in enumerate(("1500.12345678", "0.00000001", "123456789.12345678"), 1):
            Comprobante.objects.create(
                importacion=importacion, cliente=cliente, periodo="2026-09", operacion="ventas",
                fecha="2026-09-03", tipo_comprobante="A", punto_venta=1, numero=numero,
                cuit="30712345678", razon_social="Empresa Sintética", neto_gravado_centavos=100,
                alicuota="21.00", iva_centavos=21, no_gravado_exento_centavos=0,
                percepciones_centavos=0, total_centavos=121, moneda="USD", tipo_cambio=cotizacion,
                neto_gravado_origen_centavos=100, iva_origen_centavos=21,
                no_gravado_exento_origen_centavos=0, percepciones_origen_centavos=0,
                total_origen_centavos=121,
            )
        self.assertEqual([c.tipo_cambio for c in Comprobante.objects.order_by("numero")], [
            Decimal("1500.12345678"), Decimal("0.00000001"), Decimal("123456789.12345678"),
        ])
        with connection.cursor() as cursor:
            cursor.execute("SELECT tipo_cambio, alicuota FROM comprobantes_comprobante ORDER BY numero")
            self.assertEqual(cursor.fetchall(), [("1500.12345678", "21"), ("0.00000001", "21"),
                                                  ("123456789.12345678", "21")])

    def test_cliente_unico_sin_distincion_de_mayusculas(self):
        Cliente.objects.create(nombre="Cliente Sintetico")
        with self.assertRaises(IntegrityError):
            Cliente.objects.create(nombre="CLIENTE SINTETICO")

    def test_cliente_acentuado_unico_sin_distincion_de_mayusculas(self):
        Cliente.objects.create(nombre="Cliente Sintético")
        with self.assertRaises(IntegrityError):
            Cliente.objects.create(nombre="CLIENTE SINTÉTICO")
