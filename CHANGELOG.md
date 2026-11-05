# Changelog

Los cambios relevantes de cada versión se registran en este archivo.

## Sin publicar

- Rechaza identificadores fraccionarios de comprobantes y puntos de venta.
- Conserva el número de fila del archivo original en las observaciones por conflictos de lote.

## [0.2.0] - 2026-11-02

- Migración SQLite al esquema v3 con respaldo previo según la versión de origen.
- Reemplazo por cliente, período y operación; ventas y compras coexisten y los conflictos de lote no se aplican.
- Observaciones persistidas y vigentes desde la última importación aplicada, con intentos posteriores e historial con estado.
- Clave de cliente compartida con normalización Unicode, espacios y mayúsculas, conservando el nombre visible.
- Contrato de persistencia con repositorios SQLite y Django; importes en centavos y decimales canónicos, confirmación separada del informe.
- Web Django local con login, clientes, carga segura, vista previa temporal de un solo uso, historial y observaciones.
- Descarga del informe Excel consolidado por período para todos los clientes y modo demo local con datos sintéticos de solo lectura.
- Diseño web adaptable, modo oscuro y mejoras de accesibilidad: foco visible, etiquetas y estados con texto.
- Los textos con prefijos de fórmula se escriben como texto literal en todas las hojas del informe Excel.
- Documentación reorganizada, README en español e inglés, guías técnicas y comprobación automática de enlaces e imágenes.
- Exportador Excel con un solo guardado, conservando las cinco hojas y su presentación; regresiones y mediciones de rendimiento.
- Wheel limitado a los ejemplos sintéticos usados en ejecución, sin el informe de muestra; incluye plantillas y estáticos web.

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
