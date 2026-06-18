#!/usr/bin/env python3
# Theme-grouped Deepvue scan with Breakout + EP flags.
# Reads ~/.deepvue/themes.json (toggle themes on/off), fetches metrics for each theme's
# tickers via the screener WebSocket, flags Breakout (✓) and EP (⚡), prints a summary,
# and writes a daily heatmap-style markdown report (+Top10 精选) into the Obsidian vault.
import json, requests, os, sys, time, datetime, statistics
from playwright.sync_api import sync_playwright

HOME=os.environ.get("DEEPVUE_DIR", os.path.expanduser("~/.deepvue"))
API="https://api.deepvue.com"; LS="https://lightserver.deepvue.com"
UA={"user-agent":"Mozilla/5.0","origin":"https://app.deepvue.com"}

def rd_json(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

tok=rd_json(f"{HOME}/tokens.json")
cfg=rd_json(f"{HOME}/themes.json")
meta=cfg["_meta"]
# config defaults so a missing/renamed key never crashes after the scan
floors={"price":1,"adr":0.03,"perf6M":0.20,"dollarVol20d":500000,"perf3M_min":0.05,"perf1M_min":-0.20,
        "max_off_high":0.25,
        **meta.get("breakout_floors",{})}
ep={"gap_pct":0.10,"rel_vol":1.5,"perf6M_cap":1.0, **meta.get("ep_rules",{})}
OUTDIR=meta.get("output_dir", os.path.join(HOME,"scans"))

# --- auth: mint a fresh access token (clear error instead of KeyError if refresh fails) ---
try:
    resp=requests.post(f"{API}/api/v2/auth/refresh", json={"refreshToken":tok["refreshToken"]},
                       headers={**UA,"content-type":"application/json"}, timeout=20)
except requests.RequestException as e:
    sys.exit(f"❌ 连接 Deepvue 失败：{e}")
at=(resp.json() if "json" in resp.headers.get("content-type","") else {}).get("accessToken")
if not at:
    sys.exit(f"❌ Deepvue 登录已失效（refreshToken 过期？HTTP {resp.status_code}）。请重新从浏览器抓取 token/cookie。")
tok["accessToken"]=at
with open(f"{HOME}/tokens.json","w",encoding="utf-8") as f: json.dump(tok,f,indent=2,ensure_ascii=False)
H={**UA,"authorization":f"Bearer {at}"}

# ticker -> index map (cache)
mp_path=f"{HOME}/symbols2_map.json"
if os.path.exists(mp_path):
    tkr2idx={k:int(v) for k,v in rd_json(mp_path)["tkr2idx"].items()}
else:
    durls=requests.get(f"{LS}/v1.0/definition-urls",headers=H,timeout=20).json()
    sym=requests.get(durls["symbols2"],headers=UA,timeout=40).json()
    tkr2idx={r[1]:r[0] for r in sym}
    with open(mp_path,"w",encoding="utf-8") as f:
        json.dump({"idx2tkr":{r[0]:r[1] for r in sym},"tkr2idx":tkr2idx},f)

enabled={n:t for n,t in cfg["themes"].items() if t.get("enabled")}
theme_idx={}; unresolved={}; all_idx=set()
for n,t in enabled.items():
    res=[]; miss=[]
    for tk in t["tickers"]:
        if tk in tkr2idx: res.append(tkr2idx[tk]); all_idx.add(tkr2idx[tk])
        else: miss.append(tk)
    theme_idx[n]=res
    if miss: unresolved[n]=miss
all_idx=sorted(all_idx)
if not all_idx:
    sys.exit("没有可扫描的标的(全部主题关闭或 ticker 解析失败)。")
idx_themes={}
for n in enabled:
    for i in theme_idx[n]: idx_themes.setdefault(i,[]).append(n)

# cols: symIdx,ticker,last,ADR%20d,6M,3M,1M,avg$vol20d,sector, Gap%,RV20,RecentEarnDate(epoch s),%fromLastEarn,%chgToday, 52wHigh
COLUMNS=[0,17,3,1878,278,277,2081,225,20, 260,11,137,457,218, 215]

def load_cookies(path):
    SS={"strict":"Strict","lax":"Lax","no_restriction":"None","none":"None","unspecified":"Lax"}; out=[]
    for c in rd_json(path):
        ck={"name":c["name"],"value":c["value"],"domain":c["domain"],"path":c.get("path","/"),
            "secure":bool(c.get("secure",False)),"httpOnly":bool(c.get("httpOnly",False)),
            "sameSite":SS.get(str(c.get("sameSite","unspecified")).lower(),"Lax")}
        if "expirationDate" in c and not c.get("session",False): ck["expires"]=float(c["expirationDate"])
        if ck["sameSite"]=="None" and not ck["secure"]: ck["secure"]=True
        out.append(ck)
    return out
cookies=load_cookies(f"{HOME}/cookies.json")
init=f"""
localStorage.setItem('accessToken', {json.dumps(at)});
localStorage.setItem('refreshToken', {json.dumps(tok['refreshToken'])});
localStorage.setItem('deviceId', {json.dumps(tok['deviceId'])});
localStorage.setItem('deepvue-chart-device-id', {json.dumps(tok['chartDeviceId'])});
localStorage.setItem('theme','dark-mode'); localStorage.setItem('i18nextLng','en');
"""
js=r"""
async ([cols, idxs, token, deviceId]) => {
  const J=(o)=>JSON.stringify(o);
  const sid='sid-'+Math.random().toString(36).slice(2)+Date.now().toString(36);
  const proto=`${sid}***${token}***${deviceId}`; const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const CH=300;
  return await new Promise((resolve)=>{
    const ws=new WebSocket('wss://lightserver.deepvue.com/ws-data',[proto]); let by={}, started=false;
    const fin=()=>{try{ws.close()}catch(e){};resolve({rows:Object.values(by)})}; let hard=setTimeout(fin,45000);
    ws.onmessage=async(ev)=>{let m;try{m=JSON.parse(ev.data)}catch(e){return;}
      if(m.event==='Connect.Authorized'&&!started){started=true;
        for(let i=0;i<idxs.length;i+=CH){const part=idxs.slice(i,i+CH);
          ws.send(J({event:'Screener.Subscribe',data:{messageId:Math.floor(Math.random()*1e6),
            filters:[[[0,0,part]]],columns:cols,range:[0,part.length],sortBy:[],symbolIndex:0}})); await sleep(160);}
        let last=-1,stable=0;
        for(let k=0;k<40;k++){await sleep(400);const n=Object.keys(by).length; if(n>=idxs.length)break;
          if(n===last){stable++;if(stable>=5)break;}else{stable=0;last=n;}}
        clearTimeout(hard);fin();
      } else if((m.event==='Screener.Subscribe'||m.event==='Screener.Patch')&&Array.isArray(m.data&&m.data.data)){
        for(const r of m.data.data) if(Array.isArray(r)) by[r[0]]=r;}};
    ws.onerror=()=>{clearTimeout(hard);fin()};});
}
"""
with sync_playwright() as p:
    b=p.chromium.launch(headless=True); ctx=b.new_context(); ctx.add_cookies(cookies); ctx.add_init_script(init)
    page=ctx.new_page(); page.goto("https://app.deepvue.com/?p=screener",wait_until="domcontentloaded",timeout=45000)
    page.wait_for_timeout(3500); res=page.evaluate(js,[COLUMNS, all_idx, at, tok["deviceId"]]); b.close()

ci={c:i for i,c in enumerate(COLUMNS)}
v=lambda r,c: r[ci[c]] if r and ci[c]<len(r) else None
num=lambda x: x if isinstance(x,(int,float)) else None
by={r[0]:r for r in res["rows"]}
NOW=time.time()

def off_high(r):
    last,hi=num(v(r,3)),num(v(r,215))
    return (last/hi - 1) if (last and hi and hi>0) else None
def is_breakout(r):
    last,adr,p6,p3,p1,dv=[num(v(r,c)) for c in (3,1878,278,277,2081,225)]
    if None in (last,adr,p6,p3,p1,dv): return False
    # 必须贴近 52 周高点：Qullamaggie leader 在高点附近突破，不是离高点一大截的崩塌残骸(挡掉 MNTS 这种暴涨后腰斩)
    oh=off_high(r)
    if oh is not None and oh < -floors["max_off_high"]: return False
    return (last>=floors["price"] and adr>=floors["adr"] and p6>=floors["perf6M"] and dv>=floors["dollarVol20d"]
            and p3>=floors["perf3M_min"] and p1>=floors["perf1M_min"] and p6<=20)  # p6<=20(=2000%) drops data glitches
def days_since_earn(r):
    e=num(v(r,137))
    if not e or e<=0: return None
    return (NOW-e)/86400.0
def is_ep(r):
    # 原始口径: 跳空≥10% + 放量 + 过去6月没怎么涨(perf6M 上限) + 基本流动性。财报为主但不限财报。
    last,dv,gap,rv,p6=[num(v(r,c)) for c in (3,225,260,11,278)]
    if None in (last,dv,gap,rv,p6): return False
    return (gap>=ep["gap_pct"] and rv>=ep["rel_vol"] and last>=floors["price"]
            and dv>=floors["dollarVol20d"] and p6<=ep["perf6M_cap"])

# precompute flags once per fetched row (no repeated predicate calls)
flags={idx:(is_breakout(r), is_ep(r)) for idx,r in by.items()}

def pct(x): return f"{x*100:+.0f}%" if isinstance(x,(int,float)) else "–"
def pct1(x): return f"{x*100:+.1f}%" if isinstance(x,(int,float)) else "–"
def fadr(x): return f"{x*100:.0f}%" if isinstance(x,(int,float)) else "–"
def fp(x): return f"{x:.2f}" if isinstance(x,(int,float)) else "–"
def fvol(x):
    if not isinstance(x,(int,float)): return "–"
    return f"{x/1e9:.1f}B" if x>=1e9 else f"{x/1e6:.0f}M"
def frv(x): return f"{x:.1f}x" if isinstance(x,(int,float)) else "–"

date_str=datetime.datetime.now().strftime("%Y-%m-%d")
run_ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
md=[]
md.append(f"# 主题扫描 {date_str}")
md.append(f"\n> 运行：{run_ts} ｜ 数据源：Deepvue ｜ 启用主题 {len(enabled)} ｜ 去重标的 {len(all_idx)} ｜ 取到 {len(by)}")
md.append(f"> 图例：**✓**=Breakout（价≥1·ADR≥3%·6M≥20%·$额≥500K·仍上行·**离52周高≤{floors['max_off_high']*100:.0f}%**）｜ **⚡**=EP（Gap≥{ep['gap_pct']*100:.0f}%·放量≥{ep['rel_vol']}×·前6月涨幅≤{ep['perf6M_cap']*100:.0f}%；财报为主但不限财报）")
md.append("> ✓/⚡ 仅过数值门槛；Stage2 与整理/吸筹形态请在 TradingView 看图终判。\n")

# per-theme sections (show ALL members)
for name in enabled:
    rows=[by[i] for i in theme_idx[name] if i in by]
    rows.sort(key=lambda r:(num(v(r,278)) if num(v(r,278)) is not None else -9), reverse=True)
    nbk=sum(1 for r in rows if flags[r[0]][0]); nep=sum(1 for r in rows if flags[r[0]][1])
    p6s=[num(v(r,278)) for r in rows if num(v(r,278)) is not None]
    medv=statistics.median(p6s) if p6s else None
    p1s=[num(v(r,2081)) for r in rows]
    up=sum(1 for x in p1s if isinstance(x,(int,float)) and x>0)
    dn=sum(1 for x in p1s if isinstance(x,(int,float)) and x<0)
    note=enabled[name].get("note","")
    md.append(f"## {name}　({len(rows)}只 · {nbk}✓ · {nep}⚡)　中位6M {pct(medv)} ｜ 近1月 🟩{up}:🟥{dn}")
    if note: md.append(f"*{note}*")
    md.append("\n| | Tkr | Last | ADR | 6M | 3M | 1M | 离高 | Gap | RV | $Vol | Sector |")
    md.append("|--|--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--|")
    for r in rows:
        fb,fe=flags[r[0]]; mk=("✓" if fb else "")+("⚡" if fe else "")
        md.append(f"| {mk} | **{v(r,17)}** | {fp(num(v(r,3)))} | {fadr(num(v(r,1878)))} | {pct(num(v(r,278)))} | {pct(num(v(r,277)))} | {pct(num(v(r,2081)))} | {pct(off_high(r))} | {pct1(num(v(r,260)))} | {frv(num(v(r,11)))} | {fvol(num(v(r,225)))} | {v(r,20)} |")
    md.append("")

# unique cross-theme hits (dedup by ticker; aggregate theme labels)
bk_unique={idx:(r, idx_themes.get(idx,[])) for idx,r in by.items() if flags[idx][0]}
ep_unique={idx:(r, idx_themes.get(idx,[])) for idx,r in by.items() if flags[idx][1]}

def analysis(r, th):
    p6,p3,p1,adr,gap,rv,dv=[num(v(r,c)) for c in (278,277,2081,1878,260,11,225)]
    fb,fe=flags[r[0]]
    setup="Breakout＋EP" if (fb and fe) else ("Breakout" if fb else "EP")
    head=(f"- **{v(r,17)}**（{setup}｜{'/'.join(th)}）：6M {pct(p6)}·3M {pct(p3)}·1M {pct(p1)}·离高 {pct(off_high(r))}，"
          f"ADR {fadr(adr)}，20日均额 {fvol(dv)}。")
    if fb:  # Breakout：按延伸程度判断在趋势的哪一段
        if (isinstance(p1,(int,float)) and p1>0.5) or (isinstance(p6,(int,float)) and p6>5):
            body="已大幅延伸/偏抛物线——按方法属**突破后期**，别追高，等回调收紧成新 base 再看 ORH。"
        elif isinstance(p1,(int,float)) and -0.12<=p1<=0.25 and (p3 or 0)>0.2:
            body="强势且**近月在整理**——较符合 breakout 候选，等放量突破开盘区间高点(ORH)进。"
        else:
            body="仍在上升趋势中，跟住趋势、回调不破位即持有。"
        if fe: body+=f" 另今日 Gap {pct1(gap)}/放量 {frv(rv)} 同时触发 **EP**。"
    else:  # EP-only：冷门股事件驱动异动
        body=(f"今日 Gap {pct1(gap)}、放量 {frv(rv)}，前期低迷(6M {pct(p6)})——正合 EP 的**冷门股意外异动**；"
              f"盯当日 **ORH** 进、**当日低点**止损，放量不持续则放弃。")
    return head+body

bk_sorted=sorted(bk_unique.values(), key=lambda x:(num(v(x[0],278)) or -9), reverse=True)
md.append(f"---\n## 🏆 Breakout 命中 · 逐只分析（按6M，共{len(bk_sorted)}只）")
md.append("> 纪律：进场=**开盘区间高点 ORH** 突破；止损=**当日低点**且宽度≤ADR；进场3-5天卖1/3~1/2并把止损移到保本，余仓 EMA10/20 trailing；**Stage2 与整理/吸筹形态务必在 TradingView 看图终判**。\n")
if bk_sorted:
    for n,(r,th) in enumerate(bk_sorted,1):
        md.append(analysis(r,th))
        if n==10 and len(bk_sorted)>10: md.append("\n*——— 以上为 Top 10（其余按6M续列）———*\n")
else:
    md.append("_今日无 Breakout 命中。_")

ep_sorted=sorted(ep_unique.values(), key=lambda x:(num(v(x[0],260)) or -9), reverse=True)
md.append(f"\n## ⚡ EP 命中 · 逐只分析（按 Gap%，共{len(ep_sorted)}只）")
md.append("> 纪律：EP 看当日事件——开盘区间高点(ORH)进、当日低点止损；盘前没放量则要求开盘15-30分钟内放到日均量。\n")
if ep_sorted:
    for r,th in ep_sorted:
        md.append(analysis(r,th))
else:
    md.append("_今日无 EP 命中（事件驱动跳空较罕见；非交易日/盘后数据可能无当日跳空）。_")

if unresolved:
    md.append("\n---\n## ⚠️ 未解析 ticker（退市/非美股/拼写，请在 themes.json 校正）")
    for n,m in unresolved.items(): md.append(f"- **{n}**: {', '.join(m)}")

md.append(f"\n---\n*口径可在 `~/.deepvue/themes.json` 调整；板块开关改 `enabled`。EP 用当日/最近一根的 Gap%，盘前请配合 Deepvue 盘前看。本报告非投资建议。*")

os.makedirs(OUTDIR, exist_ok=True)
out_path=os.path.join(OUTDIR, f"{date_str}.md")
with open(out_path,"w",encoding="utf-8") as f: f.write("\n".join(md))

# console summary
print(f"启用主题 {len(enabled)} ｜ 去重标的 {len(all_idx)} ｜ 取到 {len(by)}")
if unresolved:
    for n,m in unresolved.items(): print(f"  ⚠️ {n} 未解析: {', '.join(m)}")
print(f"Breakout 命中 {len(bk_unique)} ｜ EP 命中 {len(ep_unique)}（均含逐只分析）")
print("各主题: "+ " ｜ ".join(f"{n}({sum(1 for i in theme_idx[n] if i in by)}/{sum(1 for i in theme_idx[n] if i in by and flags[i][0])}✓/{sum(1 for i in theme_idx[n] if i in by and flags[i][1])}⚡)" for n in enabled))
print(f"\n📄 已保存: {out_path}")
