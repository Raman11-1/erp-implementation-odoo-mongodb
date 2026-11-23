"""Business validation rules for master data migration.

Each validator takes one row (dict) and returns a list of error strings.
Empty list = row is valid.
"""
import re

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


def _blank(v):
    return v is None or (isinstance(v, float) and v != v) or str(v).strip() == ""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def validate_product(r):
    errs = []
    for f in ("SKU", "Product Name", "UoM", "Category"):
        if _blank(r.get(f)):
            errs.append(f"{f} is missing")
    cost, price = _num(r.get("Cost Price")), _num(r.get("Sale Price"))
    if cost is None or cost <= 0:
        errs.append("Cost Price must be a positive number")
    if price is None or price <= 0:
        errs.append("Sale Price must be a positive number")
    if cost and price and cost > 0 and price < cost:
        errs.append("Sale Price is below Cost Price")
    return errs


def validate_vendor(r):
    errs = []
    for f in ("Vendor Code", "Vendor Name", "GSTIN"):
        if _blank(r.get(f)):
            errs.append(f"{f} is missing")
    if _blank(r.get("Email")) or not EMAIL_RE.match(str(r.get("Email"))):
        errs.append("Email is invalid")
    return errs


def validate_customer(r):
    errs = []
    for f in ("Customer Code", "Customer Name"):
        if _blank(r.get(f)):
            errs.append(f"{f} is missing")
    if _blank(r.get("Email")) or not EMAIL_RE.match(str(r.get("Email"))):
        errs.append("Email is invalid")
    if _num(r.get("Credit Limit")) is None:
        errs.append("Credit Limit must be numeric")
    return errs


def validate_stock(r, valid_skus):
    errs = []
    if r.get("SKU") not in valid_skus:
        errs.append("SKU not found in validated product master")
    q = _num(r.get("Quantity"))
    if q is None or q < 0:
        errs.append("Quantity must be zero or positive")
    return errs
