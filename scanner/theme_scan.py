#!/usr/bin/env python3
# Theme-grouped Qullamaggie scan (Breakout ✓ / EP ⚡), dual backend (TradingView / Deepvue).
# Reads ~/.deepvue/themes.json, writes a daily heatmap-style markdown report + per-stock analysis.
# Shared backend/predicate logic lives in qmag_core.py.
import datetime, statistics, os, sys
from qmag_core import *

enabled={k:v for k,v in cfg["themes"].items() if v.get("enabled")}
theme_tickers={k:list(dict.fromkeys(v["tickers"])) for k,v in enabled.items()}
all_tickers={t for ts in theme_tickers.values() for t in ts}
if not all_tickers: sys.exit("没有启用的主题/标的。")
M=fetch(all_tickers)
unresolved={k:[t for t in ts if t not in M] for k,ts in theme_tickers.items()}
unresolved={k:v for k,v in unresolved.items() if v}
flags={t:(is_breakout(m),is_ep(m)) for t,m in M.items()}
idx_themes={}
for k,ts in theme_tickers.items():
    for t in ts: idx_themes.setdefault(t,[]).append(k)

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
        eg=m.get('eps_growth'); dse=m.get('days_since_earn')
        egs=f"，EPS增长 {eg:+.0f}%" if isinstance(eg,(int,float)) else ""
        dss=f"，距财报 {dse:.0f}d" if isinstance(dse,(int,float)) else ""
        body=f"今日 Gap {pct1(m['gap'])}、放量 {frv(m['relvol'])}{egs}{dss}，前期低迷(6M {pct(m['p6'])})——**财报型 EP**；盯当日 **ORH** 进、**当日低点**止损，放量不续则放弃。"
    return head+body

date_str=datetime.datetime.now().strftime("%Y-%m-%d"); run_ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
md=[f"# 主题扫描 {date_str}"]
md.append(f"\n> 运行：{run_ts} ｜ 后端：**{BACKEND}** ｜ 启用主题 {len(enabled)} ｜ 标的 {len(all_tickers)} ｜ 取到 {len(M)}")
reg_lines=regime_lines(); md+=reg_lines
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
print(reg_lines[0].lstrip("> ").replace("**",""))
print(f"后端 {BACKEND} ｜ 主题 {len(enabled)} ｜ 标的 {len(all_tickers)} ｜ 取到 {len(M)}")
if unresolved:
    for k,vv in unresolved.items(): print(f"  ⚠️ {k}: {', '.join(vv)}")
print(f"Breakout {len(bk)} ｜ EP {len(ep_hits)}（均含逐只分析）")
print("各主题: "+" ｜ ".join(f"{k}({sum(1 for t in theme_tickers[k] if t in M)}/{sum(1 for t in theme_tickers[k] if t in M and flags[t][0])}✓/{sum(1 for t in theme_tickers[k] if t in M and flags[t][1])}⚡)" for k in enabled))
print(f"\n📄 已保存: {out_path}")
