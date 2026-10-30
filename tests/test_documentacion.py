"""Comprueba enlaces Markdown locales y tamaño de imágenes sin dependencias."""

import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def sin_bloques(texto):
    return re.sub(r"^```[^\n]*\n.*?^```\s*$", "", texto, flags=re.MULTILINE | re.DOTALL)


def anclas(texto):
    resultado = set()
    repeticiones = {}
    for titulo in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", sin_bloques(texto), re.MULTILINE):
        titulo = re.sub(r"<[^>]+>", "", titulo).replace("`", "").lower()
        base = re.sub(r"[^\w\-\s]", "", titulo).replace(" ", "-")
        numero = repeticiones.get(base, 0)
        repeticiones[base] = numero + 1
        resultado.add(f"{base}-{numero}" if numero else base)
    return resultado


class TestDocumentacion(unittest.TestCase):
    def test_enlaces_relativos_y_anclas(self):
        documentos = [ROOT / "README.md", ROOT / "README.en.md", *sorted((ROOT / "docs").glob("*.md"))]
        for documento in documentos:
            texto = sin_bloques(documento.read_text(encoding="utf-8"))
            for enlace in re.findall(r"\]\(([^\n)]+)\)", texto):
                enlace = enlace.strip().strip("<>")
                url = urlsplit(enlace)
                if url.scheme or url.netloc:
                    continue
                with self.subTest(documento=documento.name, enlace=enlace):
                    destino = (documento.parent / unquote(url.path)).resolve() if url.path else documento
                    self.assertTrue(destino.is_relative_to(ROOT), enlace)
                    self.assertTrue(destino.is_file(), enlace)
                    if url.fragment:
                        self.assertEqual(destino.suffix, ".md", enlace)
                        self.assertIn(unquote(url.fragment), anclas(destino.read_text(encoding="utf-8")))

    def test_imagenes_menores_a_500_kib(self):
        imagenes = [p for p in (ROOT / "docs/images").rglob("*") if p.is_file()]
        self.assertTrue(imagenes)
        for imagen in imagenes:
            with self.subTest(imagen=imagen.name):
                self.assertLess(imagen.stat().st_size, 500 * 1024)
