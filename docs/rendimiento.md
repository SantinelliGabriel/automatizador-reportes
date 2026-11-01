# Rendimiento del exportador Excel

## Cambio y comprobación

`generar_informe()` aplica el formato sobre `ExcelWriter.book` antes de cerrar
el writer: una serialización, sin reabrir el XLSX. Se conserva la entrada
`aplicar_formato_excel(ruta)` para libros existentes. No cambian contabilidad,
validaciones, SQLite ni observaciones vigentes.

Los fixtures de `tests/fixtures/excel/` se generaron con `a87ad4d` antes del
cambio; sus módulos productivos son idénticos a los de `main` en `e7d0eda`.
La regresión compara cinco hojas, valores, tipos de celda, estilos, anchos,
filtros, paneles inmovilizados y propiedades de libro/impresión. Otro test
exige un solo guardado y ninguna reapertura. Fechas automáticas y bytes ZIP
no son parte de la equivalencia. Los prefijos de fórmula siguen siendo texto.

## Método

Tres pares por tamaño, en procesos y directorios temporales nuevos, alternando
exportador anterior y nuevo. El código anterior se cargó desde Git (`a87ad4d`)
en memoria; no se cambió el checkout. La selección de pares siguió el orden
de lanzamiento, sin elegir por rendimiento. Se conservaron cuatro pilotos
sin control contemporáneo, excluidos de las medianas pareadas.

Diez clientes sintéticos; N aceptados y 1 % adicional observado, ventas/compras,
NC/ND, moneda extranjera y varias alícuotas. Se prepararon dos importaciones
previas por cliente. El tiempo total mide `procesar()`, sin preparación ni
limpieza; Excel exclusivo descuenta sus consultas. La memoria es el máximo
residente del proceso, incluyendo librerías y preparación, medido en Windows.

## Medianas pareadas (tres muestras)

| Comprobantes | Total antes → después (s) | Reducción | Excel antes → después (s) | Reducción | RAM antes → después (MiB) | Reducción |
| ---: | --- | ---: | --- | ---: | --- | ---: |
| 10.000 | 38,497 → 26,304 | 31,7 % | 28,893 → 17,579 | 39,2 % | 450,5 → 326,2 | 27,6 % |
| 50.000 | 186,198 → 134,681 | 27,7 % | 140,427 → 89,094 | 36,6 % | 1.861,1 → 1.236,3 | 33,6 % |
| 100.000 | 351,463 → 257,473 | 26,7 % | 268,433 → 168,190 | 37,3 % | 3.626,0 → 2.374,2 | 34,5 % |

Reducción = `100 × (antes − después) / antes`; las medianas de etapas se
calculan por separado. Totales individuales antes/después, en segundos:

- 10.000: 37,741; 38,575; 38,497 / 26,304; 26,151; 27,202.
- 50.000: 186,198; 185,037; 193,929 / 134,681; 122,145; 140,036.
- 100.000: 382,402; 286,692; 351,463 / 274,697; 242,182; 257,473.

La auditoría histórica había medido totales de 22,424 / 129,300 / 244,682 s.
Frente a esa referencia, los nuevos totales son 17,3 / 4,2 / 5,2 % mayores.
El exportador anterior repetido ahora también fue más lento, incluso en
validación sin cambios. Por eso se usa el control contemporáneo para estimar
el efecto y no se atribuye la variación histórica al cambio del exportador.
Los pilotos nuevos: 10.000 en 29,919 / 27,157 / 28,159 s; 50.000 en 125,620 s.

## Descarga web local (2026-11-01)

HTTP real en `127.0.0.1`, modo demo, usuario no staff, SQLite temporal con
10 clientes, 10 importaciones, 10.000 comprobantes y 100 observaciones.
Se reutilizó el generador sintético del benchmark. Tres GET autenticados
con cookies, desde la petición hasta recibir el cuerpo completo:
**20,599 / 19,492 / 19,523 s; mediana 19,523 s**. Preparación/login excluidos.
HTTP 200, cinco hojas y 10.000 filas de comprobantes, 1.664.464 bytes;
`Cache-Control: no-store` y nombre `informe_consolidado_2026-09.xlsx`.
Se usó WSGI local con `DEBUG=True` para permitir HTTP, sin proxy/TLS ni
concurrencia. No es una prueba de producción ni una comparación web antes/después.
El servidor se detuvo y se eliminaron la base, entradas y archivos temporales.

## Límites de la medición

Windows 11, Python 3.12.14, Ryzen 7 5700, 31,79 GiB RAM; pandas 3.0.6,
openpyxl 3.1.5, NumPy 2.5.4, lxml 6.1.1 y SQLite 3.53.1. Tres muestras por
escenario, sin afinidad/frecuencia de CPU ni actividad del equipo controladas.
No son un SLA ni una estimación estadística universal. La ruta XML alternativa
se comprueba mediante tests con `OPENPYXL_LXML=False`, no mediante benchmark.
No hubo revisión visual manual en Microsoft Excel o LibreOffice. Las
propiedades visuales se comparan automáticamente con openpyxl.

Las métricas e instrumental originales quedan locales en `.test_tmp/`,
excluido de Git. No se publica el benchmark actual: su contador de memoria
es exclusivo de Windows. Una versión futura portable puede medir tiempos
con `perf_counter` en procesos separados y documentar la memoria aparte.

## Uso recomendado

Se recomienda conservar el guardado único: reduce tiempo y memoria en los
controles pareados y mantiene las propiedades comparadas. Para trabajo
interactivo, se propone un máximo práctico de **10.000 comprobantes por
informe consolidado**, contando todos los clientes del período; no es un
límite implementado por esta optimización. El límite de carga web por archivo
no limita el total acumulado del período.

Para informes mayores, usar la CLI local con memoria disponible y dividir
períodos cuando el caso de uso lo permita. Con 100.000, el núcleo SQLite
midió unos 257 s y 2,32 GiB de pico aun después del cambio. No extrapolar
esos valores a Django ni aumentar concurrencia sin medirla.

Mensaje propuesto, sin cambiar la web: «El período supera los 10.000
comprobantes recomendados para descarga interactiva. La generación puede
tardar y consumir memoria; utilizar la CLI local para este volumen».
