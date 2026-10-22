import json
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from tests.helpers import ROOT
from tests.test_migracion_decimal import base_v1


def app_test(path):
    tempfile.tempdir = str(ROOT / ".test_tmp")
    return AppTest.from_file(str(path))


class TestInterfaz(unittest.TestCase):
    def test_avisa_migracion_y_ruta_del_respaldo(self):
        entrada = ROOT / "ejemplos" / "Cliente Demo Norte.xlsx"
        with tempfile.TemporaryDirectory(dir=ROOT / ".test_tmp") as carpeta:
            base = base_v1(carpeta)
            app = app_test(ROOT / "automatizador" / "interfaz.py")
            app.run()
            app.text_input[1].set_value(str(base))
            app.text_input[0].set_value("2026-09")
            app.file_uploader[0].set_value(
                (entrada.name, entrada.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            )
            app.run()
            app.button[0].click()
            app.run()

            self.assertFalse(app.exception)
            self.assertTrue(any(
                "Base SQLite migrada de versión 1 a 3" in item.value
                and str(Path(carpeta) / "legacy.v1.bak.db") in item.value
                for item in app.info
            ))

    def test_importa_el_ejemplo_y_muestra_resultado(self):
        entrada = ROOT / "ejemplos" / "Cliente Demo Norte.xlsx"
        app = app_test(ROOT / "automatizador" / "interfaz.py")
        app.run()
        self.assertFalse(app.exception)

        with tempfile.TemporaryDirectory() as carpeta:
            base = Path(carpeta) / "interfaz.db"
            app.text_input[1].set_value(str(base))
            app.text_input[0].set_value("2026-09")
            app.file_uploader[0].set_value(
                (entrada.name, entrada.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            )
            app.run()
            app.button[0].click()
            app.run()

            self.assertFalse(app.exception)
            mensajes = [item.value for item in app.success]
            errores = [item.value for item in app.error]
            self.assertTrue(
                any("Importación terminada" in item for item in mensajes),
                f"success={mensajes}; error={errores}",
            )
            self.assertTrue(base.exists())
            self.assertFalse(any("Base SQLite migrada" in item.value for item in app.info))
            self.assertEqual(list(Path(carpeta).glob("*.bak*.db")), [])
            self.assertGreaterEqual(len(app.download_button), 1)
            self.assertEqual(json.loads(app.json[0].value), {
                "neto_gravado": "$150,000.00", "iva": "$26,250.00", "total": "$176,250.00",
            })

    def test_modo_demo_no_expone_carga_de_archivos(self):
        app = app_test(ROOT / "demo.py")
        app.run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.file_uploader), 0)
        self.assertEqual(len(app.radio), 0)
        self.assertGreaterEqual(len(app.download_button), 1)
        self.assertTrue(any("datos ficticios" in item.value for item in app.caption))
        self.assertEqual([metrica.value for metrica in app.metric], [
            "2", "$150,000.00", "$26,250.00", "$176,250.00",
        ])


if __name__ == "__main__":
    unittest.main()
