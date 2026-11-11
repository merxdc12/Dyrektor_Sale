"""Offscreen GUI tests for carousel empty/selection states."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pinterest_os.carousel import CarouselPage
from pinterest_os.storage import Storage


def app():
    return QApplication.instance() or QApplication([])


def test_empty_carousel_has_clear_empty_state_and_disables_invalid_actions(tmp_path):
    qt_app = app()
    assert qt_app is not None
    db = Storage(tmp_path / "empty.sqlite3")
    try:
        carousel_id = db.create_carousel("BOOKS")
        page = CarouselPage(db)
        page.carousel.setCurrentIndex(page.carousel.findData(carousel_id))
        page.reload_slides()
        assert "Слайдів ще немає" in page.preview_label.text()
        assert page.slide_info.text() == "Слайдів: 0"
        assert page.add_button.isEnabled()
        assert page.add_button.text() == "Додати перший пін"
        assert not page.fullscreen_button.isEnabled()
        assert not page.previous_button.isEnabled()
        assert not page.next_button.isEnabled()
        assert not page.remove_button.isEnabled()
        assert not page.move_left_button.isEnabled()
        assert not page.move_right_button.isEnabled()
        assert not page.export_button.isEnabled()
        assert page.slides.isHidden()
        assert page.storyboard.isHidden()
        assert page.preview_label.width() == 170
        assert page.preview_label.height() == 255
        assert page.validation_status.text() == "PNG: —"
        page.close()
    finally:
        db.close()


def test_selected_slide_enables_context_actions_but_blocks_invalid_export(tmp_path):
    qt_app = app()
    assert qt_app is not None
    db = Storage(tmp_path / "slide.sqlite3")
    try:
        first = db.create("pins", title="First")
        second = db.create("pins", title="Second")
        carousel_id = db.create_carousel("BOOKS")
        db.set_carousel_slides(carousel_id, [first, second])
        page = CarouselPage(db)
        page.carousel.setCurrentIndex(page.carousel.findData(carousel_id))
        page.reload_slides()
        assert page.slides.count() == 2
        assert page.add_button.text() == "Додати пін з бібліотеки"
        assert page.fullscreen_button.isEnabled()
        assert not page.previous_button.isEnabled()
        assert page.next_button.isEnabled()
        assert page.remove_button.isEnabled()
        assert not page.move_left_button.isEnabled()
        assert page.move_right_button.isEnabled()
        assert not page.export_button.isEnabled()
        assert "PNG: не готово" in page.validation_status.text()
        assert page.slides.isHidden()
        assert not page.storyboard.isHidden()
        assert page.storyboard.iconSize().width() == 92
        assert page.storyboard.iconSize().height() == 125
        page.slides.setCurrentRow(1)
        assert page.previous_button.isEnabled()
        assert not page.next_button.isEnabled()
        assert page.move_left_button.isEnabled()
        assert not page.move_right_button.isEnabled()
        page.close()
    finally:
        db.close()


def test_compact_workspace_does_not_overlap_controls(tmp_path):
    qt_app = app()
    db = Storage(tmp_path / "geometry.sqlite3")
    try:
        pin = db.create("pins", title="Preview")
        carousel_id = db.create_carousel("BOOKS")
        db.set_carousel_slides(carousel_id, [pin])
        page = CarouselPage(db)
        page.resize(1000, 420)
        page.show()
        qt_app.processEvents()
        preview = page.preview_label.geometry()
        fullscreen = page.fullscreen_button.geometry()
        actions = page.add_button.geometry()
        assert preview.height() == 255
        assert not preview.intersects(fullscreen)
        assert not preview.intersects(actions)
        assert page.slides.isHidden()
        page.close()
    finally:
        db.close()
