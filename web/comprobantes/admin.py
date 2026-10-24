"""Inspección local de los datos confirmados."""

from django.contrib import admin

from web.comprobantes.models import Cliente, Comprobante, DetalleAlicuota, Importacion, Observacion


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cuit")
    search_fields = ("nombre", "cuit")


@admin.register(Importacion)
class ImportacionAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "periodo", "operaciones", "aceptados", "rechazados", "fecha_importacion")
    list_filter = ("periodo", "operaciones")


@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display = ("cliente", "periodo", "operacion", "tipo_comprobante", "punto_venta", "numero")
    list_filter = ("periodo", "operacion")


admin.site.register(DetalleAlicuota)
admin.site.register(Observacion)
