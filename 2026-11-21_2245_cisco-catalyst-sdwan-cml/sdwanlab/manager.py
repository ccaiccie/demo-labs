"""A readable client for the Catalyst SD-WAN Manager REST API.

Everything you do in the Manager GUI is a call to https://<manager>/dataservice/...
Logging in takes two steps:

    1. POST /j_security_check  (form: j_username, j_password)
       -> sets a JSESSIONID session cookie
    2. GET  /dataservice/client/token
       -> returns an XSRF token that must be sent as the "X-XSRF-TOKEN"
          header on every POST/PUT/DELETE (protection against cross-site
          request forgery)

After that it is ordinary JSON over HTTPS.
"""
from __future__ import annotations

import time
from typing import Any

import requests
import urllib3

urllib3.disable_warnings()


class ManagerError(RuntimeError):
    pass


class Manager:
    def __init__(self, host: str, user: str, password: str):
        self.base = f"https://{host}"
        self.user, self.password = user, password
        self.s = requests.Session()
        self.s.verify = False

    # ------------------------------------------------------------------
    # session handling
    # ------------------------------------------------------------------
    def login(self) -> "Manager":
        r = self.s.post(f"{self.base}/j_security_check",
                        data={"j_username": self.user, "j_password": self.password}, timeout=30)
        # On success the body is empty; on failure the login HTML page comes back.
        if r.text or "JSESSIONID" not in self.s.cookies:
            raise ManagerError("login failed")
        token = self.s.get(f"{self.base}/dataservice/client/token", timeout=30)
        if token.status_code != 200 or "<html" in token.text.lower():
            raise ManagerError("no XSRF token yet (Manager still starting)")
        self.s.headers["X-XSRF-TOKEN"] = token.text
        return self

    def wait_ready(self, timeout: int = 3600, every: int = 30, log=print) -> "Manager":
        """The Manager takes 15-30 minutes to boot all its services the first time."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                self.login()
                # a login is not enough: also wait until the device inventory answers
                self.get("/dataservice/system/device/controllers")
                return self
            except (requests.RequestException, ManagerError) as e:
                log(f"  Manager not ready yet ({type(e).__name__}) - retrying in {every}s")
                time.sleep(every)
        raise TimeoutError("Manager did not come up")

    def _call(self, method: str, path: str, body: Any = None, *, timeout: int = 120, **kw) -> Any:
        r = self.s.request(method, self.base + path, json=body, timeout=timeout, **kw)
        if r.status_code == 401 or r.status_code == 403 and "token" in r.text.lower():
            self.login()                                    # session expired -> log in again
            r = self.s.request(method, self.base + path, json=body, timeout=timeout, **kw)
        if not r.ok:
            raise ManagerError(f"{method} {path} -> HTTP {r.status_code}: {r.text[:500]}")
        if not r.text:
            return None
        try:
            return r.json()
        except ValueError:
            return r.text

    def get(self, path, **kw):    return self._call("GET", path, **kw)
    def post(self, path, body=None, **kw):   return self._call("POST", path, body, **kw)
    def put(self, path, body=None, **kw):    return self._call("PUT", path, body, **kw)
    def delete(self, path, **kw): return self._call("DELETE", path, **kw)

    def data(self, path: str) -> list:
        """Most monitoring APIs wrap their result in {"header":..., "data":[...]}."""
        return (self.get(path) or {}).get("data", [])

    def wait_task(self, task_id: str, timeout: int = 900, log=print) -> dict:
        """Long operations (push config, install cert...) return a task id.
        We poll /device/action/status/<id> until it is done."""
        end = time.time() + timeout
        while time.time() < end:
            st = self.get(f"/dataservice/device/action/status/{task_id}")
            summ = st.get("summary", {})
            if summ.get("status") == "done":
                if summ.get("count", {}).get("Failure"):
                    msgs = [d.get("activity", [])[-3:] for d in st.get("data", [])]
                    raise ManagerError(f"task {task_id} failed: {msgs}")
                return st
            time.sleep(5)
        raise TimeoutError(f"task {task_id}")

    # ------------------------------------------------------------------
    # Administration > Settings
    # ------------------------------------------------------------------
    def setting(self, name: str, body: dict, method: str = "PUT"):
        return self._call(method, f"/dataservice/settings/configuration/{name}", body)

    def get_setting(self, name: str) -> dict:
        d = self.data(f"/dataservice/settings/configuration/{name}")
        return d[0] if d else {}

    # ------------------------------------------------------------------
    # Control components (Configuration > Devices > Control Components)
    # ------------------------------------------------------------------
    def controllers(self) -> list[dict]:
        return self.data("/dataservice/system/device/controllers")

    def add_controller(self, ip: str, personality: str, user: str, password: str):
        self.post("/dataservice/system/device", {
            "deviceIP": ip, "username": user, "password": password,
            "personality": personality,           # "vsmart" = Controller, "vbond" = Validator
            "generateCSR": False,
        })

    def generate_csr(self, ip: str) -> str:
        return self.post("/dataservice/certificate/generate/csr", {"deviceIP": ip},
                         timeout=180)["data"][0]["deviceCSR"]

    def install_cert(self, cert_pem: str) -> str:
        r = self.s.post(f"{self.base}/dataservice/certificate/install/signedCert",
                        data=cert_pem, timeout=180)
        if not r.ok:
            raise ManagerError(f"install cert -> {r.status_code}: {r.text[:300]}")
        return r.json()["id"]

    # ------------------------------------------------------------------
    # WAN edges
    # ------------------------------------------------------------------
    def upload_serial_file(self, path) -> dict:
        with open(path, "rb") as f:
            r = self.s.post(f"{self.base}/dataservice/system/device/fileupload",
                            files={"file": (path.name, f)},
                            data={"validity": "valid", "upload": "true"}, timeout=120)
        if not r.ok:
            raise ManagerError(f"serial upload -> {r.status_code}: {r.text[:300]}")
        return r.json()

    def wan_edges(self) -> list[dict]:
        return self.data("/dataservice/system/device/vedges")

    def bootstrap(self, uuid: str) -> str:
        """Day-0 'cloud-init' file for one edge: who it is (UUID + one-time
        password), where the Validator is, and which root CA to trust."""
        return self.get(f"/dataservice/system/device/bootstrap/device/{uuid}"
                        "?configtype=cloudinit&inclDefRootCert=false&version=v1")["bootstrapConfig"]

    # ------------------------------------------------------------------
    # Configuration groups and feature profiles (the 20.x "UX 2.0" model)
    # ------------------------------------------------------------------
    FP = "/dataservice/v1/feature-profile/sdwan"

    def create_profile(self, kind: str, name: str, description: str = "") -> str:
        """kind = system | transport | service | cli | policy-object | application-priority | topology"""
        for p in self.get(f"{self.FP}/{kind}") or []:
            if p.get("profileName") == name:
                return p["profileId"]
        return self.post(f"{self.FP}/{kind}", {"name": name, "description": description or name})["id"]

    def create_parcel(self, kind: str, profile: str, parcel: str, payload: dict) -> str:
        """Add one 'feature' (parcel) to a profile, e.g. system/basic or transport/wan/vpn."""
        r = self.post(f"{self.FP}/{kind}/{profile}/{parcel}", payload)
        return r.get("parcelId") or r.get("id")

    def find_parcel(self, kind: str, profile: str, parcel: str, name: str) -> str | None:
        """Look the parcel up by name in the profile details (so re-runs are safe)."""
        prof = self.get(f"{self.FP}/{kind}/{profile}?details=true") or {}
        todo = list(prof.get("associatedProfileParcels", []))
        while todo:
            p = todo.pop()
            if p.get("payload", {}).get("name") == name:
                return p["parcelId"]
            todo += p.get("subparcels", [])
        return None

    def config_groups(self) -> list[dict]:
        return self.get("/dataservice/v1/config-group") or []

    def create_config_group(self, name: str, description: str, profile_ids: list[str]) -> str:
        for g in self.config_groups():
            if g["name"] == name:
                return g["id"]
        return self.post("/dataservice/v1/config-group", {
            "name": name, "description": description, "solution": "sdwan",
            "profiles": [{"id": p} for p in profile_ids],
        })["id"]

    def cg_associate(self, cg: str, uuids: list[str]):
        self.put(f"/dataservice/v1/config-group/{cg}/device/associate",
                 {"devices": [{"id": u} for u in uuids]})

    def cg_variables_schema(self, cg: str) -> list:
        return self.get(f"/dataservice/v1/config-group/{cg}/device/variables/schema")

    def cg_set_variables(self, cg: str, devices: list[dict]):
        self.put(f"/dataservice/v1/config-group/{cg}/device/variables",
                 {"solution": "sdwan", "devices": devices})

    def cg_deploy(self, cg: str, uuids: list[str]) -> str:
        return self.post(f"/dataservice/v1/config-group/{cg}/device/deploy",
                         {"devices": [{"id": u} for u in uuids]})["parentTaskId"]

    # ------------------------------------------------------------------
    # Policy groups
    # ------------------------------------------------------------------
    def policy_groups(self) -> list[dict]:
        return self.get("/dataservice/v1/policy-group") or []

    # ------------------------------------------------------------------
    # Real-time monitoring (what Monitor > Devices > Real Time shows)
    # ------------------------------------------------------------------
    def devices(self) -> list[dict]:
        return self.data("/dataservice/device")

    def rt(self, what: str, system_ip: str) -> list[dict]:
        """e.g. rt('control/connections', '10.255.0.21'), rt('bfd/sessions', ...),
        rt('omp/routes/received', ...), rt('app-route/statistics', ...)"""
        return self.data(f"/dataservice/device/{what}?deviceId={system_ip}")
