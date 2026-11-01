# Migración de la base SQLite

Al abrir una base anterior del núcleo, se consulta `PRAGMA user_version`. Si ya contiene tablas, se crea un respaldo antes de cualquier migración: `.v0.bak.db`, `.v1.bak.db` o `.v2.bak.db`, según la versión real de origen. Un respaldo existente no se sobrescribe silenciosamente. Una base nueva vacía no genera respaldo ni aviso de migración.

La CLI y Streamlit informan la migración y la ruta del respaldo. Conviene conservarlo hasta revisar los informes. Las versiones futuras no soportadas se rechazan sin modificar la base. Cada salto de versión se ejecuta en su propia transacción: si falla, vuelve atrás ese salto; los pasos anteriores ya confirmados permanecen.

## Versiones

- v1 incorpora observaciones persistidas.
- v2 convierte alícuota y tipo de cambio a texto decimal canónico, sin recalcular los importes en centavos. Señala para revisión valores con más de quince cifras significativas o diferencias entre conversión de origen y ARS guardado; esas señales aparecen en las observaciones del informe.
- v3 incorpora operaciones al historial. Se rellenan desde los comprobantes que todavía están asociados a cada importación; si no se pueden identificar, el texto queda vacío.

Esta migración corresponde a `comprobantes.db` y al repositorio SQLite del núcleo. La web Django usa su propio mecanismo: `python web/manage.py migrate`; no convierte automáticamente una base del núcleo a modelos Django.

[Volver al README](../README.md)
