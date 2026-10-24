import unittest
import csv
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from automatizador.adaptadores import _leer, leer_comprobantes
from tests.helpers import ROOT, directorio_temporal


class TestAdaptadorArca(unittest.TestCase):
    def test_lee_estructura_sintetica_y_conserva_varias_alicuotas(self):
        archivo = ROOT / "tests" / "fixtures" / "arca" / "mis_comprobantes_sintetico.csv"
        comprobantes = leer_comprobantes(archivo, "arca", "ventas")

        self.assertEqual(len(comprobantes), 2)
        simple, multialicuota = comprobantes.to_dict("records")
        self.assertEqual(simple["tipo_comprobante"], "A")
        self.assertEqual(simple["numero"], "123")
        self.assertEqual(simple["neto_gravado"], 1000)
        self.assertEqual(simple["iva"], 210)
        self.assertEqual(simple["moneda"], "ARS")
        self.assertEqual(simple["tipo_cambio"], 1)
        self.assertEqual(simple["_error_adaptador"], "")
        self.assertEqual(multialicuota["neto_gravado"], 1500)
        self.assertEqual(multialicuota["iva"], 262.5)
        self.assertEqual(multialicuota["moneda"], "USD")
        self.assertEqual(multialicuota["tipo_cambio"], 1000)
        self.assertEqual(multialicuota["_error_adaptador"], "")
        self.assertEqual(
            multialicuota["detalle_alicuotas"],
            [
                {"alicuota": 10.5, "neto_gravado": 500, "iva": 52.5},
                {"alicuota": 21, "neto_gravado": 1000, "iva": 210},
            ],
        )

    def test_elige_emisor_para_compras_y_normaliza_tipos_textuales(self):
        fila = {
            "Fecha": "01/09/2026", "Tipo": "Nota de Crédito B", "Punto de Venta": 2,
            "Número Desde": 12, "Nro. Doc. Emisor": "20123456789",
            "Nro. Doc. Receptor": "27234567890", "Denominación Emisor": "Proveedor",
            "Denominación Receptor": "Cliente", "Imp. Neto Gravado IVA 21": 100,
            "IVA 21": 21, "Imp. Total": 121,
        }
        with directorio_temporal() as carpeta:
            archivo = Path(carpeta) / "compras.csv"
            pd.DataFrame([fila]).to_csv(archivo, index=False)

            resultado = leer_comprobantes(archivo, "arca", "compras").iloc[0]

        self.assertEqual(resultado["tipo_comprobante"], "NC B")
        self.assertEqual(resultado["cuit"], "20123456789")
        self.assertEqual(resultado["razon_social"], "Proveedor")
        self.assertEqual(resultado["operacion"], "compras")
        self.assertEqual(resultado["_error_adaptador"], "")

    def test_marca_registros_arca_no_soportados_agrupados_y_otros_tributos(self):
        fila = {
            "Fecha": "01/09/2026", "Tipo": 99, "Punto de Venta": 1,
            "Número Desde": 20, "Número Hasta": 21, "Nro. Doc. Receptor": "20329642330",
            "Denominación Receptor": "Cliente", "Imp. Neto Gravado IVA 21": 100,
            "IVA 21": 21, "Otros Tributos": 5, "Imp. Total": 126,
        }
        with directorio_temporal() as carpeta:
            archivo = Path(carpeta) / "arca.csv"
            pd.DataFrame([fila]).to_csv(archivo, index=False)

            resultado = leer_comprobantes(archivo, "arca").iloc[0]

        self.assertEqual(resultado["tipo_comprobante"], "99")
        self.assertIn("no soportado", resultado["_error_adaptador"])
        self.assertIn("rango de comprobantes", resultado["_error_adaptador"])
        self.assertIn("otros tributos", resultado["_error_adaptador"])

    def test_reporta_columnas_faltantes_e_importes_invalidos(self):
        with directorio_temporal() as carpeta:
            archivo = Path(carpeta) / "incompleto.csv"
            pd.DataFrame([{"Dato": "sin columnas ARCA"}]).to_csv(archivo, index=False)
            with self.assertRaisesRegex(ValueError, "No reconozco estas columnas"):
                leer_comprobantes(archivo, "arca")

            fila = {
                "Fecha": "01/09/2026", "Tipo": 1, "Punto de Venta": 1,
                "Número Desde": 20, "Nro. Doc. Receptor": "20329642330",
                "Denominación Receptor": "Cliente", "Imp. Neto Gravado": "no-numérico",
                "IVA": 21, "Imp. Total": 126,
            }
            pd.DataFrame([fila]).to_csv(archivo, index=False)
            resultado = leer_comprobantes(archivo, "arca").iloc[0]

        self.assertIn("Importes ARCA inválidos", resultado["_error_adaptador"])
        self.assertEqual(resultado["total"], 0)

    def test_conserva_importes_con_formato_decimal_local(self):
        fila = {
            "Fecha": "01/09/2026", "Tipo": 1, "Punto de Venta": 1,
            "Número Desde": 20, "Nro. Doc. Receptor": "20329642330",
            "Denominación Receptor": "Cliente", "Imp. Neto Gravado IVA 21": "(1.234,50)",
            "IVA 21": "259,25", "Imp. Total": "1.493,75",
        }
        with directorio_temporal() as carpeta:
            archivo = Path(carpeta) / "decimal_local.csv"
            pd.DataFrame([fila]).to_csv(archivo, index=False)
            resultado = leer_comprobantes(archivo, "arca").iloc[0]

        self.assertEqual(resultado["neto_gravado"], 1234.5)
        self.assertEqual(resultado["iva"], 259.25)
        self.assertEqual(resultado["total"], 1493.75)


