"""Reconstruye la base local de solo lectura con los ejemplos sintéticos."""

import os
import hashlib
from pathlib import Path

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from automatizador.procesamiento import confirmar_importacion, previsualizar
from web.comprobantes.models import Cliente, Comprobante, DetalleAlicuota, Importacion, Observacion
from web.comprobantes.repositorio import RepositorioDjango


class Command(BaseCommand):
    help = "Reconstruye la base de demostración con datos sintéticos."

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError("Activá DJANGO_DEMO_MODE=1 para reconstruir la demo.")
        base = str(settings.DATABASES["default"]["NAME"])
        if base != ":memory:" and Path(base).name.casefold() != "demo.sqlite3":
            raise CommandError("Usar una base dedicada llamada demo.sqlite3 para la demo.")
        password = os.getenv("DJANGO_DEMO_PASSWORD", "")
        if not password:
            raise CommandError("DJANGO_DEMO_PASSWORD es obligatoria.")
        fuentes = sorted((Path(__file__).resolve().parents[4] / "ejemplos").glob("Cliente Demo *.xlsx"))
        if not fuentes:
            raise CommandError("No se encontraron los ejemplos sintéticos.")
        permitidos = {fuente.stem: (fuente.name, hashlib.sha256(fuente.read_bytes()).hexdigest())
                      for fuente in fuentes}
        usuario_modelo = get_user_model()
        with transaction.atomic():
            if Cliente.objects.exclude(nombre__in=permitidos).exists():
                raise CommandError("La base contiene clientes ajenos a la demo; no se modificó nada.")
            if usuario_modelo.objects.exclude(username="demo").exists():
                raise CommandError("La base contiene otros usuarios; no se modificó nada.")
            clientes_previos = list(Cliente.objects.values_list("id", flat=True))
            importaciones = list(Importacion.objects.select_related("cliente"))
            if set(clientes_previos) - {item.cliente_id for item in importaciones}:
                raise CommandError("La base contiene clientes sin importaciones de demo; no se modificó nada.")
            for item in importaciones:
                esperado = permitidos.get(item.cliente.nombre)
                if (esperado is None or (item.archivo_origen, item.sha256) != esperado
                        or item.periodo != "2026-09"):
                    raise CommandError("La base contiene importaciones ajenas a la demo; no se modificó nada.")
            DetalleAlicuota.objects.all().delete()
            Observacion.objects.all().delete()
            Comprobante.objects.all().delete()
            Importacion.objects.all().delete()
            Cliente.objects.all().delete()
            usuario, _ = usuario_modelo.objects.get_or_create(username="demo")
            usuario.set_password(password)
            usuario.is_staff = False
            usuario.is_superuser = False
            usuario.save()
            repositorio = RepositorioDjango()
            for fuente in fuentes:
                plan = previsualizar(fuente, "2026-09", "estandar", "mixto", cliente=fuente.stem)
                confirmar_importacion(plan, repositorio)
        self.stdout.write(self.style.SUCCESS("Base de demo reconstruida con ejemplos sintéticos."))
