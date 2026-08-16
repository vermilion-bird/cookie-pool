"""
Smoke tests for Accounts / Grids / Sessions CRUD.
Run:  python tests/test_crud_smoke.py
"""

import json
import sys
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API = os.getenv("CP_API_URL", "http://158.180.87.150:8080")
KEY = os.getenv("CP_API_KEY", "cookie-pool-158-2026")

passed = 0
failed = 0

# unique suffix to avoid cross-run collisions
SUFFIX = "-smoke"


def req(method, path, body=None):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    r = Request(url, data=data, method=method)
    r.add_header("X-API-Key", KEY)
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urlopen(r, timeout=20) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            err_body = json.loads(raw)
        except Exception:
            err_body = {"_raw": raw}
        return e.code, err_body


def check(description, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f"  \033[32m✓\033[0m {description}")
    else:
        failed += 1
        print(f"  \033[31m✗\033[0m {description}")


# ── Pre-cleanup: remove leftover test data from previous runs ──
print("── Cleanup ──")
_, data = req("GET", "/api/accounts")
for a in data.get("accounts", []):
    if a["name"].endswith(SUFFIX):
        req("DELETE", f"/api/accounts/{a['id']}")
        print(f"  cleaned account: {a['name']}")

_, data = req("GET", "/api/sessions")
for s in data.get("sessions", []):
    if s["name"].endswith(SUFFIX):
        # cancel driver first if running
        if s["status"] in ("LOGIN", "ACTIVE"):
            req("POST", f"/api/sessions/{s['id']}/login/cancel")
        req("DELETE", f"/api/sessions/{s['id']}")
        print(f"  cleaned session: {s['name']}")

_, data = req("GET", "/api/grids")
for g in data.get("grids", []):
    if g["name"].endswith(SUFFIX):
        req("DELETE", f"/api/grids/{g['id']}")
        print(f"  cleaned grid: {g['name']}")


# ═══════════════════════════════════════════════
# 1. Grids CRUD
# ═══════════════════════════════════════════════
print("\n── Grids ──")
gb = passed

s, d = req("POST", "/api/grids", {
    "name": f"grid{SUFFIX}", "hub_url": "http://localhost:4445",
    "max_sessions": 2, "notes": "smoke test",
})
check("POST /api/grids → 200 + grid", s == 200 and "grid" in d)
gid = d.get("grid", {}).get("id")
check("  returned grid.id", gid is not None)

s, d = req("GET", f"/api/grids/{gid}")
check("GET /api/grids/:id → 200", s == 200 and d.get("grid", {}).get("name") == f"grid{SUFFIX}")

s, d = req("PUT", f"/api/grids/{gid}", {"name": f"grid-renamed{SUFFIX}", "max_sessions": 3})
check("PUT /api/grids/:id → 200", s == 200 and d.get("grid", {}).get("name") == f"grid-renamed{SUFFIX}")

s, d = req("GET", "/api/grids")
check("GET /api/grids → 200", s == 200 and isinstance(d.get("grids"), list))

s, d = req("POST", f"/api/grids/{gid}/check")
check("POST /api/grids/:id/check → 200", s == 200 and "status" in d)

s, d = req("DELETE", f"/api/grids/{gid}")
check("DELETE /api/grids/:id → 200", s == 200)

s, d = req("GET", f"/api/grids/{gid}")
check("  verify deleted → 404", s == 404)

print(f"  Grids: {passed-gb}/{passed+failed-gb}")


# ═══════════════════════════════════════════════
# 2. Accounts CRUD
# ═══════════════════════════════════════════════
print("\n── Accounts ──")
ab = passed

s, d = req("POST", "/api/accounts", {
    "name": f"acc{SUFFIX}", "platform": "tiktok.com", "notes": "crud test",
})
check("POST /api/accounts → 200 + account", s == 200 and "account" in d)
aid = d.get("account", {}).get("id")
check("  returned account.id", aid is not None)
check("  profile_path auto-generated", bool(d.get("account", {}).get("profile_path")))
check("  status = WAIT_LOGIN", d.get("account", {}).get("status") == "WAIT_LOGIN")

s, d = req("GET", f"/api/accounts/{aid}")
check("GET /api/accounts/:id → 200", s == 200 and d.get("account", {}).get("name") == f"acc{SUFFIX}")

s, d = req("PUT", f"/api/accounts/{aid}", {
    "name": f"acc-renamed{SUFFIX}", "platform": "instagram.com",
})
check("PUT /api/accounts/:id → 200", s == 200 and d.get("account", {}).get("name") == f"acc-renamed{SUFFIX}")
check("  platform updated", d.get("account", {}).get("platform") == "instagram.com")

s, d = req("GET", "/api/accounts")
check("GET /api/accounts → 200", s == 200 and isinstance(d.get("accounts"), list))

s, d = req("DELETE", f"/api/accounts/{aid}")
check("DELETE /api/accounts/:id → 200", s == 200)

s, d = req("GET", f"/api/accounts/{aid}")
check("  verify deleted → 404", s == 404)

