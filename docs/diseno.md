# Decisiones de diseño

## Dinero y decimales

Los importes persistidos usan centavos enteros (INTEGER en SQLite, BigIntegerField en Django). Las operaciones y los resúmenes usan `Decimal`; la conversión a ARS aplica `ROUND_HALF_UP` a dos decimales mediante `convertir_a_ars`. El tipo de cambio viene del archivo; no se consulta una cotización externa. Se conservan moneda, cotización e importes de origen.

Alícuota y tipo de cambio se almacenan como texto decimal canónico, sin exponente ni ceros finales innecesarios. `normalizar_decimal` es compartida por el núcleo y `TextoDecimalField`. Las escalas máximas son uno y ocho decimales, respectivamente; los excesos de escala se observan sin redondeo silencioso. Los valores se leen como Decimal para operar, sin sumar ni ordenar el texto numérico en SQL.

## Alcance del reemplazo

Una importación con filas aceptadas reemplaza solamente el mismo cliente, período y las operaciones presentes en esas filas. Ventas y compras pueden coexistir. Las demás operaciones, períodos e historial se conservan. Sin filas aceptadas no se reemplazan comprobantes.

Si dos archivos del mismo lote compiten por cliente, período y operación, ninguno se aplica; se informa el conflicto y los demás archivos continúan. El guardado usa transacciones con rollback. La clave de cliente usa NFC, espacios normalizados y casefold sin eliminar acentos; se conserva el nombre para mostrarlo.

## Filas observadas e historial

Las filas inválidas guardan número y motivo para revisión. Los errores de lectura también se registran; los rechazos no se insertan como comprobantes aceptados. El historial deriva el estado: aplicada, no aplicada por conflicto, o sin filas aceptadas.

Para cada cliente, período y operación, las observaciones vigentes son las de la última importación aplicada (`aceptados > 0`) y todos los intentos posteriores no aplicados. Una nueva aplicación sustituye ese conjunto. Sin ninguna aplicación se muestran todos los intentos. Las observaciones sin operación identificable permanecen hasta la siguiente aplicación de ese cliente y período. `vigencia.py` contiene esta regla compartida.

## Persistencia e informes

El contrato tiene implementaciones SQLite y Django, con reglas de lote compartidas. Confirmar guarda datos; generar el informe es una operación separada que consulta el repositorio. Las cinco hojas son Comprobantes, Detalle IVA, Resumen por cliente, IVA por alícuota y Observaciones. El historial se consulta por las interfaces, no como hoja del Excel. NC y ND ajustan los totales; las celdas de texto con prefijos de fórmula se escriben como texto literal.

![Resumen Excel sintético](images/reporte-demo.png)

## Vista previa web

Se guarda un archivo privado con nombre aleatorio y vencimiento de 30 minutos. La sesión referencia una firma que vincula usuario, sesión, hash del archivo, opciones y plan revisado. El token es de un solo uso; las versiones de las operaciones se comprueban dentro de la transacción para evitar confirmar una revisión desactualizada. Un candado evita confirmar dos veces el mismo archivo. Los originales y los informes no se conservan como archivo permanente: el informe se regenera para descargarlo.

## Límites y próximos pasos

Los adaptadores importan archivos; no se conectan a ARCA ni Holistor. La conciliación sugiere coincidencias y los vencimientos requieren un calendario aportado por el usuario. La demo sintética oculta la carga. Ampliar fixtures de variantes ARCA/Holistor y preparar un ejecutable Windows con PyInstaller son posibles pasos posteriores, todavía no implementados.

[Volver al README](../README.md)
