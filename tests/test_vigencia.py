"""Reglas puras de selección de observaciones vigentes."""

import unittest

from automatizador.vigencia import seleccionar_observaciones_vigentes


def intento(identificador, aceptados=0, operaciones=""):
    return {"id": identificador, "cliente": "Cliente Sintético", "periodo": "2026-09",
            "aceptados": aceptados, "operaciones": operaciones}


def observacion(identificador, operacion=None):
    return {"importacion_id": identificador, "cliente": "Cliente Sintético",
            "periodo": "2026-09", "operacion": operacion}


class TestVigencia(unittest.TestCase):
    def test_primera_falla_y_luego_aplicacion_sustituye_los_intentos_previos(self):
        importaciones = [intento(1), intento(2, 1, "ventas"), intento(3), intento(4, 1, "ventas")]
        filas = [observacion(i, "ventas") for i in range(1, 5)]
        self.assertEqual(seleccionar_observaciones_vigentes(importaciones, filas), filas[3:])

    def test_intentos_posteriores_fallidos_se_acumulan(self):
        importaciones = [intento(1, 1, "ventas"), intento(2), intento(3)]
        filas = [observacion(i, "ventas") for i in range(1, 4)]
        self.assertEqual(seleccionar_observaciones_vigentes(importaciones, filas), filas)

    def test_sin_aplicacion_muestra_todos_los_intentos(self):
        filas = [observacion(1, "compras"), observacion(2, "compras")]
        self.assertEqual(seleccionar_observaciones_vigentes([intento(1), intento(2)], filas), filas)

    def test_operaciones_paralelas_tienen_referencias_independientes(self):
        importaciones = [intento(1, 1, "ventas"), intento(2, 1, "compras"), intento(3, 1, "ventas")]
        filas = [observacion(1, "ventas"), observacion(2, "compras"), observacion(3, "ventas")]
        self.assertEqual(seleccionar_observaciones_vigentes(importaciones, filas), filas[1:])

    def test_sin_operacion_identificable_usa_ultima_aplicacion_del_periodo(self):
        importaciones = [intento(1), intento(2, 1, "ventas"), intento(3), intento(4, 1, "compras"), intento(5)]
        filas = [observacion(i) for i in range(1, 6)]
        self.assertEqual(seleccionar_observaciones_vigentes(importaciones, filas), filas[3:])

    def test_importacion_heredada_con_operaciones_vacias_usa_comprobantes(self):
        importaciones = [intento(1, 1), intento(2, 1, "compras")]
        filas = [observacion(1, "ventas"), observacion(2, "ventas")]
        self.assertEqual(seleccionar_observaciones_vigentes(
            importaciones, filas, {1: {"ventas"}}
        ), filas)
