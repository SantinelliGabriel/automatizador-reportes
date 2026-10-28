# Changelog

Los cambios relevantes de cada versión se registran en este archivo.

## [Unreleased]

- La web Django incorpora historial, observaciones vigentes y descarga de informes consolidados por período.
- El modo demo local reconstruye una base con ejemplos sintéticos y ofrece acceso de solo lectura.

- La interfaz local de Django permite login, alta de clientes, vista previa y confirmación de importaciones; los archivos de vista previa vencen a los 30 minutos.
- Las cargas web limitan tamaño y estructura de archivos, y los Excel se leen en modo de solo lectura.
- Los textos que comienzan con `=`, `+`, `-` o `@` se escriben como texto literal en las hojas Excel de todos los informes.
- La capa opcional de Django incluye modelos, migraciones y repositorio; la CLI y Streamlit siguen usando el núcleo. La identidad de clientes se normaliza antes de guardar, y ambos repositorios generan el mismo informe.
- El reemplazo de comprobantes se limita a cliente, período y operaciones con filas aceptadas; ventas y compras pueden coexistir.
- Los archivos de un mismo lote que compiten por una operación quedan observados; el resto del lote continúa.
- El historial registra operaciones y las observaciones vigentes se consultan por operación.
- Las observaciones vigentes parten de la última importación aplicada de cada operación e incluyen intentos posteriores no aplicados; las de operación desconocida se conservan hasta la siguiente aplicación del cliente y período. El historial muestra un estado derivado, también en CLI y Streamlit.
- La migración de SQLite a la versión 3 crea un respaldo `.v2.bak.db` antes de agregar operaciones al historial.
- La confirmación guarda comprobantes y la generación del informe se ejecuta por separado.
- Las filas observadas se persisten junto con el historial de importaciones.
- La alícuota y el tipo de cambio se guardan como texto decimal canónico.
- La migración de SQLite a la versión 2 crea un respaldo antes de convertir esos campos.

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
