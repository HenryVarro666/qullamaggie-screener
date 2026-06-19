#!/usr/bin/env python3
# Shared core for the Qullamaggie scanner: config, strict predicates, dual-backend fetchers,
# and formatters. Imported by theme_scan.py (themes) and breakout_top10.py (whole market).
# No execution on import beyond reading themes.json config.
import json, requests, os, sys, time

HOME=os.environ.get("DEEPVUE_DIR", os.path.expanduser("~/.deepvue"))
def rd_json(p):
    with open(p, encoding="utf-8") as f: return json.load(f)
cfg=rd_json(f"{HOME}/themes.json"); meta=cfg["_meta"]
BACKEND=os.environ.get("SCAN_BACKEND", meta.get("backend","tradingview")).lower()  # SCAN_BACKEND env overrides config
floors={"price":1,"adr":0.03,"perf6M":0.20,"dollarVol20d":5_000_000,"perf3M_min":0.05,"perf1M_min":-0.20,
        "max_off_high":0.25,"require_stage2":True,"require_ma_stack":True, **meta.get("breakout_floors",{})}
ep={"gap_pct":0.10,"rel_vol":1.5,"perf6M_cap":1.0,"min_dollar_vol":floors["dollarVol20d"],
    "require_earnings":True,"max_days_since_earnings":5,"min_eps_growth_pct":25, **meta.get("ep_rules",{})}
OUTDIR=os.path.expanduser(meta.get("output_dir", os.path.join(HOME,"scans")))
NOW=time.time()
UA={"user-agent":"Mozilla/5.0"}

# ---------- strict predicates (operate on a normalized metrics dict) ----------
def is_breakout(m):
    if any(m.get(k) is None for k in ("last","adr","p6","p3","p1","dollar_vol")): return False
    if m["off_high"] is not None and m["off_high"] < -floors["max_off_high"]: return False
    if floors["require_stage2"] and not (m["above_50d"] and m["above_200d"]): return False   # 周线 Stage 2: 站上 50/200 日线
    if floors["require_ma_stack"] and not m["ma50_gt_200"]: return False                      # 多头排列 50>200
    return (m["last"]>=floors["price"] and m["adr"]>=floors["adr"] and m["p6"]>=floors["perf6M"]
            and m["dollar_vol"]>=floors["dollarVol20d"] and m["p3"]>=floors["perf3M_min"]
            and m["p1"]>=floors["perf1M_min"] and m["p6"]<=20)  # p6<=20(=2000%) drops data glitches
def is_ep(m):
    if any(m.get(k) is None for k in ("last","dollar_vol","gap","relvol","p6")): return False
    if not (m["gap"]>=ep["gap_pct"] and m["relvol"]>=ep["rel_vol"] and m["last"]>=floors["price"]
            and m["dollar_vol"]>=ep["min_dollar_vol"] and m["p6"]<=ep["perf6M_cap"]): return False
    if ep["require_earnings"]:   # 财报型 EP：近财报 + 强劲 EPS 增长（贴源 EP 选股器的财务列；设 false 可含非财报催化）
        dse=m.get("days_since_earn"); eg=m.get("eps_growth")
        if dse is None or dse>ep["max_days_since_earnings"]: return False
        if eg is None or eg<ep["min_eps_growth_pct"]: return False
    return True

