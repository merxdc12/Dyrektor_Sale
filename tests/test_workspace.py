import sqlite3
import tempfile
import unittest
from pathlib import Path

from pinterest_os.workspace import backup_database, verify_database


class WorkspaceTests(unittest.TestCase):
    def test_backup_snapshot_and_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = sqlite3.connect(Path(tmp) / "live.sqlite3")
            try:
                source.execute("CREATE TABLE example (value TEXT)")
                source.execute("INSERT INTO example VALUES ('saved')")
                source.commit()
                backup = Path(tmp) / "snapshot.sqlite3"
                self.assertEqual(backup_database(source, backup), backup)
                self.assertEqual(verify_database(backup), (True, "ok"))
                copy = sqlite3.connect(backup)
                try:
                    self.assertEqual(copy.execute("SELECT value FROM example").fetchone()[0], "saved")
                finally:
                    copy.close()
                with self.assertRaises(FileExistsError):
                    backup_database(source, backup)
            finally:
                source.close()

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, _ = verify_database(Path(tmp) / "missing.sqlite3")
            self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
