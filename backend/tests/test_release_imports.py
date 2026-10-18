"""Catch missing dynamically loaded source before GPU deployment."""
import ast
import unittest
from pathlib import Path
class ReleaseImportsTest(unittest.TestCase):
    def test_dynamic_extractor_is_shipped_and_imports_existing_modules(self):
        root=Path(__file__).resolve().parents[1]
        source=root/'scripts/extract_features.py'
        self.assertTrue(source.is_file())
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('forte.'):
                self.assertTrue((root/Path(*node.module.split('.'))).with_suffix('.py').is_file(),node.module)
