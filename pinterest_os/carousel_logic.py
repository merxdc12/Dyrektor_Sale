"""Offline multi-image carousel preparation; no Pinterest API integration."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def validate_slides(slides: list[dict], minimum: int = 2, maximum: int = 10) -> list[str]:
    errors = []
    if not minimum <= len(slides) <= maximum:
        errors.append(f"Carousel must contain {minimum}–{maximum} slides")
    ids = [slide["pin_id"] for slide in slides]
    if len(set(ids)) != len(ids):
        errors.append("Each pin may appear only once")
    for index, slide in enumerate(slides, 1):
        path = Path(slide.get("png_path") or "")
        if not slide.get("png_path") or not path.is_file():
            errors.append(f"Slide {index}: exported PNG missing")
        elif path.suffix.lower() != ".png":
            errors.append(f"Slide {index}: file must be PNG")
    return errors


def export_carousel(slides: list[dict], output: Path, title: str) -> Path:
    """Write an ordered ZIP of existing PNGs; never modifies source assets."""
    errors = validate_slides(slides)
    if errors:
        raise ValueError("; ".join(errors))
    output = Path(output)
    if output.suffix.lower() != ".zip":
        raise ValueError("Output must be a ZIP file")
    manifest = {"format": "ITHutir carousel v1", "title": title, "slides": []}
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for index, slide in enumerate(slides, 1):
            name = f"slide_{index:02d}.png"
            archive.write(Path(slide["png_path"]), arcname=name)
            manifest["slides"].append({"order": index, "file": name,
                                       "pin_id": slide["pin_id"], "title": slide["title"]})
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    return output
