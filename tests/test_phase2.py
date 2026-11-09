import tempfile
import unittest
from pathlib import Path
from pinterest_os.storage import Storage


class Phase2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Storage(Path(self.tmp.name) / "data.sqlite3")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_create_update_and_relations(self):
        product = self.db.create("products", name="Book", category="KDP")
        board = self.db.create("boards", name="Word Search")
        pin = self.db.create("pins", title="Puzzle", board_id=board, product_id=product)
        self.assertEqual(self.db.get("pins", pin)["status"], "DRAFT")
        self.assertTrue(self.db.update("pins", pin, title="IT Puzzle", status="READY"))
        self.assertEqual(self.db.get("pins", pin)["title"], "IT Puzzle")
        self.assertEqual(len(self.db.all("pins")), 1)

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.db.create("pins", title=" ")
        with self.assertRaises(ValueError):
            self.db.create("pins", title="Valid", status="INVALID")
        with self.assertRaises(ValueError):
            self.db.create("unknown", name="Bad")
        with self.assertRaises(ValueError):
            self.db.update("boards", 1, invented="field")
