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
floors={"price":1,"adr":0.03,"perf6M":0.20,"dollarVol20d":1_000_000,"perf3M_min":0.05,"perf1M_min":-0.20,
        "max_off_high":0.25,"require_stage2":True,"require_ma_stack":True, **meta.get("breakout_floors",{})}
ep={"gap_pct":0.10,"rel_vol":1.5,"perf6M_cap":1.0,"min_dollar_vol":floors["dollarVol20d"],
    "require_earnings":True,"max_days_since_earnings":5,"min_eps_growth_pct":25, **meta.get("ep_rules",{})}
# "就绪/可买"门槛：在 Breakout 命中里再筛"贴52周高 + 近月整理 + 仍强"的可立即出手形态（ready_top10.py 用）
ready={"max_off_high":0.20,"min_1m":-0.10,"max_1m":0.25,"min_3m":0.20,"min_dollar_vol":10_000_000,"adr_weight":1.5, **meta.get("ready_filter",{})}
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
def is_ready(m):
    # 在 Breakout 命中里再筛"就绪/可买"：贴 52 周高 + 近月在整理(没跌破/没暴冲) + 有过像样的季度推进。
    # 目的：把按 6M 排序时浮在最上面、已大幅延伸的"突破后期"票剔掉，只留随时可放量突破的形态。
    if not is_breakout(m): return False
    oh,p1,p3=m.get("off_high"),m.get("p1"),m.get("p3")
    if oh is None or p1 is None or p3 is None: return False
    return (oh>=-ready["max_off_high"] and ready["min_1m"]<=p1<=ready["max_1m"]
            and p3>=ready["min_3m"] and m["dollar_vol"]>=ready["min_dollar_vol"])
def ready_key(m):  # 就绪度：离 52 周高越近 + 近月越紧 + ADR 越高(high ADR is gold) → 分越高（降序排前）
    return (m["off_high"]-abs(m["p1"])+m["adr"]*ready["adr_weight"])

# ---------- backend: TradingView (public scan endpoint, no login). wanted=None → whole US universe ----------
def tv_fetch(wanted=None):
    cols=["name","close","Perf.6M","Perf.3M","Perf.1M","Volatility.M","average_volume_30d_calc","average_volume_10d_calc","average_volume_90d_calc",
          "price_52_week_high","SMA50","SMA200","gap","relative_volume_10d_calc","earnings_release_date","sector","type","exchange",
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
              "avg_vol_10d":n(d["average_volume_10d_calc"]),"avg_vol_90d":n(d["average_volume_90d_calc"]),
              "off_high":(last/hi-1) if (last and hi) else None,
              "above_50d":(last>s50) if (last and s50) else None,"above_200d":(last>s200) if (last and s200) else None,
              "ma50_gt_200":(s50>s200) if (s50 and s200) else None,
              "gap":(n(d["gap"]) or 0)/100 if n(d["gap"]) is not None else None,
              "relvol":n(d["relative_volume_10d_calc"]),"type":d.get("type"),"exchange":d.get("exchange"),
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
              "dollar_vol":n(g(225)),"sector":g(20) or "N/A","avg_vol_10d":None,"avg_vol_90d":None,"off_high":(last/hi-1) if (last and hi) else None,
              "above_50d":(pv50>0) if pv50 is not None else None,"above_200d":(pv200>0) if pv200 is not None else None,
              "ma50_gt_200":(pv50<pv200) if (pv50 is not None and pv200 is not None) else None,  # 价离50d更近⟺50d>200d
              "gap":n(g(260)),"relvol":n(g(11)),"type":None,"exchange":None,"eps_growth":n(g(1576)),
              "days_since_earn":((NOW-n(g(137)))/86400.0) if n(g(137)) else None}
    return M

def fetch(wanted=None): return (tv_fetch if BACKEND=="tradingview" else deepvue_fetch)(wanted)

# ---------- market environment (Qullamaggie 三道闸门#1：只在牛市交易) ----------
# 复刻 market-environment.pine 的 NDX MA 堆叠（用 QQQ 代理；EMA20 ≈ pine 的 EMA21）。always TV (no login).
REGIME_LABEL={"bull":"🟢 牛市","pullback":"🟡 回调","bear":"🔴 熊市","unknown":"⚪ 未知"}
def market_regime(symbol="NASDAQ:QQQ"):
    try:
        r=requests.post("https://scanner.tradingview.com/america/scan",headers={**UA,"content-type":"application/json"},
            json={"symbols":{"tickers":[symbol]},"columns":["close","EMA10","EMA20","SMA50"]},timeout=20)
        close,e10,e20,s50=r.json()["data"][0]["d"]
    except Exception: return ("unknown",{})
    if None in (e10,e20,s50): return ("unknown",{})
    if e10>e20>s50: st="bull"                                   # fast>mid>slow 堆叠 = 牛
    elif e10<e20 and (s50>e10 or s50>e20): st="bear"            # 慢线压住快/中线 = 熊
    else: st="pullback"                                         # 其余 = 回调/过渡
    return (st,{"close":close,"ema10":e10,"ema20":e20,"sma50":s50})
