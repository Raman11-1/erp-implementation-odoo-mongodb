# Cutover Plan: Go-Live
**Client:** Kisan Tractor Parts Pvt. Ltd. · **Target go-live:** Monday 09:00 · **Cutover window:** Friday 18:00 – Sunday 20:00

## 1. Pre-cutover (T-7 to T-1 days)
| # | Activity | Owner | Done |
|---|---|---|---|
| 1 | UAT sign-off received from the client | Client PM | ☐ |
| 2 | Client corrects all records in the reconciliation report "Rejected Records" sheet | Client stores team | ☐ |
| 3 | Mock migration #2 run; success rate ≥ 98% | Implementation team | ☐ |
| 4 | User training completed (stores, purchase, sales) | Implementation team | ☐ |
| 5 | Production Odoo database and middleware deployed; `ODOO_DRY_RUN=false` | Implementation team | ☐ |

## 2. Cutover steps
| Step | Time | Activity | Validation |
|---|---|---|---|
| C1 | Fri 18:00 | **Data freeze**: legacy Excel locked, no new manual entries | Confirmation email from client |
| C2 | Fri 19:00 | Final physical stock count | Count sheet signed |
| C3 | Sat 09:00 | Run `python -m scripts.migrate` (masters, then opening stock) | Summary sheet: loaded counts match the expected counts |
| C4 | Sat 12:00 | Reconcile: total stock quantity in the ERP = physical count | Difference = 0 |
| C5 | Sat 14:00 | Start the middleware API and stock watcher | `/health` returns `live` |
| C6 | Sat 15:00 | Smoke test: 1 test order, 1 PO, 1 goods receipt | All complete; audit log shows success |
| C7 | Sun 18:00 | **Go/No-Go meeting** with the client | Signed decision |
| C8 | Mon 09:00 | Go-live; dealers' order channel switched to the API | First live order synced |

## 3. Rollback plan
Triggered if C4 or C6 fails and cannot be fixed before C7:
1. Stop the middleware and watcher.
2. Restore Odoo from the pre-cutover database backup.
3. Unfreeze legacy Excel; the business continues on the old process.
4. Root-cause analysis and a new cutover date agreed with the client.

## 4. Hypercare (post-go-live, 2 weeks)
- Daily 15-minute check-in call with the client's key users.
- Daily review of `/orders?status=failed`, `/alerts` and the audit log.
- Issues logged with severity (P1 = business stopped, P2 = workaround exists, P3 = cosmetic).
