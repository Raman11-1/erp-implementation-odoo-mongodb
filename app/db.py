"""MongoDB Atlas connection + collection/index setup.

Collections (middleware layer between external systems and Odoo ERP):
  migration_records   - legacy Excel rows + validation status (valid / rejected + reasons)
  staging_orders      - incoming orders, validated here before being pushed to Odoo
  inventory_snapshots - stock levels pulled from Odoo, used for low-stock alerts
  sync_audit_log      - every sync event: what, when, success/failure (change-propagation integrity)
  alerts              - low-stock alerts raised by the trigger watcher
"""
from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING, MongoClient

from app.config import MONGO_DB, MONGO_URI

_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
db = _client[MONGO_DB]

migration_records = db["migration_records"]
staging_orders = db["staging_orders"]
inventory_snapshots = db["inventory_snapshots"]
sync_audit_log = db["sync_audit_log"]
alerts = db["alerts"]


def now():
    return datetime.now(timezone.utc)


def ensure_indexes():
    migration_records.create_index([("entity", ASCENDING), ("key", ASCENDING)], unique=True)
    migration_records.create_index("status")
    staging_orders.create_index("order_ref", unique=True)
    staging_orders.create_index("status")
    inventory_snapshots.create_index("sku", unique=True)
    sync_audit_log.create_index([("timestamp", DESCENDING)])
    alerts.create_index([("sku", ASCENDING), ("status", ASCENDING)])


def audit(event: str, entity: str, ref: str, success: bool, details: dict | None = None):
    """Write one row to the audit trail. Every sync step calls this."""
    sync_audit_log.insert_one({
        "timestamp": now(),
        "event": event,
        "entity": entity,
        "ref": ref,
        "success": success,
        "details": details or {},
    })


def ping() -> bool:
    _client.admin.command("ping")
    return True
