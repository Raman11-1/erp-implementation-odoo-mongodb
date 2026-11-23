"""Create the client's 'legacy' master data workbook (data/legacy_master_data.xlsx).

Simulates what Kisan Tractor Parts Pvt. Ltd. hands over from its old system:
mostly good data, with realistic errors planted on purpose so the migration
validation has something to catch.
"""
import random
from pathlib import Path

import pandas as pd

random.seed(42)
OUT = Path(__file__).resolve().parent.parent / "data" / "legacy_master_data.xlsx"

PARTS = [
    ("Clutch Plate", "Transmission"), ("Brake Shoe", "Brakes"), ("Hydraulic Pump", "Hydraulics"),
    ("Fuel Filter", "Engine"), ("Oil Filter", "Engine"), ("Air Filter", "Engine"),
    ("Piston Ring Set", "Engine"), ("Gear Shaft", "Transmission"), ("Steering Rod", "Steering"),
    ("Radiator", "Cooling"), ("Fan Belt", "Cooling"), ("Headlamp Assembly", "Electrical"),
    ("Starter Motor", "Electrical"), ("Alternator", "Electrical"), ("Wheel Hub", "Axle"),
    ("Axle Bearing", "Axle"), ("PTO Shaft", "Transmission"), ("Seat Assembly", "Body"),
    ("Mudguard", "Body"), ("Hydraulic Hose", "Hydraulics"),
]
CITIES = ["Pune", "Nagpur", "Jalgaon", "Ahmedabad", "Rajkot", "Indore", "Ludhiana", "Wardha"]


def products():
    rows = []
    for i, (name, cat) in enumerate(PARTS, start=1):
        for variant in ("Std", "HD", "XL"):
            cost = round(random.uniform(150, 9000), 2)
            rows.append({
                "SKU": f"KTP-{i:03d}-{variant}",
                "Product Name": f"{name} {variant}",
                "Category": cat,
                "UoM": "Units",
                "Cost Price": cost,
                "Sale Price": round(cost * random.uniform(1.2, 1.6), 2),
                "Reorder Level": random.choice([10, 20, 25, 50]),
            })
    # planted errors
    rows.append({**rows[0]})                                   # duplicate SKU
    rows[5]["Product Name"] = ""                               # missing name
    rows[9]["Cost Price"] = -450.0                             # negative cost
    rows[14]["Sale Price"] = rows[14]["Cost Price"] * 0.5      # sale below cost
    rows[22]["UoM"] = None                                     # missing UoM
    return pd.DataFrame(rows)


def vendors():
    names = ["Bharat Forge Supplies", "Shakti Hydraulics", "Mahalaxmi Bearings", "Om Sai Electricals",
             "Deccan Filters", "Gujarat Steel Works", "Punjab Auto Components", "Vidarbha Rubber Co"]
    rows = [{
        "Vendor Code": f"V{i:03d}",
        "Vendor Name": n,
        "City": random.choice(CITIES),
        "Email": f"sales@{n.split()[0].lower()}{i}.in",
        "GSTIN": f"27ABCDE{1000 + i}F1Z{i}",
        "Payment Terms (days)": random.choice([15, 30, 45]),
    } for i, n in enumerate(names, start=1)]
    rows[3]["Email"] = "omsai-at-gmail"      # invalid email
    rows[6]["GSTIN"] = ""                    # missing GSTIN
    return pd.DataFrame(rows)


def customers():
    names = ["Shree Krishna Tractors", "Jai Kisan Agro", "Annadata Motors", "Green Field Dealers",
             "Sai Agro Services", "Hari Om Tractors", "Balaji Farm Equipments", "Ganesh Krishi Kendra",
             "Narmada Agro Traders", "Shivam Tractor House"]
    rows = [{
        "Customer Code": f"C{i:03d}",
        "Customer Name": n,
        "City": random.choice(CITIES),
        "Email": f"contact@{n.split()[0].lower()}{i}.com",
        "Credit Limit": random.choice([50000, 100000, 200000]),
    } for i, n in enumerate(names, start=1)]
    rows.append({**rows[2]})                 # duplicate customer
    rows[7]["Credit Limit"] = "one lakh"     # non-numeric
    return pd.DataFrame(rows)


def opening_stock(prod_df):
    skus = prod_df["SKU"].drop_duplicates().tolist()
    rows = [{"SKU": s, "Warehouse": "WH-Jalgaon", "Quantity": random.randint(0, 200)} for s in skus]
    rows.append({"SKU": "KTP-999-ZZ", "Warehouse": "WH-Jalgaon", "Quantity": 40})  # unknown SKU
    rows[3]["Quantity"] = -5                                                        # negative qty
    return pd.DataFrame(rows)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    p = products()
    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        p.to_excel(xw, sheet_name="Products", index=False)
        vendors().to_excel(xw, sheet_name="Vendors", index=False)
        customers().to_excel(xw, sheet_name="Customers", index=False)
        opening_stock(p).to_excel(xw, sheet_name="Opening Stock", index=False)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
