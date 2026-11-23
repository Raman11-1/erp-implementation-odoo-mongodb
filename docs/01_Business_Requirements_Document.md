# Business Requirements Document (BRD)
**Client:** Kisan Tractor Parts Pvt. Ltd. (simulated) · **Project:** ERP Implementation (Odoo Community) · **Version:** 1.0

## 1. Company background
Kisan Tractor Parts manufactures and distributes tractor spare parts (engine, transmission, hydraulics, electrical, body) from one warehouse in Jalgaon to about 10 dealer customers across Maharashtra, Gujarat, Madhya Pradesh and Punjab. It buys components from 8 vendors.

## 2. Current (as-is) process and pain points
| Area | Current process | Pain point |
|---|---|---|
| Product master | Excel sheet maintained by the stores team | Duplicate SKUs, missing units, wrong prices |
| Purchasing | Phone/email orders to vendors, no PO number | No visibility of what is on order; late reorders |
| Inventory | Monthly manual stock count | Stock-outs discovered only when a dealer orders |
| Sales orders | Dealers email or call; entered manually | Orders accepted without checking stock; duplicates |
| Reporting | Manual Excel compilation | No real-time view for management |

## 3. Objectives
1. One system of record for products, vendors, customers and stock.
2. Standard **Procure-to-Pay** and **Order-to-Cash** cycles in the ERP.
3. Automatic low-stock alerts, so purchasing is triggered before stock-outs.
4. Online dealer orders flowing into the ERP automatically, with validation.
5. Clean master data migrated from legacy Excel, with every rejected record explained.

## 4. Scope
**In scope:** Inventory, Purchase, Sales and Manufacturing (BoM) modules; master-data migration; order integration middleware; low-stock alerting; UAT; cutover.
**Out of scope:** Accounting/GST filing, payroll, multi-warehouse, mobile app.

## 5. To-be processes
**Procure-to-Pay (P2P)**
```
Low-stock alert -> Purchase Request -> RFQ -> Purchase Order -> Goods Receipt -> Vendor Bill -> Payment
```
**Order-to-Cash (O2C)**
```
Dealer order (API) -> Middleware validation -> Sales Order (confirmed) -> Delivery -> Customer Invoice -> Payment
```

## 6. Functional requirements
| ID | Requirement | Priority | Delivered by |
|---|---|---|---|
| FR-01 | Every product has a unique SKU, a name, a category, a UoM, cost and sale price | High | Migration validation |
| FR-02 | Sale price must not be below cost price | Medium | Migration validation |
| FR-03 | Vendors must have a valid email and GSTIN | High | Migration validation |
| FR-04 | Opening stock is loaded only for validated products | High | Migration (dependency rule) |
| FR-05 | Rejected legacy records are reported with reasons for the client to correct | High | Reconciliation report |
| FR-06 | External orders are checked for valid customer, valid SKU and available stock before entering the ERP | High | Middleware `POST /orders` |
| FR-07 | Duplicate order submissions are blocked | High | Unique index on `order_ref` |
| FR-08 | A low-stock alert is raised when quantity falls below the reorder level, with a suggested reorder quantity | High | Change-stream trigger |
| FR-09 | Every integration event is logged (what, when, success/failure) | Medium | `sync_audit_log` |

## 7. Non-functional requirements
- Integration failures must never lose an order: orders are staged first, then synced.
- Audit trail kept for every data movement.
- Credentials stored outside the code (`.env`).

## 8. Assumptions and risks
| Risk | Mitigation |
|---|---|
| Legacy data quality is poor | Validation rules plus a reconciliation report; client fixes and reloads |
| Users resist the new process | Training session and a quick-reference guide before go-live |
| Integration downtime | Orders are staged in MongoDB and retried; the audit log shows failures |
