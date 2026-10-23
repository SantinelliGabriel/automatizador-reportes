"""Actualiza claves creadas antes de normalizar Unicode y espacios."""

from django.db import migrations

from automatizador.clientes import clave_cliente


def normalizar_claves(apps, schema_editor):
    cliente_modelo = apps.get_model("comprobantes", "Cliente")
    alias = schema_editor.connection.alias
    clientes = list(cliente_modelo.objects.using(alias).all().order_by("id"))
    claves = [clave_cliente(cliente.nombre) for cliente in clientes]
    if len(claves) != len(set(claves)):
        raise ValueError("Hay clientes equivalentes en Django; requieren consolidación antes de migrar.")
    for cliente, clave in zip(clientes, claves):
        if cliente.nombre_clave != clave:
            cliente_modelo.objects.using(alias).filter(pk=cliente.pk).update(nombre_clave=clave)


class Migration(migrations.Migration):
    dependencies = [("comprobantes", "0001_initial")]
    operations = [migrations.RunPython(normalizar_claves, migrations.RunPython.noop)]
