# Automatizador de reportes de ventas

Proyecto desarrollado en Python para procesar datos de ventas desde Excel, validar la información, almacenarla en una base de datos SQLite y generar reportes de ventas con formato profesional.

## Tecnologías

- Python 3.11
- pandas
- openpyxl
- SQLite
- Excel (.xlsx)
- unittest

## Funcionalidades

- Lectura de datos desde archivos Excel.
- Validación de columnas, valores numéricos y datos obligatorios.
- Almacenamiento de ventas en una base de datos SQLite.
- Consultas SQL para obtener los subtotales por producto.
- Cálculo de la facturación total.
- Prevención de duplicados al actualizar los registros desde el Excel de entrada.
- Generación de reportes Excel con formato profesional.
- Manejo de errores de lectura y escritura.
- Pruebas automatizadas para validar los datos de entrada.

## Archivos principales

- `main.py`: lógica principal del programa.
- `test_main.py`: pruebas automatizadas.
- `ventas_entrada.xlsx`: archivo de entrada con los datos de ventas.
- `requirements.txt`: dependencias de Python.
- `ventas.db`: base de datos SQLite creada localmente al ejecutar el programa.
- `reporte_ventas.xlsx`: reporte generado por el programa.

Los archivos `ventas.db` y `reporte_ventas.xlsx` se generan o actualizan localmente y están excluidos del control de versiones mediante `.gitignore`.

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

Ejecutar el programa:

```powershell
.\.venv\Scripts\python.exe main.py
```

El programa lee `ventas_entrada.xlsx`, valida los datos, actualiza los registros en SQLite y genera `reporte_ventas.xlsx`.

## Pruebas automatizadas

Ejecutar las pruebas con:

```powershell
.\.venv\Scripts\python.exe -m unittest test_main -v
```

Las pruebas verifican diferentes casos de validación de los datos de entrada.

## Datos de ejemplo

El archivo de entrada contiene ventas de productos, unidades y precios unitarios. Con los datos de ejemplo actuales, la facturación total es de **$580.000,00**.

## Estado del proyecto

Proyecto en desarrollo. Incluye procesamiento de Excel, validaciones, persistencia de datos en SQLite, consultas SQL, generación de reportes y pruebas automatizadas.
