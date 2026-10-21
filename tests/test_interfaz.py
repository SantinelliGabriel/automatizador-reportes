import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from tests.helpers import ROOT


def app_test(path):
    tempfile.tempdir = str(ROOT / ".test_tmp")
    return AppTest.from_file(str(path))


class TestInterfaz(unittest.TestCase):
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
            self.assertGreaterEqual(len(app.download_button), 1)

    def test_modo_demo_no_expone_carga_de_archivos(self):
        app = app_test(ROOT / "demo.py")
        app.run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.file_uploader), 0)
        self.assertEqual(len(app.radio), 0)
        self.assertGreaterEqual(len(app.download_button), 1)
        self.assertTrue(any("datos ficticios" in item.value for item in app.caption))


if __name__ == "__main__":
    unittest.main()
