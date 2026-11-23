"""Real-time low-stock trigger using a MongoDB Change Stream on inventory_snapshots.

Equivalent to an Atlas Database Trigger: reacts to every insert/update of a stock snapshot.
  qty <  reorder_level -> open a low-stock alert with a suggested reorder quantity
  qty >= reorder_level -> close any open alert for that SKU

Run (keep it running in its own terminal):  python -m scripts.stock_watcher
"""
import sys

from app.db import alerts, audit, inventory_snapshots, now


def evaluate(doc):
    sku, qty, level = doc["sku"], doc.get("qty", 0), doc.get("reorder_level", 0)
    open_alert = alerts.find_one({"sku": sku, "status": "open"})
    if qty < level and not open_alert:
        suggested = max(level * 2 - qty, level)  # bring stock back to 2x reorder level
        alerts.insert_one({"sku": sku, "name": doc.get("name"), "qty": qty, "reorder_level": level,
                           "suggested_reorder_qty": suggested, "status": "open", "raised_at": now()})
        audit("low_stock_alert", "inventory", sku, True, {"qty": qty, "reorder_level": level})
        print(f"[ALERT]    {sku}: qty {qty} < reorder level {level} -> reorder {suggested}")
    elif qty >= level and open_alert:
        alerts.update_one({"_id": open_alert["_id"]}, {"$set": {"status": "closed", "closed_at": now()}})
        audit("low_stock_resolved", "inventory", sku, True, {"qty": qty})
        print(f"[RESOLVED] {sku}: qty back to {qty}")


def main():
    sys.stdout.reconfigure(line_buffering=True)  # show alerts in the terminal immediately
    print("Initial scan of current snapshots...")
    for doc in inventory_snapshots.find():
        evaluate(doc)
    print("Watching inventory_snapshots for changes (Ctrl+C to stop)...")
    pipeline = [{"$match": {"operationType": {"$in": ["insert", "update", "replace"]}}}]
    with inventory_snapshots.watch(pipeline, full_document="updateLookup") as stream:
        for change in stream:
            if change.get("fullDocument"):
                evaluate(change["fullDocument"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Stopped.")
