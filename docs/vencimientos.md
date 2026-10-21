# Agenda de vencimientos

La interfaz local cruza clientes con un calendario CSV o Excel que aporta el usuario. La agenda no consulta ni actualiza fechas oficiales en línea.

## Archivos de entrada

El calendario requiere estas columnas:

| Columna | Contenido |
| --- | --- |
| `impuesto` | Obligación que vence |
| `periodo` | Período fiscal asociado |
| `terminacion_cuit` | Dígito final, lista, rango o grupo `TODAS`/`TODOS`/`*` |
| `fecha_vencimiento` | Fecha de vencimiento |

Se aceptan encabezados equivalentes como `obligacion`, `tributo`, `terminacion`, `vencimiento`, `fecha` y `periodofiscal` (sin espacio). El archivo de clientes debe incluir `cliente` y `cuit`; para la agenda se comprueba que el CUIT tenga once dígitos y se usa su último dígito.

## Cálculo

La interfaz permite elegir el plazo en días. Se incluyen las fechas desde el día de consulta hasta el límite del plazo, ambos inclusive, y se ordenan por fecha y cliente. Un calendario con una fecha no interpretable se rechaza para evitar mostrar una agenda incompleta.

El archivo `ejemplos/vencimientos_iva_2026_10.csv` es una muestra sintética, no un calendario oficial. Reemplazalo por el calendario vigente antes de usar la agenda.
