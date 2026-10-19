import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import main
from main import validar_ventas

import database
import main
from main import validar_ventas


class TestValidacionesVentas(unittest.TestCase):

    def test_rechaza_precio_no_numerico(self):
        ventas = self.ventas.copy()
        ventas["precio_unitario"] = ventas["precio_unitario"].astype(object)
        ventas.loc[0, "precio_unitario"] = "abc"

        with self.assertRaisesRegex(
            ValueError,
            "no numéricos",
        ):
            validar_ventas(ventas)

    def test_rechaza_unidades_decimales(self):
        ventas = self.ventas.copy()
        ventas["unidades"] = ventas["unidades"].astype(float)
        ventas.loc[0, "unidades"] = 2.5

        with self.assertRaisesRegex(
            ValueError,
            "números enteros",
        ):
            validar_ventas(ventas)

    def test_acepta_precio_cero(self):
        self.ventas.loc[0, "precio_unitario"] = 0

        resultado = validar_ventas(self.ventas)

        self.assertEqual(resultado.loc[0, "precio_unitario"], 0)

    def setUp(self):
        # Datos correctos para reutilizar en las pruebas
        self.ventas = pd.DataFrame({
            "producto": ["Teclado", "Mouse"],
            "unidades": [5, 8],
            "precio_unitario": [12000, 7500],
        })

    def test_acepta_datos_correctos(self):
        resultado = validar_ventas(self.ventas.copy())
        self.assertEqual(len(resultado), 2)

    def test_rechaza_precio_negativo(self):
        self.ventas.loc[0, "precio_unitario"] = -12000

        with self.assertRaisesRegex(ValueError, "precios no pueden ser negativos"):
            validar_ventas(self.ventas)

    def test_rechaza_unidades_cero(self):
        self.ventas.loc[0, "unidades"] = 0

        with self.assertRaisesRegex(ValueError, "unidades deben ser mayores que cero"):
            validar_ventas(self.ventas)

    def test_rechaza_columna_faltante(self):
        ventas = self.ventas.drop(columns=["producto"])

        with self.assertRaisesRegex(ValueError, "Faltan estas columnas"):
            validar_ventas(ventas)

    def test_rechaza_celdas_vacias(self):
        self.ventas.loc[0, "producto"] = None

        with self.assertRaisesRegex(ValueError, "celdas vacías"):
            validar_ventas(self.ventas)


