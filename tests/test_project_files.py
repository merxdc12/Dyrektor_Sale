import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pinterest_os.storage import Storage
from pinterest_os.project_files import (
    create_project, save_project, verify_project, backup_project, restore_project, DB_NAME
)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = Storage(self.root / "source.sqlite3")
        self.addCleanup(self.db.close)

    def test_project_backup_restore_and_asset_rebase(self):
        image = self.root / "photo.png"
        image.write_bytes(b"test-image-data")
        pin = self.db.create("pins", title="Portable pin")
        self.db.save_pin_design(pin, json.dumps({
            "version": 1, "width": 1000, "height": 1500,
            "layers": [{"kind": "image", "path": str(image),
                        "x": 0, "y": 0, "width": 100, "height": 100}]
        }))
        project = create_project(self.db.conn, self.root / "project")
        verify_project(project)
        copy = sqlite3.connect(project / DB_NAME)
        try:
            row = copy.execute("SELECT project_json FROM pin_designs").fetchone()
            self.assertTrue((project / json.loads(row[0])["layers"][0]["path"]).is_file())
        finally:
            copy.close()
        archive = backup_project(project, self.root / "project.zip")
        restored = restore_project(archive, self.root / "restored")
        verify_project(restored)
        copy = sqlite3.connect(restored / DB_NAME)
        try:
            row = copy.execute("SELECT project_json FROM pin_designs").fetchone()
            path = Path(json.loads(row[0])["layers"][0]["path"])
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_absolute())
            self.assertTrue((restored / path).is_file())
        finally:
            copy.close()

    def test_save_collects_new_external_image_and_save_as(self):
        project = create_project(self.db.conn, self.root / "project")
        opened = Storage(project / DB_NAME)
        try:
            image = self.root / "new.png"
            image.write_bytes(b"new-image")
            pin = opened.create("pins", title="New design")
            opened.save_pin_design(pin, json.dumps({
                "version": 1, "width": 1000, "height": 1500,
                "layers": [{"kind": "image", "path": str(image),
                            "x": 0, "y": 0, "width": 100, "height": 100}]
            }))
            save_project(opened.conn, project)
            verify_project(project)
            record = opened.get_pin_design(pin)
            relative = Path(json.loads(record["project_json"])["layers"][0]["path"])
            self.assertFalse(relative.is_absolute())
            self.assertTrue((project / relative).is_file())
            clone = create_project(opened.conn, self.root / "clone")
            verify_project(clone)
            self.assertTrue((clone / relative).is_file())
        finally:
            opened.close()

    def test_refuses_existing_destination(self):
        with self.assertRaises(FileExistsError):
            create_project(self.db.conn, self.root)

    def test_save_updates_manifest_after_edit(self):
        folder = create_project(self.db.conn, self.root / "project")
        opened = Storage(folder / DB_NAME)
        try:
            opened.create("products", name="New", category="POD")
            save_project(opened.conn, folder)
            verify_project(folder)
        finally:
            opened.close()


if __name__ == "__main__":
    unittest.main()
