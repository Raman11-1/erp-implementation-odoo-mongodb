"""Build docs/02_UAT_Test_Cases.xlsx.

'Actual Result' and 'Status' reflect the dry-run test executed on the middleware
(see README). Re-execute against live Odoo before UAT sign-off.
"""
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill

OUT = Path(__file__).resolve().parent.parent / "docs" / "02_UAT_Test_Cases.xlsx"

CASES = [
    # id, module, scenario, steps, expected, actual, status
    ("TC-01", "Migration", "Load valid products", "Run migrate.py on legacy workbook",
     "Valid products loaded to ERP", "56 of 61 products loaded", "Pass"),
    ("TC-02", "Migration", "Reject product with missing name", "Row 7 has blank Product Name",
     "Row rejected: 'Product Name is missing'", "Rejected with expected reason", "Pass"),
    ("TC-03", "Migration", "Reject negative cost price", "Row 11 cost = -450",
     "Row rejected: cost must be positive", "Rejected with expected reason", "Pass"),
    ("TC-04", "Migration", "Reject sale price below cost", "Row 16 sale = 50% of cost",
     "Row rejected: sale below cost", "Rejected with expected reason", "Pass"),
    ("TC-05", "Migration", "Reject duplicate SKU", "KTP-001-Std appears twice",
     "Second occurrence rejected", "Row 62 rejected as duplicate", "Pass"),
    ("TC-06", "Migration", "Reject vendor with invalid email", "V004 email 'omsai-at-gmail'",
     "Vendor rejected", "Rejected with expected reason", "Pass"),
    ("TC-07", "Migration", "Reject vendor without GSTIN", "V007 GSTIN blank",
     "Vendor rejected", "Rejected with expected reason", "Pass"),
    ("TC-08", "Migration", "Reject non-numeric credit limit", "C008 credit = 'one lakh'",
     "Customer rejected", "Rejected with expected reason", "Pass"),
    ("TC-09", "Migration", "Block stock for rejected/unknown SKU", "Stock rows for KTP-999-ZZ and rejected SKUs",
     "Stock rows rejected (dependency rule)", "6 stock rows rejected", "Pass"),
    ("TC-10", "Migration", "Reconciliation report generated", "Open migration_reconciliation_report.xlsx",
     "Summary + Rejected Records sheets", "Both sheets present, 16 rejected rows", "Pass"),
    ("TC-11", "Order-to-Cash", "Valid single-line order", "POST /orders WEB-1001 (C001, 5 units)",
     "Sales order created; status synced", "Synced, SO 72, total 35,144.15", "Pass"),
    ("TC-12", "Order-to-Cash", "Valid multi-line order", "POST /orders WEB-1002 (2 lines)",
     "Sales order created with 2 lines", "Synced, SO 73, total 39,337.56", "Pass"),
    ("TC-13", "Order-to-Cash", "Unknown customer", "POST /orders WEB-1003 customer C999",
     "Order rejected with reason", "Rejected: Customer C999 not found", "Pass"),
    ("TC-14", "Order-to-Cash", "Unknown SKU", "POST /orders WEB-1004 SKU KTP-999-ZZ",
     "Order rejected with reason", "Rejected: SKU not found", "Pass"),
    ("TC-15", "Order-to-Cash", "Insufficient stock", "POST /orders WEB-1005 qty 100000",
     "Order rejected showing available qty", "Rejected: available 138", "Pass"),
    ("TC-16", "Order-to-Cash", "Duplicate order submission", "POST WEB-1001 a second time",
     "HTTP 409, no second sales order", "HTTP 409 returned", "Pass"),
    ("TC-17", "Inventory", "Stock reduces after order", "Check KTP-001-Std after WEB-2001",
     "Qty reduced by ordered amount", "43 -> 22", "Pass"),
    ("TC-18", "Procure-to-Pay", "Low-stock alert raised", "Order pushes KTP-001-Std below reorder level 25",
     "Open alert with suggested reorder qty", "Alert raised automatically (~5 s)", "Pass"),
    ("TC-19", "Procure-to-Pay", "Alert closes when stock recovers", "Receive goods for an alerted SKU",
     "Alert status -> closed", "", "Not run (needs live Odoo goods receipt)"),
    ("TC-20", "Audit", "Every sync event logged", "GET /audit",
     "Entries for received, validation, sync, alerts", "All event types present", "Pass"),
]


def main():
    df = pd.DataFrame(CASES, columns=["Test ID", "Module", "Scenario", "Steps / Test Data",
                                      "Expected Result", "Actual Result", "Status"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="UAT", index=False)
        ws = xw.sheets["UAT"]
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
        for col, width in zip("ABCDEFG", (9, 15, 34, 42, 38, 36, 14)):
            ws.column_dimensions[col].width = width
        green, amber = PatternFill("solid", fgColor="C6EFCE"), PatternFill("solid", fgColor="FFEB9C")
        for row in ws.iter_rows(min_row=2, min_col=7, max_col=7):
            row[0].fill = green if row[0].value == "Pass" else amber
        ws.freeze_panes = "A2"
    print(f"Wrote {OUT}  ({(df.Status == 'Pass').sum()}/{len(df)} passed)")


if __name__ == "__main__":
    main()
