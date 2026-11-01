"""Regresión contra libros sintéticos generados antes del experimento."""

import copy
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from xml.etree.ElementTree import tostring

import pandas as pd
from openpyxl import load_workbook

from automatizador.procesamiento import generar_informe
from automatizador.repositorio import RepositorioSQLite
from tests.helpers import comprobante, directorio_temporal
from automatizador.validaciones import validar_comprobantes


FIXTURES = Path(__file__).parent / "fixtures" / "excel"
HOJAS = ["Comprobantes", "Detalle IVA", "Resumen por cliente", "IVA por alícuota", "Observaciones"]


def generar_caso(caso, destino, carpeta):
    repo = RepositorioSQLite(Path(carpeta) / f"{caso}.db")
    if caso == "contable":
        filas = [comprobante(numero=1, razon_social="=1+1"),
                 comprobante(numero=2, tipo_comprobante="NC A"),
                 comprobante(numero=3, tipo_comprobante="ND A", operacion="compras"),
                 comprobante(numero=4, moneda="USD", tipo_cambio="1500.12345678"),
                 comprobante(numero=5, neto_gravado="1500", iva="262.50", total="1762.50",
                             detalle_alicuotas='[{"alicuota":"21","neto_gravado":"1000","iva":"210"},'
                                              '{"alicuota":"10.5","neto_gravado":"500","iva":"52.5"}]'),
                 comprobante(numero=6, total="0", razon_social="@SUM(1)")]
        buenos, malos = validar_comprobantes(pd.DataFrame(filas), "2026-09")
        repo.reemplazar_periodos([dict(cliente="=Cliente Sintético", periodo="2026-09",
                                       comprobantes=buenos, rechazados=malos, archivo_origen="sintetico.csv")])
    if caso == "limites":
        tabla = pd.DataFrame({
            "texto": ["=1+1", "+SUM(1)", "-SUM(1)", "@SUM(1)", "", None, "á\nβ", "x" * 100],
            "neto": [Decimal("123456789.12345678"), Decimal("0.00000001"), Decimal("1000.00"),
                     Decimal("-12.50"), None, Decimal("0"), Decimal("999999999999999.99"), Decimal("1.25")],
            "fecha": [datetime(2026, 9, 1)] * 8,
        })
        with patch("automatizador.procesamiento.construir_hojas", return_value=(tabla, tabla, tabla)), \
             patch("automatizador.procesamiento.construir_detalle_alicuotas", return_value=tabla), \
             patch.object(repo, "consultar_observaciones", return_value=tabla):
            return generar_informe("2026-09", destino, repo)
    return generar_informe("2026-09", destino, repo)


def xml(objeto):
    return tostring(objeto.to_tree())


class TestExportadorExcel(unittest.TestCase):
    def test_libros_equivalentes_a_la_linea_base(self):
        for caso in ("contable", "vacio", "limites"):
            with self.subTest(caso=caso), directorio_temporal() as carpeta:
                ruta = generar_caso(caso, Path(carpeta) / "nuevo.xlsx", carpeta)
                antes = load_workbook(FIXTURES / f"{caso}.xlsx", data_only=False)
                despues = load_workbook(ruta, data_only=False)
                try:
                    self.assertEqual(antes.sheetnames, HOJAS)
                    self.assertEqual(despues.sheetnames, HOJAS)
                    self.assertEqual(xml(antes.calculation), xml(despues.calculation))
                    self.assertEqual([xml(v) for v in antes.views], [xml(v) for v in despues.views])
                    for atributo in antes.properties.__elements__:
                        if atributo not in {"created", "modified"}:
                            self.assertEqual(getattr(antes.properties, atributo), getattr(despues.properties, atributo))
                    self.assertEqual(dict(antes.defined_names), dict(despues.defined_names))
                    for a, b in zip(antes, despues):
                        self.assertEqual(a.dimensions, b.dimensions, a.title)
                        self.assertEqual(a.freeze_panes, b.freeze_panes)
                        self.assertEqual(a.sheet_state, b.sheet_state)
                        self.assertEqual(str(a.merged_cells), str(b.merged_cells))
                        self.assertEqual(a.print_title_rows, b.print_title_rows)
                        self.assertEqual(a.print_title_cols, b.print_title_cols)
                        self.assertEqual(str(a.print_area), str(b.print_area))
                        self.assertEqual(xml(a.HeaderFooter), xml(b.HeaderFooter))
                        for atributo in ("auto_filter", "sheet_properties", "sheet_format", "sheet_view",
                                         "page_margins", "page_setup", "print_options", "protection"):
                            self.assertEqual(xml(getattr(a, atributo)), xml(getattr(b, atributo)), atributo)
                        self.assertEqual({k: xml(v) for k, v in a.column_dimensions.items()},
                                         {k: xml(v) for k, v in b.column_dimensions.items()})
                        self.assertEqual({k: dict(v) for k, v in a.row_dimensions.items()},
                                         {k: dict(v) for k, v in b.row_dimensions.items()})
                        for fila_a, fila_b in zip(a, b):
                            for ca, cb in zip(fila_a, fila_b):
                                etiqueta = f"{a.title}!{ca.coordinate}"
                                self.assertEqual((ca.value, ca.data_type, ca.number_format),
                                                 (cb.value, cb.data_type, cb.number_format), etiqueta)
                                for estilo in ("font", "fill", "border", "alignment", "protection"):
                                    self.assertEqual(copy.copy(getattr(ca, estilo)),
                                                     copy.copy(getattr(cb, estilo)), etiqueta)
                                self.assertEqual(ca.hyperlink, cb.hyperlink)
                                self.assertEqual(ca.comment, cb.comment)
                finally:
                    antes.close()
                    despues.close()
