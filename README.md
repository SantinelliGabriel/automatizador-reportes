# Automatizador de comprobantes e informes de IVA

[![CI](https://github.com/SantinelliGabriel/automatizador-reportes/actions/workflows/tests.yml/badge.svg)](https://github.com/SantinelliGabriel/automatizador-reportes/actions/workflows/tests.yml) [![Cobertura](https://img.shields.io/codecov/c/github/SantinelliGabriel/automatizador-reportes/main?logo=codecov)](https://codecov.io/gh/SantinelliGabriel/automatizador-reportes) [![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/) [![Demo en Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://automatizador-reportes-kqvtruqnyz7gwzj47ex7is.streamlit.app/)

Herramienta para revisar comprobantes de ventas y compras, registrar observaciones y producir informes mensuales en Excel.

<sub><strong>English summary:</strong> A Python tool for validating invoices and credit/debit notes, importing ARCA exports, and producing Argentine VAT (IVA) reports.<br>It combines source adapters, SQLite history, bank reconciliation, and a synthetic Streamlit demo.</sub>

**Estado:** proyecto personal de portfolio · **Versión:** [0.1.1](CHANGELOG.md)

![Recorrido de la demo sintética y el informe Excel generado](docs/images/flujo-demo.gif)

> Proyecto de apoyo a la revisión. No presenta declaraciones ni reemplaza la validación profesional.

## Índice

[Problema](#problema) · [Funcionalidades](#funcionalidades) · [Demo](#demo) · [Uso](#instalación-y-uso) · [Web](#interfaz-web-en-desarrollo) · [Flujo](#flujo) · [Diseño](#decisiones-de-diseño) · [Limitaciones](#limitaciones-y-próximos-pasos) · [Desarrollo](#desarrollo)

## Problema

Un estudio contable recibe archivos de varios clientes y necesita revisar comprobantes antes de consolidar cada período. El programa valida filas, conserva las aceptadas y reúne las observadas con el motivo.

## Funcionalidades

### Importación y validación
- Procesa ventas y compras; valida CUIT, período, tipo, alícuotas, importes y duplicados.
- Reconoce alias de encabezados, usa el `tipo_cambio` informado en el archivo y conserva el desglose de varias alícuotas por comprobante cuando viene en el origen.

### Informes
- Produce hojas de comprobantes, detalle de IVA, resúmenes por cliente y alícuota y observaciones.
- Conserva historial por cliente y período. [Ver libro de ejemplo](ejemplos/salida.xlsx).

![Resumen de ejemplo generado en Excel](docs/images/reporte-demo.png)

### Integraciones
- Importa archivos estándar, exportaciones de Mis Comprobantes ARCA y plantillas Holistor.
- Sugiere coincidencias para extractos bancarios y consulta vencimientos por terminación de CUIT en un calendario cargado por el usuario.

### Interfaces
- CLI instalable, interfaz Streamlit local y demo con datos sintéticos sin carga de archivos.

## Demo

**Demo en vivo:** [Abrir la aplicación](https://automatizador-reportes-kqvtruqnyz7gwzj47ex7is.streamlit.app/)

Ejecución local en PowerShell, macOS o Linux:
```bash
streamlit run demo.py
```
Guía de [configuración y despliegue](docs/demo-streamlit.md).

## Instalación y uso

Requiere Python 3.11 o posterior. PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
automatizador --period 2026-09
```
Opcional en PowerShell: si `Activate.ps1` está bloqueado, ejecutá `Set-ExecutionPolicy -Scope Process Bypass` antes de activar el entorno; el cambio dura solo esa sesión.

macOS o Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
automatizador --period 2026-09
```
Sin `--input`, la CLI usa `ejemplos/Cliente Demo Norte.xlsx`; genera `reporte_iva.xlsx` y `comprobantes.db` en el directorio actual. `--period` es obligatorio.

Para procesar una carpeta con rutas explícitas, PowerShell:
```powershell
automatizador-demo
automatizador `
  --input datos_demo `
  --output resultados/reporte.xlsx `
  --database resultados/comprobantes.db `
  --period 2026-09
```
macOS o Linux:
```bash
automatizador-demo
automatizador \
  --input datos_demo \
  --output resultados/reporte.xlsx \
  --database resultados/comprobantes.db \
  --period 2026-09
```
`automatizador-demo` crea dos archivos sintéticos en `datos_demo/`.

Más detalles de [adaptadores ARCA/Holistor](docs/adaptadores.md).

## Interfaz web (en desarrollo)

La capa opcional de Django incluye modelos, migraciones y un repositorio de comprobantes. Todavía no tiene pantallas. Para instalar sus dependencias desde la raíz del repositorio:

```bash
python -m pip install -e ".[web]"
```

## Migración de la base

Al abrir una base SQLite anterior, el programa migra su esquema y crea un respaldo `.v0.bak.db`, `.v1.bak.db` o `.v2.bak.db`, según la versión de origen, antes de hacerlo. La CLI y la interfaz local muestran la ruta del respaldo; conservá esa copia hasta revisar los informes generados. La migración a v3 registra en el historial las operaciones que todavía pueden identificarse por sus comprobantes; las importaciones antiguas sin comprobantes asociados quedan con la operación vacía.

## Flujo

```mermaid
flowchart LR
    A[Excel / CSV / PRN] --> B[Adaptador y normalización]
    B --> C[Validación por comprobante]
    C -->|Aceptado| D[Comprobantes válidos]
    C -->|Observado con motivo| E[Observaciones]
    D -->|CLI o confirmar en Streamlit| F[SQLite por cliente, período y operación]
    E --> G[Informe Excel]
    F --> G
```

## Decisiones de diseño
- Usa `Decimal` para redondear a dos decimales y guarda importes en SQLite como centavos enteros.
- Reimportar reemplaza solo las operaciones con filas aceptadas del mismo cliente y período, dentro de una transacción; conserva las demás operaciones, otros períodos y el historial. Si dos archivos del mismo lote compiten por una operación, ninguno de ellos se aplica y se informa el conflicto. Un archivo sin filas aceptadas no reemplaza comprobantes.
- Las filas rechazadas quedan observadas con el motivo, sin abortar el lote completo.
- Las observaciones vigentes de cada operación incluyen las de su última importación aplicada (con filas aceptadas) y las de intentos posteriores no aplicados; una nueva aplicación reemplaza ese conjunto. Las observaciones sin operación identificable siguen vigentes hasta la siguiente aplicación del cliente y período. El historial indica si cada intento se aplicó, entró en conflicto o no tuvo filas aceptadas.
- Para moneda extranjera usa el `tipo_cambio` informado en el archivo; no consulta una cotización externa.

## Limitaciones y próximos pasos
- No hay conexión directa a ARCA ni Holistor; detalles en [adaptadores](docs/adaptadores.md).
- La [conciliación](docs/conciliacion.md) sugiere coincidencias para revisión; la [agenda](docs/vencimientos.md) requiere mantener un calendario.
- La demo usa el ejemplo sintético y oculta la carga de archivos.
- Próximos pasos: ampliar fixtures sintéticos para distintas variantes de ARCA/Holistor y preparar un ejecutable de Windows con PyInstaller.

## Desarrollo

Instalación y controles de calidad, desde la raíz del repo:
```bash
python -m pip install -e ".[dev,web]"
ruff check .
coverage run -m unittest discover -s tests -v
coverage report -m
```
GitHub Actions ejecuta los controles en Linux y Windows.

## Estructura

```text
automatizador/                  Paquete: lógica, CLI, adaptadores e interfaz
web/                            Proyecto Django opcional: modelos y repositorio
tests/                          Pruebas por módulo
tests/fixtures/arca/            CSV sintético de Mis Comprobantes
ejemplos/                       Entradas, salida y calendario sintéticos
datos_demo/                     Archivos sintéticos de demostración
docs/                           Guías técnicas e imágenes
demo.py                         Entrada Streamlit de la demo pública
main.py                         Entrada de compatibilidad para la CLI
interfaz.py                     Entrada de compatibilidad para Streamlit
generar_datos_demo.py           Generador de ejemplos sintéticos
holistor_mapping.example.json   Mapeo de referencia para Holistor
pyproject.toml                  Metadatos, dependencias y comandos
CHANGELOG.md                    Historial de versiones
LICENSE                         Licencia MIT
```

## Datos y privacidad

Los ejemplos incluidos son sintéticos. `.gitignore` excluye `*.db`, `reporte_*.xlsx` y los directorios `datos/` y `resultados/`, usados para entradas y salidas locales.

## Licencia

Distribuido bajo la [licencia MIT](LICENSE). [Cambios por versión](CHANGELOG.md).
