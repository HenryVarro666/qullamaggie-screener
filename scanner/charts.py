#!/usr/bin/env python3
# 日K图：**真·TradingView 登录截图**（含用户自己的指标，需 ~/.deepvue/tv_cookies.json）为主；mplfinance 自绘为备。
# 存 OUTDIR/charts/<DATE>/<TICKER>_1D_<DATE>.png，报告用向下相对路径（VS Code/Typora/Obsidian 三端可渲染）。
# 开关：CHARTS=0 关；CHART_MODE=mpl 强制自绘、=tv 强制 TV；CHART_WAIT_MS/CHART_NEXT_MS 调等待。tv_cookies.json 不进 git。
import os, json, urllib.request
from qmag_core import OUTDIR, meta, HOME

CHARTS_ON  = os.environ.get("CHARTS","1")!="0"
MODE       = os.environ.get("CHART_MODE","auto")            # auto(有cookie走TV) / tv / mpl
DIRNAME    = "charts"
WAIT_MS    = int(os.environ.get("CHART_WAIT_MS","13000"))   # TV 首图（冷启动）
WAIT_NEXT  = int(os.environ.get("CHART_NEXT_MS","8000"))    # TV 后续每只
PLOT_BARS  = int(os.environ.get("CHART_BARS","180"))        # mplfinance 显示最近 N 根
MA_SPECS   = meta.get("chart_ma", [["ema",10,"#22D3EE"],["ema",21,"#22C55E"],["sma",50,"#EF4444"],["sma",200,"#9CA3AF"]])
TV_COOKIES = os.path.join(HOME, "tv_cookies.json")
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def _png_path(t,d):     return os.path.join(OUTDIR, DIRNAME, d, f"{t}_1D_{d}.png")
def chart_relpath(t,d): return f"{DIRNAME}/{d}/{t}_1D_{d}.png"

# ---------- 真·TradingView 登录截图（含用户的 LevelUpTools 等指标）----------
def _tv_cookies():
    SS={"strict":"Strict","lax":"Lax","no_restriction":"None","none":"None","unspecified":"Lax"}
    out=[]
    for c in json.load(open(TV_COOKIES, encoding="utf-8")):
        ck={"name":c["name"],"value":c["value"],"domain":c["domain"],"path":c.get("path","/"),
            "secure":bool(c.get("secure",False)),"httpOnly":bool(c.get("httpOnly",False)),
            "sameSite":SS.get(str(c.get("sameSite","lax")).lower(),"Lax")}
        if "expirationDate" in c and not c.get("session",False): ck["expires"]=float(c["expirationDate"])
        if ck["sameSite"]=="None" and not ck["secure"]: ck["secure"]=True
        out.append(ck)
    return out

def _tv_charts(todo, date, log):
    """todo: [(ticker,'EX:TICKER')] → {ticker: relpath|None}；登录失效 → 返回 None 触发整体回退 mplfinance。"""
    from playwright.sync_api import sync_playwright
    out={}
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True)
        ctx=b.new_context(viewport={"width":1500,"height":850}, user_agent=UA)
        ctx.add_cookies(_tv_cookies())
        pg=ctx.new_page()
        for i,(t,sym) in enumerate(todo):
            try:
                pg.goto(f"https://www.tradingview.com/chart/?symbol={sym}&interval=D",
                        wait_until="domcontentloaded", timeout=60000)
                pg.wait_for_timeout(WAIT_MS if i==0 else WAIT_NEXT)
                try: pg.keyboard.press("Escape")
                except Exception: pass
                if i==0 and pg.query_selector("button:has-text('Sign in')"):
                    log("  ⚠️ TradingView 未登录（cookies 失效？）→ 整体回退 mplfinance")
                    b.close(); return None
                el=pg.query_selector(".chart-container") or pg.query_selector(".chart-gui-wrapper")
                if el:
                    el.screenshot(path=_png_path(t,date)); out[t]=chart_relpath(t,date); log(f"  📈 {t}")
                else:
                    out[t]=None; log(f"  ⚠️ {t} 未找到图表元素")
            except Exception as e:
                out[t]=None; log(f"  ⚠️ {t} 截图失败：{repr(e)[:50]}")
        b.close()
    return out

