#!/usr/bin/env python3
# 形态健康度：吸筹收紧(可买) vs 放量派发(避开)。把"看图确认形态"自动化成一个评分 + AI 看图复核。
#   数值：缩量/相对量 ← TradingView 扫描列(m，与选股同源)；逐K(波动收窄/higher lows/收盘强度/派发日) ← Yahoo 日线。
#   AI 看图：把已生成的日K PNG 喂 Gemini API（需 GEMINI_API_KEY 或 ~/.deepvue/secrets.json；VISION=0 关）。HEALTH=0 整体关。
# 形态评分是辅助、非定论——关键仓位仍要自己看图。
import os, json, base64, time, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from qmag_core import OUTDIR, meta, HOME

HEALTH_ON = os.environ.get("HEALTH","1")!="0"
VISION_ON = os.environ.get("VISION","1")!="0"
def _vision_key():                       # Gemini key：env 优先，否则本地 ~/.deepvue/secrets.json（不进 git）
    k=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if k: return k
    try: return json.load(open(os.path.join(HOME,"secrets.json")))["gemini_api_key"]
    except Exception: return ""
API_KEY=_vision_key()
H = {"base":15,"prior":65,"vol_good":-0.10,"vol_bad":0.20,"atr_good":-0.05,"atr_bad":0.15,
     "close_good":0.55,"close_bad":0.40,"dist_good":1,"dist_bad":4,
     "vision_model":"gemini-3.1-pro-preview","vision_max_tokens":1024, **meta.get("health",{})}
UA={"user-agent":"Mozilla/5.0"}

# ---------- Yahoo 日线（逐K形态用）----------
_bars_cache={}
def daily_bars(ticker):
    if ticker in _bars_cache: return _bars_cache[ticker]
    rows=None
    try:
        u=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=8mo&interval=1d"
        r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=15))
        q=r["chart"]["result"][0]["indicators"]["quote"][0]
        h,l,c,v=q["high"],q["low"],q["close"],q["volume"]
        rows=[(h[i],l[i],c[i],v[i]) for i in range(len(c)) if None not in (h[i],l[i],c[i],v[i])]
    except Exception:
        rows=None
    _bars_cache[ticker]=rows
    return rows

# ---------- 数值评分（TV 量能 + Yahoo 逐K）----------
def _band(v, good, bad):                 # good 端 +1、bad 端 -1（good<bad → 越小越好；good>bad → 越大越好）
    if v is None: return 0
    if good <= bad: return 1 if v<=good else (-1 if v>=bad else 0)
    return 1 if v>=good else (-1 if v<=bad else 0)