# Duplicate name
s, d = req("POST", "/api/accounts", {"name": f"dupe{SUFFIX}", "platform": "youtube.com"})
dupe_id = d.get("account", {}).get("id")
s2, d2 = req("POST", "/api/accounts", {"name": f"dupe{SUFFIX}", "platform": "youtube.com"})
check("POST duplicate name → 400", s2 == 400)
req("DELETE", f"/api/accounts/{dupe_id}")

print(f"  Accounts: {passed-ab}/{passed+failed-ab}")


# ═══════════════════════════════════════════════
# 3. Sessions CRUD
# ═══════════════════════════════════════════════
print("\n── Sessions ──")
sb = passed

# Get a valid node_id
s, d = req("GET", "/api/grids")
grids = d.get("grids", [])
online = [g for g in grids if g.get("status") == "ONLINE"]
node_id = online[0]["id"] if online else 1

# ── Create ──
s, d = req("POST", "/api/sessions", {"name": f"sess{SUFFIX}", "node_id": node_id})
check("POST /api/sessions → 200 + session", s == 200 and "session" in d)
sid = d.get("session", {}).get("id")
check("  returned session.id", sid is not None)
check("  status = IDLE", d.get("session", {}).get("status") == "IDLE")
check("  profile_path set", bool(d.get("session", {}).get("profile_path")))

# ── Duplicate name ──
s2, d2 = req("POST", "/api/sessions", {"name": f"sess{SUFFIX}", "node_id": node_id})
check("POST duplicate name → 400", s2 == 400)

# ── Get single ──
s, d = req("GET", f"/api/sessions/{sid}")
check("GET /api/sessions/:id → 200", s == 200 and d.get("session", {}).get("name") == f"sess{SUFFIX}")

# ── List ──
s, d = req("GET", "/api/sessions")
check("GET /api/sessions → 200", s == 200 and isinstance(d.get("sessions"), list))

# ── Health (IDLE) ──
s, d = req("GET", f"/api/sessions/{sid}/health")
check("GET /health (IDLE) → 200", s == 200)
check("  alive = false", d.get("alive") is False)
check("  driver_exists = false", d.get("driver_exists") is False)

# ── Start login ──
s, d = req("POST", f"/api/sessions/{sid}/login")
check("POST /login → 200", s == 200)
check("  status = LOGIN", d.get("session", {}).get("status") == "LOGIN")
check("  grid_session_id set", bool(d.get("session", {}).get("grid_session_id")))
check("  novnc_url set", bool(d.get("session", {}).get("novnc_url")))

# ── Health (LOGIN) ──
s, d = req("GET", f"/api/sessions/{sid}/health")
check("GET /health (LOGIN) → 200", s == 200)
check("  alive = true", d.get("alive") is True)
check("  driver_exists = true", d.get("driver_exists") is True)

# ── Restart ──
s, d = req("POST", f"/api/sessions/{sid}/restart")
check("POST /restart → 200", s == 200)
check("  status = LOGIN after restart", d.get("session", {}).get("status") == "LOGIN")
new_gsid = d.get("session", {}).get("grid_session_id")
check("  new grid_session_id", bool(new_gsid))

# ── Complete login ──
s, d = req("POST", f"/api/sessions/{sid}/login/complete")
check("POST /login/complete → 200", s == 200)
check("  status = ok", d.get("status") == "ok")

# ── Create account + bind ──
s, d = req("POST", "/api/accounts", {"name": f"bind{SUFFIX}", "platform": "tiktok.com"})
baid = d.get("account", {}).get("id")

s, d = req("POST", f"/api/sessions/{sid}/accounts", {"account_id": baid})
check("POST /accounts → 200 + session_account", s == 200 and "session_account" in d)

# ── Duplicate platform bind ──
s2, d2 = req("POST", f"/api/sessions/{sid}/accounts", {"account_id": baid})
check("POST duplicate platform → 409", s2 == 409)

# ── Unbind ──
s, d = req("DELETE", f"/api/sessions/{sid}/accounts/{baid}")
check("DELETE /accounts/:aid → 200", s == 200)

# ── Cookie extract ──
s, d = req("GET", f"/api/sessions/{sid}/cookies")
check("GET /cookies → 200", s == 200)
check("  count present", "count" in d)
check("  cookie_string present", "cookie_string" in d)

s, d_plain = req("GET", f"/api/sessions/{sid}/cookies/plain")
check("GET /cookies/plain → 200", s == 200)

# ── Cancel ──
s, d = req("POST", f"/api/sessions/{sid}/login/cancel")
check("POST /login/cancel → 200", s == 200)

# ── Health after cancel ──
s, d = req("GET", f"/api/sessions/{sid}/health")
check("  health after cancel: alive = false", s == 200 and d.get("alive") is False)

# ── Delete session ──
s, d = req("DELETE", f"/api/sessions/{sid}")
check("DELETE /api/sessions/:id → 200", s == 200)

s, d = req("GET", f"/api/sessions/{sid}")
check("  verify deleted → 404", s == 404)

# ── Cleanup account ──
req("DELETE", f"/api/accounts/{baid}")

print(f"  Sessions: {passed-sb}/{passed+failed-sb}")


# ═══════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"  TOTAL: {passed}/{passed+failed} passed, {failed} failed")
print(f"{'='*50}")
if failed:
    sys.exit(1)