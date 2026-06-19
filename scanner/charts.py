#!/usr/bin/env python3
# TradingView 日K截图（Playwright 无头），给三份报告内嵌"1D 趋势形态图"。
# 存 OUTDIR/charts/<DATE>/<TICKER>_1D_<DATE>.png；报告用向下相对路径引用（VS Code/Typora/Obsidian 三端可渲染）。
# 个人盯盘用、数据延迟/EOD。环境变量：CHARTS=0 关闭配图；CHART_WAIT_MS 调等待(默认6000)；CHART_W/CHART_H 调尺寸。
import os, json
from qmag_core import OUTDIR

CHARTS_ON = os.environ.get("CHARTS","1")!="0"
WAIT_MS   = int(os.environ.get("CHART_WAIT_MS","6000"))
W, H      = int(os.environ.get("CHART_W","900")), int(os.environ.get("CHART_H","560"))
DIRNAME   = "charts"

def _png_path(ticker, date):      return os.path.join(OUTDIR, DIRNAME, date, f"{ticker}_1D_{date}.png")
def chart_relpath(ticker, date):  return f"{DIRNAME}/{date}/{ticker}_1D_{date}.png"   # 相对报告(在 OUTDIR 根)的向下路径

def _html(symbol):
    cfg={"container_id":"c","symbol":symbol,"interval":"D","theme":"dark","style":"1","locale":"en",
         "width":W,"height":H,"timezone":"America/New_York","hide_top_toolbar":False,"hide_legend":False,
         "allow_symbol_change":False,"save_image":False,"withdateranges":True,"autosize":False}
    return ("<!doctype html><html><head><meta charset=utf-8>"
            f"<style>html,body{{margin:0;background:#131722}}#c{{width:{W}px;height:{H}px}}</style></head>"
            "<body><div id=c></div><script src='https://s3.tradingview.com/tv.js'></script>"
            f"<script>new TradingView.widget({json.dumps(cfg)});</script></body></html>")

def ensure_charts(symbols_by_ticker, date, log=lambda s: None):
    """symbols_by_ticker: {ticker: 'EXCHANGE:TICKER'} → {ticker: relpath|None}.
    只截 PNG 尚不存在的（当天跨脚本天然去重、可重入）；一次 launch chromium 循环全部；单只失败不阻断。"""
    if not CHARTS_ON:
        log("  (CHARTS=0，跳过配图)"); return {t:None for t in symbols_by_ticker}
    if not symbols_by_ticker: return {}
    os.makedirs(os.path.join(OUTDIR, DIRNAME, date), exist_ok=True)
    out, todo = {}, {}
    for t,sym in symbols_by_ticker.items():
        if os.path.exists(_png_path(t,date)): out[t]=chart_relpath(t,date)   # 当天已截过 → 复用
        else: todo[t]=sym
    if not todo: return out
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        log(f"  ⚠️ Playwright 不可用，跳过配图：{repr(e)[:70]}")
        return {**out, **{t:None for t in todo}}
    log(f"  TradingView 截图 {len(todo)} 只（复用已存在 {len(out)} 只）…")
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True)
        pg=b.new_context(viewport={"width":W+20,"height":H+20}).new_page()
        for t,sym in todo.items():
            try:
                pg.set_content(_html(sym), wait_until="load")
                pg.wait_for_selector("#c iframe", timeout=15000)
                pg.wait_for_timeout(WAIT_MS)
                pg.locator("#c").screenshot(path=_png_path(t,date))
                out[t]=chart_relpath(t,date); log(f"  📈 {t}")
            except Exception as e:
                out[t]=None; log(f"  ⚠️ {t} 截图失败：{repr(e)[:70]}")
        b.close()
    return out
