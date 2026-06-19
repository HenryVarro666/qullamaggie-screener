#!/usr/bin/env python3
# Deepvue token helper (stdlib only — the keep-alive needs no pip install).
#   python3 update_token.py            # seed/re-seed: parse a DevTools storage dump (clipboard / stdin / --file) -> tokens.json
#   python3 update_token.py --refresh  # keep-alive: refresh accessToken from saved refreshToken (rotation-safe). For cron/launchd.
import json, os, sys, subprocess, base64, time, urllib.request

HOME=os.environ.get("DEEPVUE_DIR", os.path.expanduser("~/.deepvue"))
TOK=os.path.join(HOME,"tokens.json")
REFRESH_URL="https://api.deepvue.com/api/v2/auth/refresh"

def jwt_payload(at):
    try:
        p=at.split(".")[1]; p+="="*(-len(p)%4)
        return json.loads(base64.urlsafe_b64decode(p))
    except Exception: return {}

def do_refresh():
    if not os.path.exists(TOK): sys.exit(f"❌ 没有 {TOK}，先跑一次不带 --refresh 的导入。")
    tok=json.load(open(TOK,encoding="utf-8"))
    rt=tok.get("refreshToken")
    if not rt: sys.exit("❌ tokens.json 里没有 refreshToken。")
    req=urllib.request.Request(REFRESH_URL, data=json.dumps({"refreshToken":rt}).encode(),
        headers={"content-type":"application/json","origin":"https://app.deepvue.com","user-agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r: data=json.loads(r.read())
    except Exception as e:
        sys.exit(f"❌ 刷新失败（refreshToken 可能已过期/登出，需重新导入）：{e}")
    at=data.get("accessToken")
    if not at: sys.exit("❌ 刷新返回无 accessToken（refreshToken 失效）。请重新导入。")
    tok["accessToken"]=at
    if data.get("refreshToken"): tok["refreshToken"]=data["refreshToken"]   # rotation-safe: keep the latest
    if data.get("deviceId"): tok["deviceId"]=data["deviceId"]
    json.dump(tok, open(TOK,"w",encoding="utf-8"), indent=2, ensure_ascii=False)
    pl=jwt_payload(at); exp=pl.get("exp")
    left=f"，accessToken {int(exp-time.time())}s 后过期" if exp else ""
    print(f"[{time.strftime('%Y-%m-%d %H:%M')}] ✓ 刷新成功 role={pl.get('role')}{left}")

def read_dump():
    if "--file" in sys.argv: return open(sys.argv[sys.argv.index("--file")+1],encoding="utf-8").read()
    if not sys.stdin.isatty():
        s=sys.stdin.read()
        if s.strip(): return s
    try: return subprocess.run(["pbpaste"],capture_output=True,text=True).stdout
    except Exception: return ""

def do_import():
    raw=read_dump().strip()
    if not raw:
        sys.exit("❌ 没读到输入。先在已登录的 app.deepvue.com 的 DevTools Console 跑：\n"
                 "   copy(JSON.stringify({localStorage:{...localStorage},sessionStorage:{...sessionStorage}}))\n"
                 "   复制后直接跑本脚本（读剪贴板），或 `pbpaste | python3 update_token.py`，或 --file dump.json")
    try: obj=json.loads(raw)
    except Exception as e: sys.exit(f"❌ 输入不是合法 JSON：{e}")
    ls=obj.get("localStorage", obj)   # 接受完整 dump、localStorage 对象、或定向命令的扁平 blob
    field={"accessToken":["accessToken"],"refreshToken":["refreshToken"],"deviceId":["deviceId"],
           "chartDeviceId":["deepvue-chart-device-id","chartDeviceId"]}   # 两种键名都认
    out={}
    for k,srcs in field.items():
        for s in srcs:
            if ls.get(s): out[k]=ls[s]; break
    if not out.get("refreshToken"): sys.exit("❌ 没找到 refreshToken（确认是在已登录的 app.deepvue.com 上跑的 Console 命令）。")
    os.makedirs(HOME,exist_ok=True)
    json.dump(out, open(TOK,"w",encoding="utf-8"), indent=2, ensure_ascii=False); os.chmod(TOK,0o600)
    pl=jwt_payload(out.get("accessToken",""))
    print(f"✓ 已写 {TOK}  role={pl.get('role')} email={pl.get('email')}")
    print("  下一步：跑 `python3 update_token.py --refresh` 验证；装 keep-alive 让它自动续（见 AUTH_SETUP.md）。")

(do_refresh if "--refresh" in sys.argv else do_import)()
