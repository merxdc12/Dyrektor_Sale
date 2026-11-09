import tempfile
import unittest
from pathlib import Path
from pinterest_os.storage import Storage


class CalendarViewsTests(unittest.TestCase):
    def test_range_and_board_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Storage(Path(tmp) / "calendar.sqlite3")
            a = db.create("boards", name="Linux")
            b = db.create("boards", name="Electronics")
            pin_a = db.create("pins", title="A", board_id=a)
            pin_b = db.create("pins", title="B", board_id=b)
            entry = db.create_schedule(pin_a, "2026-11-10T09:00")
            db.create_schedule(pin_b, "2026-11-11T10:00")
            self.assertEqual(len(db.schedules_between("2026-11-01", "2026-11-30")), 2)
            self.assertEqual(len(db.schedules_between("2026-11-09", "2026-11-15", a)), 1)
            self.assertEqual(db.schedules_between("2026-11-10", "2026-11-10", b), [])
            db.update_schedule(entry, pin_a, "2026-11-12T09:00", "READY")
            self.assertEqual(db.schedules_between("2026-11-12", "2026-11-12", a)[0]["status"], "READY")
            with self.assertRaises(ValueError):
                db.schedules_between("2026-12-01", "2026-11-01")
            db.close()
