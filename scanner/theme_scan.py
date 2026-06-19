#!/usr/bin/env python3
# Theme-grouped swing-trading scan (Qullamaggie Breakout + EP), dual backend.
#   _meta.backend = "tradingview" (no login, free, default) | "deepvue" (own paid account, exact ADR/real-time)
# Reads ~/.deepvue/themes.json, fetches normalized metrics per ticker, flags Breakout (✓) / EP (⚡)
# with strict Stage-2 compliance, and writes a daily heatmap-style markdown report + per-stock analysis.
import json, requests, os, sys, time, datetime, statistics

HOME=os.environ.get("DEEPVUE_DIR", os.path.expanduser("~/.deepvue"))
def rd_json(p):
    with open(p, encoding="utf-8") as f: return json.load(f)
cfg=rd_json(f"{HOME}/themes.json"); meta=cfg["_meta"]
BACKEND=os.environ.get("SCAN_BACKEND", meta.get("backend","tradingview")).lower()  # SCAN_BACKEND env overrides config
floors={"price":1,"adr":0.03,"perf6M":0.20,"dollarVol20d":5_000_000,"perf3M_min":0.05,"perf1M_min":-0.20,
        "max_off_high":0.25,"require_stage2":True,"require_ma_stack":True, **meta.get("breakout_floors",{})}
ep={"gap_pct":0.10,"rel_vol":1.5,"perf6M_cap":1.0,"min_dollar_vol":floors["dollarVol20d"], **meta.get("ep_rules",{})}
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
    return (m["gap"]>=ep["gap_pct"] and m["relvol"]>=ep["rel_vol"] and m["last"]>=floors["price"]
            and m["dollar_vol"]>=ep["min_dollar_vol"] and m["p6"]<=ep["perf6M_cap"])

# ---------- backend: TradingView (public scan endpoint, no login) ----------
def tv_fetch(wanted):
    cols=["name","close","Perf.6M","Perf.3M","Perf.1M","Volatility.M","average_volume_30d_calc",
          "price_52_week_high","SMA50","SMA200","gap","relative_volume_10d_calc","earnings_release_date","sector"]
    # no is_primary filter: US-listed ADRs (ASX, ALM…) have foreign primary listings and would be dropped
    payload={"filter":[{"left":"close","operation":"greater","right":0.5},
                       {"left":"exchange","operation":"in_range","right":["NASDAQ","NYSE","AMEX"]}],
             "symbols":{"query":{"types":["stock","dr","fund"]},"tickers":[]},
             "columns":cols,"sort":{"sortBy":"Perf.6M","sortOrder":"desc"},"range":[0,30000]}
    r=requests.post("https://scanner.tradingview.com/america/scan",
                    headers={**UA,"content-type":"application/json"}, json=payload, timeout=40)
    r.raise_for_status()
    M={}
    n=lambda x: x if isinstance(x,(int,float)) else None
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
              "relvol":n(d["relative_volume_10d_calc"]),
              "days_since_earn":((NOW-ern)/86400.0) if ern else None}
    return M

