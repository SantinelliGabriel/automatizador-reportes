"""Caracteriza la preparación de lotes anterior a la persistencia."""

import unittest

import pandas as pd

from automatizador.repositorio import RepositorioLotes
from automatizador.validaciones import validar_comprobantes
from tests.helpers import comprobante


class RepositorioCaptura(RepositorioLotes):
    def _guardar_lotes(self, importaciones):
        self.lotes = importaciones
        return list(range(1, len(importaciones) + 1))


class TestLotesCompartidos(unittest.TestCase):
    def test_ambos_archivos_en_conflicto_llegan_no_aplicados_al_backend(self):
        repo = RepositorioCaptura()
        lotes = []
        for numero in (1, 2):
            aceptados, rechazados = validar_comprobantes(pd.DataFrame([
                comprobante(numero=numero),
            ]), "2026-09")
            lotes.append({"cliente": "Cliente Sintético", "periodo": "2026-09",
                          "comprobantes": aceptados, "rechazados": rechazados})
        self.assertEqual(repo.reemplazar_periodos(lotes), [1, 2])
        self.assertEqual([item["operaciones"] for item in repo.lotes], [("ventas",), ("ventas",)])
        self.assertEqual([item["aplicar"] for item in repo.lotes], [False, False])
        self.assertTrue(all("Conflicto en el lote" in item["rechazados"].iloc[0]["motivo"]
                            for item in repo.lotes))