# ---------- backend: TradingView (public scan endpoint, no login). wanted=None → whole US universe ----------
def tv_fetch(wanted=None):
    cols=["name","close","Perf.6M","Perf.3M","Perf.1M","Volatility.M","average_volume_30d_calc",
          "price_52_week_high","SMA50","SMA200","gap","relative_volume_10d_calc","earnings_release_date","sector","type",
          "earnings_per_share_diluted_yoy_growth_fq"]
    # no is_primary filter: US-listed ADRs (ASX, ALM…) have foreign primary listings and would be dropped
    payload={"filter":[{"left":"close","operation":"greater","right":0.5},
                       {"left":"exchange","operation":"in_range","right":["NASDAQ","NYSE","AMEX"]}],
             "symbols":{"query":{"types":["stock","dr","fund"]},"tickers":[]},
             "columns":cols,"sort":{"sortBy":"Perf.6M","sortOrder":"desc"},"range":[0,30000]}
    r=requests.post("https://scanner.tradingview.com/america/scan",
                    headers={**UA,"content-type":"application/json"}, json=payload, timeout=40)
    r.raise_for_status()
    M={}; n=lambda x: x if isinstance(x,(int,float)) else None
    for row in r.json().get("data",[]):
        d=dict(zip(cols,row["d"])); t=d["name"]
        if wanted and t not in wanted: continue
        last=n(d["close"]); hi=n(d["price_52_week_high"]); s50=n(d["SMA50"]); s200=n(d["SMA200"])
        av=n(d["average_volume_30d_calc"]); ern=n(d["earnings_release_date"])
        M[t]={"ticker":t,"last":last,"adr":(n(d["Volatility.M"]) or 0)/100 if n(d["Volatility.M"]) is not None else None,
              "p6":(n(d["Perf.6M"]) or 0)/100 if n(d["Perf.6M"]) is not None else None,
              "p3":(n(d["Perf.3M"]) or 0)/100 if n(d["Perf.3M"]) is not None else None,
              "p1":(n(d["Perf.1M"]) or 0)/100 if n(d["Perf.1M"]) is not None else None,
              "dollar_vol":(av*last) if (av is not None and last is not None) else None,"sector":d["sector"] or "N/A",
              "off_high":(last/hi-1) if (last and hi) else None,
              "above_50d":(last>s50) if (last and s50) else None,"above_200d":(last>s200) if (last and s200) else None,
              "ma50_gt_200":(s50>s200) if (s50 and s200) else None,
              "gap":(n(d["gap"]) or 0)/100 if n(d["gap"]) is not None else None,
              "relvol":n(d["relative_volume_10d_calc"]),"type":d.get("type"),
              "eps_growth":n(d.get("earnings_per_share_diluted_yoy_growth_fq")),
              "days_since_earn":((NOW-ern)/86400.0) if ern else None}
    return M