class TestAdaptadorHolistor(unittest.TestCase):
    def test_aplica_mapeo_configurable_a_csv(self):
        with directorio_temporal() as carpeta:
            archivo = Path(carpeta) / "holistor.csv"
            mapeo = Path(carpeta) / "mapeo.json"
            pd.DataFrame([{
                "Fecha comprobante": "03/09/2026", "Clase": "Factura A", "Sucursal": 3,
                "Número comprobante": 45, "CUIT Cliente": "20329642330",
                "Razón social": "Cliente Demo", "Importe neto": 100,
                "Tasa IVA": 21, "Importe IVA": 21, "Total comprobante": 121,
            }]).to_csv(archivo, index=False)
            mapeo.write_text(json.dumps({"columnas": {
                "Fecha comprobante": "fecha", "Clase": "tipo_comprobante",
                "Sucursal": "punto_venta", "Número comprobante": "numero",
                "CUIT Cliente": "cuit", "Razón social": "razon_social",
                "Importe neto": "neto_gravado", "Tasa IVA": "alicuota",
                "Importe IVA": "iva", "Total comprobante": "total",
            }}), encoding="utf-8")

            resultado = leer_comprobantes(archivo, "holistor", "compras", mapeo)

        self.assertEqual(resultado.loc[0, "fecha"], "03/09/2026")
        self.assertEqual(resultado.loc[0, "tipo_comprobante"], "Factura A")
        self.assertEqual(resultado.loc[0, "operacion"], "compras")

    def test_lee_excel_con_hoja_por_defecto_si_falta_hoja_de_ventas(self):
        with directorio_temporal() as carpeta:
            archivo = Path(carpeta) / "holistor.xlsx"
            pd.DataFrame([{"Fecha": "03/09/2026", "Total": 100}]).to_excel(
                archivo, sheet_name="Exportación", index=False
            )

            resultado = leer_comprobantes(archivo, "holistor", "ventas")

        self.assertEqual(resultado.loc[0, "fecha"], "03/09/2026")
        self.assertEqual(resultado.loc[0, "operacion"], "ventas")

    def test_lee_prn_de_ancho_fijo_y_rechaza_configuracion_incompleta(self):
        with directorio_temporal() as carpeta:
            archivo = Path(carpeta) / "holistor.prn"
            archivo.write_text("20260903  00121.00\n", encoding="utf-8")
            mapeo = Path(carpeta) / "mapeo.json"
            mapeo.write_text(json.dumps({
                "anchos_prn": [10, 9], "columnas_prn": ["fecha", "total"],
            }), encoding="utf-8")
            resultado = leer_comprobantes(archivo, "holistor", mapping_path=mapeo)
            with self.assertRaisesRegex(ValueError, "ancho fijo"):
                leer_comprobantes(archivo, "holistor")

        self.assertEqual(resultado.loc[0, "fecha"], "20260903")
        self.assertEqual(resultado.loc[0, "operacion"], "ventas")


class TestLecturaArchivos(unittest.TestCase):
    def test_xls_usa_xlrd(self):
        with patch("automatizador.adaptadores.pd.read_excel", return_value=pd.DataFrame()) as lectura:
            _leer(Path("sintetico.xls"))
        self.assertEqual(lectura.call_args.kwargs["engine"], "xlrd")

    def test_csv_sin_delimitador_entrega_error_controlado(self):
        with patch("automatizador.adaptadores.pd.read_csv", side_effect=csv.Error("sin separador")):
            with self.assertRaisesRegex(ValueError, "No se pudo interpretar"):
                _leer(Path("sin-datos.csv"))

    def test_excel_moderno_se_lee_solo_lectura_y_sin_enlaces(self):
        with patch("automatizador.adaptadores.pd.read_excel", return_value=pd.DataFrame()) as lectura:
            _leer(Path("sintetico.xlsx"))
        self.assertEqual(lectura.call_args.kwargs["engine"], "openpyxl")
        self.assertEqual(lectura.call_args.kwargs["engine_kwargs"],
                         {"read_only": True, "data_only": True, "keep_links": False})

    def test_lee_csv_cp1252_y_rechaza_extension_desconocida(self):
        with directorio_temporal() as carpeta:
            archivo = Path(carpeta) / "latin1.csv"
            archivo.write_bytes("Nombre;Descripción\nJosé;Comprobante\n".encode("cp1252"))
            resultado = _leer(archivo)
            self.assertEqual(resultado.loc[0, "Nombre"], "José")

            desconocido = Path(carpeta) / "archivo.bin"
            desconocido.write_bytes(b"datos")
            with self.assertRaisesRegex(ValueError, "Formato no admitido"):
                leer_comprobantes(desconocido)


if __name__ == "__main__":
    unittest.main()
