
import sqlite3
from pathlib import Path

import pandas as pd


CARPETA_PROYECTO = Path(__file__).parent
ARCHIVO_BD = CARPETA_PROYECTO / "ventas.db"


def conectar_bd():
    """Abre una conexión con la base de datos SQLite."""
    return sqlite3.connect(ARCHIVO_BD)


def crear_tabla():
    """Crea la tabla de ventas si todavía no existe."""

    conexion = conectar_bd()

    try:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto TEXT NOT NULL,
                unidades INTEGER NOT NULL,
                precio_unitario REAL NOT NULL
            )
        """)

        conexion.commit()

    finally:
        conexion.close()


def guardar_ventas(ventas):
    """Reemplaza los registros de SQLite por las ventas validadas."""

    conexion = conectar_bd()

    try:
        conexion.execute("DELETE FROM ventas")

        registros = ventas[
            ["producto", "unidades", "precio_unitario"]
        ].itertuples(index=False, name=None)

        conexion.executemany(
            """
            INSERT INTO ventas (producto, unidades, precio_unitario)
            VALUES (?, ?, ?)
            """,
            registros,
        )

        conexion.commit()

    except Exception:
        conexion.rollback()
        raise

    finally:
        conexion.close()


def consultar_ventas():
    """Obtiene las ventas y sus subtotales desde SQLite."""

    conexion = conectar_bd()

    try:
        consulta = """
            SELECT
                producto,
                unidades,
                precio_unitario,
                unidades * precio_unitario AS total
            FROM ventas
            ORDER BY id
        """

        ventas = pd.read_sql_query(consulta, conexion)

        return ventas

    finally:
        conexion.close()
