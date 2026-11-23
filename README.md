# Kisan ERP Implementation: Odoo + MongoDB Integration Middleware

End-to-end ERP implementation for a simulated tractor-parts manufacturer (**Kisan Tractor Parts Pvt. Ltd.**). It covers the full lifecycle: requirements → configuration → data migration → integration → testing → cutover.

```
Legacy Excel / Dealer orders
          │ (REST)
          ▼
 FastAPI Middleware ──────► MongoDB Atlas
   validate & stage          ├─ migration_records   (row-level validation status)
          │                  ├─ staging_orders      (received → synced / rejected / failed)
          │ (XML-RPC API)    ├─ inventory_snapshots ──► Change Stream trigger ──► alerts
          ▼                  └─ sync_audit_log      (every sync event)
      Odoo ERP
 (Inventory, Purchase, Sales, Manufacturing)
```

## Business cycles covered
- **Procure-to-Pay:** low-stock alert → suggested reorder quantity → purchase
- **Order-to-Cash:** dealer order → validation → confirmed sales order → stock reduction

## Project structure
| Path | What it does |
|---|---|
| `app/config.py` | Settings from `.env` |
| `app/db.py` | MongoDB collections, indexes, audit helper |
| `app/validation.py` | Business rules for master-data migration |
| `app/odoo_client.py` | Odoo XML-RPC client (with dry-run simulator) |
| `app/main.py` | FastAPI middleware (REST endpoints) |
| `scripts/generate_legacy_data.py` | Creates the client's messy legacy Excel workbook |
| `scripts/migrate.py` | Extract → validate → stage → load → reconciliation report |
| `scripts/stock_watcher.py` | Real-time low-stock trigger (MongoDB Change Stream) |
| `scripts/demo_orders.py` | Sends sample good and bad orders |
| `scripts/build_uat_workbook.py` | Builds the UAT test-case workbook |
| `docs/` | BRD, UAT test cases, cutover plan, weekly status report |

## Setup
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then put your MongoDB Atlas URI in .env
```

## Run the demo (3 terminals)
```powershell
# 1. Create legacy data and migrate it
python -m scripts.generate_legacy_data
python -m scripts.migrate                 # -> data/output/migration_reconciliation_report.xlsx

# 2. Start the middleware          (terminal 1)
uvicorn app.main:app --port 8000          # API docs: http://127.0.0.1:8000/docs

# 3. Start the low-stock trigger   (terminal 2)
python -m scripts.stock_watcher

# 4. Send demo orders              (terminal 3)
python -m scripts.demo_orders
```

## Results (dry-run)
| Metric | Result |
|---|---|
| Legacy records migrated | 125 / 141 (89%); 16 rejected with reasons |
| Orders tested | 2 synced, 3 rejected with reasons, 1 duplicate blocked (HTTP 409) |
| Low-stock alerts | Raised automatically by the change-stream trigger |
| UAT | 19 / 20 passed (1 pending live Odoo) |

## Switching to real Odoo
1. Install **Odoo 17/18 Community** using the Windows installer from odoo.com (it bundles PostgreSQL).
2. Open `http://localhost:8069`, create a database named `kisan_erp`, and install the **Inventory, Purchase, Sales, Manufacturing** apps.
3. In `.env`, set `ODOO_PASSWORD` to your admin password and `ODOO_DRY_RUN=false`.
4. Run `python -m scripts.migrate` again. The data now appears in Odoo's screens.
