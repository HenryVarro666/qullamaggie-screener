#!/usr/bin/env python3
# 近期可买 Breakout Top-N：在全市场 Breakout 命中里再筛"就绪/可买"形态（贴52周高 + 近月整理 + 仍强），
# 按就绪度排序。一份文档同时给：🌐 全市场可买 Top-N + 🎯 我的主题内可买 Top-N（§2 是 §1 的子集）。
# 双后端、复用 qmag_core。跑法：python3 ~/.deepvue/ready_top10.py （TOPN=15 改条数；SCAN_BACKEND=deepvue 切后端）
import datetime, os
from qmag_core import *
from charts import ensure_charts

N=int(os.environ.get("TOPN","10"))
enabled,_,idx_themes,theme_set=load_themes()

M=fetch(None)                                           # 全市场抓一次；主题是其子集，按 ticker 过滤即可，不二次抓
ready_hits=[m for m in M.values() if is_ready(m) and is_equity(m)]
ready_hits.sort(key=ready_key, reverse=True)            # 就绪度高 → 排前（剔除杠杆 ETF，同 breakout_top10）
mkt_top=ready_hits[:N]
theme_top=[m for m in ready_hits if m["ticker"] in theme_set][:N]
nbk=sum(1 for m in M.values() if is_breakout(m))

date_str=datetime.datetime.now().strftime("%Y-%m-%d"); run_ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
chart_rows={m["ticker"]:m for m in (mkt_top+theme_top)}                     # 全市场+主题并集，去重
print("配图（TradingView 日K截图）…")
cm=ensure_charts({t:tv_symbol(m) for t,m in chart_rows.items()}, date_str, print)
def table(rows):
    out=["| # | Tkr | 6M | 3M | 1M | 离高 | ADR | $Vol | 就绪度 | Sector |",
         "|--:|--|--:|--:|--:|--:|--:|--:|--:|--|"]
    for i,m in enumerate(rows,1):
        thm=("｜"+"/".join(idx_themes[m["ticker"]])) if m["ticker"] in theme_set else ""
        out.append(f"| {i} | **{m['ticker']}** | {pct(m['p6'])} | {pct(m['p3'])} | {pct(m['p1'])} | {pct(m['off_high'])} | {fadr(m['adr'])} | {fvol(m['dollar_vol'])} | {fmt_ready(m)} | {m['sector']}{thm} |")
    return "\n".join(out)
def detail(rows):
    blocks=[]
    for m in rows:
        b=analysis(m, idx_themes.get(m["ticker"],[]), True, is_ep(m))
        rel=cm.get(m["ticker"])
        if rel: b+=f"\n  - ![{m['ticker']} 日K]({rel})"
        blocks.append(b)
    return blocks

reg=regime_lines()
md=[f"# 近期可买 Breakout Top{N} · {date_str}"]
md.append(f"\n> 运行：{run_ts} ｜ 后端：**{BACKEND}** ｜ 全市场扫描 {len(M)} 只 ｜ Breakout 命中 {nbk} ｜ 其中**就绪/可买 {len(ready_hits)}** 只")
md+=reg
md.append(">")
md.append("> **情况说明（先读）**")
md.append(f"> - **「可买」口径**：在 Breakout 命中里再筛 —— **贴 52 周高（离高 ≥ -{ready['max_off_high']*100:.0f}%）+ 近一个月在整理（1M 介于 {ready['min_1m']*100:+.0f}% ~ {ready['max_1m']*100:+.0f}%、没跌破也没暴冲）+ 有过像样的季度推进（3M ≥ {ready['min_3m']*100:.0f}%）+ 日均额 ≥ ${ready['min_dollar_vol']/1e6:.0f}M（够流动性、进得去出得来）**。即「大涨过 → 现在缩量贴高蓄势 → 随时放量突破」的标准形态。")
md.append("> - **为什么不用涨幅榜**：按 6M 涨幅排序，最上面永远是涨得最久最远、已进\"突破后期\"的票（如 SNDK/MU，1M 还 +70%）——追=接盘、盈亏比差。本表特意把它们剔掉。")
md.append(f"> - **两段关系**：**§1 🌐 全市场**（全美 {len(M)} 只里选）；**§2 🎯 仅你启用的 {len(enabled)} 个主题**（是 §1 的子集）。**同一只可能两段都出现**（既是全市场最就绪、又落在你的主题里，表格 Sector 后会标主题）。")
md.append(f"> - **就绪度** = `离高 − |近月涨幅| + ADR×{ready['adr_weight']}`，越高越好（贴高 + 整理紧 + 波动大者优先——high ADR is gold；权重在 `ready_filter.adr_weight` 调），已按它降序排。")
md.append("> - **纪律**：这是**数值**就绪筛选，仍须在 **TradingView 看图**确认吸筹/收紧形态。进场=ORH 突破，止损=当日低点且≤ADR，3-5 天卖 1/3~1/2 移保本、余仓 EMA10/20 trailing。**非投资建议。**\n")

md.append(f"## 🌐 全市场可买 Top{len(mkt_top)}（按就绪度）")
if mkt_top:
    md.append(table(mkt_top)+"\n\n### 逐只分析"); md+=detail(mkt_top)
else:
    md.append("_今日全市场无就绪可买 —— 强势票多在延伸期，按方法空仓等回调收紧。_")

md.append(f"\n## 🎯 我的主题内可买 Top{len(theme_top)}（同口径，仅启用主题）")
if theme_top:
    md.append(table(theme_top)+"\n\n### 逐只分析"); md+=detail(theme_top)
else:
    md.append("_今日你的主题篮子里无就绪可买（看上面 §1 全市场，或等主题里的票整理到位）。_")

md.append(f"\n---\n*后端={BACKEND}；可买门槛在 `themes.json` 的 `_meta.ready_filter` 调（max_off_high/min_1m/max_1m/min_3m）。TV 后端免登录、数据延迟/EOD。非投资建议。*")

os.makedirs(OUTDIR, exist_ok=True); out_path=os.path.join(OUTDIR, f"ready-top{N}-{date_str}.md")
with open(out_path,"w",encoding="utf-8") as f: f.write("\n".join(md))
print(reg[0].lstrip("> ").replace("**",""))
print(f"后端 {BACKEND} ｜ 全市场 {len(M)} ｜ Breakout {nbk} ｜ 就绪可买 {len(ready_hits)}")
print(f"\n🌐 全市场可买 Top{len(mkt_top)}:")
for i,m in enumerate(mkt_top,1):
    tag=("  ["+"/".join(idx_themes[m["ticker"]])+"]") if m["ticker"] in theme_set else ""
    print(f"{i:>2}. {m['ticker']:<6} 6M {pct(m['p6']):>6} 1M {pct(m['p1']):>5} 离高 {pct(m['off_high']):>5} ADR {fadr(m['adr']):>4}{tag}")
print(f"\n🎯 主题内可买 Top{len(theme_top)}:")
for i,m in enumerate(theme_top,1):
    print(f"{i:>2}. {m['ticker']:<6} 6M {pct(m['p6']):>6} 1M {pct(m['p1']):>5} 离高 {pct(m['off_high']):>5} [{'/'.join(idx_themes[m['ticker']])}]")
print(f"\n📄 已保存: {out_path}")
