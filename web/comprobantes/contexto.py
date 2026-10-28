"""Variables compartidas por las plantillas de la interfaz."""

from django.conf import settings


def modo_demo(request):
    return {"DEMO_MODE": settings.DEMO_MODE}
