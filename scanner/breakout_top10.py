#!/usr/bin/env python3
# Whole-market Qullamaggie Breakout Top-N (strict Stage-2 screen), dual backend.
#   TradingView backend (default in themes.json): NO login — scans the whole US market in one call.
#   Deepvue backend: own paid account (slower for whole market). Override per run: SCAN_BACKEND=tradingview / TOPN=25.
import datetime, os, sys
from qmag_core import *

N=int(os.environ.get("TOPN","25"))
M=fetch(None)                                   # None = whole US universe
# whole-market Breakout = individual equities only (exclude leveraged ETFs/ETNs like SOXL/KORU)
cands=[m for m in M.values() if is_breakout(m) and (m.get("type") in ("stock","dr") or m.get("type") is None)]
cands.sort(key=lambda m:(m["p6"] if m["p6"] is not None else -9), reverse=True)
top=cands[:N]

date_str=datetime.datetime.now().strftime("%Y-%m-%d"); run_ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
md=[f"# 全市场 Breakout Top {N} · {date_str}"]
md.append(f"\n> 运行：{run_ts} ｜ 后端：**{BACKEND}** ｜ 扫描 {len(M)} 只 ｜ Breakout 命中 {len(cands)} ｜ 取前 {len(top)}")
md+=regime_lines()
md.append(f"> 口径：价≥1·ADR≥{floors['adr']*100:.0f}%·6M≥{floors['perf6M']*100:.0f}%·$额≥{floors['dollarVol20d']/1e6:.0f}M·Stage2(站50&200日·50>200)·离52周高≤{floors['max_off_high']*100:.0f}%。进场ORH/止损当日低点≤ADR/形态TV终判；非投资建议。\n")
md.append("| # | Tkr | Last | ADR | 6M | 3M | 1M | 离高 | St2 | $Vol | Sector |")
md.append("|--:|--|--:|--:|--:|--:|--:|--:|:--:|--:|--|")
for i,m in enumerate(top,1):
    md.append(f"| {i} | **{m['ticker']}** | {fp(m['last'])} | {fadr(m['adr'])} | {pct(m['p6'])} | {pct(m['p3'])} | {pct(m['p1'])} | {pct(m['off_high'])} | {st2(m)} | {fvol(m['dollar_vol'])} | {m['sector']} |")

os.makedirs(OUTDIR, exist_ok=True); out_path=os.path.join(OUTDIR, f"breakout-top{N}-{date_str}.md")
with open(out_path,"w",encoding="utf-8") as f: f.write("\n".join(md))
print(f"后端 {BACKEND} ｜ 扫描 {len(M)} ｜ Breakout 命中 {len(cands)} ｜ Top{len(top)}")
for i,m in enumerate(top,1):
    print(f"{i:>2}. {m['ticker']:<6} 6M {pct(m['p6']):>6} 3M {pct(m['p3']):>6} 1M {pct(m['p1']):>6} ADR {fadr(m['adr']):>4} 离高 {pct(m['off_high']):>5} ${fvol(m['dollar_vol'])}  {m['sector']}")
print(f"\n📄 已保存: {out_path}")
