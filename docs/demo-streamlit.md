# Interfaz y demo de Streamlit

El repositorio contiene dos entradas de Streamlit:

- `automatizador/interfaz.py`: interfaz local para importar comprobantes, conciliar extractos y consultar vencimientos. Los datos se guardan en la base SQLite indicada.
- `demo.py`: activa el modo demo y presenta el libro sintético `ejemplos/Cliente Demo Norte.xlsx`. En ese modo la interfaz no muestra controles para subir archivos.

## Probar localmente

Desde la raíz del repositorio:

```powershell
streamlit run automatizador/interfaz.py
streamlit run demo.py
```

En macOS o Linux, los mismos comandos funcionan desde la raíz del repositorio.

## Despliegue público

La aplicación pública usa `demo.py` como entrypoint y el `requirements.txt` que está en la raíz. En Streamlit Community Cloud, creá una app y elegí este repositorio, la rama `main` y el archivo `demo.py`. La plataforma toma el código y la configuración de dependencias desde GitHub; consultá la [guía oficial de despliegue](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) y la [guía de organización de archivos](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization) para los pasos vigentes.

El modo demo utiliza un directorio temporal para SQLite y solo expone la salida ficticia. La demo no debe aceptar archivos de visitantes ni usar datos de clientes. La disponibilidad de la URL pública puede cambiar con el estado de la cuenta o de la app.
