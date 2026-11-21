"""Small FMC REST API client: login, token refresh, rate-limit retries, paging, get-or-create."""
import time, requests, urllib3
urllib3.disable_warnings()

def load_secrets(path="/root/lab-secrets.env"):
    out = {}
    for line in open(path):
        if "=" in line: k, v = line.strip().split("=", 1); out[k] = v
    return out

class FMC:
    def __init__(self, host, username, password):
        self.base = f"https://{host}"; self.user, self.pw = username, password
        self.s = requests.Session(); self.s.verify = False
        self.login()

    def login(self):
        r = self.s.post(f"{self.base}/api/fmc_platform/v1/auth/generatetoken", auth=(self.user, self.pw), timeout=60)
        r.raise_for_status()
        self.token = r.headers["X-auth-access-token"]; self.refresh = r.headers["X-auth-refresh-token"]
        self.domain = r.headers["DOMAIN_UUID"]; self.t0 = time.time()
        self.s.headers.update({"X-auth-access-token": self.token, "Content-Type": "application/json"})

    def _url(self, path):
        if path.startswith("/api/"): return self.base + path
        return f"{self.base}/api/fmc_config/v1/domain/{self.domain}/{path.lstrip('/')}"

    def req(self, method, path, **kw):
        for attempt in range(8):
            if time.time() - self.t0 > 25 * 60: self.login()        # tokens last 30 min
            r = self.s.request(method, self._url(path), timeout=120, **kw)
            if r.status_code == 401: self.login(); continue
            if r.status_code == 429: time.sleep(5 * (attempt + 1)); continue   # FMC allows ~120 calls/min
            if r.status_code >= 400:
                raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:600]}")
            return r.json() if r.text else {}
        raise RuntimeError(f"{method} {path}: too many retries")

    def get(self, path, **kw):   return self.req("GET", path, **kw)
    def post(self, path, body):  return self.req("POST", path, json=body)
    def put(self, path, body):   return self.req("PUT", path, json=body)

    def get_all(self, path, expanded=True):
        items, offset = [], 0
        while True:
            sep = "&" if "?" in path else "?"
            d = self.get(f"{path}{sep}offset={offset}&limit=100&expanded={str(expanded).lower()}")
            items += d.get("items", [])
            if offset + 100 >= d.get("paging", {}).get("count", 0): return items
            offset += 100

    def find(self, path, name):
        return next((i for i in self.get_all(path) if i.get("name") == name), None)

    def get_or_create(self, path, body):
        existing = self.find(path, body["name"])
        if existing: return existing, False
        return self.post(path, body), True

    def wait_task(self, task_id, timeout=1800, label="task"):
        end = time.time() + timeout
        while time.time() < end:
            t = self.get(f"job/taskstatuses/{task_id}")
            st = (t.get("status") or "").upper()
            if st in ("SUCCESS", "COMPLETED", "DEPLOYED"): return t
            if st in ("FAILED", "ERROR"): raise RuntimeError(f"{label} failed: {t}")
            time.sleep(15)
        raise TimeoutError(label)
