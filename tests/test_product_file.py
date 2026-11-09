import json
import tempfile
import unittest
from pathlib import Path

from pinterest_os.storage import Storage
from pinterest_os.product_io import import_products, export_products


class ProductFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = Storage(self.root / "test.sqlite3")
        self.addCleanup(self.db.close)

    def test_search_filter_and_safe_delete(self):
        first = self.db.create("products", name="Linux T-Shirt", category="POD")
        self.db.create("products", name="Circuit Calculator", category="FREE_TOOL")
        pin = self.db.create("pins", title="Linux Pin", product_id=first)
        self.assertEqual(len(self.db.search_products("linux", "POD")), 1)
        self.assertEqual(len(self.db.search_products("linux", "FREE_TOOL")), 0)
        self.assertEqual(self.db.product_pin_count(first), 1)
        self.assertTrue(self.db.delete_product(first))
        self.assertIsNone(self.db.get("pins", pin)["product_id"])

    def test_csv_json_roundtrip(self):
        self.db.create("products", name="Книга", category="KDP",
                       target_url="https://example.org/book")
        for suffix in (".csv", ".json"):
            path = self.root / ("products" + suffix)
            self.assertEqual(export_products(self.db, path), 1)
            self.assertEqual(import_products(self.db, path), 1)
            self.assertEqual(len(self.db.all("products")), 2)
            self.db.delete_product(self.db.all("products")[0]["id"])

    def test_invalid_file_does_not_partially_import(self):
        path = self.root / "invalid.json"
        path.write_text(json.dumps({
            "format": "ithutir-products-v1",
            "products": [
                {"name": "Valid", "category": "POD"},
                {"name": "", "category": "POD"},
            ],
        }), encoding="utf-8")
        with self.assertRaises(ValueError):
            import_products(self.db, path)
        self.assertEqual(self.db.all("products"), [])

    def test_no_silent_overwrite_of_existing_pin(self):
        pin = self.db.create("pins", title="Keep")
        product = self.db.create("products", name="Product", category="POD")
        self.db.delete_product(product)
        self.assertEqual(self.db.get("pins", pin)["title"], "Keep")


if __name__ == "__main__":
    unittest.main()
