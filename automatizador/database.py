"""Persistencia de comprobantes por cliente y período."""

import sqlite3
import json
import shutil
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

from automatizador.config import ARCHIVO_BD
from automatizador.decimales import normalizar_decimal


VERSION_ESQUEMA = 2
CENTAVOS = Decimal("0.01")
COLUMNAS_IMPORTES = ("neto_gravado", "iva", "no_gravado_exento", "percepciones", "total")


@dataclass(frozen=True)
class MigracionBase:
    version_anterior: int
    version_actual: int
    respaldo: Path

    def mensaje(self) -> str:
        return (
            f"Base SQLite migrada de versión {self.version_anterior} a {self.version_actual}. "
            f"Respaldo: {self.respaldo}"
        )


def conectar_bd(ruta=None):
    conexion = sqlite3.connect(ruta or ARCHIVO_BD)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def crear_tabla(ruta=None):
    ruta = Path(ruta or ARCHIVO_BD)
    existia = ruta.is_file()
    conexion = conectar_bd(ruta)
    try:
        version = conexion.execute("PRAGMA user_version").fetchone()[0]
        if version > VERSION_ESQUEMA:
            raise ValueError(f"La base usa una versión de esquema no admitida: {version}")
        if version == VERSION_ESQUEMA:
            return
        version_anterior = version
        habia_tablas = existia and conexion.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone() is not None
        respaldo = _crear_respaldo(ruta, version) if habia_tablas else None
        if version == 0:
            conexion.execute("BEGIN IMMEDIATE")
            _migrar_a_v1(conexion)
            conexion.execute("PRAGMA user_version = 1")
            conexion.commit()
            version = 1
        if version == 1:
            conexion.execute("BEGIN IMMEDIATE")
            _migrar_a_v2(conexion)
            conexion.execute("PRAGMA user_version = 2")
            conexion.commit()
            if respaldo is not None:
                return MigracionBase(version_anterior, VERSION_ESQUEMA, respaldo)
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def _migrar_a_v1(conexion):
    """Incorpora observaciones sin alterar los comprobantes ya guardados."""
    conexion.execute("""CREATE TABLE IF NOT EXISTS importaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_importacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            archivo_origen TEXT NOT NULL,
            sha256 TEXT NOT NULL DEFAULT '',
            cliente TEXT NOT NULL DEFAULT '', periodo TEXT NOT NULL DEFAULT '',
            aceptados INTEGER NOT NULL DEFAULT 0, rechazados INTEGER NOT NULL DEFAULT 0,
            cantidad_ventas INTEGER NOT NULL DEFAULT 0, total_centavos INTEGER NOT NULL DEFAULT 0
        )""")
    columnas = {r[1] for r in conexion.execute("PRAGMA table_info(importaciones)")}
    for nombre, tipo in (("cliente", "TEXT NOT NULL DEFAULT ''"), ("periodo", "TEXT NOT NULL DEFAULT ''"),
                         ("aceptados", "INTEGER NOT NULL DEFAULT 0"), ("rechazados", "INTEGER NOT NULL DEFAULT 0"),
                         ("sha256", "TEXT NOT NULL DEFAULT ''")):
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
            moneda TEXT NOT NULL DEFAULT 'ARS', tipo_cambio REAL NOT NULL DEFAULT 1,
            neto_gravado_origen_centavos INTEGER NOT NULL DEFAULT 0,
            iva_origen_centavos INTEGER NOT NULL DEFAULT 0,
            no_gravado_exento_origen_centavos INTEGER NOT NULL DEFAULT 0,
            percepciones_origen_centavos INTEGER NOT NULL DEFAULT 0,
            total_origen_centavos INTEGER NOT NULL DEFAULT 0,
            detalle_alicuotas_json TEXT NOT NULL DEFAULT '[]',
            UNIQUE(cliente, periodo, operacion, tipo_comprobante, punto_venta, numero, cuit)
        )""")
    columnas_comprobantes = {r[1] for r in conexion.execute("PRAGMA table_info(comprobantes)")}
    migraciones = {
        "moneda": "TEXT NOT NULL DEFAULT 'ARS'",
        "tipo_cambio": "REAL NOT NULL DEFAULT 1",
        "neto_gravado_origen_centavos": "INTEGER NOT NULL DEFAULT 0",
        "iva_origen_centavos": "INTEGER NOT NULL DEFAULT 0",
        "no_gravado_exento_origen_centavos": "INTEGER NOT NULL DEFAULT 0",
        "percepciones_origen_centavos": "INTEGER NOT NULL DEFAULT 0",
        "total_origen_centavos": "INTEGER NOT NULL DEFAULT 0",
        "detalle_alicuotas_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    for nombre, tipo in migraciones.items():
        if nombre not in columnas_comprobantes:
            conexion.execute(f"ALTER TABLE comprobantes ADD COLUMN {nombre} {tipo}")
    conexion.execute("""UPDATE comprobantes SET
            neto_gravado_origen_centavos = neto_gravado_centavos,
            iva_origen_centavos = iva_centavos,
            no_gravado_exento_origen_centavos = no_gravado_exento_centavos,
            percepciones_origen_centavos = percepciones_centavos,
            total_origen_centavos = total_centavos
            WHERE neto_gravado_origen_centavos = 0 AND iva_origen_centavos = 0
              AND no_gravado_exento_origen_centavos = 0 AND percepciones_origen_centavos = 0
              AND total_origen_centavos = 0 AND moneda = 'ARS'""")
    conexion.execute("""CREATE TABLE IF NOT EXISTS observaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        importacion_id INTEGER NOT NULL REFERENCES importaciones(id),
        fila_excel TEXT NOT NULL DEFAULT '', motivo TEXT NOT NULL,
        datos_json TEXT NOT NULL DEFAULT '{}'
    )""")
    conexion.execute("CREATE INDEX IF NOT EXISTS idx_observaciones_importacion ON observaciones(importacion_id)")


def _crear_respaldo(ruta, version):
    ruta = Path(ruta)
    indice = 0
    while True:
        sufijo = "" if indice == 0 else f".{indice}"
        respaldo = ruta.with_name(f"{ruta.stem}.v{version}.bak{sufijo}.db")
        try:
            with ruta.open("rb") as origen, respaldo.open("xb") as destino:
                try:
                    shutil.copyfileobj(origen, destino)
                except Exception:
                    destino.close()
                    respaldo.unlink()
                    raise
            break
        except FileExistsError:
            indice += 1
    return respaldo


def _migrar_a_v2(conexion):
    """Recrea comprobantes con tasas como texto y copia centavos sin recalcularlos."""
    conexion.execute("""CREATE TABLE comprobantes_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        importacion_id INTEGER NOT NULL REFERENCES importaciones(id),
        cliente TEXT NOT NULL, periodo TEXT NOT NULL, operacion TEXT NOT NULL,
        fecha TEXT NOT NULL, tipo_comprobante TEXT NOT NULL,
        punto_venta INTEGER NOT NULL, numero INTEGER NOT NULL,
        cuit TEXT NOT NULL, razon_social TEXT NOT NULL,
        neto_gravado_centavos INTEGER NOT NULL, alicuota TEXT NOT NULL,
        iva_centavos INTEGER NOT NULL, no_gravado_exento_centavos INTEGER NOT NULL,
        percepciones_centavos INTEGER NOT NULL, total_centavos INTEGER NOT NULL,
        moneda TEXT NOT NULL DEFAULT 'ARS', tipo_cambio TEXT NOT NULL DEFAULT '1',
        neto_gravado_origen_centavos INTEGER NOT NULL DEFAULT 0,
        iva_origen_centavos INTEGER NOT NULL DEFAULT 0,
        no_gravado_exento_origen_centavos INTEGER NOT NULL DEFAULT 0,
        percepciones_origen_centavos INTEGER NOT NULL DEFAULT 0,
        total_origen_centavos INTEGER NOT NULL DEFAULT 0,
        detalle_alicuotas_json TEXT NOT NULL DEFAULT '[]',
        revision_decimal TEXT NOT NULL DEFAULT '',
        UNIQUE(cliente, periodo, operacion, tipo_comprobante, punto_venta, numero, cuit)
    )""")
    columnas = [fila[1] for fila in conexion.execute("PRAGMA table_info(comprobantes)")]
    consulta = "SELECT " + ", ".join(columnas) + " FROM comprobantes ORDER BY id"
    nuevas_columnas = [*columnas, "revision_decimal"]
    insertar = (
        "INSERT INTO comprobantes_v2 (" + ", ".join(nuevas_columnas) + ") VALUES ("
        + ", ".join("?" for _ in nuevas_columnas) + ")"
    )
    for fila in conexion.execute(consulta):
        datos = dict(zip(columnas, fila))
        alicuota = Decimal(repr(datos["alicuota"]))
        tipo_cambio = Decimal(repr(datos["tipo_cambio"]))
        datos["alicuota"] = normalizar_decimal(alicuota, "alicuota", validar_escala=False)
        datos["tipo_cambio"] = normalizar_decimal(tipo_cambio, "tipo_cambio", validar_escala=False)
        revision = []
        if any(len(valor.normalize().as_tuple().digits) > 15 for valor in (alicuota, tipo_cambio)):
            revision.append("más de 15 cifras significativas")
        if any(
            (Decimal(datos[f"{campo}_origen_centavos"]).scaleb(-2) * tipo_cambio)
            .quantize(CENTAVOS, rounding=ROUND_HALF_UP)
            != Decimal(datos[f"{campo}_centavos"]).scaleb(-2)
            for campo in COLUMNAS_IMPORTES
        ):
            revision.append("conversión a ARS diferente")
        datos["revision_decimal"] = "; ".join(revision)
        conexion.execute(insertar, [datos[columna] for columna in nuevas_columnas])
    conexion.execute("DROP TABLE comprobantes")
    conexion.execute("ALTER TABLE comprobantes_v2 RENAME TO comprobantes")


def _centavos(valor):
    return int(Decimal(str(valor)) * 100)


def _valor_observado(valor):
    if isinstance(valor, (dict, list, tuple)):
        return json.dumps(valor, ensure_ascii=False, default=str)
    if valor is None or pd.isna(valor):
        return None
    return str(valor)


def _reemplazar_periodo_en_conexion(conexion, cliente, periodo, comprobantes, rechazados, archivo_origen,
                                   sha256="", aplicar=True):
    if aplicar:
        conexion.execute("DELETE FROM comprobantes WHERE cliente = ? AND periodo = ?", (cliente, periodo))
    columnas_importacion = {r[1] for r in conexion.execute("PRAGMA table_info(importaciones)")}
    campos = ["archivo_origen", "sha256", "cliente", "periodo", "aceptados", "rechazados"]
    valores = [archivo_origen, sha256, cliente, periodo, len(comprobantes) if aplicar else 0, len(rechazados)]
    if "cantidad_ventas" in columnas_importacion:
        campos.append("cantidad_ventas")
        valores.append(len(comprobantes) if aplicar else 0)
    if "total_centavos" in columnas_importacion:
        campos.append("total_centavos")
        valores.append(sum(_centavos(x) for x in comprobantes.get("total", [])) if aplicar else 0)
    sql = f"INSERT INTO importaciones({', '.join(campos)}) VALUES ({', '.join('?' for _ in campos)})"
    cur = conexion.execute(sql, valores)
    importacion_id = cur.lastrowid
    registros = []
    for fila in (comprobantes.to_dict("records") if aplicar else []):
        registros.append((
            importacion_id, cliente, periodo, fila["operacion"], fila["fecha"],
            fila["tipo_comprobante"], int(fila["punto_venta"]), int(fila["numero"]),
            fila["cuit"], fila["razon_social"], _centavos(fila["neto_gravado"]),
            normalizar_decimal(fila["alicuota"], "alicuota"), _centavos(fila["iva"]),
            _centavos(fila["no_gravado_exento"]), _centavos(fila["percepciones"]),
            _centavos(fila["total"]), fila.get("moneda", "ARS"),
            normalizar_decimal(fila.get("tipo_cambio", 1), "tipo_cambio"),
            _centavos(fila.get("neto_gravado_origen", fila["neto_gravado"])),
            _centavos(fila.get("iva_origen", fila["iva"])),
            _centavos(fila.get("no_gravado_exento_origen", fila["no_gravado_exento"])),
            _centavos(fila.get("percepciones_origen", fila["percepciones"])),
            _centavos(fila.get("total_origen", fila["total"])),
            json.dumps(fila.get("detalle_alicuotas", []), ensure_ascii=False, default=str),
        ))
    conexion.executemany("""INSERT INTO comprobantes(
        importacion_id, cliente, periodo, operacion, fecha, tipo_comprobante,
        punto_venta, numero, cuit, razon_social, neto_gravado_centavos,
        alicuota, iva_centavos, no_gravado_exento_centavos,
        percepciones_centavos, total_centavos, moneda, tipo_cambio,
        neto_gravado_origen_centavos, iva_origen_centavos,
        no_gravado_exento_origen_centavos, percepciones_origen_centavos,
        total_origen_centavos, detalle_alicuotas_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", registros)
    observaciones = []
    for fila in rechazados.to_dict("records"):
        datos = {str(clave): _valor_observado(valor) for clave, valor in fila.items()
                 if clave not in {"fila_excel", "motivo", "cliente"}}
        numero_fila = fila.get("fila_excel")
        observaciones.append((
            importacion_id,
            _valor_observado(numero_fila) or "",
            str(fila.get("motivo", "")),
            json.dumps(datos, ensure_ascii=False),
        ))
    conexion.executemany(
        "INSERT INTO observaciones(importacion_id, fila_excel, motivo, datos_json) VALUES (?, ?, ?, ?)",
        observaciones,
    )
    return importacion_id


def reemplazar_periodos(importaciones, ruta=None):
    """Aplica varios reemplazos en una única transacción SQLite."""
    conexion = conectar_bd(ruta)
    try:
        conexion.execute("BEGIN IMMEDIATE")
        ids = [
            _reemplazar_periodo_en_conexion(
                conexion,
                item["cliente"],
                item["periodo"],
                item["comprobantes"],
                item["rechazados"],
                item["archivo_origen"],
                item.get("sha256", ""),
                item.get("aplicar", True),
            )
            for item in importaciones
        ]
        conexion.commit()
        return ids
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def reemplazar_periodo(cliente, periodo, comprobantes, rechazados, archivo_origen, ruta=None):
    """Compatibilidad para reemplazar un cliente/período en una transacción."""
    ids = reemplazar_periodos([{
        "cliente": cliente,
        "periodo": periodo,
        "comprobantes": comprobantes,
        "rechazados": rechazados,
        "archivo_origen": archivo_origen,
    }], ruta)
    return ids[0]


def consultar_comprobantes(ruta=None, periodo=None):
    conexion = conectar_bd(ruta)
    try:
        consulta = """SELECT cliente, periodo, operacion, fecha, tipo_comprobante,
            punto_venta, numero, cuit, razon_social,
            neto_gravado_centavos, alicuota, iva_centavos,
            no_gravado_exento_centavos, percepciones_centavos,
            total_centavos, moneda, tipo_cambio,
            neto_gravado_origen_centavos, iva_origen_centavos,
            no_gravado_exento_origen_centavos, percepciones_origen_centavos,
            total_origen_centavos, detalle_alicuotas_json, revision_decimal
            FROM comprobantes"""
        params = ()
        if periodo:
            consulta += " WHERE periodo = ?"
            params = (periodo,)
        consulta += " ORDER BY cliente, fecha, punto_venta, numero"
        resultado = pd.read_sql_query(consulta, conexion, params=params)
        for campo in COLUMNAS_IMPORTES:
            resultado[campo] = resultado.pop(f"{campo}_centavos").map(lambda valor: Decimal(int(valor)).scaleb(-2))
            resultado[f"{campo}_origen"] = resultado.pop(f"{campo}_origen_centavos").map(
                lambda valor: Decimal(int(valor)).scaleb(-2)
            )
        for campo in ("alicuota", "tipo_cambio"):
            resultado[campo] = resultado[campo].map(lambda valor: Decimal(valor) if valor is not None else None)
        if "detalle_alicuotas_json" in resultado:
            resultado["detalle_alicuotas"] = resultado["detalle_alicuotas_json"].map(
                lambda valor: json.loads(valor) if valor else []
            )
            resultado = resultado.drop(columns=["detalle_alicuotas_json"])
        return resultado
    finally:
        conexion.close()


def consultar_totales(ruta=None, periodo=None) -> dict[str, Decimal]:
    """Suma centavos persistidos y devuelve pesos exactos; las NC restan."""
    columnas = ("neto_gravado", "iva", "total")
    sumas = [
        f"COALESCE(SUM(CASE WHEN tipo_comprobante LIKE 'NC%' "
        f"THEN -{columna}_centavos ELSE {columna}_centavos END), 0)"
        for columna in columnas
    ]
    consulta = "SELECT " + ", ".join(sumas) + " FROM comprobantes"
    params = ()
    if periodo:
        consulta += " WHERE periodo = ?"
        params = (periodo,)
    conexion = conectar_bd(ruta)
    try:
        centavos = conexion.execute(consulta, params).fetchone()
        return {columna: Decimal(importe).scaleb(-2) for columna, importe in zip(columnas, centavos)}
    finally:
        conexion.close()


def consultar_importaciones(ruta=None):
    conexion = conectar_bd(ruta)
    try:
        return pd.read_sql_query("SELECT * FROM importaciones ORDER BY id DESC", conexion)
    finally:
        conexion.close()


def consultar_observaciones(ruta=None, periodo=None, importacion_id=None):
    """Lee las observaciones de una importación o las vigentes de un período."""
    conexion = conectar_bd(ruta)
    try:
        consulta = """SELECT i.id AS importacion_id, i.cliente, i.periodo, i.archivo_origen,
            o.fila_excel, o.motivo, o.datos_json
            FROM observaciones o JOIN importaciones i ON i.id = o.importacion_id"""
        condiciones = []
        params = []
        if importacion_id is not None:
            condiciones.append("i.id = ?")
            params.append(importacion_id)
        else:
            condiciones.append(
                "i.id = (SELECT MAX(id) FROM importaciones WHERE cliente = i.cliente AND periodo = i.periodo)"
            )
        if periodo is not None:
            condiciones.append("i.periodo = ?")
            params.append(periodo)
        consulta += " WHERE " + " AND ".join(condiciones) + " ORDER BY i.cliente, o.id"
        filas = conexion.execute(consulta, params).fetchall()
        columnas = ("importacion_id", "cliente", "periodo", "archivo_origen", "fila_excel", "motivo", "datos_json")
        resultado = []
        for fila in filas:
            registro = dict(zip(columnas, fila))
            datos = json.loads(registro.pop("datos_json"))
            registro = {**datos, **registro}
            resultado.append(registro)
        extras = sorted({clave for registro in resultado for clave in registro if clave not in columnas})
        return pd.DataFrame(resultado, columns=[*columnas[:-1], *extras])
    finally:
        conexion.close()
