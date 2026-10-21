"""Normalización y validación de comprobantes contables."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata

import pandas as pd


COLUMNAS = [
    "fecha", "tipo_comprobante", "punto_venta", "numero", "cuit",
    "razon_social", "neto_gravado", "alicuota", "iva",
    "no_gravado_exento", "percepciones", "total",
]
ALIAS = {
    "fecha": {"fecha", "fecha_comprobante", "date"},
    "tipo_comprobante": {"tipo", "tipo_comprobante", "comprobante", "tipo_factura"},
    "punto_venta": {"punto_venta", "pto_venta", "pos", "sucursal"},
    "numero": {"numero", "nro", "numero_comprobante", "nro_comprobante"},
    "cuit": {"cuit", "cuit_emisor", "cuit_cliente", "identificacion_fiscal"},
    "razon_social": {"razon_social", "cliente", "proveedor", "nombre_fiscal"},
    "neto_gravado": {"neto_gravado", "neto", "importe_neto"},
    "alicuota": {"alicuota", "alicuota_iva", "tasa_iva", "iva_pct"},
    "iva": {"iva", "importe_iva", "iva_debito_credito"},
    "no_gravado_exento": {"no_gravado_exento", "no_gravado", "exento"},
    "percepciones": {"percepciones", "otros_impuestos", "percepciones_otros"},
    "total": {"total", "importe_total", "total_comprobante"},
    "operacion": {"operacion", "tipo_operacion", "libro"},
    "moneda": {"moneda", "currency", "divisa"},
    "tipo_cambio": {"tipo_cambio", "tipo_de_cambio", "cotizacion", "exchange_rate", "cambio"},
}
TIPOS_VALIDOS = {
    "A", "B", "C", "E", "M",
    "NC A", "NC B", "NC C", "NC E", "NC M",
    "ND A", "ND B", "ND C", "ND E", "ND M",
}
# Tabla de alícuotas de ARCA para Libro IVA Digital: 0, 2.5, 5, 10.5, 21 y 27.
ALICUOTAS_VALIDAS = {Decimal(v) for v in ("0", "2.5", "5", "10.5", "21", "27")}
CENTAVOS = Decimal("0.01")


def clave_encabezado(valor):
    texto = unicodedata.normalize("NFKD", str(valor).strip().casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return "".join(c for c in texto if c.isalnum())


def normalizar_columnas(df):
    alias = {clave_encabezado(a): canon for canon, nombres in ALIAS.items() for a in nombres}
    renombres, usados = {}, {}
    for original in df.columns:
        canon = alias.get(clave_encabezado(original))
        if canon:
            if canon in usados:
                raise ValueError(f"Los encabezados '{usados[canon]}' y '{original}' son ambiguos para '{canon}'.")
            usados[canon] = original
            renombres[original] = canon
    return df.rename(columns=renombres)


def validar_cuit(valor):
    digitos = re.sub(r"\D", "", str(valor))
    if len(digitos) != 11:
        return False
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    resto = sum(int(d) * p for d, p in zip(digitos[:10], pesos)) % 11
    verificador = 11 - resto
    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        # Casos de prefijo 20/23/24/27 tienen regla alternativa del CUIT.
        verificador = 9 if digitos[:2] in {"20", "23", "24", "27"} else 0
    return int(digitos[-1]) == verificador


def _importe(valor):
    importe = Decimal(str(valor)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    if not importe.is_finite():
        raise InvalidOperation
    return importe


def validar_comprobantes(df, periodo):
    """Devuelve (aceptados, rechazados) con validación aislada por fila."""
    df = normalizar_columnas(df.copy())
    if df.empty:
        raise ValueError("El archivo no contiene comprobantes para procesar.")
    faltantes = [col for col in COLUMNAS if col not in df.columns]
    if faltantes:
        raise ValueError("Faltan columnas obligatorias: " + ", ".join(faltantes))
    if "operacion" not in df.columns:
        df["operacion"] = "ventas"

    aceptados, rechazados, claves = [], [], set()
    for indice, fila in df.iterrows():
        fila_numero = fila.get("_fila_original", int(indice) + 2 if isinstance(indice, int) else str(indice))
        motivos = []
        registro = fila.to_dict()

        try:
            valor_fecha = fila["fecha"]
            if isinstance(valor_fecha, str) and len(valor_fecha.strip()) == 10 and valor_fecha.strip()[2] == "/":
                fecha = pd.to_datetime(valor_fecha.strip(), format="%d/%m/%Y", errors="raise").date()
            else:
                fecha = pd.to_datetime(valor_fecha, errors="raise").date()
            if fecha.strftime("%Y-%m") != periodo:
                motivos.append(f"La fecha no pertenece al período {periodo}.")
            registro["fecha"] = fecha.isoformat()
        except (ValueError, TypeError, OverflowError):
            motivos.append("Fecha inválida.")

        tipo = " ".join(str(fila["tipo_comprobante"]).upper().split())
        tipo = tipo.replace("NOTA DE CREDITO", "NC").replace("NOTA DE CRÉDITO", "NC")
        tipo = tipo.replace("NOTA DE DEBITO", "ND").replace("NOTA DE DÉBITO", "ND")
        if tipo not in TIPOS_VALIDOS:
            motivos.append("Tipo de comprobante no reconocido (A/B/C/E/M, NC o ND).")
        registro["tipo_comprobante"] = tipo

        try:
            registro["punto_venta"] = int(fila["punto_venta"])
            registro["numero"] = int(fila["numero"])
            if registro["punto_venta"] < 1 or registro["numero"] < 1:
                motivos.append("Punto de venta y número deben ser mayores que cero.")
        except (ValueError, TypeError, OverflowError):
            motivos.append("Punto de venta y número deben ser enteros válidos.")

        valor_cuit = fila["cuit"]
        if isinstance(valor_cuit, float) and valor_cuit.is_integer():
            valor_cuit = str(int(valor_cuit))
        cuit = re.sub(r"\D", "", str(valor_cuit))
        if not validar_cuit(cuit):
            motivos.append("CUIT inválido: formato o dígito verificador incorrecto.")
        registro["cuit"] = cuit
        registro["razon_social"] = str(fila["razon_social"]).strip()
        if not registro["razon_social"] or registro["razon_social"].casefold() == "nan":
            motivos.append("Razón social vacía.")

        try:
            alicuota = Decimal(str(fila["alicuota"]).replace("%", "").replace(",", "."))
            if alicuota not in ALICUOTAS_VALIDAS:
                motivos.append("Alícuota inválida; use 0, 2,5, 5, 10,5, 21 o 27.")
            registro["alicuota"] = float(alicuota)
        except (InvalidOperation, ValueError, TypeError):
            motivos.append("Alícuota inválida.")
            alicuota = Decimal("0")

        columnas_importes = ("neto_gravado", "iva", "no_gravado_exento", "percepciones", "total")
        for col in columnas_importes:
            try:
                registro[col] = _importe(fila[col])
            except (InvalidOperation, ValueError, TypeError):
                motivos.append(f"Importe inválido en '{col}'.")
                registro[col] = Decimal("0")

        moneda = fila.get("moneda", "ARS")
        moneda = "ARS" if pd.isna(moneda) or not str(moneda).strip() else str(moneda).strip().upper()
        moneda = {"PES": "ARS", "DOL": "USD"}.get(moneda, moneda)
        if len(moneda) != 3 or not moneda.isalpha():
            motivos.append("Moneda inválida; use un código de tres letras, por ejemplo ARS o USD.")
        tipo_cambio_raw = fila.get("tipo_cambio", 1 if moneda == "ARS" else None)
        if pd.isna(tipo_cambio_raw) or not str(tipo_cambio_raw).strip():
            tipo_cambio = None
        else:
            try:
                tipo_cambio = Decimal(str(tipo_cambio_raw).replace(",", "."))
                if not tipo_cambio.is_finite() or tipo_cambio <= 0:
                    motivos.append("El tipo de cambio debe ser un número mayor que cero.")
                    tipo_cambio = None
            except (InvalidOperation, ValueError, TypeError):
                motivos.append("Tipo de cambio inválido.")
                tipo_cambio = None
        if moneda == "ARS" and tipo_cambio not in (None, Decimal("1")):
            motivos.append("Para ARS, el tipo de cambio debe ser 1.")
        elif moneda != "ARS" and tipo_cambio is None:
            motivos.append("Falta el tipo de cambio a ARS para la moneda extranjera.")
        if moneda == "ARS" and tipo_cambio is None:
            tipo_cambio = Decimal("1")

        for col in columnas_importes:
            registro[f"{col}_origen"] = registro[col]
        registro["moneda"] = moneda
        registro["tipo_cambio"] = float(tipo_cambio) if tipo_cambio is not None else None

        if all(isinstance(registro[c], Decimal) for c in columnas_importes):
            esperado = registro["neto_gravado"] * alicuota / Decimal("100")
            if abs(esperado.quantize(CENTAVOS, rounding=ROUND_HALF_UP) - registro["iva"]) > CENTAVOS:
                motivos.append("El IVA no coincide con neto gravado por alícuota (tolerancia de $0,01).")
            suma = sum((registro[c] for c in ("neto_gravado", "iva", "no_gravado_exento", "percepciones")), Decimal("0"))
            if abs(suma - registro["total"]) > CENTAVOS:
                motivos.append("Neto, IVA, no gravado/exento y percepciones no coinciden con el total.")

        if moneda != "ARS" and tipo_cambio is not None:
            for col in columnas_importes:
                registro[col] = (registro[f"{col}_origen"] * tipo_cambio).quantize(CENTAVOS, rounding=ROUND_HALF_UP)

        operacion = str(fila["operacion"]).strip().casefold()
        if operacion not in {"ventas", "compras"}:
            motivos.append("Operación debe ser 'ventas' o 'compras'.")
        registro["operacion"] = operacion
        clave = (tipo, registro.get("punto_venta"), registro.get("numero"), cuit)
        if clave in claves:
            motivos.append("Comprobante duplicado (tipo, punto de venta, número y CUIT).")
        if not motivos:
            claves.add(clave)
            aceptados.append(registro)
        else:
            rechazados.append({**registro, "fila_excel": fila_numero, "motivo": " ".join(motivos)})

    return pd.DataFrame(aceptados), pd.DataFrame(rechazados)
