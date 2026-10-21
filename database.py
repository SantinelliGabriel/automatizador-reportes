
import sqlite3
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from config import ARCHIVO_BD


def conectar_bd(ruta=None):
    """Abre una conexión con la base de datos SQLite."""
    return sqlite3.connect(ruta or ARCHIVO_BD)


def crear_tabla(ruta=None):
    """Crea la tabla de ventas si todavía no existe."""

    conexion = conectar_bd() if ruta is None else conectar_bd(ruta)

    try:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto TEXT NOT NULL,
                unidades INTEGER NOT NULL,
                precio_unitario REAL NOT NULL,
                precio_unitario_centavos INTEGER
            )
        """)

        columnas = {
            fila[1]
            for fila in conexion.execute("PRAGMA table_info(ventas)").fetchall()
        }
        if "precio_unitario_centavos" not in columnas:
            conexion.execute(
                "ALTER TABLE ventas ADD COLUMN precio_unitario_centavos INTEGER"
            )
        conexion.execute(
            """UPDATE ventas
               SET precio_unitario_centavos = CAST(ROUND(precio_unitario * 100) AS INTEGER)
               WHERE precio_unitario_centavos IS NULL"""
        )

        conexion.commit()

    finally:
        conexion.close()


def guardar_ventas(ventas, antes_de_commit=None, ruta=None):
    """Reemplaza las ventas en una transacción y ejecuta una acción previa al commit."""

    conexion = conectar_bd() if ruta is None else conectar_bd(ruta)

    try:
        conexion.execute("DELETE FROM ventas")

        registros = []
        for fila in ventas.itertuples(index=False):
            precio = getattr(fila, "precio_unitario")
            centavos = getattr(fila, "precio_unitario_centavos", None)
            if centavos is None or pd.isna(centavos):
                centavos = int(
                    (Decimal(str(precio)) * 100).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                )
            registros.append(
                (fila.producto, int(fila.unidades), int(centavos) / 100, int(centavos))
            )

        conexion.executemany(
            """
            INSERT INTO ventas (
                producto, unidades, precio_unitario, precio_unitario_centavos
            ) VALUES (?, ?, ?, ?)
            """,
            registros,
        )

        if antes_de_commit is not None:
            ventas_guardadas = _consultar_ventas(conexion)
            antes_de_commit(ventas_guardadas)

        conexion.commit()

    except Exception:
        conexion.rollback()
        raise

    finally:
        conexion.close()


def consultar_ventas(ruta=None):
    """Obtiene las ventas y sus subtotales desde SQLite."""

    conexion = conectar_bd() if ruta is None else conectar_bd(ruta)

    try:
        return _consultar_ventas(conexion)

    finally:
        conexion.close()


def _consultar_ventas(conexion):
    consulta = """
        SELECT
            producto,
            unidades,
                precio_unitario_centavos / 100.0 AS precio_unitario,
                unidades * precio_unitario_centavos AS total_centavos,
                (unidades * precio_unitario_centavos) / 100.0 AS total
        FROM ventas
        ORDER BY id
    """
    return pd.read_sql_query(consulta, conexion)
