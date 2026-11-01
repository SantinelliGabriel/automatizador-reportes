# Libros sintéticos de referencia

Generados antes de modificar el exportador, con el código productivo de `a87ad4d` y los casos de `tests/test_exportador_excel.py`, pandas 3.0.6 y openpyxl 3.1.5.

- `contable.xlsx`: facturas, NC/ND, compras y ventas, cotización extranjera, varias alícuotas y observaciones con prefijos de fórmula.
- `vacio.xlsx`: las cinco hojas sin comprobantes.
- `limites.xlsx`: prefijos de fórmula en todas las hojas, vacíos, Unicode, fechas, valores numéricos de alta precisión y límites de ancho.

No contienen datos de clientes reales. No se deben regenerar automáticamente con el exportador nuevo: son el oráculo de regresión de contenido, tipos y presentación. Las fechas automáticas de creación/modificación y el ZIP binario no se comparan; varían entre ejecuciones.

La generación original se hizo con el script descartable `.test_tmp/crear_golden.py`,
que invocaba `generar_caso` para estos tres casos antes de modificar producción.
Para regenerarlos **a propósito**, revisar primero el cambio del oráculo y ejecutar:

```bash
python tests/fixtures/excel/regenerar.py --confirmar
```

`regenerar.py` carga desde Git los dos componentes originales de `a87ad4d`
en memoria y usa los mismos casos, sin cambiar archivos productivos ni el checkout.
Requiere ese objeto Git y las dependencias fijadas en `pyproject.toml`.
No ejecutar para hacer pasar una regresión del exportador optimizado.
