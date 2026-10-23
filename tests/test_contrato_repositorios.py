"""El mismo contrato observable debe cumplirse en SQLite y Django."""

import sqlite3
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.db import IntegrityError

from automatizador.procesamiento import generar_informe
from automatizador.repositorio import RepositorioSQLite
from automatizador.validaciones import validar_comprobantes
from tests.django_utils import limpiar_bd, preparar_bd
from tests.helpers import comprobante, directorio_temporal
from web.comprobantes.models import Cliente, Comprobante, DetalleAlicuota, Importacion
from web.comprobantes.repositorio import RepositorioDjango


PERIODO = "2026-09"
CLIENTE = "Cliente Sintético"


def lote(nombre, *filas, cliente=CLIENTE):
    aceptados, rechazados = validar_comprobantes(pd.DataFrame(filas), PERIODO)
    return {"cliente": cliente, "periodo": PERIODO, "comprobantes": aceptados,
            "rechazados": rechazados, "archivo_origen": nombre}


def repositorios():
    for nombre in ("sqlite", "django"):
        with directorio_temporal() as carpeta:
            if nombre == "django":
                limpiar_bd()
                repo = RepositorioDjango()
            else:
                repo = RepositorioSQLite(Path(carpeta) / "comprobantes.db")
            yield nombre, repo, Path(carpeta)


