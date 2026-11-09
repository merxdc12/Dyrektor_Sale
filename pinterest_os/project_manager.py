"""Read-only project inventory and non-destructive recent-project registry."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .project_files import DB_NAME, MANIFEST


def project_summary(folder: str | Path) -> dict:
    root = Path(folder).resolve()
    if not (root / DB_NAME).is_file() or not (root / MANIFEST).is_file():
        raise ValueError("Not an ITHutir project folder")
    conn = sqlite3.connect(f"file:{root / DB_NAME}?mode=ro", uri=True)
    try:
        counts = {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                  for name in ("products", "pins", "boards")}
        referenced = set()
        for raw, png in conn.execute("SELECT project_json,png_path FROM pin_designs"):
            data = json.loads(raw)
            for layer in data.get("layers", []):
                if layer.get("kind") == "image" and layer.get("path"):
                    path = Path(layer["path"])
                    if not path.is_absolute():
                        referenced.add(path.as_posix())
            if png and not Path(png).is_absolute():
                referenced.add(Path(png).as_posix())
    finally:
        conn.close()
    assets = sorted(p for p in (root / "assets").rglob("*") if p.is_file()) if (root / "assets").exists() else []
    inventory = []
    for file in assets:
        rel = file.relative_to(root).as_posix()
        inventory.append({"path": rel, "size": file.stat().st_size,
                          "referenced": rel in referenced})
    counts.update({"assets": inventory, "asset_count": len(inventory),
                   "unused_assets": sum(not x["referenced"] for x in inventory),
                   "bytes": sum(p.stat().st_size for p in root.rglob("*") if p.is_file())})
    return counts


def rename_project(folder: str | Path, new_name: str) -> Path:
    """Rename an INACTIVE project directory without editing its contents."""
    source = Path(folder).resolve()
    name = new_name.strip()
    if not name or name in {".", ".."} or "/" in name or "\\\\" in name:
        raise ValueError("Invalid project name")
    if not (source / DB_NAME).is_file() or not (source / MANIFEST).is_file():
        raise ValueError("Not an ITHutir project")
    target = source.with_name(name)
    if target.exists():
        raise FileExistsError("Target project folder already exists")
    source.rename(target)
    return target
