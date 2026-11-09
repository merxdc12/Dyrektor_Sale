"""Evidence-based Pinterest metrics computed only from imported CSV records."""


def ctr(clicks, impressions):
    """Outbound click-through rate in percent; None means no denominator."""
    return (100.0 * clicks / impressions) if impressions else None


def pin_performance(storage):
    rows = storage.conn.execute(
        """SELECT p.id,p.title,COUNT(m.date),SUM(m.impressions),
                  SUM(m.outbound_clicks),SUM(m.saves)
           FROM pinterest_metrics m JOIN pins p ON p.id=m.pin_id
           GROUP BY p.id,p.title ORDER BY SUM(m.outbound_clicks) DESC,p.id"""
    ).fetchall()
    return [
        {"pin_id": pin_id, "title": title, "days": days,
         "impressions": impressions, "outbound_clicks": clicks,
         "saves": saves, "ctr": ctr(clicks, impressions)}
        for pin_id, title, days, impressions, clicks, saves in rows
    ]


def daily_performance(storage, pin_id=None):
    if pin_id is not None and not isinstance(pin_id, int):
        raise ValueError("pin_id must be an integer")
    query = """SELECT date,SUM(impressions),SUM(outbound_clicks),SUM(saves)
               FROM pinterest_metrics"""
    params = ()
    if pin_id is not None:
        query += " WHERE pin_id=?"
        params = (pin_id,)
    query += " GROUP BY date ORDER BY date"
    return storage.conn.execute(query, params).fetchall()


def group_performance(storage, dimension="board"):
    """Aggregate imported metrics by CURRENT local board or board category.

    Group membership is not historical: changing a pin's board reattributes
    previously imported daily metrics. Unassigned pins are kept separate.
    """
    if dimension not in {"board", "category"}:
        raise ValueError("Unsupported grouping")
    if dimension == "board":
        group_id = "COALESCE(CAST(b.id AS TEXT), 'unassigned')"
        group_name = "COALESCE(b.name, 'Unassigned')"
    else:
        group_id = "COALESCE(b.category, 'Unassigned')"
        group_name = group_id
    query = f"""SELECT {group_id}, {group_name}, COUNT(DISTINCT p.id),
                       SUM(m.impressions), SUM(m.outbound_clicks), SUM(m.saves)
                FROM pinterest_metrics m
                JOIN pins p ON p.id=m.pin_id
                LEFT JOIN boards b ON b.id=p.board_id
                GROUP BY {group_id}, {group_name}
                ORDER BY SUM(m.outbound_clicks) DESC, {group_name}"""
    rows = storage.conn.execute(query).fetchall()
    return [
        {"group_id": key, "name": name, "pins": pins,
         "impressions": impressions, "outbound_clicks": clicks,
         "saves": saves, "ctr": ctr(clicks, impressions)}
        for key, name, pins, impressions, clicks, saves in rows
    ]