# ---------- backend: Deepvue (own paid account, WS) ----------
def deepvue_fetch(wanted):
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
    if data.get("refreshToken"): tok["refreshToken"]=data["refreshToken"]   # rotation-safe: keep the latest
    with open(f"{HOME}/tokens.json","w",encoding="utf-8") as f: json.dump(tok,f,indent=2,ensure_ascii=False)
    H={**DUA,"authorization":f"Bearer {at}"}
    mp_path=f"{HOME}/symbols2_map.json"
    if os.path.exists(mp_path): tkr2idx={k:int(v) for k,v in rd_json(mp_path)["tkr2idx"].items()}
    else:
        durls=requests.get(f"{LS}/v1.0/definition-urls",headers=H,timeout=20).json()
        sym=requests.get(durls["symbols2"],headers=DUA,timeout=40).json(); tkr2idx={r[1]:r[0] for r in sym}
        with open(mp_path,"w",encoding="utf-8") as f: json.dump({"idx2tkr":{r[0]:r[1] for r in sym},"tkr2idx":tkr2idx},f)
    idxs=[tkr2idx[t] for t in wanted if t in tkr2idx]; idx2tkr={tkr2idx[t]:t for t in wanted if t in tkr2idx}
    if not idxs: return {}
    # cols: idx,last,ADR%,6M,3M,1M,$vol,sector,gap%,RV20,RecentEarn,52wHigh,priceVs50d,priceVs200d
    C=[0,3,1878,278,277,2081,225,20,260,11,137,215,284,286]
    def load_cookies(path):
        SS={"strict":"Strict","lax":"Lax","no_restriction":"None","none":"None","unspecified":"Lax"};out=[]
        for c in rd_json(path):
            ck={"name":c["name"],"value":c["value"],"domain":c["domain"],"path":c.get("path","/"),"secure":bool(c.get("secure",False)),"httpOnly":bool(c.get("httpOnly",False)),"sameSite":SS.get(str(c.get("sameSite","unspecified")).lower(),"Lax")}
            if "expirationDate" in c and not c.get("session",False): ck["expires"]=float(c["expirationDate"])
            if ck["sameSite"]=="None" and not ck["secure"]: ck["secure"]=True
            out.append(ck)
        return out
    init=f"localStorage.setItem('accessToken',{json.dumps(at)});localStorage.setItem('refreshToken',{json.dumps(tok['refreshToken'])});localStorage.setItem('deviceId',{json.dumps(tok['deviceId'])});localStorage.setItem('deepvue-chart-device-id',{json.dumps(tok['chartDeviceId'])});localStorage.setItem('theme','dark-mode');localStorage.setItem('i18nextLng','en');"
    js=r"""async ([cols,idxs,token,deviceId])=>{const J=o=>JSON.stringify(o);const sid='sid-'+Math.random().toString(36).slice(2)+Date.now().toString(36);const proto=`${sid}***${token}***${deviceId}`;const sleep=ms=>new Promise(r=>setTimeout(r,ms));const CH=300;return await new Promise(res=>{const ws=new WebSocket('wss://lightserver.deepvue.com/ws-data',[proto]);let by={},started=false;const fin=()=>{try{ws.close()}catch(e){};res({rows:Object.values(by)})};let hard=setTimeout(fin,45000);ws.onmessage=async ev=>{let m;try{m=JSON.parse(ev.data)}catch(e){return;}if(m.event==='Connect.Authorized'&&!started){started=true;for(let i=0;i<idxs.length;i+=CH){const part=idxs.slice(i,i+CH);ws.send(J({event:'Screener.Subscribe',data:{messageId:Math.floor(Math.random()*1e6),filters:[[[0,0,part]]],columns:cols,range:[0,part.length],sortBy:[],symbolIndex:0}}));await sleep(160);}let last=-1,stable=0;for(let k=0;k<40;k++){await sleep(400);const nn=Object.keys(by).length;if(nn>=idxs.length)break;if(nn===last){stable++;if(stable>=5)break;}else{stable=0;last=nn;}}clearTimeout(hard);fin();}else if((m.event==='Screener.Subscribe'||m.event==='Screener.Patch')&&Array.isArray(m.data&&m.data.data)){for(const r of m.data.data)if(Array.isArray(r))by[r[0]]=r;}};ws.onerror=()=>{clearTimeout(hard);fin()};});}"""
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True); ctx=b.new_context(); ctx.add_cookies(load_cookies(f"{HOME}/cookies.json")); ctx.add_init_script(init)
        pg=ctx.new_page(); pg.goto("https://app.deepvue.com/?p=screener",wait_until="domcontentloaded",timeout=45000); pg.wait_for_timeout(3500)
        res=pg.evaluate(js,[C,idxs,at,tok["deviceId"]]); b.close()
    ci={c:i for i,c in enumerate(C)}; n=lambda x: x if isinstance(x,(int,float)) else None
    M={}
    for row in res["rows"]:
        g=lambda c: row[ci[c]] if ci[c]<len(row) else None
        t=idx2tkr.get(g(0));
        if not t: continue
        last=n(g(3)); hi=n(g(215)); pv50=n(g(284)); pv200=n(g(286))
        M[t]={"ticker":t,"last":last,"adr":n(g(1878)),"p6":n(g(278)),"p3":n(g(277)),"p1":n(g(2081)),
              "dollar_vol":n(g(225)),"sector":g(20) or "N/A","off_high":(last/hi-1) if (last and hi) else None,
              "above_50d":(pv50>0) if pv50 is not None else None,"above_200d":(pv200>0) if pv200 is not None else None,
              "ma50_gt_200":(pv50<pv200) if (pv50 is not None and pv200 is not None) else None,  # 价离50d更近⟺50d>200d
              "gap":n(g(260)),"relvol":n(g(11)),
              "days_since_earn":((NOW-n(g(137)))/86400.0) if n(g(137)) else None}
    return M

