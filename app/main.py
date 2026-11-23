"""Kisan ERP Middleware - REST integration layer between external systems and Odoo ERP.

Flow for an incoming order (mirrors an ODS -> ODL staging pattern):
  received (staged in MongoDB) -> validated -> pushed to Odoo -> synced | rejected | failed
Every step is written to sync_audit_log.

Run:  uvicorn app.main:app --reload     then open http://127.0.0.1:8000/docs
"""
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.db import (alerts, audit, ensure_indexes, inventory_snapshots, migration_records, now,
                    staging_orders, sync_audit_log)
from app.odoo_client import OdooClient

app = FastAPI(title="Kisan ERP Middleware",
              description="Stages, validates and syncs external orders and inventory with Odoo ERP.")


@app.on_event("startup")
def _startup():
    ensure_indexes()


def _clean(doc):
    doc.pop("_id", None)
    return doc


# ---------------- models ----------------
class OrderLine(BaseModel):
    sku: str
    qty: float = Field(gt=0)


class IncomingOrder(BaseModel):
    order_ref: str = Field(description="Unique order number from the external (e-commerce/dealer) system")
    customer_code: str
    lines: list[OrderLine] = Field(min_length=1)


# ---------------- endpoints ----------------
@app.get("/health")
def health():
    return {"status": "ok", "odoo_mode": "dry-run" if OdooClient().dry_run else "live"}


@app.post("/orders", status_code=201)
def receive_order(order: IncomingOrder):
    # 1. Stage (unique index on order_ref blocks duplicate submissions)
    try:
        staging_orders.insert_one({**order.model_dump(), "status": "received", "errors": [],
                                   "received_at": now()})
    except DuplicateKeyError:
        raise HTTPException(409, f"Order {order.order_ref} already received")
    audit("order_received", "order", order.order_ref, True)

    # 2. Validate against ERP master data
    odoo = OdooClient()
    errors, priced = [], []
    partner_id = odoo.find_partner(order.customer_code)
    if not partner_id:
        errors.append(f"Customer {order.customer_code} not found in ERP")
    for line in order.lines:
        info = odoo.product_info(line.sku)
        if not info:
            errors.append(f"SKU {line.sku} not found in ERP")
        elif info["qty"] < line.qty:
            errors.append(f"Insufficient stock for {line.sku}: requested {line.qty}, available {info['qty']}")
        else:
            priced.append({"sku": line.sku, "qty": line.qty, "price": info["price"]})

    if errors:
        staging_orders.update_one({"order_ref": order.order_ref},
                                  {"$set": {"status": "rejected", "errors": errors}})
        audit("order_validation", "order", order.order_ref, False, {"errors": errors})
        return {"order_ref": order.order_ref, "status": "rejected", "errors": errors}

    # 3. Push to Odoo
    try:
        so_id = odoo.create_sale_order(partner_id, priced, order.order_ref)
    except Exception as e:
        staging_orders.update_one({"order_ref": order.order_ref},
                                  {"$set": {"status": "failed", "errors": [str(e)]}})
        audit("order_sync", "order", order.order_ref, False, {"error": str(e)})
        raise HTTPException(502, f"Odoo sync failed: {e}")

    total = round(sum(l["qty"] * l["price"] for l in priced), 2)
    staging_orders.update_one({"order_ref": order.order_ref},
                              {"$set": {"status": "synced", "odoo_sale_order_id": so_id,
                                        "order_total": total, "synced_at": now()}})
    audit("order_sync", "order", order.order_ref, True, {"odoo_sale_order_id": so_id, "total": total})
    sync_inventory()  # refresh snapshots so the low-stock trigger sees the new levels
    return {"order_ref": order.order_ref, "status": "synced", "odoo_sale_order_id": so_id,
            "order_total": total}


@app.get("/orders")
def list_orders(status: Literal["received", "synced", "rejected", "failed"] | None = None):
    q = {"status": status} if status else {}
    return [_clean(o) for o in staging_orders.find(q).sort("received_at", -1)]


@app.post("/inventory/sync")
def sync_inventory():
    """Pull stock levels from Odoo into inventory_snapshots (reorder level comes from migrated master data)."""
    reorder = {r["key"]: r["data"].get("Reorder Level")
               for r in migration_records.find({"entity": "product", "status": "loaded"})}
    levels = OdooClient().get_stock_levels()
    for s in levels:
        inventory_snapshots.update_one(
            {"sku": s["sku"]},
            {"$set": {"name": s["name"], "qty": s["qty"],
                      "reorder_level": reorder.get(s["sku"], 0), "updated_at": now()}},
            upsert=True)
    audit("inventory_sync", "inventory", "all", True, {"products": len(levels)})
    return {"synced_products": len(levels)}


@app.get("/inventory/low-stock")
def low_stock():
    return [_clean(d) for d in inventory_snapshots.find({"$expr": {"$lt": ["$qty", "$reorder_level"]}})]


@app.get("/alerts")
def list_alerts(status: Literal["open", "closed"] = "open"):
    return [_clean(a) for a in alerts.find({"status": status}).sort("raised_at", -1)]


@app.get("/audit")
def audit_log(limit: int = Query(50, le=500)):
    return [_clean(a) for a in sync_audit_log.find().sort("timestamp", -1).limit(limit)]


@app.get("/migration/summary")
def migration_summary():
    pipeline = [{"$group": {"_id": {"entity": "$entity", "status": "$status"}, "count": {"$sum": 1}}}]
    out: dict = {}
    for r in migration_records.aggregate(pipeline):
        out.setdefault(r["_id"]["entity"], {})[r["_id"]["status"]] = r["count"]
    return out
