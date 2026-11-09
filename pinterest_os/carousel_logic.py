"""Offline multi-image carousel preparation; no Pinterest API integration."""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def png_dimensions(path: Path) -> tuple[int, int]:
    """Validate complete PNG chunk framing, CRCs and IEND."""
    data = Path(path).read_bytes()
    if not data.startswith(bytes.fromhex("89504e470d0a1a0a")):
        raise ValueError("Invalid PNG signature")
    pos = 8
    dimensions = None
    ended = False
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        end = pos + 12 + length
        if end > len(data):
            raise ValueError("Truncated PNG chunk")
        chunk_type = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        crc = int.from_bytes(data[end - 4:end], "big")
        if zlib.crc32(chunk_type + payload) & 0xffffffff != crc:
            raise ValueError("PNG chunk CRC mismatch")
        if pos == 8:
            if chunk_type != b"IHDR" or length != 13:
                raise ValueError("Missing PNG IHDR")
            dimensions = struct.unpack(">II", payload[:8])
            if not all(dimensions):
                raise ValueError("Invalid PNG dimensions")
        if chunk_type == b"IEND":
            if length != 0 or end != len(data):
                raise ValueError("Invalid PNG end")
            ended = True
            break
        pos = end
    if not ended or dimensions is None:
        raise ValueError("Missing PNG IEND")
    return dimensions


def validate_slides(slides: list[dict], minimum: int = 2, maximum: int = 10) -> list[str]:
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
                sizes.add(png_dimensions(path))
            except (OSError, ValueError) as exc:
                errors.append(f"Slide {index}: {exc}")
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
