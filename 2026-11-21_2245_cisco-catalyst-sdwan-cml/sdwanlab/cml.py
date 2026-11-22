"""A small, readable client for the Cisco Modeling Labs (CML) REST API.

CML exposes everything you can do in its web UI at https://<cml>/api/v0.
We only need a handful of calls:

    POST /authenticate                  -> bearer token
    POST /import?title=...              -> create a lab from a YAML topology
    PUT  /labs/{id}/start | stop | wipe -> control the whole lab
    POST /labs/{id}/nodes               -> add a node (we add edges later)
    POST /labs/{id}/links               -> cable two interfaces together
    PATCH /labs/{id}/links/{id}/condition -> add delay/loss to a cable
"""
from __future__ import annotations

import time

import requests
import urllib3

urllib3.disable_warnings()


class CML:
    def __init__(self, host: str, user: str, password: str):
        self.base = f"https://{host}/api/v0"
        self.s = requests.Session()
        self.s.verify = False                    # lab uses a self-signed cert
        token = self.s.post(f"{self.base}/authenticate",
                            json={"username": user, "password": password}, timeout=30)
        token.raise_for_status()
        self.s.headers["Authorization"] = f"Bearer {token.json()}"

    # -- generic helpers -------------------------------------------------
    def _req(self, method: str, path: str, **kw):
        r = self.s.request(method, self.base + path, timeout=kw.pop("timeout", 120), **kw)
        if not r.ok:
            raise RuntimeError(f"CML {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.text and r.headers.get("content-type", "").startswith("application/json") else r.text

    get = lambda self, p, **k: self._req("GET", p, **k)
    post = lambda self, p, **k: self._req("POST", p, **k)
    put = lambda self, p, **k: self._req("PUT", p, **k)
    patch = lambda self, p, **k: self._req("PATCH", p, **k)
    delete = lambda self, p, **k: self._req("DELETE", p, **k)

    # -- labs ------------------------------------------------------------
    def find_lab(self, title: str) -> str | None:
        for lab_id in self.get("/labs", params={"show_all": "true"}):
            if self.get(f"/labs/{lab_id}").get("lab_title") == title:
                return lab_id
        return None

    def import_lab(self, title: str, topology_yaml: str) -> str:
        return self.post("/import", params={"title": title}, data=topology_yaml.encode(),
                         headers={"Content-Type": "application/x-yaml"})["id"]

    def start_lab(self, lab: str):
        self.put(f"/labs/{lab}/start")

    def stop_lab(self, lab: str):
        self.put(f"/labs/{lab}/stop")

    def wipe_lab(self, lab: str):
        self.put(f"/labs/{lab}/wipe")

    def delete_lab(self, lab: str):
        self.delete(f"/labs/{lab}")

    def lab_state(self, lab: str) -> str:
        return self.get(f"/labs/{lab}/state")

    # -- nodes -----------------------------------------------------------
    def nodes(self, lab: str) -> list[dict]:
        return self.get(f"/labs/{lab}/nodes", params={"data": "true"})

    def node_by_label(self, lab: str, label: str) -> dict | None:
        return next((n for n in self.nodes(lab) if n["label"] == label), None)

    def add_node(self, lab: str, label: str, node_definition: str, x: int, y: int,
                 image: str | None = None, config: str | list | None = None, **extra) -> str:
        body = {"label": label, "node_definition": node_definition, "x": x, "y": y, **extra}
        if image:
            body["image_definition"] = image
        if config is not None:
            body["configuration"] = config
        return self.post(f"/labs/{lab}/nodes", params={"populate_interfaces": "true"}, json=body)["id"]

    def interfaces(self, lab: str, node: str) -> list[dict]:
        return self.get(f"/labs/{lab}/nodes/{node}/interfaces", params={"data": "true"})

    def iface(self, lab: str, node: str, label: str) -> str:
        for i in self.interfaces(lab, node):
            if i["label"] == label:
                return i["id"]
        raise KeyError(f"interface {label} not found")

    def free_port(self, lab: str, node: str) -> str:
        """First unused port on a switch; add one if they are all in use."""
        for i in self.interfaces(lab, node):
            if i["type"] == "physical" and not i.get("is_connected"):
                return i["id"]
        return self.post(f"/labs/{lab}/interfaces", json={"node": node})["id"]

    def connect(self, lab: str, src_if: str, dst_if: str) -> str:
        return self.post(f"/labs/{lab}/links", json={"src_int": src_if, "dst_int": dst_if})["id"]

    def start_node(self, lab: str, node: str):
        self.put(f"/labs/{lab}/nodes/{node}/state/start")

    def stop_node(self, lab: str, node: str):
        self.put(f"/labs/{lab}/nodes/{node}/state/stop")

    def wait_booted(self, lab: str, labels: list[str] | None = None, timeout: int = 1800):
        """Wait until CML reports the nodes as BOOTED (VM up, console ready)."""
        end = time.time() + timeout
        while time.time() < end:
            pending = [n["label"] for n in self.nodes(lab)
                       if (labels is None or n["label"] in labels)
                       and n["node_definition"] not in ("unmanaged_switch", "external_connector")
                       and n["state"] != "BOOTED"]
            if not pending:
                return
            time.sleep(15)
        raise TimeoutError(f"nodes not booted: {pending}")

    # -- links -----------------------------------------------------------
    def links(self, lab: str) -> list[dict]:
        return self.get(f"/labs/{lab}/links", params={"data": "true"})

    def link_between(self, lab: str, a: str, b: str) -> dict:
        ids = {n["label"]: n["id"] for n in self.nodes(lab)}
        for l in self.links(lab):
            if {l["node_a"], l["node_b"]} == {ids[a], ids[b]}:
                return l
        raise KeyError(f"no link {a} <-> {b}")

    def condition(self, lab: str, link: str, **impairment):
        """Add impairment to a cable, e.g. latency=300 (ms), loss=5 (%).
        Call with no arguments to remove it again."""
        if impairment:
            self.patch(f"/labs/{lab}/links/{link}/condition", json={"enabled": True, **impairment})
        else:
            self.delete(f"/labs/{lab}/links/{link}/condition")
