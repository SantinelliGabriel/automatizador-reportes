# Changelog

Los cambios relevantes de cada versión se registran en este archivo.

## [Unreleased]

## [0.1.1] - 2026-10-21

### Added

- Conversión opcional de importes en moneda extranjera a ARS usando el tipo de cambio informado en el archivo, conservando los importes de origen.
- Modo demo de Streamlit con datos sintéticos y sin controles de carga de archivos.
- Vista previa y confirmación de importaciones antes de modificar la base SQLite.
- Conciliación bancaria con referencias, detección de coincidencias ambiguas y posibles pagos agrupados para revisión.
- Detalle de IVA con varias alícuotas por comprobante y conversión de importes de origen a ARS.
- Ampliación de pruebas para adaptadores, conciliación, vencimientos, interfaz y validaciones.
- Documentación técnica separada para adaptadores, conciliación, vencimientos y demo.
- Recorrido animado de la demo que muestra el resumen de Streamlit y el informe Excel sintético.

## [0.1.0] - 2026-10-20

### Added

- Paquete instalable con comandos de consola, importación de comprobantes, persistencia SQLite e informes Excel.
- Validación de CUIT, período, importes, alícuotas y duplicados, con observaciones por fila.
- Integración inicial de CI para Linux y Windows y pruebas automatizadas.
