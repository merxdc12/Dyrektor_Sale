"""Offline multi-image carousel preparation; no Pinterest API integration."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def validate_slides(slides: list[dict], minimum: int = 2, maximum: int = 10) -> list[str]:
    """Validate slide count, uniqueness, readable PNG headers and uniform dimensions."""
    errors = []
    if not minimum <= len(slides) <= maximum:
        errors.append(f"Carousel must contain {minimum}–{maximum} slides")
    ids = [slide["pin_id"] for slide in slides]
    if len(set(ids)) != len(ids):
        errors.append("Each pin may appear only once")
    sizes = set()
    for index, slide in enumerate(slides, 1):
        path_string = slide.get("png_path") or ""
        path = Path(path_string)
        if not path_string or not path.is_file():
            errors.append(f"Slide {index}: exported PNG missing")
        elif path.suffix.lower() != ".png":
            errors.append(f"Slide {index}: file must be PNG")
        else:
            try:
                with path.open("rb") as handle:
                    header = handle.read(24)
                if len(header) < 24 or header[:8] != bytes.fromhex("89504e470d0a1a0a") or header[12:16] != b"IHDR":
                    errors.append(f"Slide {index}: invalid PNG header")
                    continue
                width = int.from_bytes(header[16:20], "big")
                height = int.from_bytes(header[20:24], "big")
                if width <= 0 or height <= 0:
                    errors.append(f"Slide {index}: invalid PNG dimensions")
                else:
                    sizes.add((width, height))
            except OSError as exc:
                errors.append(f"Slide {index}: cannot read PNG ({exc})")
    if len(sizes) > 1:
        errors.append("Slides have different dimensions; export all slides at the same size")
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
