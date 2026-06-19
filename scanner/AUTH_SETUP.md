# Deepvue 凭证设置 / Getting your Deepvue credentials

> The scanner drives **your own** logged-in Deepvue session. Deepvue has no public API, so
> you supply your session the way the web app does: a **refresh token** (mints short-lived
> access tokens) + your **device IDs** + your **cookies**. Everything stays local in
> `~/.deepvue/` and is git-ignored — nothing is uploaded anywhere.
>
> 扫描器用**你自己**登录的 Deepvue 会话。Deepvue 没有公开 API，所以你像网页端一样提供会话：
> 一个 **refreshToken**（用来续签 5 分钟有效的 access token）+ **deviceId** + **cookies**。
> 全部只存在本地 `~/.deepvue/`，已被 .gitignore，不会上传。

You need a **paid Deepvue account** (the screener is a premium feature).

---

## 1. Create the local folder

```bash
mkdir -p ~/.deepvue
```

## 2. Grab your tokens (DevTools → Console)

1. Log in to **https://app.deepvue.com** in Chrome and confirm you can see the screener.
2. Press **F12** → **Console** tab.
3. Paste this and press Enter (it copies a JSON blob of all storage to your clipboard):

   ```js
   copy(JSON.stringify({localStorage:{...localStorage}, sessionStorage:{...sessionStorage}}))
   ```
   *(If it says `copy is not defined`, run the same line without `copy(...)` and copy the printed output manually.)*

4. From that blob, pull out **`accessToken`**, **`refreshToken`**, **`deviceId`**, and
   **`deepvue-chart-device-id`**, and save them to `~/.deepvue/tokens.json`:

   ```json
   {
     "refreshToken": "<refreshToken from localStorage>",
     "deviceId": "<deviceId from localStorage>",
     "chartDeviceId": "<deepvue-chart-device-id from localStorage>",
     "accessToken": "<accessToken — optional, the script refreshes it anyway>"
   }
   ```
   The **`refreshToken`** is the important one — the script POSTs it to
   `api.deepvue.com/api/v2/auth/refresh` to mint a fresh access token on every run.

## 3. Export your cookies

Use a cookie-export browser extension (e.g. **Cookie-Editor** → *Export* → *JSON*) on
`app.deepvue.com`, and save the exported array to `~/.deepvue/cookies.json`. The expected
shape is the standard export array:

```json
[
  {"domain": ".deepvue.com", "name": "__cf_bm", "value": "...", "path": "/", "secure": true, "httpOnly": true, "sameSite": "no_restriction"},
  {"domain": "app.deepvue.com", "name": "oauth_last_used_provider", "value": "...", "path": "/"}
]
```
(`expirationDate`, `session`, etc. are accepted and optional.)

## 4. Theme config

```bash
cp scanner/themes.example.json ~/.deepvue/themes.json
```
Edit `~/.deepvue/themes.json` — toggle `enabled`, edit `tickers`, and set `_meta.output_dir`
to wherever you want the daily report written.

## 5. Run

```bash
pip install -r requirements.txt
playwright install chromium
python3 scanner/theme_scan.py        # theme-grouped daily report
# or
python3 scanner/breakout_top10.py    # whole-market Breakout Top 10
```

Prefer a different folder for credentials? Point `DEEPVUE_DIR` at it:
```bash
DEEPVUE_DIR=/path/to/secrets python3 scanner/theme_scan.py
```

---

## One-command import & manual refresh / 一键导入 + 手动续期

**`update_token.py` 让导入和续期都一条命令（纯标准库，无需 pip）：**

```bash
# 导入/重新导入：在【已登录的 app.deepvue.com】DevTools Console（上下文选 top，别选扩展）跑
#   copy(JSON.stringify({localStorage:{...localStorage}, sessionStorage:{...sessionStorage}}))
# 复制后（剪贴板里），直接：
python3 scanner/update_token.py            # 读剪贴板 → 写 tokens.json（自动提取 4 个字段）
# 或： pbpaste | python3 scanner/update_token.py   /   python3 scanner/update_token.py --file dump.json

# 手动续期：用保存的 refreshToken 换新 accessToken（并保存轮换后的新值）
python3 scanner/update_token.py --refresh
```

**用法很简单：** access token 只有 ~5 分钟，但 **`theme_scan.py` / `breakout_top10.py` 每次跑都会自动续**
——所以正常情况你什么都不用做，跑扫描器就行。只有当 **refreshToken 本身过期**（在别处登出 / 放太久）时，
脚本会明确提示，这时**重新导入一次**（上面那条 Console → `update_token.py`）即可，10 秒搞定。

> 不装任何后台定时服务（按需手动续即可）。**完全不想维护 token？把 `themes.json` 的 `backend` 设成
> `tradingview`——免登录、零 token、永不掉线；要 Deepvue 的实时/精确 ADR 时再切回 `deepvue`。**

---

## Heads-up / 注意

- **Tokens expire.** Access tokens last ~5 minutes; the script auto-refreshes via your
  `refreshToken`. If you **log out of Deepvue elsewhere**, the refreshToken dies — re-grab it
  (repeat step 2). The script will tell you with a clear message rather than a stack trace.
- **Never commit** `tokens.json` / `cookies.json`. They're git-ignored, but don't move them
  into the repo.
- This uses **your own paid account** and is subject to **Deepvue's Terms of Service**. Run it
  at human cadence (a few times a day), don't hammer it, and don't redistribute Deepvue data.
