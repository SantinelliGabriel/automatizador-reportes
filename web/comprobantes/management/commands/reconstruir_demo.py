"""Reconstruye la base local de solo lectura con los ejemplos sintéticos."""

import os
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
        password = os.getenv("DJANGO_DEMO_PASSWORD", "")
        if not password:
            raise CommandError("DJANGO_DEMO_PASSWORD es obligatoria.")
        fuentes = sorted((Path(__file__).resolve().parents[4] / "ejemplos").glob("Cliente Demo *.xlsx"))
        if not fuentes:
            raise CommandError("No se encontraron los ejemplos sintéticos.")
        permitidos = {fuente.stem for fuente in fuentes}
        if Cliente.objects.exclude(nombre__in=permitidos).exists():
            raise CommandError("La base contiene clientes ajenos a la demo; usá una base separada.")
        usuario_modelo = get_user_model()
        if usuario_modelo.objects.exclude(username="demo").exists():
            raise CommandError("La base contiene otros usuarios; usá una base separada.")
        with transaction.atomic():
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
