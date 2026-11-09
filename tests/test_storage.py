import tempfile
import unittest
from pathlib import Path
from pinterest_os.storage import Storage


class StorageTests(unittest.TestCase):
    def test_persistence_and_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.sqlite3"
            db = Storage(path)
            pin_id = db.add_pin("Example pin")
            board_id = db.add_board("Electronics")
            session = db.start_session()
            db.save_elapsed(session, 12)
            db.end_session(session)
            db.close()
            reopened = Storage(path)
            self.assertEqual(reopened.list_rows("pins"), [(pin_id, "Example pin")])
            self.assertEqual(reopened.list_rows("boards"), [(board_id, "Electronics")])
            self.assertEqual(reopened.conn.execute(
                "SELECT active_seconds FROM work_sessions WHERE id=?", (session,)
            ).fetchone()[0], 12)
            reopened.close()

    def test_invalid_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Storage(Path(tmp) / "test.sqlite3")
            with self.assertRaises(ValueError):
                db.add_pin("  ")
            with self.assertRaises(ValueError):
                db.add_board("")
            db.close()


if __name__ == "__main__":
    unittest.main()
