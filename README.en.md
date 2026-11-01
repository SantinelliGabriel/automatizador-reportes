# Argentine VAT (IVA) invoice reports

A personal portfolio project for Argentine accounting firms: validate sales and purchases, review rejected rows and produce monthly Excel reports.

[Español](README.md) · [Documentation](README.md#documentación) · [License: MIT](LICENSE)

## Try it

[Open the synthetic Streamlit demo](https://automatizador-reportes-kqvtruqnyz7gwzj47ex7is.streamlit.app/), with file uploads disabled.
For local use, clone the repository with Python 3.11–3.13, create a virtual environment, then:

```bash
python -m pip install -e .
automatizador --period 2026-09
```

[Windows, macOS and Linux setup](docs/instalacion.md).

## Features and limits

- Invoice and credit/debit note validation, multiple VAT rates and file-provided exchange rates.
- Excel reports, SQLite history, ARCA/Holistor file adapters, bank matching suggestions and a user-supplied due-date calendar.
- CLI, Streamlit and an optional Django web interface with secure upload, preview, history, current observations and consolidated reports.
- Django demo mode provides read-only synthetic data locally; [setup](docs/web.md).

Version [0.2.0](CHANGELOG.md). This supports professional review and does not replace it or submit tax returns. There is no direct ARCA/Holistor connection or public Django service. Existing core SQLite databases are backed up before migration; [details](docs/migracion.md).
