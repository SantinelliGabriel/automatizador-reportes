# Automatizador de comprobantes e informes de IVA

[![CI](https://github.com/SantinelliGabriel/automatizador-reportes/actions/workflows/tests.yml/badge.svg)](https://github.com/SantinelliGabriel/automatizador-reportes/actions/workflows/tests.yml)
[![Cobertura](https://img.shields.io/codecov/c/github/SantinelliGabriel/automatizador-reportes/main?logo=codecov)](https://codecov.io/gh/SantinelliGabriel/automatizador-reportes)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)

Herramienta en Python con pandas para importar comprobantes de ventas y compras, revisar inconsistencias, guardar cargas por cliente y período en SQLite y generar informes en Excel. Incluye una interfaz local con Streamlit.

> Proyecto de portfolio y apoyo a la revisión. No presenta declaraciones ni reemplaza la validación profesional de la información.

## Problema que resuelve

Un estudio contable recibe archivos de varios clientes y necesita revisar comprobantes antes de consolidar la información mensual. La herramienta valida cada fila, conserva los comprobantes aceptados y reúne las filas observadas con su motivo para facilitar la revisión y la corrección.

## Funcionalidades

- Importa comprobantes de ventas y compras con fecha, tipo, punto de venta, número, CUIT, razón social, neto gravado, alícuota, IVA, importes no gravados o exentos, percepciones y total.
- Acepta alias de encabezados en español e inglés, ignorando mayúsculas, acentos, espacios y guiones.
- Valida CUIT, tipos de comprobante, alícuotas, fechas del período, conciliación de importes y duplicados.
- Exporta las filas observadas a la hoja `Observaciones`, con número de fila y motivo.
- Procesa un archivo por cliente y reemplaza solo la combinación de cliente y período importada; conserva los demás períodos.
- Guarda comprobantes e historial de importaciones en SQLite.
- Genera las hojas `Comprobantes`, `Resumen por cliente`, `IVA por alícuota` y `Observaciones`.
- Incluye adaptadores para Excel/CSV estándar, descargas de Mis Comprobantes ARCA y plantillas Holistor con mapeo editable.
- Concilia movimientos bancarios firmados con comprobantes por importe y fecha, asignando cada movimiento una sola vez.
- Consulta vencimientos por CUIT a partir de un calendario oficial cargado por el usuario.
- Ofrece una interfaz local en Streamlit para importar, conciliar y consultar vencimientos.
- Incluye datos sintéticos de ejemplo y pruebas para validaciones, persistencia, reportes e importación.

Las alícuotas admitidas incluyen 0 %, 2,5 %, 5 %, 10,5 %, 21 % y 27 %, según la tabla de [ARCA para Libro IVA Digital](https://arca.gob.ar/libro-iva-digital/documentos/Libro-IVA-Digital-Tablas-del-Sistema.pdf). La inclusión en la tabla no determina qué tasa corresponde a cada operación.

## Informe de ejemplo

El libro completo se puede abrir en [ejemplos/salida.xlsx](ejemplos/salida.xlsx). La captura muestra el resumen por cliente generado a partir de datos ficticios:

![Captura del resumen generado en Excel](docs/images/reporte-demo.png)

Los archivos de muestra están en `ejemplos/`. Para generar dos archivos de cliente con datos sintéticos:

```powershell
automatizador-demo
```

Los CUIT de demostración tienen dígito de control calculado, pero son sintéticos; no se debe inferir que estén libres de asignación en registros reales.

## Instalación

Requiere Python 3.11 o posterior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

La instalación editable registra el comando `automatizador` y sus dependencias. `requirements.txt` también instala el paquete editable para quienes ya usan ese flujo.

## Uso

Importá el archivo de ejemplo para septiembre de 2026:

```powershell
automatizador --period 2026-09
```

El comando usa por defecto `ejemplos/Cliente Demo Norte.xlsx`, guarda la base local en `comprobantes.db` y genera `reporte_iva.xlsx`.

Para indicar otras rutas o procesar una carpeta con un archivo por cliente:

```powershell
automatizador `
  --input datos/clientes `
  --output resultados/reporte.xlsx `
  --database resultados/comprobantes.db `
  --period 2026-09
```

También se puede ejecutar desde el checkout sin instalar el comando:

```powershell
python main.py --period 2026-09
```

Consultá el historial de cargas con:

```powershell
automatizador --history
```

### Adaptadores ARCA y Holistor

Para una descarga de `Mis Comprobantes`, indicá el formato de origen y si se trata de emitidos o recibidos:

```powershell
automatizador --input compras.csv --source arca --operation compras --period 2026-09
```

Si una descarga agrupa varias alícuotas o no permite separar moneda, percepciones y otros tributos de forma inequívoca, la fila queda observada para revisión en el comprobante fuente.

Holistor distribuye modelos vinculados a sus productos y versiones. El adaptador acepta Excel/CSV con encabezados mapeables y archivos `.prn` configurados con JSON. La [guía de Holistor](https://soporte.holistor.com.ar/portal/es/kb/articles/iva-importacion-de-mis-comprobantes-emitidos) describe modelos para cargar datos exportados desde ARCA; no se presupone un ancho fijo universal. La configuración de ejemplo está en `holistor_mapping.example.json`.

### Conciliación bancaria

En la interfaz local, seleccioná las columnas de fecha e importe de un extracto CSV/Excel. Los importes deben venir firmados: créditos positivos para ventas y débitos negativos para compras. El margen de días y la tolerancia de importe son configurables.

### Vencimientos

La agenda espera un calendario CSV/Excel con `impuesto`, `periodo`, `terminacion_cuit` y `fecha_vencimiento`, y un archivo de clientes con `cliente` y `cuit`. El calendario incluido es un ejemplo para octubre de 2026. Cargá el calendario oficial vigente cada mes porque las fechas pueden cambiar.

### Interfaz local

```powershell
streamlit run automatizador/interfaz.py
```

También sigue disponible el comando anterior `python -m streamlit run interfaz.py`. La aplicación guarda los datos localmente en la base SQLite indicada.

## Desarrollo

Instalá las herramientas de desarrollo, ejecutá Ruff y los tests con cobertura:

```powershell
python -m pip install -e ".[dev]"
ruff check .
coverage run -m unittest discover -s tests -v
coverage report -m
```

El workflow de GitHub Actions ejecuta Ruff y las pruebas en Linux y Windows con Python 3.11 y envía el reporte de cobertura de Linux a Codecov.

## Estructura

```text
automatizador/       Lógica del paquete, CLI, adaptadores e interfaz
tests/               Pruebas separadas por validación, base, reportes y proceso
ejemplos/            Entrada, salida y calendario sintéticos
docs/images/         Captura del informe de ejemplo para el README
```

`automatizador.procesamiento.procesar(entrada, salida, base, periodo)` expone el caso de uso fuera de la CLI. Devuelve una instancia de `ResultadoProcesamiento` con comprobantes, filas observadas, cantidades, totales y ruta del informe, lista para reutilizar desde Streamlit u otras interfaces.

## Licencia

Este proyecto se distribuye bajo la licencia [MIT](LICENSE).

## Datos y privacidad

No incluyas CUIT, razones sociales, comprobantes ni importes reales en el repositorio. Los archivos de `ejemplos/` y `datos_demo/` contienen datos sintéticos. Las bases SQLite y los reportes generados quedan excluidos por `.gitignore`.
