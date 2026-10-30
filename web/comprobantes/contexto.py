"""Variables compartidas por las plantillas de la interfaz."""

from importlib.metadata import PackageNotFoundError, version

from django.conf import settings


def modo_demo(request):
    try:
        version_actual = version("automatizador-comprobantes-iva")
    except PackageNotFoundError:
        version_actual = "0.2.0"
    return {"DEMO_MODE": settings.DEMO_MODE, "VERSION_APP": version_actual}
