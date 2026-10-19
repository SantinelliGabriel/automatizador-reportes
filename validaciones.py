import pandas as pd

COLUMNAS_REQUERIDAS = [
    "producto",
    "unidades",
    "precio_unitario",
]


def validar_ventas(ventas):
    """Comprueba que los datos de ventas sean válidos."""

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

    nombres = ventas["producto"].astype(str).str.strip()

    if nombres.eq("").any():
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

    return ventas