# ---------- mplfinance 自绘（fallback：无 cookie / 登录失效 / 仓库用户）----------
_cache={}
def _ohlcv(ticker):
    if ticker in _cache: return _cache[ticker]
    df=None
    try:
        import pandas as pd
        u=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2y&interval=1d"
        r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"user-agent":UA}),timeout=20))
        res=r["chart"]["result"][0]; ts=res["timestamp"]; q=res["indicators"]["quote"][0]
        df=pd.DataFrame({"Open":q["open"],"High":q["high"],"Low":q["low"],"Close":q["close"],"Volume":q["volume"]},
                        index=pd.to_datetime(ts, unit="s")).dropna()
    except Exception:
        df=None
    _cache[ticker]=df; return df

def _render(ticker, df, path):
    import mplfinance as mpf, matplotlib.pyplot as plt, matplotlib.lines as mlines
    aps=[]
    for typ,length,color in MA_SPECS:
        n=int(length)
        s=(df["Close"].ewm(span=n,adjust=False).mean() if str(typ).lower().startswith("e") else df["Close"].rolling(n).mean())
        aps.append(mpf.make_addplot(s.tail(PLOT_BARS), color=color, width=1.1))
    sub=df.tail(PLOT_BARS)
    mc=mpf.make_marketcolors(up="#26A69A", down="#EF5350", edge="inherit", wick="inherit", volume="#3a4250")
    style=mpf.make_mpf_style(marketcolors=mc, facecolor="#131722", figcolor="#131722", gridcolor="#1f2630",
                             gridstyle="-", edgecolor="#2a2e39",
                             rc={"axes.labelcolor":"#cfd3dc","xtick.color":"#8b93a7","ytick.color":"#8b93a7"})
    fig, axes = mpf.plot(sub, type="candle", style=style, volume=True, addplot=aps, figsize=(11.5,6.4),
                         returnfig=True, tight_layout=True, ylabel="", ylabel_lower="", xrotation=0,
                         datetime_format="%b %y", warn_too_much_data=100000)
    last=df["Close"].iloc[-1]; chg=(last/df["Close"].iloc[-2]-1)*100 if len(df)>1 else 0
    axes[0].set_title(f"{ticker}  ·  1D  ·  {last:.2f}  ({chg:+.2f}%)", color="#e6e8ee", loc="left", fontsize=12, pad=8)
    handles=[mlines.Line2D([],[],color=c,lw=1.6,label=f"{'EMA' if str(typ).lower().startswith('e') else 'SMA'}{int(n)}") for typ,n,c in MA_SPECS]
    axes[0].legend(handles=handles, loc="upper left", fontsize=8.5, framealpha=0.0, labelcolor="#cfd3dc", ncol=len(MA_SPECS))
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="#131722"); plt.close(fig)

def _mpl_charts(todo, date, log):
    out={}
    try: import mplfinance, pandas  # noqa
    except Exception:
        log("  ⚠️ 需要 mplfinance：pip install mplfinance"); return {t:None for t,_ in todo}
    for t,_ in todo:
        df=_ohlcv(t)
        if df is None or len(df)<30: out[t]=None; log(f"  ⚠️ {t} 无足够日线数据"); continue
        try: _render(t, df, _png_path(t,date)); out[t]=chart_relpath(t,date); log(f"  📈 {t}")
        except Exception as e: out[t]=None; log(f"  ⚠️ {t} 画图失败：{repr(e)[:60]}")
    return out

def ensure_charts(symbols_by_ticker, date, log=lambda s: None):
    if not CHARTS_ON:
        log("  (CHARTS=0，跳过配图)"); return {t:None for t in symbols_by_ticker}
    if not symbols_by_ticker: return {}
    os.makedirs(os.path.join(OUTDIR, DIRNAME, date), exist_ok=True)
    out, todo = {}, []
    for t,sym in symbols_by_ticker.items():
        if os.path.exists(_png_path(t,date)): out[t]=chart_relpath(t,date)
        else: todo.append((t,sym))
    if not todo: return out
    if MODE!="mpl" and os.path.exists(TV_COOKIES):
        log(f"  真·TradingView 登录截图 {len(todo)} 只（含你的指标；复用已存在 {len(out)} 只）…")
        res=_tv_charts(todo, date, log)
        if res is not None: return {**out, **res}
        log("  → 回退 mplfinance 自绘")
    else:
        log(f"  自绘日K {len(todo)} 只（无 tv_cookies.json 或 CHART_MODE=mpl；复用 {len(out)}）…")
    return {**out, **_mpl_charts(todo, date, log)}