class TestContratoRepositorios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preparar_bd()

    def test_reemplazo_por_operacion_y_archivo_mixto(self):
        for nombre, repo, _ in repositorios():
            with self.subTest(backend=nombre):
                repo.reemplazar_periodos([lote("ventas.csv", comprobante(numero=1))])
                repo.reemplazar_periodos([lote("compras.csv", comprobante(numero=2, operacion="compras"))])
                self.assertEqual(set(repo.consultar_comprobantes(PERIODO)["numero"]), {1, 2})
                repo.reemplazar_periodos([lote("ventas2.csv", comprobante(numero=3))])
                self.assertEqual(set(repo.consultar_comprobantes(PERIODO)["numero"]), {2, 3})
                repo.reemplazar_periodos([lote("mixto.csv", comprobante(numero=4),
                                             comprobante(numero=5, operacion="compras"))])
                self.assertEqual(set(repo.consultar_comprobantes(PERIODO)["numero"]), {4, 5})
                self.assertEqual(repo.consultar_importaciones().iloc[0]["operaciones"], "compras,ventas")

    def test_duplicado_revierte_lote_completo(self):
        for nombre, repo, _ in repositorios():
            with self.subTest(backend=nombre):
                repo.reemplazar_periodos([lote("original.csv", comprobante(numero=1))])
                segundo = lote("duplicado.csv", comprobante(numero=3), cliente="Otro Cliente Sintético")
                segundo["comprobantes"] = pd.concat([segundo["comprobantes"]] * 2, ignore_index=True)
                with self.assertRaises((sqlite3.IntegrityError, IntegrityError)):
                    repo.reemplazar_periodos([lote("reemplazo.csv", comprobante(numero=2)), segundo])
                self.assertEqual(repo.consultar_comprobantes(PERIODO)["numero"].tolist(), [1])
                self.assertEqual(len(repo.consultar_importaciones()), 1)

    def test_centavos_notas_de_credito_y_debito(self):
        for nombre, repo, carpeta in repositorios():
            with self.subTest(backend=nombre):
                repo.reemplazar_periodos([lote(
                    "notas.csv",
                    comprobante(numero=1, neto_gravado="0.20", iva="0.04", total="0.24"),
                    comprobante(numero=2, tipo_comprobante="NC A", neto_gravado="0.10", iva="0.02", total="0.12"),
                    comprobante(numero=3, tipo_comprobante="ND A", neto_gravado="0.10", iva="0.02", total="0.12"),
                )])
                comprobantes = repo.consultar_comprobantes(PERIODO)
                self.assertEqual(comprobantes["total"].tolist(),
                                 [Decimal("0.24"), Decimal("0.12"), Decimal("0.12")])
                informe = carpeta / "informe.xlsx"
                generar_informe(PERIODO, informe, repo)
                resumen = pd.read_excel(informe, sheet_name="Resumen por cliente")
                alicuotas = pd.read_excel(informe, sheet_name="IVA por alícuota")
                self.assertEqual(Decimal(str(resumen.iloc[0]["total"])), Decimal("0.24"))
                self.assertEqual(Decimal(str(alicuotas.iloc[0]["iva"])), Decimal("0.04"))
                if nombre == "django":
                    self.assertEqual(list(Comprobante.objects.order_by("numero").values_list(
                        "total_centavos", flat=True)), [24, 12, 12])

    def test_observaciones_persistidas_y_conflictos(self):
        for nombre, repo, _ in repositorios():
            with self.subTest(backend=nombre):
                repo.reemplazar_periodos([lote("inicial.csv", comprobante(numero=1),
                                             comprobante(numero=2, cuit="CUIT sintético inválido"))])
                repo.reemplazar_periodos([lote("conflicto-a.csv", comprobante(numero=3)),
                                         lote("conflicto-b.csv", comprobante(numero=4))])
                self.assertEqual(repo.consultar_comprobantes(PERIODO)["numero"].tolist(), [1])
                self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["2", "3", "4"])
                self.assertEqual(repo.consultar_importaciones()["estado"].tolist(), [
                    "no aplicada: conflicto", "no aplicada: conflicto", "aplicada",
                ])

    def test_rechazo_total_y_operaciones_paralelas(self):
        for nombre, repo, _ in repositorios():
            with self.subTest(backend=nombre):
                repo.reemplazar_periodos([lote("ventas.csv", comprobante(numero=1),
                                             comprobante(numero=2, cuit="CUIT sintético inválido"))])
                repo.reemplazar_periodos([lote("compras.csv", comprobante(numero=3, operacion="compras"),
                                             comprobante(numero=4, operacion="compras",
                                                         cuit="CUIT sintético inválido"))])
                repo.reemplazar_periodos([lote("rechazo.csv", comprobante(numero=5,
                                             cuit="CUIT sintético inválido"))])
                self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["2", "4", "5"])
                repo.reemplazar_periodos([lote("ventas2.csv", comprobante(numero=6),
                                             comprobante(numero=7, cuit="CUIT sintético inválido"))])
                self.assertEqual(set(repo.consultar_comprobantes(PERIODO)["numero"]), {3, 6})
                self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["4", "7"])

    def test_rechazo_total_conserva_carga_valida_y_sus_observaciones(self):
        for nombre, repo, _ in repositorios():
            with self.subTest(backend=nombre):
                repo.reemplazar_periodos([lote("inicial.csv", comprobante(numero=1),
                                             comprobante(numero=2, cuit="CUIT sintético inválido"))])
                repo.reemplazar_periodos([lote("rechazo.csv", comprobante(
                    numero=3, cuit="CUIT sintético inválido"))])
                self.assertEqual(repo.consultar_comprobantes(PERIODO)["numero"].tolist(), [1])
                self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["2", "3"])
                self.assertEqual(repo.consultar_importaciones()["estado"].tolist(), [
                    "no aplicada: sin filas aceptadas", "aplicada",
                ])

    def test_reimportar_ventas_conserva_observaciones_de_compras(self):
        for nombre, repo, _ in repositorios():
            with self.subTest(backend=nombre):
                repo.reemplazar_periodos([lote("ventas.csv", comprobante(numero=1),
                                             comprobante(numero=2, cuit="CUIT sintético inválido"))])
                repo.reemplazar_periodos([lote("compras.csv", comprobante(numero=3, operacion="compras"),
                                             comprobante(numero=4, operacion="compras",
                                                         cuit="CUIT sintético inválido"))])
                repo.reemplazar_periodos([lote("ventas2.csv", comprobante(numero=5),
                                             comprobante(numero=6, cuit="CUIT sintético inválido"))])
                self.assertEqual(set(repo.consultar_comprobantes(PERIODO)["numero"]), {3, 5})
                self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["4", "6"])

    def test_lecturas_tienen_mismas_columnas_y_valores(self):
        lecturas = {}
        for nombre, repo, _ in repositorios():
            repo.reemplazar_periodos([lote("mixto.csv", comprobante(numero=1),
                                         comprobante(numero=2, operacion="compras"),
                                         comprobante(numero=3, cuit="CUIT sintético inválido"))])
            lecturas[nombre] = (repo.consultar_comprobantes(PERIODO), repo.consultar_observaciones(PERIODO))
        for sqlite, django in zip(lecturas["sqlite"], lecturas["django"]):
            self.assertEqual(list(sqlite.columns), list(django.columns))
            self.assertEqual(sqlite.to_dict("records"), django.to_dict("records"))

    def test_historial_heredado_sin_operaciones(self):
        for nombre, repo, _ in repositorios():
            with self.subTest(backend=nombre):
                repo.reemplazar_periodos([lote("inicial.csv", comprobante(numero=1),
                                             comprobante(numero=2, cuit="CUIT sintético inválido"))])
                if nombre == "django":
                    Importacion.objects.update(operaciones="")
                else:
                    with closing(sqlite3.connect(repo.ruta)) as conexion:
                        conexion.execute("UPDATE importaciones SET operaciones = ''")
                        conexion.commit()
                repo.reemplazar_periodos([lote("rechazo.csv", comprobante(
                    numero=3, cuit="CUIT sintético inválido"))])
                self.assertEqual(repo.consultar_observaciones(PERIODO)["numero"].tolist(), ["2", "3"])

    def test_detalle_alicuotas_usa_centavos_en_modelo(self):
        for nombre, repo, _ in repositorios():
            with self.subTest(backend=nombre):
                repo.reemplazar_periodos([lote("uno.csv", comprobante(numero=1))])
                if nombre == "django":
                    self.assertEqual(list(DetalleAlicuota.objects.values_list(
                        "neto_gravado_centavos", "iva_centavos")), [(10000000, 2100000)])

    def test_nombre_del_contrato_se_vincula_a_un_cliente_django(self):
        limpiar_bd()
        repo = RepositorioDjango()
        repo.reemplazar_periodos([lote("primero.csv", comprobante(numero=1), cliente="Cliente Sintético")])
        repo.reemplazar_periodos([lote("segundo.csv", comprobante(numero=2), cliente="CLIENTE SINTÉTICO")])
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(repo.consultar_comprobantes(PERIODO)["numero"].tolist(), [2])
