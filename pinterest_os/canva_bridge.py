"""Canva interchange: SVG preserves text/vector objects when importer supports them.

Canva does not expose a general lossless layer-tree export in this integration.
This module deliberately never claims to reconstruct arbitrary Canva layers.
"""
from __future__ import annotations
import html
import json
from pathlib import Path
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def project_to_svg(project: dict, destination: str) -> None:
    if project.get("version") != 1:
        raise ValueError("Unsupported project version")
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": str(project["width"]), "height": str(project["height"]),
        "viewBox": f"0 0 {project['width']} {project['height']}",
    })
    ET.SubElement(root, f"{{{SVG_NS}}}rect", {
        "width": "100%", "height": "100%",
        "fill": project.get("background", "#ffffff"),
    })
    layers = sorted(project.get("layers", []), key=lambda layer: layer.get("z", 0))
    for layer in layers:
        if layer["kind"] == "text":
            # Preserve text as SVG <text>, not vector outlines or a raster image.
            size = int(layer["size"])
            x = float(layer["x"])
            width = float(layer.get("width", 820))
            align = layer.get("align", "center")
            anchor = {"left": "start", "center": "middle", "right": "end"}[align]
            tx = x + (0 if align == "left" else width / 2 if align == "center" else width)
            text = ET.SubElement(root, f"{{{SVG_NS}}}text", {
                "x": str(tx), "y": str(float(layer["y"]) + size),
                "font-family": layer.get("font", "DejaVu Sans"),
                "font-size": str(size), "font-weight": "bold",
                "text-anchor": anchor, "fill": layer.get("color", "#000000"),
                "data-ithutir-layer": "text",
            })
            text.text = layer["text"]
        elif layer["kind"] == "image":
            # Embedded data URI avoids publishing private image paths to Canva.
            import base64
            import mimetypes
            path = Path(layer["path"])
            mime = mimetypes.guess_type(path.name)[0]
            if mime not in {"image/png", "image/jpeg", "image/webp"}:
                raise ValueError(f"Unsupported image format: {path.name}")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            ET.SubElement(root, f"{{{SVG_NS}}}image", {
                "x": str(layer["x"]), "y": str(layer["y"]),
                "width": str(layer["width"]), "height": str(layer["height"]),
                "href": f"data:{mime};base64,{encoded}",
                "data-ithutir-layer": "image",
            })
        else:
            raise ValueError(f"Cannot export unsupported layer: {layer.get('kind')}")
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)


def validate_canva_design_id(value: str) -> str:
    import re
    if not re.fullmatch(r"D[A-Za-z0-9_-]{10}", value):
        raise ValueError("Canva design ID must start with D and contain 11 characters")
    return value