def regime_lines(symbol="NASDAQ:QQQ"):
    st,d=market_regime(symbol)
    if not d: return [f"> 市场环境（{symbol.split(':')[-1]}）：{REGIME_LABEL[st]}"]
    stack=f"EMA10 {d['ema10']:.0f} {'>' if d['ema10']>d['ema20'] else '<'} EMA20 {d['ema20']:.0f} {'>' if d['ema20']>d['sma50'] else '<'} SMA50 {d['sma50']:.0f}"
    out=[f"> 市场环境（{symbol.split(':')[-1]} {stack}）：**{REGIME_LABEL[st]}**"]
    if st!="bull": out.append("> ⚠️ **非牛市** —— Qullamaggie 三道闸门第一条（只在牛市交易）不成立；熊市/回调会系统性拉低胜率，建议空仓等待或只做观察。")
    return out

# ---------- format helpers ----------
def pct(x): return f"{x*100:+.0f}%" if isinstance(x,(int,float)) else "–"
def pct1(x): return f"{x*100:+.1f}%" if isinstance(x,(int,float)) else "–"
def fadr(x): return f"{x*100:.0f}%" if isinstance(x,(int,float)) else "–"
def fp(x): return f"{x:.2f}" if isinstance(x,(int,float)) else "–"
def fvol(x): return ("–" if not isinstance(x,(int,float)) else (f"{x/1e9:.1f}B" if x>=1e9 else f"{x/1e6:.0f}M"))
def frv(x): return f"{x:.1f}x" if isinstance(x,(int,float)) else "–"
def st2(m): return "✓" if (m.get("above_50d") and m.get("above_200d") and m.get("ma50_gt_200")) else ("50" if m.get("above_50d") else "—")
def tv_symbol(m): return f"{m['exchange']}:{m['ticker']}" if m.get("exchange") else m["ticker"]  # TradingView 图表用 EXCHANGE:TICKER

# ---------- 逐只详细分析（theme_scan / ready_top10 共用；themes 为空时表头只显示 sector）----------
def analysis(m, themes, fb, fe):
    setup="Breakout＋EP" if (fb and fe) else ("Breakout" if fb else "EP")
    p6,p3,p1,adr,gap,rv,dv,oh=m["p6"],m["p3"],m["p1"],m["adr"],m["gap"],m["relvol"],m["dollar_vol"],m["off_high"]
    eg,dse=m.get("eps_growth"),m.get("days_since_earn")
    # —— 选中理由（逐条对应过的门槛）——
    why=[f"6M {pct(p6)}·3M {pct(p3)}·1M {pct(p1)}（{'三周期共振、当下领涨' if (isinstance(p3,(int,float)) and p3>0.2) else '半年维度领涨'}）"]
    if fb:
        why.append("站稳 50/200 日线且 50>200 → **Stage 2 多头排列**")
        why.append(f"离52周高 {pct(oh)} → {'贴着高点蓄势（不是暴涨后的残骸）' if (isinstance(oh,(int,float)) and oh>-0.10) else '仍在 25% 阈值内、偏离 base'}")
    why.append(f"ADR {fadr(adr)}（爆发力够）·20日均额 {fvol(dv)}（流动性）")
    if fe:
        why.append(f"今日 Gap {pct1(gap)}·放量 {frv(rv)}" + (f"·EPS同比 {eg:+.0f}%·距财报 {dse:.0f}d → **财报型 EP**" if isinstance(eg,(int,float)) and isinstance(dse,(int,float)) else " → EP"))
    # —— 阶段判断 + 该股专属注意点 ——
    note=[]
    if fb:
        if (isinstance(p1,(int,float)) and p1>0.5) or (isinstance(p6,(int,float)) and p6>5):
            note.append("**已大幅延伸/偏抛物线（突破后期）**——别追高，现价进盈亏比差，等它回调收紧成新 base 再在 ORH 进")
        elif isinstance(p1,(int,float)) and -0.12<=p1<=0.25 and (p3 or 0)>0.2:
            note.append("**强势 + 近月在整理（较理想的 breakout 候选）**——等放量突破开盘区间高点(ORH)进")
        else:
            note.append("站上均线、趋势延续——跟随趋势，回调不破位即持有")
    elif fe:
        note.append("**冷门股被意外利好点燃**——盯当日 ORH 进、当日低点止损；盘前没放量则要求开盘 15-30 分钟内放到日均量，量不续即放弃")
    if isinstance(dv,(int,float)) and dv<50e6: note.append(f"⚠️ 成交额偏薄（{fvol(dv)}）→ 流动性/滑点风险，仓位别大")
    if isinstance(adr,(int,float)) and adr>=0.12: note.append(f"⚠️ 高波动（ADR {fadr(adr)}）→ 止损按 ADR 放宽、仓位相应缩小")
    if isinstance(oh,(int,float)) and oh<-0.18: note.append(f"⚠️ 已离高 {pct(oh)} → 偏离 base，确认是回踩而非破位再动")
    if isinstance(p1,(int,float)) and p1<-0.05 and fb: note.append(f"⚠️ 近1月 {pct(p1)} 在回调 → 等企稳重新站上短均线再考虑")
    if fe and isinstance(dse,(int,float)) and dse<=5: note.append("⚠️ 紧贴财报 → 注意财报后的二次波动/回吐")
    parts=[setup]+(['/'.join(themes)] if themes else [])+[m['sector']]
    return "\n".join([
        f"- **{m['ticker']}**（{'｜'.join(parts)}）",
        "  - **选中理由**：" + "；".join(why) + "。",
        "  - **阶段与注意**：" + "；".join(note) + "。",
    ])
