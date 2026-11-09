import tempfile
import unittest
from pathlib import Path
from pinterest_os.storage import Storage


class CalendarStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "app.sqlite3"
        self.db = Storage(self.path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_schedule_lifecycle_and_persistence(self):
        pin = self.db.add_pin("IoT tutorial")
        entry = self.db.create_schedule(pin, "2026-11-15T09:30")
        self.assertEqual(len(self.db.schedules_for_day("2026-11-15")), 1)
        self.assertEqual(self.db.schedules_for_day("2026-11-16"), [])
        self.assertTrue(self.db.update_schedule(entry, pin, "2026-11-16T12:00", "READY"))
        self.assertEqual(self.db.get_schedule(entry)["status"], "READY")
        self.db.close()
        self.db = Storage(self.path)
        self.assertEqual(self.db.schedules_for_day("2026-11-16")[0]["title"], "IoT tutorial")
        self.assertTrue(self.db.delete_schedule(entry))
        self.assertIsNone(self.db.get_schedule(entry))
        self.assertEqual(self.db.get("pins", pin)["title"], "IoT tutorial")

    def test_invalid_entries(self):
        pin = self.db.add_pin("Test")
        for args in ((pin, "2026-11-15T09:30", "AUTOPUBLISH"),
                     (pin, "bad date", "PLANNED"),
                     (99999, "2026-11-15T09:30", "PLANNED")):
            with self.assertRaises(ValueError):
                self.db.create_schedule(*args)
