"""Send sample orders to the running middleware to demonstrate the full flow.

Includes good orders plus deliberate failures (unknown customer, unknown SKU,
insufficient stock, duplicate submission) so every validation path is exercised.

Run (with the API running):  python -m scripts.demo_orders
"""
import json
import urllib.error
import urllib.request

API = "http://127.0.0.1:8000"

ORDERS = [
    {"order_ref": "WEB-1001", "customer_code": "C001", "lines": [{"sku": "KTP-001-Std", "qty": 5}]},
    {"order_ref": "WEB-1002", "customer_code": "C002",
     "lines": [{"sku": "KTP-010-HD", "qty": 3}, {"sku": "KTP-004-HD", "qty": 2}]},
    {"order_ref": "WEB-1003", "customer_code": "C999", "lines": [{"sku": "KTP-001-Std", "qty": 1}]},
    {"order_ref": "WEB-1004", "customer_code": "C004", "lines": [{"sku": "KTP-999-ZZ", "qty": 1}]},
    {"order_ref": "WEB-1005", "customer_code": "C005", "lines": [{"sku": "KTP-003-Std", "qty": 100000}]},
    {"order_ref": "WEB-1001", "customer_code": "C001", "lines": [{"sku": "KTP-001-Std", "qty": 5}]},
]


def post(path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    print("Syncing inventory from ERP...", post("/inventory/sync"))
    for o in ORDERS:
        code, body = post("/orders", o)
        print(f"{o['order_ref']}  HTTP {code}  {body}")


if __name__ == "__main__":
    main()
