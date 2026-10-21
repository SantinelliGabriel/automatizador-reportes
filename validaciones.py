import pandas as pd
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

COLUMNAS_REQUERIDAS = [
    "producto",
    "unidades",
    "precio_unitario",
]


def validar_ventas(ventas):
    """Comprueba que los datos de ventas sean válidos."""
    ventas = ventas.copy()

    if ventas.empty:
        raise ValueError("El Excel no contiene ventas para procesar.")

    columnas_faltantes = [
        columna
        for columna in COLUMNAS_REQUERIDAS
        if columna not in ventas.columns
    ]

    if columnas_faltantes:
        raise ValueError(
            "Faltan estas columnas en el Excel: "
            + ", ".join(columnas_faltantes)
        )

    if ventas[COLUMNAS_REQUERIDAS].isna().any().any():
        raise ValueError("Hay celdas vacías en los datos de ventas.")

    ventas["producto"] = ventas["producto"].astype(str).str.strip()

    if ventas["producto"].eq("").any():
        raise ValueError("Hay productos sin nombre.")

    for columna in ["unidades", "precio_unitario"]:
        try:
            ventas[columna] = pd.to_numeric(
                ventas[columna],
                errors="raise",
            )
        except (ValueError, TypeError) as error:
            raise ValueError(
                f"La columna '{columna}' contiene valores no numéricos."
            ) from error

        if not ventas[columna].map(
            lambda valor: pd.notna(valor) and abs(valor) != float("inf")
        ).all():
            raise ValueError(
                f"La columna '{columna}' contiene números no válidos."
            )

    if (ventas["unidades"] <= 0).any():
        raise ValueError("Las unidades deben ser mayores que cero.")

    if (ventas["unidades"] % 1 != 0).any():
        raise ValueError("Las unidades deben ser números enteros.")

    if (ventas["precio_unitario"] < 0).any():
        raise ValueError("Los precios no pueden ser negativos.")

    if (ventas["unidades"] > 2**63 - 1).any():
        raise ValueError(
            "Las unidades están fuera del rango permitido por SQLite."
        )

    centavos = []
    try:
        for precio in ventas["precio_unitario"]:
            decimal = Decimal(str(precio))
            centavos.append(
                int((decimal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            )
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise ValueError("Hay precios que no se pueden representar en centavos.") from error

    ventas["precio_unitario_centavos"] = centavos
    ventas["precio_unitario"] = [importe / 100 for importe in centavos]
    unidades_enteras = [int(unidad) for unidad in ventas["unidades"]]
    ventas["unidades"] = unidades_enteras

    limite_sqlite = 2**63 - 1
    importes_centavos = [
        unidades * precio
        for unidades, precio in zip(unidades_enteras, centavos)
    ]
    if any(importe > limite_sqlite for importe in importes_centavos):
        raise ValueError("El importe calculado por producto no es válido.")
    if sum(importes_centavos) > limite_sqlite:
        raise ValueError("El total de ventas está fuera del rango permitido.")

    return ventas