# ---------- backend: Deepvue (own paid account, WS). wanted=None → whole market (all symbols) ----------
def deepvue_fetch(wanted=None):
    from playwright.sync_api import sync_playwright
    API="https://api.deepvue.com"; LS="https://lightserver.deepvue.com"; DUA={**UA,"origin":"https://app.deepvue.com"}
    tok=rd_json(f"{HOME}/tokens.json")
    try:
        resp=requests.post(f"{API}/api/v2/auth/refresh",json={"refreshToken":tok["refreshToken"]},
                           headers={**DUA,"content-type":"application/json"},timeout=20)
    except requests.RequestException as e: sys.exit(f"❌ 连接 Deepvue 失败：{e}")
    data=resp.json() if "json" in resp.headers.get("content-type","") else {}
    at=data.get("accessToken")
    if not at: sys.exit(f"❌ Deepvue 登录已失效（refreshToken 过期？HTTP {resp.status_code}）。跑 `python3 update_token.py` 重新导入，或把 themes.json 的 backend 改成 tradingview。")
    tok["accessToken"]=at
    if data.get("refreshToken"): tok["refreshToken"]=data["refreshToken"]   # rotation-safe
    with open(f"{HOME}/tokens.json","w",encoding="utf-8") as f: json.dump(tok,f,indent=2,ensure_ascii=False)
    H={**DUA,"authorization":f"Bearer {at}"}
    mp_path=f"{HOME}/symbols2_map.json"
    if os.path.exists(mp_path): tkr2idx={k:int(v) for k,v in rd_json(mp_path)["tkr2idx"].items()}
    else:
        durls=requests.get(f"{LS}/v1.0/definition-urls",headers=H,timeout=20).json()
        sym=requests.get(durls["symbols2"],headers=DUA,timeout=40).json(); tkr2idx={r[1]:r[0] for r in sym}
        with open(mp_path,"w",encoding="utf-8") as f: json.dump({"idx2tkr":{r[0]:r[1] for r in sym},"tkr2idx":tkr2idx},f)
    if wanted is None: wanted=set(tkr2idx.keys())                          # whole market
    idxs=[tkr2idx[t] for t in wanted if t in tkr2idx]; idx2tkr={tkr2idx[t]:t for t in wanted if t in tkr2idx}
    if not idxs: return {}
    C=[0,3,1878,278,277,2081,225,20,260,11,137,215,284,286,1576]  # …pvs200,EPSgrowthQtr
    def load_cookies(path):
        SS={"strict":"Strict","lax":"Lax","no_restriction":"None","none":"None","unspecified":"Lax"};out=[]
        for c in rd_json(path):
            ck={"name":c["name"],"value":c["value"],"domain":c["domain"],"path":c.get("path","/"),"secure":bool(c.get("secure",False)),"httpOnly":bool(c.get("httpOnly",False)),"sameSite":SS.get(str(c.get("sameSite","unspecified")).lower(),"Lax")}
            if "expirationDate" in c and not c.get("session",False): ck["expires"]=float(c["expirationDate"])
            if ck["sameSite"]=="None" and not ck["secure"]: ck["secure"]=True
            out.append(ck)
        return out
    init=f"localStorage.setItem('accessToken',{json.dumps(at)});localStorage.setItem('refreshToken',{json.dumps(tok['refreshToken'])});localStorage.setItem('deviceId',{json.dumps(tok['deviceId'])});localStorage.setItem('deepvue-chart-device-id',{json.dumps(tok['chartDeviceId'])});localStorage.setItem('theme','dark-mode');localStorage.setItem('i18nextLng','en');"
    js=r"""async ([cols,idxs,token,deviceId])=>{const J=o=>JSON.stringify(o);const sid='sid-'+Math.random().toString(36).slice(2)+Date.now().toString(36);const proto=`${sid}***${token}***${deviceId}`;const sleep=ms=>new Promise(r=>setTimeout(r,ms));const CH=300;return await new Promise(res=>{const ws=new WebSocket('wss://lightserver.deepvue.com/ws-data',[proto]);let by={},started=false;const fin=()=>{try{ws.close()}catch(e){};res({rows:Object.values(by)})};let hard=setTimeout(fin,60000);ws.onmessage=async ev=>{let m;try{m=JSON.parse(ev.data)}catch(e){return;}if(m.event==='Connect.Authorized'&&!started){started=true;for(let i=0;i<idxs.length;i+=CH){const part=idxs.slice(i,i+CH);ws.send(J({event:'Screener.Subscribe',data:{messageId:Math.floor(Math.random()*1e6),filters:[[[0,0,part]]],columns:cols,range:[0,part.length],sortBy:[],symbolIndex:0}}));await sleep(150);}let last=-1,stable=0;for(let k=0;k<80;k++){await sleep(450);const nn=Object.keys(by).length;if(nn>=idxs.length)break;if(nn===last){stable++;if(stable>=6)break;}else{stable=0;last=nn;}}clearTimeout(hard);fin();}else if((m.event==='Screener.Subscribe'||m.event==='Screener.Patch')&&Array.isArray(m.data&&m.data.data)){for(const r of m.data.data)if(Array.isArray(r))by[r[0]]=r;}};ws.onerror=()=>{clearTimeout(hard);fin()};});}"""
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True); ctx=b.new_context(); ctx.add_cookies(load_cookies(f"{HOME}/cookies.json")); ctx.add_init_script(init)
        pg=ctx.new_page(); pg.goto("https://app.deepvue.com/?p=screener",wait_until="domcontentloaded",timeout=45000); pg.wait_for_timeout(3500)
        res=pg.evaluate(js,[C,idxs,at,tok["deviceId"]]); b.close()
    ci={c:i for i,c in enumerate(C)}; n=lambda x: x if isinstance(x,(int,float)) else None
    M={}
    for row in res["rows"]:
        g=lambda c: row[ci[c]] if ci[c]<len(row) else None
        t=idx2tkr.get(g(0))
        if not t: continue
        last=n(g(3)); hi=n(g(215)); pv50=n(g(284)); pv200=n(g(286))
        M[t]={"ticker":t,"last":last,"adr":n(g(1878)),"p6":n(g(278)),"p3":n(g(277)),"p1":n(g(2081)),
              "dollar_vol":n(g(225)),"sector":g(20) or "N/A","off_high":(last/hi-1) if (last and hi) else None,
              "above_50d":(pv50>0) if pv50 is not None else None,"above_200d":(pv200>0) if pv200 is not None else None,
              "ma50_gt_200":(pv50<pv200) if (pv50 is not None and pv200 is not None) else None,  # 价离50d更近⟺50d>200d
              "gap":n(g(260)),"relvol":n(g(11)),"type":None,"eps_growth":n(g(1576)),
              "days_since_earn":((NOW-n(g(137)))/86400.0) if n(g(137)) else None}
    return M

def fetch(wanted=None): return (tv_fetch if BACKEND=="tradingview" else deepvue_fetch)(wanted)

# ---------- format helpers ----------
def pct(x): return f"{x*100:+.0f}%" if isinstance(x,(int,float)) else "–"
def pct1(x): return f"{x*100:+.1f}%" if isinstance(x,(int,float)) else "–"
def fadr(x): return f"{x*100:.0f}%" if isinstance(x,(int,float)) else "–"
def fp(x): return f"{x:.2f}" if isinstance(x,(int,float)) else "–"
def fvol(x): return ("–" if not isinstance(x,(int,float)) else (f"{x/1e9:.1f}B" if x>=1e9 else f"{x/1e6:.0f}M"))
def frv(x): return f"{x:.1f}x" if isinstance(x,(int,float)) else "–"
def st2(m): return "✓" if (m.get("above_50d") and m.get("above_200d") and m.get("ma50_gt_200")) else ("50" if m.get("above_50d") else "—")
