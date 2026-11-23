"""Thin wrapper over Odoo's external XML-RPC API.

Real mode : talks to Odoo at ODOO_URL (Odoo 17 or 18 Community).
Dry-run   : simulates Odoo in data/output/dryrun_odoo.json so the whole
            pipeline can be developed and demoed before Odoo is installed.
"""
import json
import xmlrpc.client
from pathlib import Path

from app import config

DRYRUN_FILE = Path(__file__).resolve().parent.parent / "data" / "output" / "dryrun_odoo.json"


class OdooClient:
    def __init__(self):
        self.dry_run = config.ODOO_DRY_RUN
        if self.dry_run:
            DRYRUN_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._state = json.loads(DRYRUN_FILE.read_text()) if DRYRUN_FILE.exists() else {
                "next_id": 1, "products": {}, "partners": {}, "orders": {}}
            return
        common = xmlrpc.client.ServerProxy(f"{config.ODOO_URL}/xmlrpc/2/common")
        self.version = int(str(common.version()["server_version"]).split(".")[0])
        self.uid = common.authenticate(config.ODOO_DB, config.ODOO_USER, config.ODOO_PASSWORD, {})
        if not self.uid:
            raise RuntimeError("Odoo authentication failed - check ODOO_DB / ODOO_USER / ODOO_PASSWORD")
        self.models = xmlrpc.client.ServerProxy(f"{config.ODOO_URL}/xmlrpc/2/object", allow_none=True)

    # ---------- helpers ----------
    def _call(self, model, method, *args, **kwargs):
        return self.models.execute_kw(config.ODOO_DB, self.uid, config.ODOO_PASSWORD,
                                      model, method, list(args), kwargs)

    def _save(self):
        DRYRUN_FILE.write_text(json.dumps(self._state, indent=2))

    def _new_id(self):
        i = self._state["next_id"]
        self._state["next_id"] += 1
        return i

    # ---------- products ----------
    def upsert_product(self, sku, name, cost, price, reorder_level):
        if self.dry_run:
            p = self._state["products"].get(sku) or {"id": self._new_id(), "qty": 0}
            p.update(name=name, cost=cost, price=price, reorder_level=reorder_level)
            self._state["products"][sku] = p
            self._save()
            return p["id"]
        vals = {"name": name, "default_code": sku, "standard_price": cost, "list_price": price}
        # Odoo 18 replaced type='product' with type='consu' + is_storable=True
        vals.update({"type": "consu", "is_storable": True} if self.version >= 18 else {"type": "product"})
        found = self._call("product.product", "search", [["default_code", "=", sku]], limit=1)
        if found:
            vals.pop("type", None); vals.pop("is_storable", None)
            self._call("product.product", "write", found, vals)
            return found[0]
        return self._call("product.product", "create", vals)

    # ---------- partners ----------
    def upsert_partner(self, ref, name, email, is_vendor):
        if self.dry_run:
            p = self._state["partners"].get(ref) or {"id": self._new_id()}
            p.update(name=name, email=email, vendor=is_vendor)
            self._state["partners"][ref] = p
            self._save()
            return p["id"]
        vals = {"name": name, "ref": ref, "email": email, "is_company": True,
                ("supplier_rank" if is_vendor else "customer_rank"): 1}
        found = self._call("res.partner", "search", [["ref", "=", ref]], limit=1)
        if found:
            self._call("res.partner", "write", found, vals)
            return found[0]
        return self._call("res.partner", "create", vals)

    def find_partner(self, ref):
        if self.dry_run:
            p = self._state["partners"].get(ref)
            return p["id"] if p else None
        found = self._call("res.partner", "search", [["ref", "=", ref]], limit=1)
        return found[0] if found else None

    # ---------- stock ----------
    def set_stock(self, sku, qty):
        if self.dry_run:
            self._state["products"][sku]["qty"] = qty
            self._save()
            return
        pid = self._call("product.product", "search", [["default_code", "=", sku]], limit=1)[0]
        wh = self._call("stock.warehouse", "search_read", [], fields=["lot_stock_id"], limit=1)[0]
        quant = self._call("stock.quant", "create", {
            "product_id": pid, "location_id": wh["lot_stock_id"][0], "inventory_quantity": qty})
        try:
            self._call("stock.quant", "action_apply_inventory", [quant])
        except xmlrpc.client.Fault as e:  # method returns None -> marshalling fault, but it applied
            if "cannot marshal None" not in str(e):
                raise

    def get_stock_levels(self):
        """Return [{sku, name, qty}] for all products."""
        if self.dry_run:
            return [{"sku": s, "name": p["name"], "qty": p["qty"]} for s, p in self._state["products"].items()]
        rows = self._call("product.product", "search_read", [["default_code", "!=", False]],
                          fields=["default_code", "name", "qty_available"])
        return [{"sku": r["default_code"], "name": r["name"], "qty": r["qty_available"]} for r in rows]

    # ---------- sales ----------
    def product_info(self, sku):
        if self.dry_run:
            p = self._state["products"].get(sku)
            return {"id": p["id"], "price": p["price"], "qty": p["qty"]} if p else None
        r = self._call("product.product", "search_read", [["default_code", "=", sku]],
                       fields=["id", "list_price", "qty_available"], limit=1)
        return {"id": r[0]["id"], "price": r[0]["list_price"], "qty": r[0]["qty_available"]} if r else None

    def create_sale_order(self, partner_id, lines, client_ref):
        """lines: [{sku, qty, price}] -> confirmed sale order id."""
        if self.dry_run:
            oid = self._new_id()
            for l in lines:  # simulate delivery reducing stock
                self._state["products"][l["sku"]]["qty"] -= l["qty"]
            self._state["orders"][str(oid)] = {"partner_id": partner_id, "lines": lines, "ref": client_ref}
            self._save()
            return oid
        order_lines = [(0, 0, {"product_id": self.product_info(l["sku"])["id"],
                               "product_uom_qty": l["qty"], "price_unit": l["price"]}) for l in lines]
        oid = self._call("sale.order", "create", {"partner_id": partner_id, "client_order_ref": client_ref,
                                                   "order_line": order_lines})
        self._call("sale.order", "action_confirm", [oid])
        return oid
