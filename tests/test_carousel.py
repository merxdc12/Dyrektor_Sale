"""Carousel ordering, project persistence and offline export."""
import json
from zipfile import ZipFile

import pytest

from pinterest_os.carousel_logic import export_carousel, validate_slides
from pinterest_os.storage import Storage


def test_carousel_order_and_zip(tmp_path):
    db = Storage(tmp_path / "project.sqlite3")
    try:
        first = db.create("pins", title="First")
        second = db.create("pins", title="Second")
        carousel = db.create_carousel("Tutorial")
        db.set_carousel_slides(carousel, [second, first])
        assert [r["pin_id"] for r in db.carousel_slides(carousel)] == [second, first]
        db.set_carousel_slides(carousel, [first, second])
        slides = db.carousel_slides(carousel)
        for slide in slides:
            png = tmp_path / f'{slide["pin_id"]}.png'
            png.write_bytes(b"png-fixture")
            db.save_pin_design(slide["pin_id"], '{"version":1}', str(png))
        slides = db.carousel_slides(carousel)
        assert validate_slides(slides) == []
        result = export_carousel(slides, tmp_path / "tutorial.zip", "Tutorial")
        with ZipFile(result) as archive:
            assert archive.namelist() == ["slide_01.png", "slide_02.png", "manifest.json"]
            manifest = json.loads(archive.read("manifest.json"))
            assert [item["pin_id"] for item in manifest["slides"]] == [first, second]
    finally:
        db.close()


def test_carousel_rejects_duplicates_and_missing_assets(tmp_path):
    db = Storage(tmp_path / "project.sqlite3")
    try:
        pin = db.create("pins", title="Single")
        carousel = db.create_carousel("Draft")
        with pytest.raises(ValueError, match="Duplicate"):
            db.set_carousel_slides(carousel, [pin, pin])
        db.set_carousel_slides(carousel, [pin])
        assert validate_slides(db.carousel_slides(carousel))
    finally:
        db.close()
