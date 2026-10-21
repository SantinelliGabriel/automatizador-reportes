"""Persistencia de comprobantes por cliente y período."""

import sqlite3
from decimal import Decimal

import pandas as pd

from automatizador.config import ARCHIVO_BD


def conectar_bd(ruta=None):
    conexion = sqlite3.connect(ruta or ARCHIVO_BD)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def crear_tabla(ruta=None):
    conexion = conectar_bd(ruta)
    try:
        conexion.execute("""CREATE TABLE IF NOT EXISTS importaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_importacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            archivo_origen TEXT NOT NULL,
            cliente TEXT NOT NULL DEFAULT '', periodo TEXT NOT NULL DEFAULT '',
            aceptados INTEGER NOT NULL DEFAULT 0, rechazados INTEGER NOT NULL DEFAULT 0,
            cantidad_ventas INTEGER NOT NULL DEFAULT 0, total_centavos INTEGER NOT NULL DEFAULT 0
        )""")
        columnas = {r[1] for r in conexion.execute("PRAGMA table_info(importaciones)")}
        for nombre, tipo in (("cliente", "TEXT NOT NULL DEFAULT ''"), ("periodo", "TEXT NOT NULL DEFAULT ''"), ("aceptados", "INTEGER NOT NULL DEFAULT 0"), ("rechazados", "INTEGER NOT NULL DEFAULT 0")):
            if nombre not in columnas:
                conexion.execute(f"ALTER TABLE importaciones ADD COLUMN {nombre} {tipo}")
        conexion.execute("""CREATE TABLE IF NOT EXISTS comprobantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            importacion_id INTEGER NOT NULL REFERENCES importaciones(id),
            cliente TEXT NOT NULL, periodo TEXT NOT NULL, operacion TEXT NOT NULL,
            fecha TEXT NOT NULL, tipo_comprobante TEXT NOT NULL,
            punto_venta INTEGER NOT NULL, numero INTEGER NOT NULL,
            cuit TEXT NOT NULL, razon_social TEXT NOT NULL,
            neto_gravado_centavos INTEGER NOT NULL, alicuota REAL NOT NULL,
            iva_centavos INTEGER NOT NULL, no_gravado_exento_centavos INTEGER NOT NULL,
            percepciones_centavos INTEGER NOT NULL, total_centavos INTEGER NOT NULL,
            UNIQUE(cliente, periodo, operacion, tipo_comprobante, punto_venta, numero, cuit)
        )""")
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def _centavos(valor):
    return int(Decimal(str(valor)) * 100)


def reemplazar_periodo(cliente, periodo, comprobantes, rechazados, archivo_origen, ruta=None):
    """Reemplaza atómicamente los comprobantes aceptados de un cliente y período."""
    conexion = conectar_bd(ruta)
    try:
        conexion.execute("BEGIN IMMEDIATE")
        conexion.execute("DELETE FROM comprobantes WHERE cliente = ? AND periodo = ?", (cliente, periodo))
        columnas_importacion = {r[1] for r in conexion.execute("PRAGMA table_info(importaciones)")}
        campos = ["archivo_origen", "cliente", "periodo", "aceptados", "rechazados"]
        valores = [archivo_origen, cliente, periodo, len(comprobantes), len(rechazados)]
        if "cantidad_ventas" in columnas_importacion:
            campos.append("cantidad_ventas")
            valores.append(len(comprobantes))
        if "total_centavos" in columnas_importacion:
            campos.append("total_centavos")
            valores.append(sum(_centavos(x) for x in comprobantes.get("total", [])))
        sql = f"INSERT INTO importaciones({', '.join(campos)}) VALUES ({', '.join('?' for _ in campos)})"
        cur = conexion.execute(sql, valores)
        importacion_id = cur.lastrowid
        registros = []
        for fila in comprobantes.to_dict("records"):
            registros.append((
                importacion_id, cliente, periodo, fila["operacion"], fila["fecha"],
                fila["tipo_comprobante"], int(fila["punto_venta"]), int(fila["numero"]),
                fila["cuit"], fila["razon_social"], _centavos(fila["neto_gravado"]),
                float(fila["alicuota"]), _centavos(fila["iva"]),
                _centavos(fila["no_gravado_exento"]), _centavos(fila["percepciones"]),
                _centavos(fila["total"]),
            ))
        conexion.executemany("""INSERT INTO comprobantes(
            importacion_id, cliente, periodo, operacion, fecha, tipo_comprobante,
            punto_venta, numero, cuit, razon_social, neto_gravado_centavos,
            alicuota, iva_centavos, no_gravado_exento_centavos,
            percepciones_centavos, total_centavos
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", registros)
        conexion.commit()
        return importacion_id
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def consultar_comprobantes(ruta=None, periodo=None):
    conexion = conectar_bd(ruta)
    try:
        consulta = """SELECT cliente, periodo, operacion, fecha, tipo_comprobante,
            punto_venta, numero, cuit, razon_social,
            neto_gravado_centavos / 100.0 AS neto_gravado, alicuota,
            iva_centavos / 100.0 AS iva,
            no_gravado_exento_centavos / 100.0 AS no_gravado_exento,
            percepciones_centavos / 100.0 AS percepciones,
            total_centavos / 100.0 AS total
            FROM comprobantes"""
        params = ()
        if periodo:
            consulta += " WHERE periodo = ?"
            params = (periodo,)
        consulta += " ORDER BY cliente, fecha, punto_venta, numero"
        return pd.read_sql_query(consulta, conexion, params=params)
    finally:
        conexion.close()


def consultar_importaciones(ruta=None):
    conexion = conectar_bd(ruta)
    try:
        return pd.read_sql_query("SELECT * FROM importaciones ORDER BY id DESC", conexion)
    finally:
        conexion.close()
