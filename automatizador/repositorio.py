"""Contrato mínimo de persistencia para la CLI, Streamlit y una futura web."""

from pathlib import Path
from typing import Protocol

import pandas as pd

from automatizador.lotes import preparar_lotes
from automatizador.database import (
    consultar_comprobantes,
    consultar_importaciones,
    consultar_observaciones,
    crear_tabla,
    reemplazar_periodos,
)


class RepositorioComprobantes(Protocol):
    def reemplazar_periodos(self, importaciones: list[dict]) -> list[int]:
        """Guarda comprobantes y observaciones en una transacción por lote."""
        ...

    def consultar_comprobantes(self, periodo: str | None = None) -> pd.DataFrame:
        ...

    def consultar_importaciones(self) -> pd.DataFrame:
        ...

    def consultar_observaciones(self, periodo: str | None = None, importacion_id: int | None = None) -> pd.DataFrame:
        ...


class RepositorioLotes:
    """Aplica las mismas reglas de lote antes de invocar cada backend."""

    def reemplazar_periodos(self, importaciones: list[dict]) -> list[int]:
        return self._guardar_lotes(preparar_lotes(importaciones))

    def _guardar_lotes(self, importaciones: list[dict]) -> list[int]:
        raise NotImplementedError


class RepositorioSQLite(RepositorioLotes):
    """Implementación SQLite del contrato; conserva las funciones públicas existentes."""

    def __init__(self, ruta: Path | str):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.migracion = crear_tabla(self.ruta)

    def _guardar_lotes(self, importaciones: list[dict]) -> list[int]:
        return reemplazar_periodos(importaciones, self.ruta, _preparados=True)

    def consultar_comprobantes(self, periodo: str | None = None) -> pd.DataFrame:
        return consultar_comprobantes(self.ruta, periodo)

    def consultar_importaciones(self) -> pd.DataFrame:
        return consultar_importaciones(self.ruta)

    def consultar_observaciones(self, periodo: str | None = None, importacion_id: int | None = None) -> pd.DataFrame:
        return consultar_observaciones(self.ruta, periodo, importacion_id)
