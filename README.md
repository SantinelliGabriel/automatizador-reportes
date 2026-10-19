# Automatizador de reportes de ventas

Proyecto desarrollado en Python para procesar datos de ventas desde Excel, validar la información, almacenarla en una base de datos SQLite y generar reportes de ventas con formato profesional.

## Tecnologías

- Python 3.11
- pandas
- openpyxl
- SQLite
- Excel (.xlsx)
- unittest
- logging

## Funcionalidades

- Lectura de datos desde archivos Excel.
- Validación de columnas requeridas, valores numéricos y datos obligatorios.
- Almacenamiento de ventas en una base de datos SQLite.
- Consultas SQL para obtener los subtotales por producto.
- Cálculo de la facturación total.
- Prevención de duplicados al actualizar los registros desde el Excel de entrada.
- Generación de reportes Excel con formato profesional.
- Ajuste automático del ancho de las columnas.
- Formato de encabezados y fila de total general.
- Manejo de errores de lectura, validación y escritura.
- Registro de eventos y errores mediante `logging`.
- Pruebas automatizadas para validaciones, base de datos, formato Excel y generación completa del reporte.

## Estructura del proyecto

- `main.py`: coordina el procesamiento y la generación del reporte.
- `config.py`: centraliza las rutas de los archivos del proyecto.
- `database.py`: administra la conexión y las operaciones con SQLite.
- `validaciones.py`: valida los datos de entrada.
- `reportes.py`: aplica el formato profesional al archivo Excel.
- `test_main.py`: contiene las pruebas automatizadas.
- `ventas_entrada.xlsx`: archivo de entrada con los datos de ventas.
- `requirements.txt`: dependencias de Python.

Los archivos `ventas.db` y `reporte_ventas.xlsx` se generan localmente y están excluidos del control de versiones mediante `.gitignore`.

## Instalación

1. Instalar Python 3.11.
2. Abrir una terminal en la carpeta del proyecto.
3. Crear un entorno virtual:

   ```powershell
   python -m venv .venv
   ```

4. Instalar las dependencias:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

## Ejecución

Colocar el archivo `ventas_entrada.xlsx` en la carpeta del proyecto y ejecutar:

```powershell
.\.venv\Scripts\python.exe main.py
```

El programa lee y valida los datos, guarda las ventas en SQLite, calcula los totales y genera `reporte_ventas.xlsx`.

Las rutas de entrada, salida y base de datos se definen en `config.py`, por lo que pueden modificarse desde un único lugar.

## Pruebas automatizadas

Ejecutar todas las pruebas con:

```powershell
.\.venv\Scripts\python.exe -m unittest test_main -v
```

Las pruebas verifican:

- Validación de los datos de entrada.
- Creación y consulta de la base de datos.
- Prevención de duplicados y manejo de errores en SQLite.
- Aplicación del formato profesional al Excel.
- Generación completa del reporte y cálculo de los totales.

## Registro de eventos

El programa utiliza el módulo `logging` de Python para mostrar información sobre la ejecución, incluyendo:

- Inicio de la generación del reporte.
- Finalización correcta del proceso.
- Cantidad de productos procesados.
- Total de ventas.
- Ruta del archivo generado.
- Errores que impiden completar el proceso.

Los mensajes se muestran en la terminal. Actualmente, el programa no genera un archivo de log independiente.

## Datos de ejemplo

Con los datos de ejemplo actuales, la facturación total es de **$580.000,00**. Este importe depende del contenido del archivo de entrada.

## Estado del proyecto

Proyecto en desarrollo. Cuenta con una estructura modular, validaciones, persistencia en SQLite, generación de reportes Excel, registro de eventos y pruebas automatizadas.
