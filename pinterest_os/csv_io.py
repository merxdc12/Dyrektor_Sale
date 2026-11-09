"""UTF-8 CSV exchange for local pin metadata; never auto-publishes."""
import csv

FIELDS = ("title", "description", "destination_url", "status", "board", "product")


def export_pins(storage, path):
    boards = {r["id"]: r["name"] for r in storage.all("boards")}
    products = {r["id"]: r["name"] for r in storage.all("products")}
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for pin in storage.all("pins"):
            writer.writerow({
                "title": pin["title"], "description": pin.get("description") or "",
                "destination_url": pin.get("destination_url") or "",
                "status": pin.get("status") or "DRAFT",
                "board": boards.get(pin.get("board_id"), ""),
                "product": products.get(pin.get("product_id"), ""),
            })


def import_pins(storage, path):
    """Validate entire file before writes; names must match existing records."""
    boards = {r["name"]: r["id"] for r in storage.all("boards")}
    products = {r["name"]: r["id"] for r in storage.all("products")}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):
            raise ValueError("CSV requires columns: " + ", ".join(FIELDS))
        rows = []
        for line, row in enumerate(reader, 2):
            title = (row.get("title") or "").strip()
            board = (row.get("board") or "").strip()
            product = (row.get("product") or "").strip()
            status = (row.get("status") or "DRAFT").strip() or "DRAFT"
            if not title:
                raise ValueError(f"Row {line}: title required")
            if board and board not in boards:
                raise ValueError(f"Row {line}: unknown board '{board}'")
            if product and product not in products:
                raise ValueError(f"Row {line}: unknown product '{product}'")
            if status not in {"DRAFT", "IN_REVIEW", "READY", "PUBLISHED"}:
                raise ValueError(f"Row {line}: invalid status")
            rows.append({
                "title": title, "description": row.get("description") or "",
                "destination_url": row.get("destination_url") or "",
                "status": status, "board_id": boards.get(board),
                "product_id": products.get(product),
            })
    # SQLite transaction ensures an invalid insert cannot partially import.
    with storage.conn:
        from .storage import utc_now
        for row in rows:
            storage.conn.execute(
                """INSERT INTO pins(title,description,destination_url,status,board_id,product_id,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (row["title"], row["description"], row["destination_url"], row["status"],
                 row["board_id"], row["product_id"], utc_now()),
            )
    return len(rows)
