"""Esquema relacional equivalente a la persistencia SQLite v3."""

from django.db import models
from django.db.models.functions import Lower

from automatizador.clientes import clave_cliente
from web.comprobantes.campos import TextoDecimalField


class Cliente(models.Model):
    nombre = models.TextField()
    nombre_clave = models.TextField(unique=True, editable=False)
    cuit = models.CharField(max_length=11, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("nombre"), name="cliente_nombre_sin_mayusculas_unico")]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre_clave = clave_cliente(self.nombre)
        super().save(*args, **kwargs)


class Importacion(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="importaciones")
    periodo = models.CharField(max_length=7)
    archivo_origen = models.TextField()
    sha256 = models.CharField(max_length=64, blank=True)
    fecha_importacion = models.DateTimeField(auto_now_add=True)
    aceptados = models.PositiveIntegerField(default=0)
    rechazados = models.PositiveIntegerField(default=0)
    operaciones = models.TextField(blank=True, default="")
    cantidad_ventas = models.PositiveIntegerField(default=0)
    total_centavos = models.BigIntegerField(default=0)


class Comprobante(models.Model):
    importacion = models.ForeignKey(Importacion, on_delete=models.PROTECT, related_name="comprobantes")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="comprobantes")
    periodo = models.CharField(max_length=7)
    operacion = models.CharField(max_length=7)
    fecha = models.DateField()
    tipo_comprobante = models.CharField(max_length=20)
    punto_venta = models.IntegerField()
    numero = models.IntegerField()
    cuit = models.CharField(max_length=11)
    razon_social = models.TextField()
    neto_gravado_centavos = models.BigIntegerField()
    alicuota = TextoDecimalField(campo="alicuota")
    iva_centavos = models.BigIntegerField()
    no_gravado_exento_centavos = models.BigIntegerField()
    percepciones_centavos = models.BigIntegerField()
    total_centavos = models.BigIntegerField()
    moneda = models.CharField(max_length=10, default="ARS")
    tipo_cambio = TextoDecimalField(campo="tipo_cambio", default="1")
    neto_gravado_origen_centavos = models.BigIntegerField()
    iva_origen_centavos = models.BigIntegerField()
    no_gravado_exento_origen_centavos = models.BigIntegerField()
    percepciones_origen_centavos = models.BigIntegerField()
    total_origen_centavos = models.BigIntegerField()
    detalle_alicuotas = models.JSONField(default=list)
    revision_decimal = models.TextField(blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["cliente", "periodo", "operacion", "tipo_comprobante", "punto_venta", "numero", "cuit"],
            name="comprobante_identidad_unica",
        )]


class DetalleAlicuota(models.Model):
    comprobante = models.ForeignKey(Comprobante, on_delete=models.CASCADE, related_name="alicuotas")
    alicuota = TextoDecimalField(campo="alicuota")
    neto_gravado_centavos = models.BigIntegerField()
    iva_centavos = models.BigIntegerField()


class Observacion(models.Model):
    importacion = models.ForeignKey(Importacion, on_delete=models.PROTECT, related_name="observaciones")
    fila_excel = models.TextField(blank=True, default="")
    motivo = models.TextField()
    datos = models.JSONField(default=dict)
