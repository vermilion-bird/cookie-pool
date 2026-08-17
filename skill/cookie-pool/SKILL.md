---
name: "cookie-pool"
description: "获取 YouTube/TikTok/Meta/Google Ads 登录态 cookie，优先使用 cp CLI 脚本。"
---

# Cookie Pool — Cookie 获取

> 使用 `cp` CLI 获取已登录账号的 cookie。支持 JSON 表格和 Netscape 纯文本格式。

## 初始化

`cp` 脚本自动从项目 `.env` 读取 API Key，无需手动配置。

Key 来源优先级：`CP_API_KEY` 环境变量 → `projects/cookie-pool/.env` → `/tmp/cp_key`

## CLI 命令

### 列出账号

```bash
cp list                # 只显示 ACTIVE 账号
cp list --all          # 显示所有账号（含 WAIT_LOGIN）
```

### 获取 Account Cookie

```bash
cp get <名称|ID>                  # JSON 表格
cp get <名称|ID> --plain          # Netscape 格式（可用于 curl/yt-dlp）
cp get <名称|ID> --domain <d>    # 按 domain 过滤
```

### 获取 Session Cookie

```bash
cp session <ID>                   # JSON 表格
cp session <ID> --plain           # Netscape 格式
cp session <ID> --platform <p>   # 按平台过滤（如 tiktok）
```

## 示例

```bash
# 查所有活跃账号
cp list

# 获取 YouTube cookie（Netscape 格式，可直传 curl）
cp get Youtube01 --plain > /tmp/yt_cookies.txt
curl --cookie /tmp/yt_cookies.txt "https://www.youtube.com/..."

# 获取 TikTok session cookie
cp session 1 --platform tiktok

# 只看 YouTube 域名的 cookie
cp get Youtube01 --domain youtube.com
```

## 直连 API（高级/脚本用）

`cp` 覆盖不了的场景才直连 API。Base: `http://158.180.87.150:8080`，Header: `X-API-Key`

| Endpoint | 说明 |
|----------|------|
| `GET /api/accounts` | 账号列表 |
| `GET /api/accounts/{id}/cookies` | JSON: `{count, cookie_string, cookies}` |
| `GET /api/accounts/{id}/cookies/plain?domain=x` | Netscape |
| `GET /api/sessions/{id}/cookies` | Session JSON |
| `GET /api/sessions/{id}/cookies/plain?platform=x` | Session Netscape |

完整 API 文档: `https://cookie.8tb.cc/docs`