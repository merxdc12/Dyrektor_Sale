import json
import tempfile
import unittest
from pathlib import Path
from pinterest_os.storage import Storage


class PinDesignPersistenceTests(unittest.TestCase):
    def test_project_and_png_link_survive_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.sqlite3"
            db = Storage(path)
            pin_id = db.add_pin("Test design")
            project = json.dumps({"version": 1, "width": 1000, "height": 1500,
                                  "background": "#0B1110", "layers": []})
            db.save_pin_design(pin_id, project)
            self.assertEqual(db.get_pin_design(pin_id)["png_path"], "")
            db.save_pin_design(pin_id, project, "/tmp/test-pin.png")
            db.save_pin_design(pin_id, project)
            self.assertEqual(db.get_pin_design(pin_id)["png_path"], "/tmp/test-pin.png")
            db.close()
            db = Storage(path)
            self.assertEqual(json.loads(db.get_pin_design(pin_id)["project_json"])["version"], 1)
            self.assertEqual(db.get_pin_design(pin_id)["png_path"], "/tmp/test-pin.png")
            with self.assertRaises(ValueError):
                db.save_pin_design(999999, project)
            db.close()
