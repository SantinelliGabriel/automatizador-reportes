"""Representación canónica de tasas y cotizaciones sin float."""

from decimal import Decimal, InvalidOperation


ESCALAS_MAXIMAS = {"alicuota": 1, "tipo_cambio": 8}


def normalizar_decimal(valor, campo: str, *, validar_escala: bool = True) -> str:
    """Devuelve texto decimal sin ceros finales ni exponente."""
    if campo not in ESCALAS_MAXIMAS:
        raise ValueError(f"Campo decimal desconocido: {campo}")
    texto = repr(float(valor)) if isinstance(valor, float) else str(valor)
    texto = texto.strip().replace(",", ".")
    if campo == "alicuota":
        texto = texto.removesuffix("%").strip()
    try:
        numero = Decimal(texto)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{campo} inválido: {valor}") from error
    if not numero.is_finite():
        raise ValueError(f"{campo} debe ser finito")
    normalizado = numero.normalize()
    if normalizado == 0:
        return "0"
    escala = max(0, -normalizado.as_tuple().exponent)
    if validar_escala and escala > ESCALAS_MAXIMAS[campo]:
        raise ValueError(f"{campo} supera la escala máxima de {ESCALAS_MAXIMAS[campo]} decimales")
    return format(normalizado, "f")