# ---------- resolve themes, fetch ----------
enabled={k:v for k,v in cfg["themes"].items() if v.get("enabled")}
theme_tickers={k:list(dict.fromkeys(v["tickers"])) for k,v in enabled.items()}
all_tickers={t for ts in theme_tickers.values() for t in ts}
if not all_tickers: sys.exit("没有启用的主题/标的。")
M=(tv_fetch if BACKEND=="tradingview" else deepvue_fetch)(all_tickers)
unresolved={k:[t for t in ts if t not in M] for k,ts in theme_tickers.items()}
unresolved={k:v for k,v in unresolved.items() if v}
flags={t:(is_breakout(m),is_ep(m)) for t,m in M.items()}
idx_themes={}
for k,ts in theme_tickers.items():
    for t in ts: idx_themes.setdefault(t,[]).append(k)

# ---------- format helpers ----------
def pct(x): return f"{x*100:+.0f}%" if isinstance(x,(int,float)) else "–"
def pct1(x): return f"{x*100:+.1f}%" if isinstance(x,(int,float)) else "–"
def fadr(x): return f"{x*100:.0f}%" if isinstance(x,(int,float)) else "–"
def fp(x): return f"{x:.2f}" if isinstance(x,(int,float)) else "–"
def fvol(x): return ("–" if not isinstance(x,(int,float)) else (f"{x/1e9:.1f}B" if x>=1e9 else f"{x/1e6:.0f}M"))
def frv(x): return f"{x:.1f}x" if isinstance(x,(int,float)) else "–"
def st2(m): return "✓" if (m.get("above_50d") and m.get("above_200d") and m.get("ma50_gt_200")) else ("50" if m.get("above_50d") else "—")

# ---------- build report ----------
date_str=datetime.datetime.now().strftime("%Y-%m-%d"); run_ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
md=[f"# 主题扫描 {date_str}"]
md.append(f"\n> 运行：{run_ts} ｜ 后端：**{BACKEND}** ｜ 启用主题 {len(enabled)} ｜ 标的 {len(all_tickers)} ｜ 取到 {len(M)}")
md.append(f"> 图例：**✓**=Breakout（价≥1·ADR≥{floors['adr']*100:.0f}%·6M≥{floors['perf6M']*100:.0f}%·$额≥{floors['dollarVol20d']/1e6:.0f}M·**Stage2:站50&200日·50>200**·离52周高≤{floors['max_off_high']*100:.0f}%）｜ **⚡**=EP（Gap≥{ep['gap_pct']*100:.0f}%·放量≥{ep['rel_vol']}×·前6月≤{ep['perf6M_cap']*100:.0f}%）")
md.append("> St2 列：✓=站上50&200日且50>200；50=仅站50日；—=未站50日。✓/⚡仅过数值门槛，整理/吸筹形态仍须看图终判。\n")
for name in enabled:
    rows=[M[t] for t in theme_tickers[name] if t in M]
    rows.sort(key=lambda m:(m["p6"] if m["p6"] is not None else -9), reverse=True)
    nbk=sum(1 for m in rows if flags[m["ticker"]][0]); nep=sum(1 for m in rows if flags[m["ticker"]][1])
    p6s=[m["p6"] for m in rows if m["p6"] is not None]; medv=statistics.median(p6s) if p6s else None
    up=sum(1 for m in rows if isinstance(m["p1"],(int,float)) and m["p1"]>0); dn=sum(1 for m in rows if isinstance(m["p1"],(int,float)) and m["p1"]<0)
    md.append(f"## {name}　({len(rows)}只 · {nbk}✓ · {nep}⚡)　中位6M {pct(medv)} ｜ 近1月 🟩{up}:🟥{dn}")
    if enabled[name].get("note"): md.append(f"*{enabled[name]['note']}*")
    md.append("\n| | Tkr | Last | ADR | 6M | 3M | 1M | 离高 | St2 | Gap | RV | $Vol | Sector |")
    md.append("|--|--|--:|--:|--:|--:|--:|--:|:--:|--:|--:|--:|--|")
    for m in rows:
        fb,fe=flags[m["ticker"]]; mk=("✓" if fb else "")+("⚡" if fe else "")
        md.append(f"| {mk} | **{m['ticker']}** | {fp(m['last'])} | {fadr(m['adr'])} | {pct(m['p6'])} | {pct(m['p3'])} | {pct(m['p1'])} | {pct(m['off_high'])} | {st2(m)} | {pct1(m['gap'])} | {frv(m['relvol'])} | {fvol(m['dollar_vol'])} | {m['sector']} |")
    md.append("")

