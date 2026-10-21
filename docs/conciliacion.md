# Conciliación bancaria

La conciliación compara un extracto CSV/Excel con los comprobantes del período elegido en la interfaz local. No mueve fondos ni cambia el estado contable de los comprobantes.

## Archivo bancario

El extracto debe incluir columnas de fecha e importe, que se seleccionan en la interfaz. La descripción es opcional y puede ayudar a identificar referencias que incluyan punto de venta y número. Los importes deben venir firmados: cobros positivos para ventas y pagos negativos para compras.

El usuario puede ajustar la tolerancia de fechas y de importes. El sistema compara el signo, el importe esperado y la distancia entre fechas. En notas de crédito invierte el signo del comprobante. Para compras también espera el signo inverso al de ventas.

## Estados y revisión

- `Conciliado`: hay una coincidencia única para movimiento y comprobante.
- `Coincidencia ambigua`: hay más de un candidato igualmente válido; quedan listados para revisión.
- `Referencia detectada; revisar diferencia`: se reconoció el comprobante, pero importe o fecha no están dentro de tolerancia.
- `Posible pago parcial`, `agrupado` o `fraccionado`: son sugerencias por importe y referencias. No concilian automáticamente los comprobantes.
- `Sin coincidencia`: no se encontró candidato según los criterios configurados.

El archivo exportado incluye `Extracto bancario`, `Comprobantes`, `Pendientes banco` y `Pendientes comprobantes`. Los estados sirven para revisar; no reemplazan una conciliación aprobada por una persona.
