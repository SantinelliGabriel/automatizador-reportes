"""Campo de texto decimal exacto para tasas y cotizaciones."""

from decimal import Decimal

from django import forms
from django.db import models

from automatizador.decimales import ESCALAS_MAXIMAS, normalizar_decimal


class TextoDecimalField(models.TextField):
    """Guarda texto canónico y entrega Decimal al leer de SQLite."""

    def __init__(self, *args, campo, **kwargs):
        if campo not in ESCALAS_MAXIMAS:
            raise ValueError(f"Campo decimal desconocido: {campo}")
        self.campo = campo
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["campo"] = self.campo
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        return None if value is None else Decimal(value)

    def to_python(self, value):
        if value is None:
            return None
        return Decimal(normalizar_decimal(value, self.campo))

    def get_prep_value(self, value):
        return None if value is None else normalizar_decimal(value, self.campo)

    def formfield(self, **kwargs):
        defaults = {"form_class": forms.DecimalField, "max_digits": 30,
                    "decimal_places": ESCALAS_MAXIMAS[self.campo]}
        defaults.update(kwargs)
        return models.Field.formfield(self, **defaults)