bk={t:(m,idx_themes.get(t,[])) for t,m in M.items() if flags[t][0]}
ep_hits={t:(m,idx_themes.get(t,[])) for t,m in M.items() if flags[t][1]}
def analysis(m,th):
    fb,fe=flags[m["ticker"]]; setup="Breakout＋EP" if (fb and fe) else ("Breakout" if fb else "EP")
    head=(f"- **{m['ticker']}**（{setup}｜{'/'.join(th)}）：6M {pct(m['p6'])}·3M {pct(m['p3'])}·1M {pct(m['p1'])}·离高 {pct(m['off_high'])}，ADR {fadr(m['adr'])}，$额 {fvol(m['dollar_vol'])}。")
    if fb:
        p1,p6,p3=m["p1"],m["p6"],m["p3"]
        if (isinstance(p1,(int,float)) and p1>0.5) or (isinstance(p6,(int,float)) and p6>5):
            body="已大幅延伸/偏抛物线——按方法属**突破后期**，别追高，等回调收紧成新 base 再看 ORH。"
        elif isinstance(p1,(int,float)) and -0.12<=p1<=0.25 and (p3 or 0)>0.2:
            body="**站上 50/200 日线 + 近月在整理**——较符合 breakout 候选，等放量突破开盘区间高点(ORH)进。"
        else: body="站上均线、仍在上升趋势中，跟住趋势、回调不破位即持有。"
        if fe: body+=f" 另今日 Gap {pct1(m['gap'])}/放量 {frv(m['relvol'])} 同时触发 **EP**。"
    else:
        body=f"今日 Gap {pct1(m['gap'])}、放量 {frv(m['relvol'])}，前期低迷(6M {pct(m['p6'])})——正合 EP 的**冷门股意外异动**；盯当日 **ORH** 进、**当日低点**止损，放量不续则放弃。"
    return head+body
bk_sorted=sorted(bk.values(), key=lambda x:(x[0]["p6"] if x[0]["p6"] is not None else -9), reverse=True)
md.append(f"---\n## 🏆 Breakout 命中 · 逐只分析（按6M，共{len(bk_sorted)}只）")
md.append("> 纪律：进场=**开盘区间高点 ORH** 突破；止损=**当日低点**且宽度≤ADR；进场3-5天卖1/3~1/2并移止损到保本，余仓 EMA10/20 trailing；**整理/吸筹形态务必在 TradingView 看图终判**。\n")
if bk_sorted:
    for i,(m,th) in enumerate(bk_sorted,1):
        md.append(analysis(m,th))
        if i==10 and len(bk_sorted)>10: md.append("\n*——— 以上为 Top 10（其余按6M续列）———*\n")
else: md.append("_今日无 Breakout 命中。_")
ep_sorted=sorted(ep_hits.values(), key=lambda x:(x[0]["gap"] if x[0]["gap"] is not None else -9), reverse=True)
md.append(f"\n## ⚡ EP 命中 · 逐只分析（按 Gap%，共{len(ep_sorted)}只）")
if ep_sorted:
    for m,th in ep_sorted: md.append(analysis(m,th))
else: md.append("_今日无 EP 命中（事件驱动跳空较罕见；非交易日/盘后数据可能无当日跳空）。_")
if unresolved:
    md.append("\n---\n## ⚠️ 未取到数据的 ticker（退市/非美股/拼写）")
    for k,vv in unresolved.items(): md.append(f"- **{k}**: {', '.join(vv)}")
md.append(f"\n---\n*后端={BACKEND}；口径在 `themes.json` 调（backend/breakout_floors/ep_rules）。TV 后端免登录、数据为延迟/EOD、ADR≈Volatility.M。非投资建议。*")

os.makedirs(OUTDIR, exist_ok=True); out_path=os.path.join(OUTDIR, f"{date_str}.md")
with open(out_path,"w",encoding="utf-8") as f: f.write("\n".join(md))
print(f"后端 {BACKEND} ｜ 主题 {len(enabled)} ｜ 标的 {len(all_tickers)} ｜ 取到 {len(M)}")
if unresolved:
    for k,vv in unresolved.items(): print(f"  ⚠️ {k}: {', '.join(vv)}")
print(f"Breakout {len(bk)} ｜ EP {len(ep_hits)}（均含逐只分析）")
print("各主题: "+" ｜ ".join(f"{k}({sum(1 for t in theme_tickers[k] if t in M)}/{sum(1 for t in theme_tickers[k] if t in M and flags[t][0])}✓/{sum(1 for t in theme_tickers[k] if t in M and flags[t][1])}⚡)" for k in enabled))
print(f"\n📄 已保存: {out_path}")
