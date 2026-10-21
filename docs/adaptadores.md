# Adaptadores de archivos

El importador acepta Excel, CSV, TXT y PRN. `automatizador.adaptadores.leer_comprobantes` convierte las fuentes a columnas comunes; `automatizador.validaciones.validar_comprobantes` aplica las reglas contables después de la lectura.

## Excel y CSV estándar

Los encabezados se normalizan ignorando acentos, mayúsculas, espacios y signos de puntuación. Se aceptan los alias declarados en `automatizador/validaciones.py`. Si dos columnas se convierten en el mismo nombre canónico, el archivo se observa como ambiguo.

La CLI usa el formato estándar por defecto. Para importar un archivo o una carpeta:

```powershell
automatizador --input ejemplos/Cliente Demo Norte.xlsx --period 2026-09
```

## Mis Comprobantes ARCA

Indicá el formato y el libro asociado a la descarga:

```powershell
automatizador --input compras.csv --source arca --operation compras --period 2026-09
```

En macOS o Linux se usa el mismo comando. Para continuarlo en varias líneas, terminá cada línea intermedia con `\`.

El adaptador reconoce códigos y nombres de tipos de comprobante, punto de venta, numeración, CUIT, razón social, importes, moneda y tipo de cambio. Si el archivo tiene netos e IVA desglosados por tasa, conserva el detalle. Si agrupa números, agrupa otros tributos sin separarlos, o no permite reconstruir el desglose, agrega una observación para revisión. No se conecta a ARCA ni descarga cotizaciones.

## Holistor

Holistor permite configurar la correspondencia entre encabezados de la plantilla local y columnas canónicas. El ejemplo editable está en [`holistor_mapping.example.json`](../holistor_mapping.example.json). Se pasa mediante `--mapping`:

```powershell
automatizador --input compras.xlsx --source holistor --operation compras --mapping holistor_mapping.example.json --period 2026-09
```

Para archivos `.prn`, el JSON también debe declarar `anchos_prn` y `columnas_prn`, con un ancho y un nombre para cada campo. No existe un ancho fijo común a todas las instalaciones. Las hojas Excel se leen desde la hoja de comprobantes emitidos cuando está disponible; si no, se intenta la primera hoja.

## Moneda extranjera

El tipo de cambio debe venir informado en `tipo_cambio` o en el encabezado equivalente. Para ARCA se lee el campo de cotización exportado; en archivos estándar/Holistor se mapea desde la plantilla. El sistema no consulta una cotización de mercado ni el servicio de ARCA. Se conserva la moneda, la cotización y los importes de origen, y se convierten a ARS para los informes.

## Errores de lectura y validación

Los errores de lectura que detecta el flujo de procesamiento quedan en `Observaciones` con el nombre del archivo. Los errores por fila guardan su número y motivo; una fila observada no se inserta en SQLite.
