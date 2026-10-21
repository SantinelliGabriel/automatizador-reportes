"""Entrypoint de la demo pública, limitada a datos sintéticos."""

import os
from pathlib import Path
import runpy


os.environ["AUTOMATIZADOR_DEMO"] = "1"
runpy.run_path(str(Path(__file__).parent / "automatizador" / "interfaz.py"), run_name="__main__")