def numeric_health(m, rows):
    f={}
    # 缩量 ← TradingView 优先（10日/90日均量），deepvue 无列则用 Yahoo 量回退
    a10,a90=m.get("avg_vol_10d"),m.get("avg_vol_90d")
    if isinstance(a10,(int,float)) and isinstance(a90,(int,float)) and a90>0:
        f["vol_contraction"]=a10/a90-1; f["vol_src"]="TV"
    elif rows and len(rows)>=H["prior"]:
        base=rows[-H["base"]:]; prior=rows[-H["prior"]:-H["base"]]
        bv=sum(r[3] for r in base)/len(base); pv=sum(r[3] for r in prior)/len(prior)
        f["vol_contraction"]=(bv/pv-1) if pv>0 else None; f["vol_src"]="Yahoo"
    else:
        f["vol_contraction"]=None; f["vol_src"]=None
    # 逐K ← Yahoo
    if rows and len(rows)>=H["prior"]:
        n=len(rows); base=rows[-H["base"]:]; prior=rows[-H["prior"]:-H["base"]]
        rng=lambda r:(r[0]-r[1])/r[2] if r[2] else 0
        atrb=sum(rng(r) for r in base)/len(base); atrp=sum(rng(r) for r in prior)/len(prior)
        f["atr_contraction"]=(atrb/atrp-1) if atrp>0 else None
        f["close_strength"]=sum(((r[2]-r[1])/(r[0]-r[1]) if r[0]>r[1] else .5) for r in base)/len(base)
        f["dist_days"]=sum(1 for i in range(n-H["base"],n) if rows[i][2]<rows[i-1][2] and rows[i][3]>rows[i-1][3])
        lows=[r[1] for r in base]; f["higher_lows"]=lows[-1]>=min(lows[:max(1,len(lows)//3)])
    else:
        f.update(atr_contraction=None, close_strength=None, dist_days=None, higher_lows=None)
    s =_band(f["vol_contraction"],H["vol_good"],H["vol_bad"])
    s+=_band(f["atr_contraction"],H["atr_good"],H["atr_bad"])
    s+=_band(f["close_strength"],H["close_good"],H["close_bad"])
    s+=_band(f["dist_days"],H["dist_good"],H["dist_bad"])
    if f.get("higher_lows") is True: s+=1
    elif f.get("higher_lows") is False: s-=1
    f["score"]=s
    f["emoji"]="🟢" if s>=2 else ("🔴" if s<=-2 else "🟡")          # 显式字段，调用方不必再从中文 verdict 抠 emoji
    f["verdict"]=f["emoji"]+("吸筹收紧" if s>=2 else ("派发疑虑" if s<=-2 else "中性"))
    return f

# ---------- AI 看图复核（Anthropic 视觉；需 key）----------
_VIS_PROMPT=("这是一只美股日K图（约8个月）。看**最近1–2个月**的整理阶段，按 Qullamaggie/VCP，逐项核对 量能/振幅/低点/收盘 四项证据后客观三选一（不同股票结论应有差异，按图实判）：\n"
  "A=健康吸筹收紧：量缩 + 振幅收窄 + 低点抬高 + 收盘偏上沿，回调浅、贴着上升均线；\n"
  "B=放量派发/破位：高位反复放量、长上影、收盘被压回、低点走弱或跌破均线；\n"
  "C=普通/不够紧/仍在宽幅调整（多数属此）。\n"
  "只回 JSON：{\"verdict\":\"A|B|C\",\"reason\":\"≤15字中文具体依据\",\"confidence\":0-1}")
_last=[0.0]; _rate_lock=threading.Lock()                  # 全局起跑节流闸（并发 vision 调用共用）
_vision_dead=[False]                                       # key 失效/无效(400/401/403)后置位 → 本次运行余下直接跳过，不再白打
def vision_health(png_path):
    if not (VISION_ON and API_KEY and png_path) or _vision_dead[0]:
        return None
    p=png_path if os.path.isabs(png_path) else os.path.join(OUTDIR, png_path)
    if not os.path.exists(p): return None
    try:
        b64=base64.b64encode(open(p,"rb").read()).decode()
    except Exception as e:
        return {"error":repr(e)[:60]}
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{H['vision_model']}:generateContent?key={API_KEY}"
    data=json.dumps({"contents":[{"parts":[{"inline_data":{"mime_type":"image/png","data":b64}},
        {"text":_VIS_PROMPT}]}],"generationConfig":{"temperature":0,"maxOutputTokens":int(H.get("vision_max_tokens",1024))}}).encode()
    interval=float(os.environ.get("VISION_INTERVAL", H.get("vision_interval_s",0.4)))
    err=None
    for attempt in range(4):                                   # 节流 + 重试（429/503/空响应是 free-tier 常态）
        with _rate_lock:                                       # 锁内只排开"起跑"间隔；请求本身在锁外并发跑
            gap=time.time()-_last[0]
            if gap<interval: time.sleep(interval-gap)
            _last[0]=time.time()
        try:
            req=urllib.request.Request(url, data=data, headers={"content-type":"application/json"})
            r=json.load(urllib.request.urlopen(req, timeout=90))
            c=r.get("candidates",[{}])[0]
            txt="".join(p.get("text","") for p in c.get("content",{}).get("parts",[]) if "text" in p)
            i,j=txt.find("{"),txt.rfind("}")
            if i<0 or j<=i:                                    # 空/截断响应（含 MAX_TOKENS）→ 不强行解析；重试或记错误
                err=f"empty/truncated(finish={c.get('finishReason')})"
                if attempt<3: time.sleep(1.5*(attempt+1)); continue
                break
            js=json.loads(txt[i:j+1])
            emoji={"A":"🟢","B":"🔴","C":"🟡"}.get(str(js.get("verdict","C")).strip()[:1].upper(),"🟡")
            return {"emoji":emoji,"reason":str(js.get("reason",""))[:20],"confidence":js.get("confidence")}
        except urllib.error.HTTPError as e:
            err=f"HTTP {e.code}"
            if e.code in (400,401,403): _vision_dead[0]=True; break   # key 过期/无效 → 不重试、置全局死标
            if e.code in (429,500,503) and attempt<3: time.sleep(2*(attempt+1)); continue
            break
        except Exception as e:
            err=repr(e)[:50]
            if attempt<3: time.sleep(1.5*(attempt+1)); continue
            break
    return {"error":err}

# ---------- 批量 + 当天缓存（vision 贵）----------
def health_for(items, cm, date, log=lambda s: None):
    """items: list[m dict]（含 ticker + avg_vol…）；cm: {ticker: chart relpath|None} → {ticker: health dict}."""
    if not HEALTH_ON:
        log("  (HEALTH=0，跳过形态评分)"); return {}
    cdir=os.path.join(OUTDIR,"charts",date); os.makedirs(cdir, exist_ok=True)
    cache_path=os.path.join(cdir,"_health.json")
    cache={}
    if os.path.exists(cache_path):
        try: cache=json.load(open(cache_path,encoding="utf-8"))
        except Exception: cache={}
    todo=[m for m in items if m["ticker"] not in cache]
    if todo:
        log(f"  形态评分 {len(todo)} 只（复用 {len(items)-len(todo)}）" + ("" if (VISION_ON and API_KEY) else "（无 AI 看图：未设 GEMINI key 或 VISION=0）") + "…")
    out={m["ticker"]:cache[m["ticker"]] for m in items if m["ticker"] in cache}
    lock=threading.Lock()
    def _save():
        try: json.dump(cache, open(cache_path,"w",encoding="utf-8"), ensure_ascii=False)
        except Exception: pass
    def work(m):                                          # 每只：数值(快) + 看图(慢网络) → 并发
        t=m["ticker"]
        h=numeric_health(m, daily_bars(t))
        vis=vision_health(cm.get(t))
        if vis and "error" not in vis: h["vision"]=vis
        elif vis and "error" in vis: h["vision_err"]=vis["error"]
        return t,h
    workers=max(1,int(os.environ.get("VISION_WORKERS","6")))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for t,h in ex.map(work, todo):
            out[t]=h
            with lock:                                    # 串行化缓存写入；vision 瞬时失败不落盘 → 下次重试
                if "vision_err" not in h: cache[t]=h; _save()
            log(f"  🩺 {t} {h['verdict']}" + (f" 👁{h['vision']['emoji']}" if h.get("vision") else ""))
    if _vision_dead[0]: log("  ⚠️ Gemini key 已过期/无效 → 本次仅数值形态。去 aistudio.google.com 续期后写入 secrets.json。")
    return out

def health_emoji(h):                                  # 数值形态 emoji；兼容旧缓存（无 emoji 字段则从 verdict 推）
    if not h: return "🟡"
    if h.get("emoji"): return h["emoji"]
    v=h.get("verdict","")
    return "🟢" if "吸筹" in v else ("🔴" if "派发" in v else "🟡")
def _pc(x): return f"{x*100:+.0f}%" if isinstance(x,(int,float)) else "–"
def health_line(h):
    if not h: return None
    nums=[]
    if h.get("vol_contraction") is not None: nums.append(f"缩量{_pc(h['vol_contraction'])}[{h.get('vol_src','')}]")
    if h.get("atr_contraction") is not None: nums.append(f"收窄{_pc(h['atr_contraction'])}")
    if h.get("dist_days") is not None: nums.append(f"派发{h['dist_days']}")
    if isinstance(h.get("close_strength"),(int,float)): nums.append(f"收盘{h['close_strength']:.2f}")
    if h.get("higher_lows") is not None: nums.append("低点抬高" if h["higher_lows"] else "低点走弱")
    line=f"  - 形态：数值 {h.get('verdict','–')}（{'·'.join(nums) or '数据不足'}）"
    v=h.get("vision")
    if v: line+=f" ｜ 👁AI {v['emoji']}" + (f"「{v['reason']}」" if v.get("reason") else "")
    return line
