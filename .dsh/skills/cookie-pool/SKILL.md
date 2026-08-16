---
name: cookie-pool
description: Fetch cookies for TikTok, YouTube, Instagram, Facebook, Google Ads and other platforms from the Cookie Pool API. Use when scripts need authenticated cookies, when a task asks for "cookies", "登录态", "cookie string", or when browser automation needs pre-authenticated sessions.
---

# Cookie Pool — API Usage

Cookie Pool is a Selenium Grid + noVNC cookie management system. It maintains persistent Chrome browser sessions where humans log in to platforms, then exposes cookies through a REST API.

## Base URL & Auth

All requests require the `X-API-Key` header.

```
Base:  http://158.180.87.150:8080
Key:   cookie-pool-158-2026
```

## Endpoints

### List accounts

```
GET /api/accounts
```

Returns all accounts with their status, platform, and grid binding. An account with `status: "ACTIVE"` has valid login cookies.

### Get cookies for an account (plain string)

```
GET /api/accounts/{id}/cookies/plain?domain=tiktok.com
```

Returns a semicolon-separated Netscape cookie string ready for use in `Cookie` headers or curl.

Optional `domain` query param filters by domain substring match.

### Get cookies for a session (plain string)

```
GET /api/sessions/{id}/cookies/plain?platform=tiktok
```

Same format. Use `platform` param to filter by platform domain.

### Get cookies as JSON

```
GET /api/accounts/{id}/cookies
GET /api/sessions/{id}/cookies
```

Returns `{count, cookie_string, cookies: [{name, value, domain}]}`.

### Health check

```
GET /health
```

## Usage patterns

### 1. Find an active account by platform

```bash
# List all ACTIVE TikTok accounts
curl -s http://158.180.87.150:8080/api/accounts \
  -H "X-API-Key: cookie-pool-158-2026" \
  | python3 -c "
import sys,json
for a in json.load(sys.stdin)['accounts']:
    if a['status']=='ACTIVE' and 'tiktok' in a['platform'].lower():
        print(f'id={a[\"id\"]} name={a[\"name\"]} platform={a[\"platform\"]}')
"
```

### 2. Fetch cookies as curl-ready string

```bash
curl -s "http://158.180.87.150:8080/api/accounts/8/cookies/plain?domain=tiktok.com" \
  -H "X-API-Key: cookie-pool-158-2026"
```

Output: `sessionid=abc123; tt_webid=def456; ...`

### 3. Use cookies in Python requests

```python
import requests
import json

API = "http://158.180.87.150:8080"
KEY = "cookie-pool-158-2026"

# Get cookie string
resp = requests.get(
    f"{API}/api/accounts/8/cookies/plain?domain=tiktok.com",
    headers={"X-API-Key": KEY}
)
cookie_str = resp.text

# Use in subsequent requests
resp = requests.get(
    "https://ads.tiktok.com/api/some-endpoint",
    headers={"Cookie": cookie_str, "User-Agent": "..."}
)
```

### 4. Use cookies in Selenium

```python
from selenium import webdriver

# Fetch cookies as JSON
resp = requests.get(
    f"{API}/api/accounts/8/cookies",
    headers={"X-API-Key": KEY}
)
cookies = resp.json()["cookies"]

# Inject into browser
driver = webdriver.Chrome()
driver.get("https://www.tiktok.com")
for c in cookies:
    driver.add_cookie({"name": c["name"], "value": c["value"], "domain": c["domain"]})
driver.refresh()
```

### 5. Use cookies in curl

```bash
COOKIES=$(curl -s "http://158.180.87.150:8080/api/accounts/8/cookies/plain?domain=tiktok.com" \
  -H "X-API-Key: cookie-pool-158-2026")

curl -s "https://www.tiktok.com/api/some-endpoint" \
  -H "Cookie: $COOKIES" \
  -H "User-Agent: Mozilla/5.0 ..."
```

## Platform filter values

| Platform | `domain` / `platform` param |
|----------|---------------------------|
| TikTok | `tiktok.com` |
| YouTube | `youtube.com` |
| Instagram | `instagram.com` |
| Facebook | `facebook.com` |
| Twitter/X | `twitter.com` |
| LinkedIn | `linkedin.com` |
| Reddit | `reddit.com` |
| 微信 | `weixin.qq.com` |
| 抖音 | `douyin.com` |
| 小红书 | `xiaohongshu.com` |
| Bilibili | `bilibili.com` |
| 微博 | `weibo.com` |
| 快手 | `kuaishou.com` |
| 知乎 | `zhihu.com` |

## Important notes

- **Cookies come from real Chrome browsers** logged in by humans. If an account is `WAIT_LOGIN`, its cookies are not yet available.
- **Session-based cookies**: New architecture uses persistent browser sessions (`/api/sessions`). An account bound to an ACTIVE session has fresh cookies.
- **Cookie freshness**: The browser maintains the login session; cookies extracted are current at the time of the API call.
- **Do NOT start new browsers** through this API for simple cookie extraction — only fetch from already-ACTIVE accounts or sessions.
- If no account is ACTIVE for the needed platform, tell the user they need to log in through the Web UI (noVNC) first.