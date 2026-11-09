"""TIME 5: observed workload trends and bottlenecks, not causal conclusions."""
from collections import defaultdict
from datetime import datetime


def workload_trends(storage):
    """Use recorded UTC timestamps; avoid treating event count as completed work."""
    records = storage.conn.execute(
        "SELECT task, seconds, created_at FROM time_entries ORDER BY created_at, id"
    ).fetchall()
    by_week = defaultdict(lambda: {"seconds": 0, "entries": 0})
    by_task = defaultdict(lambda: {"seconds": 0, "entries": 0})
    invalid = 0
    for task, seconds, created_at in records:
        try:
            day = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            week = f"{day.isocalendar().year}-W{day.isocalendar().week:02d}"
        except (ValueError, AttributeError):
            invalid += 1
            continue
        by_week[week]["seconds"] += seconds
        by_week[week]["entries"] += 1
        by_task[task]["seconds"] += seconds
        by_task[task]["entries"] += 1
    weeks = [{"week": week, **totals} for week, totals in sorted(by_week.items())]
    tasks = [{"task": task, **totals} for task, totals in by_task.items()]
    tasks.sort(key=lambda row: (-row["seconds"], row["task"]))
    total = sum(item["seconds"] for item in tasks)
    for item in tasks:
        item["share_percent"] = round(item["seconds"] * 100 / total, 1) if total else 0
    return {"weeks": weeks, "tasks": tasks, "invalid_timestamps": invalid,
            "tracked_seconds": total}
