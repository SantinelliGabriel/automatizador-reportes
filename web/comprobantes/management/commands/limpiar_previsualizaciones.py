"""Elimina vistas previas vencidas del directorio privado."""

from django.core.management.base import BaseCommand

from web.comprobantes.previews import limpiar_vencidas


class Command(BaseCommand):
    help = "Elimina archivos de vista previa de más de 30 minutos."

    def handle(self, *args, **options):
        cantidad = limpiar_vencidas()
        self.stdout.write(f"Vistas previas vencidas eliminadas: {cantidad}")
