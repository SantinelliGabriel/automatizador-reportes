"""Regeneración deliberada del oráculo usando exclusivamente el exportador anterior."""

import argparse
import ast
from pathlib import Path
import subprocess
import sys
import types


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmar", action="store_true", required=True)
    parser.parse_args()
    raiz = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(raiz))
    import automatizador.procesamiento as procesamiento

    def original(ruta):
        return subprocess.check_output(
            ["git", "show", f"a87ad4d:{ruta}"], cwd=raiz, encoding="utf8",
        )

    anterior = types.ModuleType("exportador_original")
    exec(compile(original("automatizador/reportes.py"), "exportador_original.py", "exec"), anterior.__dict__)
    funcion = next(n for n in ast.parse(original("automatizador/procesamiento.py")).body
                   if isinstance(n, ast.FunctionDef) and n.name == "generar_informe")
    contexto = dict(procesamiento.__dict__, aplicar_formato_excel=anterior.aplicar_formato_excel)
    exec(compile(ast.Module(body=[funcion], type_ignores=[]), "generador_original.py", "exec"), contexto)
    procesamiento.generar_informe = contexto["generar_informe"]
    from tests.test_exportador_excel import FIXTURES, generar_caso
    from tests.helpers import directorio_temporal

    for caso in ("contable", "vacio", "limites"):
        with directorio_temporal() as carpeta:
            generar_caso(caso, FIXTURES / f"{caso}.xlsx", carpeta)


if __name__ == "__main__":
    main()
