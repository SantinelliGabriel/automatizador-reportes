# Instalación y uso

Desde un clon del repositorio, con Python 3.11, 3.12 o 3.13 (matriz de CI).

## PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
automatizador --period 2026-09
```

Si la activación está bloqueada, `Set-ExecutionPolicy -Scope Process Bypass` permite ejecutarla solo durante esa sesión.

## macOS y Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
automatizador --period 2026-09
```

Sin `--input`, se usa `ejemplos/Cliente Demo Norte.xlsx`. Se generan `reporte_iva.xlsx` y `comprobantes.db` en el directorio actual. `--period` es obligatorio salvo para `--history`.

## Carpeta de ejemplos

`automatizador-demo` genera dos archivos sintéticos en `datos_demo/`, para septiembre de 2026. La CLI crea los directorios de salida necesarios.

PowerShell:

```powershell
automatizador-demo
automatizador `
  --input datos_demo `
  --output resultados/reporte.xlsx `
  --database resultados/comprobantes.db `
  --period 2026-09
```

bash y zsh:

```bash
automatizador-demo
automatizador \
  --input datos_demo \
  --output resultados/reporte.xlsx \
  --database resultados/comprobantes.db \
  --period 2026-09
```

Las opciones `--source`, `--operation` y `--mapping` se describen en [adaptadores](adaptadores.md). El [libro sintético de muestra](../ejemplos/salida.xlsx) permite revisar la salida.

## Entorno para controles de desarrollo

Instalación: `python -m pip install -e ".[dev,web]"`.
Antes de los comandos Django de desarrollo, configurar estas variables de producción simuladas; no constituyen un despliegue.

PowerShell:

```powershell
$env:DJANGO_DEBUG = "0"
$env:DJANGO_ALLOWED_HOSTS = "example.test"
$env:DJANGO_SECRET_KEY = (& python -c "import secrets; print(secrets.token_urlsafe(64))")
$env:DJANGO_DB_PATH = ":memory:"
```

bash y zsh:

```bash
export DJANGO_DEBUG=0 DJANGO_ALLOWED_HOSTS=example.test DJANGO_DB_PATH=:memory:
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
```

El [README](../README.md#desarrollo) enumera los controles. Para repetir el check de demo se establece `DJANGO_DEMO_MODE=1` y se ejecuta de nuevo `python web/manage.py check --deploy`; luego se elimina esa variable para recuperar el modo habitual. El CI también genera `coverage.xml` y lo envía a Codecov en Linux.

[Volver al README](../README.md)
