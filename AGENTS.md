# Instrucciones para agentes

## Proyecto
Automatizador de comprobantes e informes de IVA (Python 3.11+, pandas,
SQLite, Streamlit). Es un proyecto de portfolio pensado para estudios
contables de Argentina.

## Reglas
1. Datos: usá solo datos sintéticos. Nunca CUIT, razones sociales,
   comprobantes ni importes reales, ni en tests, ejemplos, capturas o
   commits. Si una tarea requiere datos reales, frená y preguntá.
2. Documentación: no escribas en README ni en docs/ nada que no hayas
   verificado en el código. Si encontrás una discrepancia entre documentación
   y código, reportala; no la arregles en silencio.
3. README público: sin notas internas, TODOs ni frases de trabajo. Escribí
   para un lector externo (reclutador o contador).
4. Antes de cada commit corré `ruff check .` y
   `coverage run -m unittest discover -s tests -v`. Si algo falla, no
   commitees.
5. Commits chicos, un tema por commit, mensajes claros en español.
6. En tareas de documentación no cambies el comportamiento del código.
7. Todo cambio de comportamiento lleva tests.
8. Importes de dinero: Decimal o centavos enteros, nunca float.
9. El código debe funcionar en Windows y Linux (el CI corre en ambos). Usá
   pathlib y evitá rutas absolutas.
10. No hagas push, tags ni releases salvo que se pida explícitamente.
11. No afirmes cumplimiento normativo ni formatos de registro de ARCA que no
    estén verificados en fuentes oficiales. La herramienta apoya la revisión
    y no reemplaza la validación profesional.
12. Respondé de forma explícita cada pregunta de la tarea. Si no pudiste
    hacer o verificar algo, decilo; no des por hecho que algo existe sin
    comprobarlo.

## Cierre de cada tarea
Entregá: resumen de lo que cambiaste, resultado de ruff y de los tests,
`git diff --stat` y una lista de lo que no pudiste verificar.