class TestBaseDeDatos(unittest.TestCase):

    def setUp(self):
        """Prepara una base de datos temporal para cada prueba."""
        self.carpeta_temporal = tempfile.TemporaryDirectory()
        self.archivo_bd = Path(self.carpeta_temporal.name) / "pruebas.db"

        self.parche_bd = patch.object(database, "ARCHIVO_BD", self.archivo_bd)
        self.parche_bd.start()

        self.addCleanup(self.parche_bd.stop)
        self.addCleanup(self.carpeta_temporal.cleanup)

        database.crear_tabla()

    def test_crea_tabla_ventas(self):
        """Comprueba que se crea la tabla de ventas."""
        conexion = database.conectar_bd()

        try:
            resultado = conexion.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'ventas'
                """
            ).fetchone()
        finally:
            conexion.close()

        self.assertIsNotNone(resultado)


    def test_guarda_ventas_en_la_base_de_datos(self):
        """Comprueba que las ventas se guardan correctamente."""
        ventas = pd.DataFrame({
            "producto": ["Teclado", "Mouse"],
            "unidades": [5, 8],
            "precio_unitario": [12000, 7500],
        })

        database.guardar_ventas(ventas)
        resultado = database.consultar_ventas()

        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado["producto"].tolist(), ["Teclado", "Mouse"])
        self.assertEqual(resultado["total"].tolist(), [60000, 60000])


    def test_guardar_dos_veces_no_duplica_ventas(self):
        """Comprueba que guardar dos veces no genere duplicados."""
        ventas = pd.DataFrame({
            "producto": ["Teclado", "Mouse"],
            "unidades": [5, 8],
            "precio_unitario": [12000, 7500],
        })

        database.guardar_ventas(ventas)
        database.guardar_ventas(ventas)

        resultado = database.consultar_ventas()

        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado["producto"].tolist(), ["Teclado", "Mouse"])


    def test_base_de_datos_inicialmente_vacia(self):
        """Comprueba que la tabla no tenga ventas al crearse."""
        resultado = database.consultar_ventas()

        self.assertTrue(resultado.empty)
        self.assertEqual(
            list(resultado.columns),
            ["producto", "unidades", "precio_unitario", "total"],
        )


    def test_error_al_guardar_conserva_las_ventas_anteriores(self):
        """Comprueba que un error deshaga la operación incompleta."""
        ventas_originales = pd.DataFrame({
            "producto": ["Teclado", "Mouse"],
            "unidades": [5, 8],
            "precio_unitario": [12000, 7500],
        })

        ventas_nuevas = pd.DataFrame({
            "producto": ["Monitor"],
            "unidades": [2],
            "precio_unitario": [150000],
        })

        database.guardar_ventas(ventas_originales)

        with patch.object(
            database,
            "conectar_bd",
            side_effect=RuntimeError("Error simulado"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Error simulado"):
                database.guardar_ventas(ventas_nuevas)

        resultado = database.consultar_ventas()

        self.assertEqual(
            resultado["producto"].tolist(),
            ["Teclado", "Mouse"],
        )
        self.assertEqual(len(resultado), 2)


    def test_rollback_restaura_ventas_tras_error_de_insercion(self):
        """Comprueba que rollback restaure los datos anteriores."""
        ventas_originales = pd.DataFrame({
            "producto": ["Teclado", "Mouse"],
            "unidades": [5, 8],
            "precio_unitario": [12000, 7500],
        })

        ventas_nuevas = pd.DataFrame({
            "producto": ["Monitor"],
            "unidades": [2],
            "precio_unitario": [150000],
        })

        database.guardar_ventas(ventas_originales)

        conexion_original = database.conectar_bd

        def conectar_con_error():
            conexion = conexion_original()

            conexion.execute(
                """
                CREATE TRIGGER provocar_error
                BEFORE INSERT ON ventas
                BEGIN
                    SELECT RAISE(ABORT, 'Error de inserción simulado');
                END
                """
            )

            conexion.commit()
            return conexion

        with patch.object(
            database,
            "conectar_bd",
            side_effect=conectar_con_error,
        ):
            with self.assertRaisesRegex(
                Exception,
                "Error de inserción simulado",
            ):
                database.guardar_ventas(ventas_nuevas)

        resultado = database.consultar_ventas()

        self.assertEqual(
            resultado["producto"].tolist(),
            ["Teclado", "Mouse"],
        )
        self.assertEqual(len(resultado), 2)

    def test_rollback_restaura_ventas_tras_error_de_insercion(self):
        """Comprueba que rollback restaure los datos anteriores."""
        ventas_originales = pd.DataFrame({
            "producto": ["Teclado", "Mouse"],
            "unidades": [5, 8],
            "precio_unitario": [12000, 7500],
        })

        ventas_nuevas = pd.DataFrame({
            "producto": ["Monitor"],
            "unidades": [2],
            "precio_unitario": [150000],
        })

        database.guardar_ventas(ventas_originales)

        conexion_original = database.conectar_bd

        def conectar_con_error():
            conexion = conexion_original()

            conexion.execute(
                """
                CREATE TRIGGER provocar_error
                BEFORE INSERT ON ventas
                BEGIN
                    SELECT RAISE(ABORT, 'Error de inserción simulado');
                END
                """
            )

            conexion.commit()
            return conexion

        with patch.object(
            database,
            "conectar_bd",
            side_effect=conectar_con_error,
        ):
            with self.assertRaisesRegex(
                Exception,
                "Error de inserción simulado",
            ):
                database.guardar_ventas(ventas_nuevas)

        resultado = database.consultar_ventas()

        self.assertEqual(
            resultado["producto"].tolist(),
            ["Teclado", "Mouse"],
        )
        self.assertEqual(len(resultado), 2)

    def test_calcula_subtotales_correctamente(self):
        """Comprueba que SQL calcule los importes de cada venta."""
        ventas = pd.DataFrame({
            "producto": ["Teclado", "Mouse"],
            "unidades": [5, 8],
            "precio_unitario": [12000, 7500],
        })

        database.guardar_ventas(ventas)
        resultado = database.consultar_ventas()

        self.assertEqual(resultado["total"].tolist(), [60000, 60000])
        self.assertEqual(resultado["total"].sum(), 120000)

if __name__ == "__main__":
    unittest.main(verbosity=2)
