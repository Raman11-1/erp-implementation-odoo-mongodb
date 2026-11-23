"""Legacy master-data migration: Excel -> validate -> MongoDB staging -> Odoo -> reconciliation report.

Run:  python -m scripts.migrate
"""
from pathlib import Path

import pandas as pd

from app import validation as v
from app.db import audit, ensure_indexes, migration_records, now
from app.odoo_client import OdooClient

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "legacy_master_data.xlsx"
REPORT = ROOT / "data" / "output" / "migration_reconciliation_report.xlsx"

# entity -> (sheet, key column, validator)
ENTITIES = [
    ("product", "Products", "SKU", v.validate_product),
    ("vendor", "Vendors", "Vendor Code", v.validate_vendor),
    ("customer", "Customers", "Customer Code", v.validate_customer),
    ("stock", "Opening Stock", "SKU", None),  # validated against the product master
]


def clean(row: dict) -> dict:
    return {k: (None if isinstance(x, float) and x != x else x) for k, x in row.items()}


def stage(entity, sheet, key_col, validator, sheets, valid_skus):
    """Validate every row and upsert it into migration_records. Returns list of staged docs."""
    seen, staged = set(), []
    for i, raw in enumerate(sheets[sheet].to_dict("records"), start=2):  # row 1 = Excel header
        row = clean(raw)
        key = str(row.get(key_col) or f"<blank row {i}>")
        errs = v.validate_stock(row, valid_skus) if entity == "stock" else validator(row)
        if key in seen:
            errs.append(f"Duplicate {key_col} in source file")
        seen.add(key)
        doc = {"entity": entity, "key": key if key not in [d["key"] for d in staged] else f"{key}#row{i}",
               "excel_row": i, "data": row, "status": "rejected" if errs else "valid",
               "errors": errs, "staged_at": now()}
        migration_records.replace_one({"entity": entity, "key": doc["key"]}, doc, upsert=True)
        staged.append(doc)
        if entity == "product" and not errs:
            valid_skus.add(key)
    return staged


def load(entity, doc, odoo: OdooClient):
    d = doc["data"]
    if entity == "product":
        odoo.upsert_product(d["SKU"], d["Product Name"], float(d["Cost Price"]),
                            float(d["Sale Price"]), int(d["Reorder Level"]))
    elif entity == "vendor":
        odoo.upsert_partner(d["Vendor Code"], d["Vendor Name"], d["Email"], is_vendor=True)
    elif entity == "customer":
        odoo.upsert_partner(d["Customer Code"], d["Customer Name"], d["Email"], is_vendor=False)
    elif entity == "stock":
        odoo.set_stock(d["SKU"], float(d["Quantity"]))


def main():
    ensure_indexes()
    odoo = OdooClient()
    print(f"Odoo mode: {'DRY-RUN (simulated)' if odoo.dry_run else 'LIVE'}")
    sheets = pd.read_excel(SOURCE, sheet_name=None)
    migration_records.delete_many({})  # each run is a fresh mock load
    valid_skus: set[str] = set()

    summary, rejected_rows = [], []
    for entity, sheet, key_col, validator in ENTITIES:
        staged = stage(entity, sheet, key_col, validator, sheets, valid_skus)
        loaded = failed = 0
        for doc in staged:
            if doc["status"] != "valid":
                rejected_rows.append({"Entity": entity, "Excel Row": doc["excel_row"], "Key": doc["key"],
                                      "Errors": "; ".join(doc["errors"])})
                continue
            try:
                load(entity, doc, odoo)
                migration_records.update_one({"entity": entity, "key": doc["key"]},
                                             {"$set": {"status": "loaded", "loaded_at": now()}})
                audit("migration_load", entity, doc["key"], True)
                loaded += 1
            except Exception as e:  # load failure is recorded, not fatal
                migration_records.update_one({"entity": entity, "key": doc["key"]},
                                             {"$set": {"status": "load_failed", "errors": [str(e)]}})
                audit("migration_load", entity, doc["key"], False, {"error": str(e)})
                failed += 1
        total = len(staged)
        rejected = sum(1 for d in staged if d["status"] == "rejected")
        summary.append({"Entity": entity, "Records In": total, "Loaded": loaded,
                        "Rejected (validation)": rejected, "Load Failed": failed,
                        "Success %": round(100 * loaded / total, 1) if total else 0})
        print(f"  {entity:9s} in={total:3d} loaded={loaded:3d} rejected={rejected:2d} failed={failed}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(REPORT, engine="openpyxl") as xw:
        pd.DataFrame(summary).to_excel(xw, sheet_name="Summary", index=False)
        pd.DataFrame(rejected_rows).to_excel(xw, sheet_name="Rejected Records", index=False)
    print(f"Reconciliation report: {REPORT}")


if __name__ == "__main__":
    main()
